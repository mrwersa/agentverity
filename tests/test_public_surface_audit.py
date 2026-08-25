"""The reviewed public surface changes only through an explicit fixture diff."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.audit_public_surface import AUDIT_SCHEMA, collect_surface, main

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "compatibility"
    / "v0.21.0"
    / "public-surface.json"
)


def test_current_top_level_and_cli_surface_matches_the_reviewed_release():
    """The candidate differs only by the reviewed additive plan options."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["producer"] == "agentverity==0.21.0"
    assert fixture["surface"]["schema"] == AUDIT_SCHEMA
    current = deepcopy(collect_surface())
    plan = current["cli"]["commands"]["plan"]
    by_name = {entry["dest"]: entry for entry in plan}

    assert by_name["observed"] == {
        "action": "_StoreAction",
        "dest": "observed",
        "names": ["--observed"],
        "required": False,
    }
    assert by_name["max_pairs"] == {
        "action": "_StoreAction",
        "dest": "max_pairs",
        "names": ["--max-pairs"],
        "required": False,
        "type": "builtins.int",
    }
    assert by_name["suite"]["required"] is False

    plan[:] = [
        entry for entry in plan if entry["dest"] not in {"observed", "max_pairs"}
    ]
    next(entry for entry in plan if entry["dest"] == "suite")["required"] = True
    assert current == fixture["surface"]


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
