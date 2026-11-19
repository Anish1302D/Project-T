"""Hard quality validation invariants and diagnostic quality score Q."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from project_t_contracts import ContentType, ProtectedSpan, ValidationSummary

from .._segments import split_segments, try_parse_json
from ..constraints import ConstraintAnalysis

_WS_RE = re.compile(r"\s+")


def _norm_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _collect_json_structure_signature(obj: object) -> object:
    """Capture nested dict keys and list lengths to verify structural equivalence."""
    if isinstance(obj, dict):
        return {k: _collect_json_structure_signature(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_collect_json_structure_signature(item) for item in obj]
    return type(obj).__name__


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Detailed validation result including diagnostic score components (I, C, S, R)."""

    summary: ValidationSummary
    intent_score: float
    constraint_score: float
    structure_score: float
    reference_score: float
    failure_reasons: tuple[str, ...]

    def to_contract(self) -> ValidationSummary:
        return self.summary


class QualityValidator:
    """
    Enforces non-negotiable preservation invariants before emitting an optimized candidate.

    Computes provisional diagnostic score Q = 0.35I + 0.25C + 0.20S + 0.20R.
    Note: Q is an internal diagnostic only, never proof of downstream semantic equivalence.
    """

    def validate(
        self,
        *,
        original: str,
        candidate: str,
        content_type: ContentType,
        analysis: ConstraintAnalysis,
        preserve_identifiers: bool = True,
    ) -> ValidationReport:
        if not candidate and original:
            return ValidationReport(
                summary=ValidationSummary(
                    passed=False,
                    constraints_preserved=False,
                    identifiers_preserved=False,
                    structure_preserved=False,
                    quality_score=0.0,
                ),
                intent_score=0.0,
                constraint_score=0.0,
                structure_score=0.0,
                reference_score=0.0,
                failure_reasons=("empty_candidate",),
            )

        failures: list[str] = []
        norm_candidate = _norm_ws(candidate)

        # 1. Constraint preservation (C)
        constraints = analysis.constraints.constraints
        constraint_spans = [
            s.value
            for s in analysis.protected_spans
            if s.category in {"explicit_constraint", "output_format"}
        ]
        all_constraint_clauses = list(dict.fromkeys([*constraints, *constraint_spans]))
        if all_constraint_clauses:
            preserved_c = sum(1 for clause in all_constraint_clauses if _norm_ws(clause) in norm_candidate)
            c_score = preserved_c / len(all_constraint_clauses)
            constraints_ok = preserved_c == len(all_constraint_clauses)
        else:
            c_score = 1.0
            constraints_ok = True

        if not constraints_ok:
            failures.append("missing_or_altered_constraint")

        # 2. Identifier & protected reference preservation (R)
        ref_values = list(
            dict.fromkeys(
                s.value
                for s in analysis.protected_spans
                if s.category not in {"explicit_constraint", "output_format"}
            )
        )
        if ref_values:
            preserved_r = sum(1 for val in ref_values if val in candidate)
            r_score = preserved_r / len(ref_values)
            identifiers_ok = (preserved_r == len(ref_values)) if preserve_identifiers else True
        else:
            r_score = 1.0
            identifiers_ok = True

        if not identifiers_ok:
            failures.append("missing_or_altered_identifier")

        # 3. Structural preservation (S)
        structure_ok = self._check_structure(original, candidate, content_type)
        s_score = 1.0 if structure_ok else 0.0
        if not structure_ok:
            failures.append("structural_integrity_failed")

        # 4. Intent preservation heuristic (I)
        intent_targets = list(
            dict.fromkeys([*analysis.constraints.objectives, *analysis.constraints.targets])
        )
        if intent_targets:
            preserved_i = 0.0
            for item in intent_targets:
                words = [w.lower() for w in re.findall(r"[A-Za-z0-9_]{3,}", item)]
                if not words:
                    preserved_i += 1.0
                else:
                    matched = sum(1 for w in words if w in candidate.lower())
                    preserved_i += matched / len(words)
            i_score = min(1.0, preserved_i / len(intent_targets))
        else:
            i_score = 1.0 if candidate.strip() else 0.0

        # Provisional diagnostic quality score: Q = 0.35I + 0.25C + 0.20S + 0.20R
        q_score = round(
            min(1.0, max(0.0, 0.35 * i_score + 0.25 * c_score + 0.20 * s_score + 0.20 * r_score)),
            4,
        )

        passed = constraints_ok and identifiers_ok and structure_ok
        summary = ValidationSummary(
            passed=passed,
            constraints_preserved=constraints_ok,
            identifiers_preserved=identifiers_ok,
            structure_preserved=structure_ok,
            quality_score=q_score,
        )
        return ValidationReport(
            summary=summary,
            intent_score=round(i_score, 4),
            constraint_score=round(c_score, 4),
            structure_score=s_score,
            reference_score=round(r_score, 4),
            failure_reasons=tuple(failures),
        )

    def _check_structure(
        self,
        original: str,
        candidate: str,
        content_type: ContentType,
    ) -> bool:
        # Standalone JSON / tool_result invariance: keys and data structure must remain valid & equal
        orig_json = try_parse_json(original)
        if content_type in {ContentType.JSON, ContentType.TOOL_RESULT} or orig_json is not None:
            cand_json = try_parse_json(candidate)
            if orig_json is None or cand_json is None:
                return False
            return (
                _collect_json_structure_signature(orig_json)
                == _collect_json_structure_signature(cand_json)
                and json.dumps(orig_json, sort_keys=True) == json.dumps(cand_json, sort_keys=True)
            )

        # Balanced fenced blocks (when original fences were balanced) & JSON fence validity
        if original.count("```") % 2 == 0 and candidate.count("```") % 2 != 0:
            return False

        orig_segs = split_segments(original)
        cand_segs = split_segments(candidate)
        orig_fences = {s.text for s in orig_segs if s.kind in {"code_fence", "json_block"}}
        cand_fences = {s.text for s in cand_segs if s.kind in {"code_fence", "json_block"}}
        if not orig_fences.issubset(cand_fences):
            return False

        for seg in cand_segs:
            if seg.kind == "json_block":
                first_nl = seg.text.find("\n")
                body = seg.text[first_nl + 1 : -3] if first_nl != -1 else ""
                if try_parse_json(body) is None:
                    return False

        return True
