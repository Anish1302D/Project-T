"""Runtime lifecycle service wiring configuration, credentials, database, and engine."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from project_t_contracts import (
    AnalyzeRequest,
    AnalyzeResponse,
    ContextCompressRequest,
    ContextSelectRequest,
    ContextSelectResponse,
    HealthResponse,
    LogCompressRequest,
    MetricsSummaryResponse,
    OptimizationRequestWire,
    OptimizationResultWire,
    ProvidersResponse,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    TokenCountRequest,
    TokenCountResult,
)
from project_t_optimization_core import (
    ContextDocument,
    PipelineConfig,
    PipelineOrchestrator,
    TokenEstimator,
)
from project_t_provider_adapters import ModelRequest, ProviderRegistry

from ..auth import CredentialStore, InstallationCredentials
from ..config import RUNTIME_VERSION, RuntimeConfig
from .database import LocalDatabase

_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".turbo"})
_MAX_SCAN_FILE_BYTES = 262_144  # 256 KiB per workspace file
_SYMBOL_RE = re.compile(r"(?:def|class|function|interface|type|const)\s+([A-Za-z_][A-Za-z0-9_]*)")
_IMPORT_RE = re.compile(r"(?:from\s+([\w.]+)\s+import|import\s+[^\n]*?from\s+['\"]([^'\"]+)['\"])")


class WorkspaceForbiddenError(PermissionError):
    """Raised when workspace_root or pinned_files violates approved workspace confinement."""


class LocalRuntimeService:
    """Lifecycle container hosting engine orchestrators, credentials, and SQLite state."""

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config if config is not None else RuntimeConfig()
        self.registry = ProviderRegistry(allow_tiktoken=self.config.allow_tiktoken)
        self.credential_store = CredentialStore(
            self.config.data_dir,
            use_os_keyring=self.config.use_os_keyring,
        )
        self.credentials: InstallationCredentials = self.credential_store.load_or_create()
        self.db = LocalDatabase(self.config.resolved_db_path)
        self.db.initialize(
            installation_id=self.credentials.installation_id,
            runtime_version=RUNTIME_VERSION,
            registry=self.registry,
        )
        # Purge expired metadata on boot according to configured retention policy
        settings = self.db.get_settings()
        self.db.purge_expired(retention_days=settings.local_retention_days)

    def _orchestrator_for(self, provider: str | None) -> PipelineOrchestrator:
        adapter = self.registry.resolve_tokenizer(provider)
        settings = self.db.get_settings()
        return PipelineOrchestrator(
            token_estimator=TokenEstimator(adapter=adapter),
            config=PipelineConfig(
                allow_ai_semantic_compression=settings.allow_ai_semantic_compression
            ),
        )

    def health(self) -> HealthResponse:
        sqlite_ok = self.db.is_ready()
        return HealthResponse(
            status="ok" if sqlite_ok else "degraded",
            version=RUNTIME_VERSION,
            engine_ready=True,
            sqlite_ready=sqlite_ok,
        )

    def optimize(self, request: OptimizationRequestWire) -> OptimizationResultWire:
        orchestrator = self._orchestrator_for(request.provider)
        execution = orchestrator.optimize(request)
        self.db.record_optimization_run(
            installation_id=self.credentials.installation_id,
            integration=request.integration,
            provider=request.provider,
            model=request.model,
            content_type=str(execution.classification.mapped_content_type),
            status=execution.status,
            result=execution.result,
        )
        return execution.result

    def count_tokens(self, request: TokenCountRequest) -> TokenCountResult:
        adapter = self.registry.resolve_tokenizer(request.provider)
        if request.text is not None:
            return adapter.count_text(request.text, request.model)
        payload = request.request_payload or {}
        model_req = ModelRequest(
            provider=request.provider,
            model=request.model,
            messages=list(payload.get("messages", [])) if isinstance(payload.get("messages"), list) else [],
            system=payload.get("system") if isinstance(payload.get("system"), str) else None,
            tools=list(payload.get("tools", [])) if isinstance(payload.get("tools"), list) else [],
        )
        return adapter.count_request(model_req)

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        orchestrator = self._orchestrator_for(request.provider)
        return orchestrator.analyze(
            content=request.content,
            content_type=request.content_type,
            model=request.model,
        )

    def select_context(self, request: ContextSelectRequest) -> ContextSelectResponse:
        root_path = self._validate_workspace_root(request.workspace_root)
        normalized_pinned = self._validate_pinned_files(root_path, request.pinned_files)
        documents = self._scan_workspace_documents(root_path)

        orchestrator = self._orchestrator_for(request.provider)
        return orchestrator.select_context(
            task_description=request.task_description,
            documents=documents,
            pinned_files=normalized_pinned,
            max_files=request.max_files,
            max_tokens=request.max_tokens,
            model=request.model,
        )

    def compress_context(self, request: ContextCompressRequest) -> OptimizationResultWire:
        orchestrator = self._orchestrator_for(request.provider)
        execution = orchestrator.compress_context_items(request)
        self.db.record_optimization_run(
            installation_id=self.credentials.installation_id,
            integration="api",
            provider=request.provider,
            model=request.model,
            content_type="documentation",
            status=execution.status,
            result=execution.result,
        )
        return execution.result

    def compress_logs(self, request: LogCompressRequest) -> OptimizationResultWire:
        orchestrator = self._orchestrator_for(request.provider)
        execution = orchestrator.compress_logs(request)
        self.db.record_optimization_run(
            installation_id=self.credentials.installation_id,
            integration="api",
            provider=request.provider,
            model=request.model,
            content_type="terminal_output",
            status=execution.status,
            result=execution.result,
        )
        return execution.result

    def metrics(self, *, integration: str | None = None, window_days: int = 30) -> MetricsSummaryResponse:
        return self.db.query_metrics(integration=integration, window_days=window_days)

    def get_settings(self) -> RuntimeSettings:
        return self.db.get_settings()

    def update_settings(self, update: RuntimeSettingsUpdate) -> RuntimeSettings:
        return self.db.update_settings(update)

    def providers(self) -> ProvidersResponse:
        return ProvidersResponse(providers=self.registry.list_catalog_entries())

    def close(self) -> None:
        self.db.close()

    def _validate_workspace_root(self, workspace_root: str) -> Path:
        if not self.config.approved_workspaces:
            raise WorkspaceForbiddenError("No approved workspaces configured for context selection.")
        try:
            candidate = Path(workspace_root).expanduser().resolve(strict=True)
        except OSError as exc:
            raise WorkspaceForbiddenError("Workspace root does not exist or is inaccessible.") from exc

        if not candidate.is_dir():
            raise WorkspaceForbiddenError("Workspace root must be a directory.")

        for approved in self.config.approved_workspaces:
            approved_resolved = approved.expanduser().resolve()
            if candidate == approved_resolved or candidate.is_relative_to(approved_resolved):
                return candidate

        raise WorkspaceForbiddenError("Requested workspace_root is outside approved workspaces.")

    def _validate_pinned_files(self, root_path: Path, pinned_files: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw_rel in pinned_files:
            rel_path = Path(raw_rel)
            if rel_path.is_absolute():
                raise WorkspaceForbiddenError("Pinned files must be relative to workspace_root.")
            try:
                resolved = (root_path / rel_path).resolve(strict=False)
            except OSError as exc:
                raise WorkspaceForbiddenError("Invalid pinned file path.") from exc
            if not resolved.is_relative_to(root_path):
                raise WorkspaceForbiddenError("Path traversal detected in pinned_files.")
            normalized.append(resolved.relative_to(root_path).as_posix())
        return normalized

    def _scan_workspace_documents(self, root_path: Path, max_files_scanned: int = 500) -> list[ContextDocument]:
        docs: list[ContextDocument] = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("."))
            for filename in sorted(filenames):
                if len(docs) >= max_files_scanned:
                    return docs
                file_path = Path(dirpath) / filename
                try:
                    resolved = file_path.resolve(strict=True)
                except OSError:
                    continue
                if not resolved.is_relative_to(root_path):
                    continue  # skip escaping symlinks
                try:
                    stat = resolved.stat()
                    if stat.st_size == 0 or stat.st_size > _MAX_SCAN_FILE_BYTES:
                        continue
                    content = resolved.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue

                rel_posix = resolved.relative_to(root_path).as_posix()
                symbols = tuple(dict.fromkeys(_SYMBOL_RE.findall(content)))[:30]
                imports = tuple(
                    dict.fromkeys(
                        m.group(1) or m.group(2)
                        for m in _IMPORT_RE.finditer(content)
                        if (m.group(1) or m.group(2))
                    )
                )[:20]
                file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                docs.append(
                    ContextDocument(
                        relative_path=rel_posix,
                        content=content,
                        symbols=symbols,
                        imports=imports,
                        modified_epoch=stat.st_mtime,
                        file_hash=file_hash,
                    )
                )
        return docs
