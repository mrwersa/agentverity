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
    / "v0.22.0"
    / "public-surface.json"
)


def test_current_top_level_and_cli_surface_matches_the_reviewed_release():
    """The candidate differs only by reviewed additive replay surfaces."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["producer"] == "agentverity==0.22.0"
    assert fixture["surface"]["schema"] == AUDIT_SCHEMA
    baseline = fixture["surface"]
    current = deepcopy(collect_surface())
    python = {entry["name"]: entry for entry in current["python"]}

    assert python.pop("CurtailmentReplayResult") == {
        "name": "CurtailmentReplayResult",
        "kind": "class",
        "module": "agentverity.runner",
        "qualified_name": "CurtailmentReplayResult",
        "signature": (
            "(endpoint_pairs: 'int', stopping_pair: 'int | None', "
            "observed_flips: 'int', meter_calls_avoided: 'int', reason: 'str') "
            "-> None"
        ),
    }
    baseline_python = {entry["name"]: entry for entry in baseline["python"]}
    for name in ("RunResult", "assess_evidence"):
        assert python[name]["signature"] != baseline_python[name]["signature"]
        python[name]["signature"] = baseline_python[name]["signature"]
    current["python"] = sorted(python.values(), key=lambda entry: entry["name"])

    assess = current["cli"]["commands"]["assess"]
    replay = [item for item in assess if item["dest"] == "replay_curtailment"]
    assert replay == [
        {
            "action": "_StoreTrueAction",
            "dest": "replay_curtailment",
            "names": ["--replay-curtailment"],
            "required": False,
            "nargs": 0,
            "default": False,
        }
    ]
    current["cli"]["commands"]["assess"] = [
        item for item in assess if item["dest"] != "replay_curtailment"
    ]

    assert current == baseline


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
