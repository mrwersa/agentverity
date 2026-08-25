"""Published return semantics change only through an explicit fixture diff."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.audit_return_semantics import (
    AUDIT_SCHEMA,
    collect_return_semantics,
    main,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "compatibility"
    / "v0.21.0"
    / "return-semantics.json"
)


def test_current_return_semantics_match_the_published_release():
    """Replay adds one optional JSON field without changing return classes."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["producer"] == "agentverity==0.21.0"
    assert fixture["semantics"]["schema"] == AUDIT_SCHEMA
    current = deepcopy(collect_return_semantics())
    current["reports"]["json"]["top_level_keys"].remove("curtailment_replay")
    assert current == fixture["semantics"]


def test_every_canonical_run_status_has_an_executed_scenario():
    """Status precedence is covered without reconstructing it from internals."""
    statuses = collect_return_semantics()["statuses"]
    assert set(statuses) == {
        "blind",
        "contract",
        "curtailed",
        "deterministic",
        "incomplete",
        "stochastic",
        "target-failed",
        "undecided",
        "unmeasured",
        "vacuous",
        "violations",
    }
    assert all(scenario["status"] == name for name, scenario in statuses.items())


def test_the_auditor_refuses_to_mislabel_the_current_checkout(monkeypatch, tmp_path):
    """A later checkout cannot silently replace the published-release record."""
    output = tmp_path / "semantics.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit_return_semantics.py",
            str(output),
            "--expected-version",
            "0.18.0",
        ],
    )

    with pytest.raises(SystemExit, match="expected agentverity 0.18.0"):
        main()

    assert not output.exists()
