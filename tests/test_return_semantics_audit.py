"""Published return semantics change only through an explicit fixture diff."""

from __future__ import annotations

import json
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
    / "v0.19.0"
    / "return-semantics.json"
)


def test_current_return_semantics_match_the_published_release():
    """Main Python boundaries retain their reviewed types and relationships."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["producer"] == "agentverity==0.19.0"
    assert fixture["semantics"]["schema"] == AUDIT_SCHEMA
    assert collect_return_semantics() == fixture["semantics"]


def test_every_canonical_run_status_has_an_executed_scenario():
    """Status precedence is covered without reconstructing it from internals."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert set(fixture["semantics"]["statuses"]) == {
        "blind",
        "contract",
        "deterministic",
        "incomplete",
        "stochastic",
        "target-failed",
        "undecided",
        "unmeasured",
        "vacuous",
        "violations",
    }
    assert all(
        scenario["status"] == name
        for name, scenario in fixture["semantics"]["statuses"].items()
    )


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
