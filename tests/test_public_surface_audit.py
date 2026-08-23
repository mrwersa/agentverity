"""The reviewed public surface changes only through an explicit fixture diff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_public_surface import AUDIT_SCHEMA, collect_surface, main

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "compatibility"
    / "v0.19.0"
    / "public-surface.json"
)


def test_current_surface_is_the_reviewed_release_plus_the_020_addition():
    """The release candidate records its one additive compatibility delta."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    current = collect_surface()
    addition = {
        "kind": "function",
        "module": "agentverity.meter",
        "name": "best_case_admission_pairs",
        "qualified_name": "best_case_admission_pairs",
        "signature": "(epsilon: 'float', *, flips: 'int', pairs: 'int', "
        "max_pairs: 'int | None' = None, z: 'float' = 1.96) -> 'int | None'",
    }
    expected_python = sorted(
        [*fixture["surface"]["python"], addition], key=lambda entry: entry["name"]
    )

    assert fixture["producer"] == "agentverity==0.19.0"
    assert fixture["surface"]["schema"] == AUDIT_SCHEMA
    assert current["cli"] == fixture["surface"]["cli"]
    assert current["python"] == expected_python


def test_the_auditor_refuses_to_mislabel_the_current_checkout(monkeypatch, tmp_path):
    """A later checkout cannot silently replace the published-release inventory."""
    output = tmp_path / "surface.json"
    monkeypatch.setattr(
        "sys.argv",
        ["audit_public_surface.py", str(output), "--expected-version", "0.18.0"],
    )

    with pytest.raises(SystemExit, match="expected agentverity 0.18.0"):
        main()

    assert not output.exists()
