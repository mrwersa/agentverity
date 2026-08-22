"""Current readers preserve durable files written by an earlier minor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentverity import (
    DECISION_SUITE_SCHEMA,
    EVIDENCE_SCHEMA,
    SNAPSHOT_SCHEMA,
    NoDecision,
    load_decision_suite,
    load_evidence,
    load_snapshot,
    save_decision_suite,
    save_evidence,
    save_snapshot,
)
from scripts.generate_compatibility_fixtures import generate

FIXTURES = Path(__file__).parent / "fixtures" / "compatibility" / "v0.16.0"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_historical_manifest_matches_every_current_reader_schema():
    """The producer predates the reader while every stored schema still matches."""
    manifest = _json(FIXTURES / "manifest.json")

    assert manifest == {
        "producer": "agentverity==0.16.0",
        "schemas": {
            "decision_suite": DECISION_SUITE_SCHEMA,
            "evidence": EVIDENCE_SCHEMA,
            "snapshot": SNAPSHOT_SCHEMA,
        },
    }


def test_current_loaders_preserve_the_historical_files(tmp_path):
    """Loading and rewriting v0.16.0 files neither loses nor invents meaning."""
    suite = load_decision_suite(FIXTURES / "decision-suite.json")
    evidence = load_evidence(FIXTURES / "evidence.json")
    snapshot = load_snapshot(FIXTURES / "snapshot.json")

    assert suite.inputs == ("routine request", "ambiguous request")
    assert suite.contract.allowed_no_decisions == frozenset({"refused"})
    assert evidence.cases[1].observations == (
        NoDecision("refused"),
        NoDecision("refused"),
    )
    assert evidence.isolation == "fresh-session"
    assert snapshot.agentverity_version == "0.16.0"
    assert snapshot.isolation == "fresh-session"
    assert snapshot.probes[1].expected == {
        "kind": "no_decision",
        "reason": "refused",
    }

    rewritten = {
        "decision-suite.json": (suite, save_decision_suite),
        "evidence.json": (evidence, save_evidence),
        "snapshot.json": (snapshot, save_snapshot),
    }
    for name, (value, save) in rewritten.items():
        destination = tmp_path / name
        save(value, destination)
        assert _json(destination) == _json(FIXTURES / name)


def test_the_generator_refuses_to_relabel_a_fixture_from_another_release(tmp_path):
    """A current writer cannot accidentally overwrite the historical corpus."""
    with pytest.raises(SystemExit, match="expected agentverity 0.16.0"):
        generate(tmp_path, "0.16.0")

    assert list(tmp_path.iterdir()) == []
