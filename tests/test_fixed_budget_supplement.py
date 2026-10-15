"""Run the standalone workshop supplement without shadowing library modules."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SUPPLEMENT = Path(__file__).resolve().parents[1] / "research" / "fixed_budget_qualification"


def run_supplement(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=SUPPLEMENT,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


def test_standalone_numerical_and_pathwise_checks_pass() -> None:
    result = run_supplement("-m", "unittest", "discover", "-s", "tests", "-v")
    assert "Ran 24 tests" in result.stderr
    assert "OK" in result.stderr


@pytest.mark.skipif(sys.version_info[:2] != (3, 12), reason="Generated outputs pin Python 3.12")
@pytest.mark.parametrize("script", ["analyse_maintenance.py", "budget_analysis.py"])
def test_python312_generated_outputs_are_current(script: str) -> None:
    assert "PASS" in run_supplement(script, "--check").stdout


def test_reproduction_files_match_manifest() -> None:
    manifest = json.loads((SUPPLEMENT / "SOURCE_MANIFEST.json").read_text())
    assert manifest["scope"] == "core workshop supplement"
    assert manifest["raw_maintenance_receipts_included"] is False
    assert manifest["first_crossing_positions_independently_verified"] is False
    assert {
        name for name, record in manifest["files"].items()
        if record["sha256"] != record["source_sha256"]
    } == set(manifest["changes"])
    for name, record in manifest["files"].items():
        assert Path(name).as_posix() == name and ".." not in Path(name).parts
        assert hashlib.sha256((SUPPLEMENT / name).read_bytes()).hexdigest() == record["sha256"]
