"""Contract validation tests against canonical Draft 2020-12 JSON Schema."""

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from project_t_contracts import (
    ContentClassification,
    ContentType,
    ExtractedConstraints,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationResultWire,
    TokenCountRequest,
    TokenCountResult,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "contracts.v1.schema.json"
)
CANONICAL_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_against_def(def_name: str, payload: dict) -> None:
    subschema = {
        "$schema": CANONICAL_SCHEMA["$schema"],
        "$defs": CANONICAL_SCHEMA["$defs"],
        "$ref": f"#/$defs/{def_name}",
    }
    jsonschema.validate(instance=payload, schema=subschema)


def test_optimization_request_validates_against_canonical_schema() -> None:
    req = OptimizationRequestWire(
        content="Fix JWT middleware without changing schema.",
        content_type=ContentType.DEVELOPER_PROMPT,
        provider="openai",
        model="example-model",
        mode=OptimizationMode.BALANCED,
    )
    payload = req.model_dump(exclude_none=True)
    _validate_against_def("OptimizationRequestWire", payload)


def test_optimization_result_validates_against_canonical_schema() -> None:
    res = OptimizationResultWire(
        request_id="req_001",
        original_content="Original",
        optimized_content="Optimized",
        tokens={
            "original": 100,
            "optimized": 75,
            "saved": 25,
            "reduction_percentage": 25.0,
            "accuracy": "estimated",
        },
        validation={
            "passed": True,
            "constraints_preserved": True,
            "identifiers_preserved": True,
            "structure_preserved": True,
            "quality_score": 0.95,
        },
        optimization={
            "methods": ["deduplication", "rule_based_compression"],
            "mode": "balanced",
        },
        duration_ms=12,
        warnings=[],
    )
    _validate_against_def("OptimizationResultWire", res.model_dump(exclude_none=True))


def test_token_count_classification_and_constraints_schemas() -> None:
    token_res = TokenCountResult(
        count=42, accuracy="exact", model="example-model", provider="openai"
    )
    _validate_against_def("TokenCountResult", token_res.model_dump())

    classification = ContentClassification(
        type="developer_instruction",
        mapped_content_type=ContentType.DEVELOPER_PROMPT,
        language="en",
        contains_code=False,
        contains_constraints=True,
    )
    _validate_against_def("ContentClassification", classification.model_dump())

    constraints = ExtractedConstraints(
        objectives=["Fix authentication issue"],
        targets=["JWT middleware", "login API"],
        constraints=["Do not change the database schema"],
    )
    _validate_against_def("ExtractedConstraints", constraints.model_dump())


def test_forbids_unknown_fields_and_invalid_values() -> None:
    with pytest.raises(ValidationError):
        OptimizationRequestWire(content="", mode="balanced")

    with pytest.raises(ValidationError):
        OptimizationRequestWire(content="hello", unexpected_field=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        TokenCountRequest(provider="openai", model="example-model")
