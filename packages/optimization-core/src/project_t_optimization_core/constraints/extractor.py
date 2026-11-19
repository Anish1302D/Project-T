"""Constraint extraction and 10-category protected-span detection."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from project_t_contracts import ExtractedConstraints, ProtectedSpan

from .._segments import split_segments

# 1. Explicit constraint & output format patterns (prose sentences/clauses)
_CONSTRAINT_CLAUSE_RE = re.compile(
    r"(?:^|(?<=[.!?\n]))\s*"
    r"([^\n.!?]*\b(?:do not|don't|never|avoid|must not|must|always|ensure|only modify|only edit|without changing|without altering|strictly)\b[^\n.!?]*[.!?]?)",
    re.IGNORECASE,
)
_OUTPUT_FORMAT_RE = re.compile(
    r"\b(?:return valid json|valid json|unified diff|markdown table|json schema|yaml format|output format|respond (?:only )?(?:with|as|in) [^\n,.!?]+)\b",
    re.IGNORECASE,
)
_MD_TABLE_HEADER_RE = re.compile(r"^\s*\|[^\n]+\|\s*\n\s*\|(?:\s*:?-+:?\s*\|)+\s*$", re.MULTILINE)

# 2. Technical & identifier span extractors across all protected categories
_IMPORT_OR_TYPE_RE = re.compile(
    r"(?:^\s*(?:from\s+[A-Za-z0-9_.]+\s+import\s+[^\n]+|import\s+[^\n]+)|"
    r"\b(?:interface|type)\s+[A-Z][A-Za-z0-9_]*\b|"
    r"\b(?:List|Dict|Tuple|Set|Optional|Union|Sequence|Mapping|Record|Promise|Array)<[^>\n]+>|"
    r"\b(?:list|dict|tuple|set)\[[^\]\n]+\])",
    re.MULTILINE,
)
_API_ENDPOINT_RE = re.compile(
    r"(?:\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/[A-Za-z0-9_./:{}-]*|"
    r"https?://[^\s)>\"'`]+|"
    r"(?<![\w.])/(?:api|v\d+)/[A-Za-z0-9_./:{}-]+)"
)
_FILE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s\"'<>|]+|"
    r"(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,8}(?:#L\d+(?:-L?\d+)?|:\d+(?::\d+)?)?|"
    r"\b[\w.-]+\.(?:py|ts|tsx|js|jsx|json|yaml|yml|sql|md|toml|lock|sh|ps1)\b(?:#L\d+(?:-L?\d+)?|:\d+(?::\d+)?)?)"
)
_VERSION_OR_CONFIG_RE = re.compile(
    r"(?:\b127\.0\.0\.1:\d+\b|"
    r"\bv?\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9.-]+|\+)?\b|"
    r"\b[A-Z][A-Z0-9]{1,}(?:_[A-Z0-9]+)+\b)"
)
_ERROR_RE = re.compile(
    r"(?:\b(?:ERR_[A-Z0-9_]+|E[A-Z]{4,}|HTTP\s+[45]\d\d)\b|"
    r"\b[A-Z][a-zA-Z]*(?:Error|Exception|Warning)\b)"
)
_JSON_KEY_RE = re.compile(r'"([A-Za-z0-9_.$@-]{1,64})"\s*:')
_TOOL_NAME_RE = re.compile(
    r"\b(?:tool_name|tool_call_id|response_format|function_call|optimize_prompt|analyze_context|compress_terminal_output|select_relevant_files|deduplicate_context|estimate_tokens|get_optimization_report)\b"
)
_BACKTICK_CODE_RE = re.compile(r"`([^`\n]{1,120})`")
_IDENTIFIER_RE = re.compile(
    r"(?:\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|"  # snake_case
    r"\b[a-z][a-z0-9]*(?:[A-Z][a-zA-Z0-9]*)+\b|"  # camelCase
    r"\b[A-Z][a-z0-9]+(?:[A-Z][a-zA-Z0-9]*)+\b)"  # PascalCase (2+ humps)
)
_OBJECTIVE_LINE_RE = re.compile(
    r"^\s*(?:please\s+)?((?:fix|debug|implement|build|create|check|inspect|refactor|optimize|update|add|remove|test|review|verify|analyze)\b[^\n.!?]*)",
    re.IGNORECASE | re.MULTILINE,
)

# Common English capitalized compound words to avoid over-tagging as PascalCase identifiers
_COMMON_PROSE_WORDS = frozenset({"JavaScript", "TypeScript", "GitHub", "PostgreSQL", "SQLite", "FastAPI"})


@dataclass(frozen=True, slots=True)
class ConstraintAnalysis:
    """Combined constraint structure and full protected-span inventory."""

    constraints: ExtractedConstraints
    protected_spans: tuple[ProtectedSpan, ...]


def _extract_python_ast_identifiers(code_text: str, base_offset: int) -> list[ProtectedSpan]:
    """Use Python stdlib AST to capture exact function, class, and argument symbols when valid."""
    lines = code_text.splitlines(keepends=True)
    if len(lines) >= 2 and lines[0].startswith("```"):
        inner_offset = base_offset + len(lines[0])
        closing_len = len(lines[-1]) if lines[-1].strip() == "```" else 0
        body = "".join(lines[1:-1]) if closing_len else "".join(lines[1:])
    else:
        inner_offset = base_offset
        body = code_text

    try:
        tree = ast.parse(body)
    except SyntaxError:
        return []

    spans: list[ProtectedSpan] = []
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in [*node.args.args, *node.args.kwonlyargs]:
                    if arg.arg not in {"self", "cls"}:
                        names.add(arg.arg)

    for name in sorted(names):
        for match in re.finditer(rf"\b{re.escape(name)}\b", body):
            spans.append(
                ProtectedSpan(
                    category="identifier",
                    value=name,
                    start=inner_offset + match.start(),
                    end=inner_offset + match.end(),
                )
            )
    return spans


def _make_trimmed_span(category: str, text_slice: str, start: int, end: int) -> ProtectedSpan | None:
    ltrim = len(text_slice) - len(text_slice.lstrip())
    rtrim = len(text_slice) - len(text_slice.rstrip())
    trimmed = text_slice.strip()
    if not trimmed:
        return None
    return ProtectedSpan(
        category=category,
        value=trimmed,
        start=start + ltrim,
        end=end - rtrim,
    )


def _dedupe_spans(spans: list[ProtectedSpan]) -> tuple[ProtectedSpan, ...]:
    seen: set[tuple[str, int, int]] = set()
    ordered = sorted(spans, key=lambda s: (s.start, s.end, s.category))
    unique: list[ProtectedSpan] = []
    for span in ordered:
        key = (span.category, span.start, span.end)
        if key not in seen and span.value:
            seen.add(key)
            unique.append(span)
    return tuple(unique)


class ConstraintExtractor:
    """Extracts explicit constraints, objectives, targets, and all 10 protected-span categories."""

    def extract(self, content: str) -> ConstraintAnalysis:
        if not content:
            return ConstraintAnalysis(
                constraints=ExtractedConstraints(objectives=[], targets=[], constraints=[]),
                protected_spans=(),
            )

        spans: list[ProtectedSpan] = []
        constraints_list: list[str] = []
        objectives_list: list[str] = []
        targets_list: list[str] = []

        segments = split_segments(content)

        # Whole fenced blocks (code/json) are structurally protected spans plus inner AST/keys
        for seg in segments:
            if seg.kind == "code_fence":
                if (seg.language or "") in {"python", "py"}:
                    spans.extend(_extract_python_ast_identifiers(seg.text, seg.start))
            elif seg.kind == "json_block":
                for m in _JSON_KEY_RE.finditer(seg.text):
                    spans.append(
                        ProtectedSpan(
                            category="json_key_or_schema",
                            value=m.group(1),
                            start=seg.start + m.start(1),
                            end=seg.start + m.end(1),
                        )
                    )

        # Prose-only extractions (objectives, explicit constraints, output formats)
        for seg in segments:
            if seg.kind != "prose":
                continue

            for m in _CONSTRAINT_CLAUSE_RE.finditer(seg.text):
                span = _make_trimmed_span(
                    "explicit_constraint",
                    m.group(1),
                    seg.start + m.start(1),
                    seg.start + m.end(1),
                )
                if span is not None:
                    constraints_list.append(span.value)
                    spans.append(span)

            for m in _OUTPUT_FORMAT_RE.finditer(seg.text):
                span = _make_trimmed_span(
                    "output_format",
                    m.group(0),
                    seg.start + m.start(),
                    seg.start + m.end(),
                )
                if span is not None:
                    spans.append(span)

            for m in _MD_TABLE_HEADER_RE.finditer(seg.text):
                span = _make_trimmed_span(
                    "output_format",
                    m.group(0),
                    seg.start + m.start(),
                    seg.start + m.end(),
                )
                if span is not None:
                    spans.append(span)

            for m in _OBJECTIVE_LINE_RE.finditer(seg.text):
                obj_text = m.group(1).strip()
                # Avoid classifying pure negative constraint lines as objectives
                if obj_text and not re.match(r"^(?:do not|don't|never|avoid)\b", obj_text, re.I):
                    objectives_list.append(obj_text)

        # Cross-document pattern scans across all 10 categories
        pattern_map: tuple[tuple[str, re.Pattern[str], int], ...] = (
            ("import_or_type", _IMPORT_OR_TYPE_RE, 0),
            ("api_endpoint", _API_ENDPOINT_RE, 0),
            ("file_path_or_line", _FILE_PATH_RE, 0),
            ("error_code_or_message", _ERROR_RE, 0),
            ("tool_name_or_arg", _TOOL_NAME_RE, 0),
            ("version_or_config", _VERSION_OR_CONFIG_RE, 0),
            ("json_key_or_schema", _JSON_KEY_RE, 1),
            ("identifier", _BACKTICK_CODE_RE, 1),
            ("identifier", _IDENTIFIER_RE, 0),
        )

        for category, regex, group_idx in pattern_map:
            for m in regex.finditer(content):
                raw_val = m.group(group_idx)
                val = raw_val.strip()
                if not val:
                    continue
                if category == "identifier" and val in _COMMON_PROSE_WORDS:
                    continue
                span = _make_trimmed_span(
                    category,
                    raw_val,
                    m.start(group_idx),
                    m.end(group_idx),
                )
                if span is not None:
                    spans.append(span)

        # Populate targets from paths, endpoints, backticked symbols, and key architectural nouns
        seen_targets: set[str] = set()
        for span in spans:
            if span.category in {"api_endpoint", "file_path_or_line", "identifier", "tool_name_or_arg"}:
                if span.value not in seen_targets:
                    seen_targets.add(span.value)
                    targets_list.append(span.value)

        # Preserve order while deduplicating extracted constraint & objective strings
        unique_constraints = list(dict.fromkeys(constraints_list))
        unique_objectives = list(dict.fromkeys(objectives_list))

        return ConstraintAnalysis(
            constraints=ExtractedConstraints(
                objectives=unique_objectives,
                targets=targets_list[:20],
                constraints=unique_constraints,
            ),
            protected_spans=_dedupe_spans(spans),
        )
