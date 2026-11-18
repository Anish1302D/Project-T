"""Verify parity across docs schemas, packages/contracts schemas, Python Pydantic models, and TypeScript enums."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "contracts" / "src"))

from project_t_contracts import (  # noqa: E402
    AccuracyLevel,
    ContentClassification,
    ContentType,
    ExtractedConstraints,
    IntegrationSource,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationResultWire,
    TokenCountResult,
)


def _extract_ts_const_array(ts_source: str, const_name: str) -> list[str]:
    pattern = rf"export const {const_name}\s*=\s*\[(.*?)\]\s*as const;"
    match = re.search(pattern, ts_source, flags=re.DOTALL)
    if not match:
        raise AssertionError(f"Could not find TypeScript const array '{const_name}' in wire.ts")
    return re.findall(r'"([^"]+)"', match.group(1))


def main() -> int:
    docs_schema_path = ROOT / "docs" / "api" / "contracts.schema.json"
    pkg_schema_path = ROOT / "packages" / "contracts" / "schemas" / "contracts.v1.schema.json"
    docs_openapi_path = ROOT / "docs" / "api" / "openapi-local-v1.yaml"
    pkg_openapi_path = ROOT / "packages" / "contracts" / "schemas" / "openapi-local-v1.yaml"
    ts_wire_path = ROOT / "packages" / "contracts" / "src" / "wire.ts"
    sql_schema_path = ROOT / "docs" / "architecture" / "schema.sql"

    # 1. JSON Schema parity
    docs_schema = json.loads(docs_schema_path.read_text(encoding="utf-8"))
    pkg_schema = json.loads(pkg_schema_path.read_text(encoding="utf-8"))
    assert docs_schema == pkg_schema, (
        "Schema drift between docs/api/contracts.schema.json and packages/contracts/schemas/contracts.v1.schema.json"
    )

    # 2. OpenAPI parity and ref resolution
    docs_openapi = yaml.safe_load(docs_openapi_path.read_text(encoding="utf-8"))
    pkg_openapi = yaml.safe_load(pkg_openapi_path.read_text(encoding="utf-8"))
    assert docs_openapi == pkg_openapi, (
        "OpenAPI drift between docs/api/openapi-local-v1.yaml and packages/contracts/schemas/openapi-local-v1.yaml"
    )

    def _check_refs(node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str) and v.startswith("#/"):
                    target: object = pkg_openapi
                    for part in v[2:].split("/"):
                        assert isinstance(target, dict) and part in target, f"Broken $ref: {v}"
                        target = target[part]
                else:
                    _check_refs(v)
        elif isinstance(node, list):
            for item in node:
                _check_refs(item)

    _check_refs(pkg_openapi)

    # 3. Enum parity across JSON Schema, OpenAPI, Python StrEnum, and TypeScript wire.ts
    ts_source = ts_wire_path.read_text(encoding="utf-8")
    defs = pkg_schema["$defs"]
    openapi_schemas = pkg_openapi["components"]["schemas"]

    enum_checks = [
        ("OptimizationMode", OptimizationMode, "OPTIMIZATION_MODES"),
        ("ContentType", ContentType, "CONTENT_TYPES"),
        ("AccuracyLevel", AccuracyLevel, "ACCURACY_LEVELS"),
    ]
    for schema_name, py_enum, ts_const in enum_checks:
        expected = defs[schema_name]["enum"]
        assert openapi_schemas[schema_name]["enum"] == expected, (
            f"OpenAPI mismatch for {schema_name}"
        )
        assert [m.value for m in py_enum] == expected, f"Python enum mismatch for {schema_name}"
        assert _extract_ts_const_array(ts_source, ts_const) == expected, (
            f"TypeScript const mismatch for {ts_const}"
        )

    assert [m.value for m in IntegrationSource] == _extract_ts_const_array(
        ts_source, "INTEGRATION_SOURCES"
    ), "IntegrationSource mismatch between Python and TypeScript"

    # 4. Pydantic model required/field parity against $defs
    model_checks = [
        ("OptimizationRequestWire", OptimizationRequestWire),
        ("OptimizationResultWire", OptimizationResultWire),
        ("TokenCountResult", TokenCountResult),
        ("ContentClassification", ContentClassification),
        ("ExtractedConstraints", ExtractedConstraints),
    ]
    for def_name, model_cls in model_checks:
        schema_def = defs[def_name]
        py_schema = model_cls.model_json_schema()
        expected_props = set(schema_def["properties"].keys())
        actual_props = set(py_schema["properties"].keys())
        assert expected_props == actual_props, (
            f"Property mismatch for {def_name}: expected {expected_props}, got {actual_props}"
        )
        expected_req = set(schema_def.get("required", []))
        actual_req = set(py_schema.get("required", []))
        assert expected_req == actual_req, (
            f"Required field mismatch for {def_name}: expected {expected_req}, got {actual_req}"
        )

    # 5. Reference SQL DDL execution check
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql_schema_path.read_text(encoding="utf-8"))

    print("Contract verification passed: JSON Schema, OpenAPI 3.1, Python Pydantic, TypeScript, and SQLite DDL aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
