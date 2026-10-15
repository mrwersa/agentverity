"""A fixture-only projection exercises the real consumer without a new API."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from agentverity import (
    EvidenceError,
    EvidenceSet,
    assess_evidence,
    create_snapshot,
)
from agentverity.snapshot import SnapshotRefused
from research.evalport_conformance.check import _project_review_fixture

FIXTURES = Path(__file__).resolve().parents[1] / "research/evalport_conformance/fixtures"


def _document(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())["document"]


def test_a_quality_failure_retains_its_observed_decision_and_pair_flip():
    evidence = _project_review_fixture(_document("four_attempt_disagreement_valid"))
    assert evidence.cases[0].observations == ("approve", "review", "approve", "approve")
    result = assess_evidence(evidence)
    assert (result.meter.pair_trials, result.meter.pair_flips) == (2, 1)
    assert result.complete
    assert evidence.isolation == "fresh-instance"
    assert EvidenceSet.from_dict(evidence.to_dict()) == evidence


def test_attempt_order_recovers_pairs_instead_of_pairing_array_positions():
    evidence = _project_review_fixture(_document("interleaved_attempt_order_valid"))
    assert evidence.inputs == ("synthetic routing probe", "synthetic secondary probe")
    assert evidence.cases[0].observations == ("approve", "approve", "review", "review")
    assert evidence.cases[1].observations == ("deny",) * 4
    result = assess_evidence(evidence)
    assert (result.meter.pair_trials, result.meter.pair_flips) == (4, 0)


def test_case_order_is_first_appearance_while_attempts_order_each_case():
    document = _document("interleaved_attempt_order_valid")
    document["results"] = [document["results"][1], *document["results"][:1],
                           *document["results"][2:]]
    evidence = _project_review_fixture(document)
    assert evidence.inputs == ("synthetic secondary probe", "synthetic routing probe")
    assert evidence.cases[1].observations == ("approve", "approve", "review", "review")


def test_shared_evidence_is_assessed_but_refuses_snapshot_admission():
    evidence = _project_review_fixture(_document("repeated_shared_session_valid"))
    # A loose test tolerance makes isolation the only admission blocker.
    result = assess_evidence(evidence, epsilon=0.5)
    assert result.meter.call == "verdict-deterministic"
    assert not result.blindness.blind
    assert result.complete
    assert evidence.isolation == "shared-session"
    with pytest.raises(SnapshotRefused, match="shared-session"):
        create_snapshot(result, approved=True)


def test_a_recorded_runner_error_refuses_the_collection_before_pairing():
    with pytest.raises(EvidenceError, match="incomplete"):
        _project_review_fixture(_document("repeated_runner_error_valid"))


@pytest.mark.parametrize("isolation", [None, "unknown", "fresh", "provider-reset-v2"])
def test_unspecified_or_ambiguous_isolation_remains_unknown_with_source_preserved(isolation):
    document = _document("four_attempt_disagreement_valid")
    if isolation is None:
        del document["isolation"]
    else:
        document["isolation"] = isolation
    evidence = _project_review_fixture(document)
    assert evidence.isolation == "unknown"
    assert evidence.provenance["source_isolation"] == isolation


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "gap", "single", "aggregate"])
def test_ambiguous_or_inadequate_attempt_evidence_is_refused(mutation):
    document = deepcopy(_document("four_attempt_disagreement_valid"))
    if mutation == "missing":
        del document["results"][0]["attempt"]
    elif mutation == "duplicate":
        document["results"][1]["attempt"] = 1
    elif mutation == "gap":
        document["results"].pop(1)
    elif mutation == "single":
        document["results"] = document["results"][:1]
    else:
        del document["results"]
        document["summary"] = {"total": 4, "passed": 3}
    with pytest.raises(EvidenceError):
        _project_review_fixture(document)


def test_the_rehearsal_refuses_unreviewed_real_suites():
    document = _document("four_attempt_disagreement_valid")
    document["suite_id"] = "some-other-suite"
    with pytest.raises(EvidenceError, match="synthetic review suite"):
        _project_review_fixture(document)
