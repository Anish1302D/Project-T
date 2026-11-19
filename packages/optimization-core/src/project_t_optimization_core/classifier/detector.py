"""Deterministic content classification and mixed-segment detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from project_t_contracts import ContentClassification, ContentType

from .._segments import Segment, SegmentKind, split_segments, try_parse_json

_CONSTRAINT_RE = re.compile(
    r"\b(?:do not|don't|never|avoid|must not|must|always|ensure|only modify|only edit|without changing|strictly)\b",
    re.IGNORECASE,
)
_DEV_ACTION_RE = re.compile(
    r"\b(?:fix|debug|refactor|implement|review|optimize|check|update|add|remove|test|migrate|deploy)\b"
    r".*\b(?:api|endpoint|auth|jwt|middleware|database|schema|function|class|module|component|react|python|typescript|sql|repo|file|bug|error|test)\b",
    re.IGNORECASE | re.DOTALL,
)
_TERMINAL_RE = re.compile(
    r"(?:"
    r"Traceback \(most recent call last\):|"
    r"^\s*File \"[^\"]+\", line \d+|"
    r"\b(?:EXIT CODE|Exit code|exit status)\s*[:=]?\s*\d+|"
    r"^\s*(?:FAILED|ERROR)\s+[^\s]+|"
    r"\b\d+\s+passed(?:,\s*\d+\s+(?:failed|skipped|errors?))?\b|"
    r"npm ERR!|"
    r"\x1b\[[0-9;]*[A-Za-z]"
    r")",
    re.MULTILINE,
)
_CONVERSATION_TURN_RE = re.compile(
    r"^(?:User|Assistant|System|Human|AI)\s*:",
    re.MULTILINE | re.IGNORECASE,
)
_CODE_LINE_RE = re.compile(
    r"^\s*(?:def |class |import |from \S+ import |export |interface |type |const |let |function |async def |public |private |return )",
    re.MULTILINE,
)
_DOC_HEADING_RE = re.compile(r"^#{1,6}\s+\S+", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Rich classification output mapped cleanly to ContentClassification wire DTO."""

    type: str
    mapped_content_type: ContentType
    language: str
    contains_code: bool
    contains_constraints: bool
    segments: tuple[Segment, ...] = field(default_factory=tuple)

    def to_contract(self) -> ContentClassification:
        return ContentClassification(
            type=self.type,
            mapped_content_type=self.mapped_content_type,
            language=self.language,
            contains_code=self.contains_code,
            contains_constraints=self.contains_constraints,
        )


class ContentClassifier:
    """Deterministic classifier mapping inputs into canonical ContentType & subtype."""

    def classify(
        self,
        content: str,
        hint: ContentType | None = None,
    ) -> ClassificationResult:
        segments = split_segments(content)
        has_fence_code = any(seg.kind == "code_fence" for seg in segments)
        contains_constraints = bool(_CONSTRAINT_RE.search(content))

        parsed_json = try_parse_json(content)
        if parsed_json is not None:
            is_tool_payload = isinstance(parsed_json, dict) and (
                "tool_name" in parsed_json
                or "tool_call_id" in parsed_json
                or ("tool" in parsed_json and ("result" in parsed_json or "output" in parsed_json))
            )
            detected_type = "tool_result" if is_tool_payload else "json_document"
            mapped = (
                hint
                if hint is not None
                else (ContentType.TOOL_RESULT if is_tool_payload else ContentType.JSON)
            )
            return ClassificationResult(
                type=detected_type,
                mapped_content_type=mapped,
                language="json",
                contains_code=False,
                contains_constraints=contains_constraints,
                segments=(Segment(kind="json_block", start=0, end=len(content), text=content, language="json"),),
            )

        terminal_hits = len(_TERMINAL_RE.findall(content))
        code_hits = len(_CODE_LINE_RE.findall(content))
        turn_hits = len(_CONVERSATION_TURN_RE.findall(content))
        doc_headings = len(_DOC_HEADING_RE.findall(content))
        contains_code = has_fence_code or code_hits >= 2

        if terminal_hits >= 2 or (terminal_hits >= 1 and "Traceback" in content):
            detected_type = "terminal_log"
            auto_mapped = ContentType.TERMINAL_OUTPUT
            lang = "log"
        elif turn_hits >= 2:
            detected_type = "conversation_transcript"
            auto_mapped = ContentType.CONVERSATION
            lang = "en"
        elif not has_fence_code and code_hits >= 3 and doc_headings == 0:
            detected_type = "source_code"
            auto_mapped = ContentType.SOURCE_CODE
            lang = "code"
        elif _DEV_ACTION_RE.search(content) or (contains_constraints and (has_fence_code or "API" in content or "schema" in content.lower())):
            detected_type = "developer_instruction"
            auto_mapped = ContentType.DEVELOPER_PROMPT
            lang = "en"
        elif doc_headings >= 2 and not _DEV_ACTION_RE.search(content):
            detected_type = "markdown_documentation"
            auto_mapped = ContentType.DOCUMENTATION
            lang = "en"
        else:
            detected_type = "general_prompt"
            auto_mapped = ContentType.PROMPT
            lang = "en"

        mapped = hint if hint is not None else auto_mapped
        if mapped == ContentType.SOURCE_CODE:
            contains_code = True

        return ClassificationResult(
            type=detected_type,
            mapped_content_type=mapped,
            language=lang,
            contains_code=contains_code,
            contains_constraints=contains_constraints,
            segments=segments,
        )
