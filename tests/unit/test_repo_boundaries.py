"""Foundation boundary and contract verification tests."""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_CORE_IMPORTS = frozenset(
    {
        "apps",
        "services",
        "fastapi",
        "starlette",
        "uvicorn",
        "httpx",
        "requests",
        "urllib3",
        "openai",
        "anthropic",
        "google",
        "tiktoken",
        "project_t_provider_adapters",
    }
)


def test_verify_contracts_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_contracts.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_optimization_core_has_no_forbidden_boundary_imports() -> None:
    core_src = ROOT / "packages" / "optimization-core" / "src"
    py_files = sorted(core_src.rglob("*.py"))
    assert py_files, "Expected optimization-core Python files to exist"

    violations: list[str] = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    if top_pkg in FORBIDDEN_CORE_IMPORTS:
                        violations.append(f"{py_file}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_pkg = node.module.split(".")[0]
                if top_pkg in FORBIDDEN_CORE_IMPORTS:
                    violations.append(f"{py_file}: from {node.module}")

    assert violations == [], f"Boundary violations detected: {violations}"
