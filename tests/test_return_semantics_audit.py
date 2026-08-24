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
    / "v0.20.0"
    / "return-semantics.json"
)


def test_current_return_semantics_match_the_published_release():
    """The candidate adds only reviewed curtailment return semantics."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["producer"] == "agentverity==0.20.0"
    assert fixture["semantics"]["schema"] == AUDIT_SCHEMA
    baseline = fixture["semantics"]
    current = deepcopy(collect_return_semantics())
    curtailed = current["statuses"].pop("curtailed")
    assert curtailed == {
        "type": "RunResult",
        "status": "curtailed",
        "complete": True,
        "is_stochastic": False,
        "is_blind": False,
        "error_count": 0,
    }
    current["reports"]["json"]["top_level_keys"].remove("curtailment")

    assert current == baseline


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
