"""Foundation boundary and contract verification tests."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_verify_contracts_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_contracts.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
