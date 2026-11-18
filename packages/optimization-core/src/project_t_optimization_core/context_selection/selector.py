"""BM25 / SQLite FTS5 lexical context selection with structural & freshness signals."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from project_t_contracts import AccuracyLevel, SelectedContextFile

from ..tokenization import TokenEstimator

_QUERY_TERM_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_FTS_STOPWORDS = frozenset(
    {"the", "and", "for", "with", "that", "this", "from", "into", "not", "without", "fix", "check"}
)


@dataclass(frozen=True, slots=True)
class ContextDocument:
    """Indexable workspace file representation for context selection."""

    relative_path: str
    content: str
    symbols: tuple[str, ...] = field(default_factory=tuple)
    imports: tuple[str, ...] = field(default_factory=tuple)
    modified_epoch: float = 0.0
    file_hash: str = ""


@dataclass(frozen=True, slots=True)
class ContextSelectionOutcome:
    """Budgeted ranking output ready for ContextSelectResponse mapping."""

    selected_files: tuple[SelectedContextFile, ...]
    total_tokens: int
    accuracy: AccuracyLevel
    warnings: tuple[str, ...]


def _fts_query_from_task(task_description: str) -> str:
    terms = [
        t.lower()
        for t in _QUERY_TERM_RE.findall(task_description)
        if t.lower() not in _FTS_STOPWORDS
    ]
    unique_terms = list(dict.fromkeys(terms))
    if not unique_terms:
        return ""
    return " OR ".join(f'"{t}"' for t in unique_terms)


def _stem_without_test_prefix(path: str) -> str:
    name = PurePosixPath(path.replace("\\", "/")).stem.lower()
    for prefix in ("test_",):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    for suffix in ("_test", ".test", ".spec"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def _is_test_file(path: str) -> bool:
    norm = path.replace("\\", "/").lower()
    name = PurePosixPath(norm).name
    return (
        "/tests/" in f"/{norm}"
        or "/test/" in f"/{norm}"
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


class ContextSelector:
    """
    Ranks workspace documents using SQLite FTS5 BM25 plus structural repository signals.

    Signals combined:
    - SQLite FTS5 BM25 score across relative_path, symbols, and content
    - Filename & path token match
    - Symbol & import matches against task keywords
    - 1-hop dependency proximity & associated test files for top candidates
    - Recent modification freshness boost
    - Explicit pinned_files preservation within budget
    """

    def __init__(self, token_estimator: TokenEstimator | None = None) -> None:
        self._estimator = token_estimator if token_estimator is not None else TokenEstimator()

    def select(
        self,
        *,
        task_description: str,
        documents: list[ContextDocument],
        pinned_files: list[str] | tuple[str, ...] = (),
        max_files: int = 15,
        max_tokens: int = 8000,
        model: str = "generic",
    ) -> ContextSelectionOutcome:
        if not documents:
            return ContextSelectionOutcome(
                selected_files=(),
                total_tokens=0,
                accuracy=AccuracyLevel.ESTIMATED,
                warnings=(),
            )

        pinned_set = {p.replace("\\", "/") for p in pinned_files}
        doc_by_path = {d.relative_path.replace("\\", "/"): d for d in documents}
        query_terms = {
            t.lower()
            for t in _QUERY_TERM_RE.findall(task_description)
            if t.lower() not in _FTS_STOPWORDS
        }

        bm25_scores = self._compute_fts_bm25(documents, task_description)
        max_epoch = max((d.modified_epoch for d in documents), default=0.0)
        min_epoch = min((d.modified_epoch for d in documents), default=0.0)
        epoch_span = max(1.0, max_epoch - min_epoch)

        base_scores: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}
        token_counts: dict[str, int] = {}
        accuracies: set[AccuracyLevel] = set()

        for norm_path, doc in doc_by_path.items():
            tok_res = self._estimator.count(doc.content, model=model)
            token_counts[norm_path] = tok_res.count
            accuracies.add(tok_res.accuracy)

            score = 0.0
            doc_reasons: list[str] = []

            fts_val = bm25_scores.get(norm_path, 0.0)
            if fts_val > 0.0:
                score += fts_val * 2.0
                doc_reasons.append("bm25_match")

            path_tokens = {t.lower() for t in _QUERY_TERM_RE.findall(norm_path)}
            path_overlap = len(query_terms & path_tokens)
            if path_overlap > 0:
                score += path_overlap * 2.5
                doc_reasons.append("path_match")

            symbol_tokens = {s.lower() for s in doc.symbols}
            symbol_overlap = len(query_terms & symbol_tokens)
            if symbol_overlap > 0:
                score += symbol_overlap * 2.0
                doc_reasons.append("symbol_match")

            if max_epoch > min_epoch and doc.modified_epoch > 0.0:
                freshness = (doc.modified_epoch - min_epoch) / epoch_span
                score += freshness * 0.5
                if freshness > 0.7:
                    doc_reasons.append("recent_change")

            base_scores[norm_path] = score
            reasons[norm_path] = doc_reasons

        # Second pass: boost 1-hop dependencies and associated tests of strong primary targets
        top_primary = [
            p
            for p, s in sorted(base_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
            if s > 0.0 or p in pinned_set
        ]
        primary_stems = {_stem_without_test_prefix(p) for p in top_primary}
        primary_imports = {
            imp.lower() for p in top_primary for imp in doc_by_path[p].imports
        }

        for norm_path, doc in doc_by_path.items():
            if norm_path in top_primary:
                continue
            stem = _stem_without_test_prefix(norm_path)
            if _is_test_file(norm_path) and stem in primary_stems:
                base_scores[norm_path] += 2.2
                reasons[norm_path].append("associated_test")
            elif stem in primary_imports or any(
                imp.lower() in norm_path.lower() for imp in primary_imports if len(imp) > 2
            ):
                base_scores[norm_path] += 1.5
                reasons[norm_path].append("dependency_neighbor")

        # Rank pinned first, then descending relevance score
        ranked_paths = sorted(
            doc_by_path.keys(),
            key=lambda p: (1 if p in pinned_set else 0, base_scores[p], -token_counts[p]),
            reverse=True,
        )

        selected: list[SelectedContextFile] = []
        used_tokens = 0
        warnings: list[str] = []

        for path in ranked_paths:
            if len(selected) >= max_files:
                break
            is_pinned = path in pinned_set
            est_tokens = token_counts[path]
            if not is_pinned and base_scores[path] <= 0.0:
                continue
            if used_tokens + est_tokens > max_tokens:
                if is_pinned and used_tokens == 0:
                    # Single pinned file exceeds max_tokens: still surface with explicit budget warning
                    warnings.append(f"pinned_file_exceeds_token_budget:{path}")
                else:
                    continue

            reason_str = ", ".join(reasons[path]) if reasons[path] else ("pinned" if is_pinned else "relevant")
            if is_pinned and "pinned" not in reason_str:
                reason_str = f"pinned, {reason_str}" if reasons[path] else "pinned"

            selected.append(
                SelectedContextFile(
                    relative_path=path,
                    score=round(base_scores[path], 4),
                    reason=reason_str,
                    estimated_tokens=est_tokens,
                    pinned=is_pinned,
                )
            )
            used_tokens += est_tokens

        overall_accuracy = (
            AccuracyLevel.EXACT
            if accuracies == {AccuracyLevel.EXACT}
            else AccuracyLevel.ESTIMATED
        )

        return ContextSelectionOutcome(
            selected_files=tuple(selected),
            total_tokens=used_tokens,
            accuracy=overall_accuracy,
            warnings=tuple(warnings),
        )

    def _compute_fts_bm25(
        self,
        documents: list[ContextDocument],
        task_description: str,
    ) -> dict[str, float]:
        query = _fts_query_from_task(task_description)
        if not query:
            return {}

        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE workspace_lexical_index USING fts5(
                    relative_path,
                    symbols,
                    content_excerpt,
                    tokenize = 'porter unicode61'
                )
                """
            )
            conn.executemany(
                "INSERT INTO workspace_lexical_index (relative_path, symbols, content_excerpt) VALUES (?, ?, ?)",
                [
                    (
                        doc.relative_path.replace("\\", "/"),
                        " ".join(doc.symbols),
                        doc.content,
                    )
                    for doc in documents
                ],
            )
            rows = conn.execute(
                """
                SELECT relative_path, bm25(workspace_lexical_index) AS rank
                FROM workspace_lexical_index
                WHERE workspace_lexical_index MATCH ?
                ORDER BY rank ASC
                """,
                (query,),
            ).fetchall()
            # SQLite FTS5 bm25() returns negative scores (more negative = stronger match)
            return {row[0]: max(0.0, -float(row[1])) for row in rows}
        finally:
            conn.close()
