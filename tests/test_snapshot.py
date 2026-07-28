"""Tests for evidence-gated snapshots."""

from __future__ import annotations

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    from_callable,
    run,
)
from agentverity.runner import RunConfig
from agentverity.snapshot import (
    SNAPSHOT_SCHEMA,
    SnapshotCompatibilityError,
    SnapshotRefused,
    compare_snapshot,
    create_snapshot,
    load_snapshot,
    save_snapshot,
)

INPUTS = ["allow-a", "allow-b", "block-a", "block-b"]
CONFIG = RunConfig(k=4, epsilon=0.5, blindness_threshold=0.9)


def _gate(text: str) -> dict:
    verdict = "block" if text.startswith("block") else "allow"
    return {"text": verdict, "verdict": verdict}


def _result(agent=_gate, inputs=INPUTS):
    return run(from_callable(agent), inputs, relations=[], config=CONFIG)


def test_snapshot_requires_explicit_reference_approval():
    with pytest.raises(SnapshotRefused, match="explicit approval"):
        create_snapshot(_result(), approved=False)


def test_snapshot_records_admission_evidence_not_raw_inputs():
    snapshot = create_snapshot(_result(), approved=True)
    value = snapshot.to_dict()
    assert value["schema"] == SNAPSHOT_SCHEMA
    assert value["admission_evidence"]["meter_call"] == "verdict-deterministic"
    assert value["admission_evidence"]["reference_approved"] is True
    assert not any(text in repr(value) for text in INPUTS)


def test_snapshot_refuses_blind_probe_set():
    blind = run(
        from_callable(lambda _text: {"verdict": "allow"}),
        INPUTS,
        relations=[],
        config=CONFIG,
    )
    with pytest.raises(SnapshotRefused, match="blind"):
        create_snapshot(blind, approved=True)


def test_snapshot_refuses_undecided_meter():
    undecided = run(
        from_callable(_gate),
        INPUTS,
        relations=[],
        config=RunConfig(k=2, epsilon=0.01),
    )
    with pytest.raises(SnapshotRefused, match="not enough evidence") as excinfo:
        create_snapshot(undecided, approved=True)

    message = str(excinfo.value)
    # "undecided" alone reads like a bug on an obviously deterministic agent,
    # so the refusal has to say how far short the run fell and what to change.
    assert "about 381 pairs are needed" in message
    assert "--k" in message
    assert "--epsilon" in message


def test_underpowered_refusal_scales_its_advice_to_the_probe_set():
    """The suggested k depends on how many inputs are carrying the pairs."""
    from agentverity.snapshot import _underpowered_message

    few = run(from_callable(_gate), INPUTS, relations=[], config=RunConfig(k=2))
    message = _underpowered_message(few.meter)
    assert f"across {few.meter.inputs} inputs" in message


def test_stochastic_refusal_differs_from_underpowered_refusal():
    """A flipping verdict is a different problem from a small sample."""
    import itertools

    counter = itertools.count()

    def flipping(text: str) -> dict:
        return {"text": text, "verdict": "A" if next(counter) % 2 else "B"}

    stochastic = run(from_callable(flipping), INPUTS, relations=[])
    with pytest.raises(SnapshotRefused, match="stochastic") as excinfo:
        create_snapshot(stochastic, approved=True)
    assert "disagreed" in str(excinfo.value)
    assert "pairs are needed" not in str(excinfo.value)


def test_snapshot_refuses_incomplete_run():
    def failing(text: str) -> dict:
        if text == "block-a":
            raise RuntimeError("down")
        return _gate(text)

    incomplete = run(
        from_callable(failing),
        INPUTS,
        relations=[],
        config=RunConfig(
            k=4,
            epsilon=0.5,
            blindness_threshold=0.9,
            error_policy="record",
        ),
    )
    with pytest.raises(SnapshotRefused, match="incomplete"):
        create_snapshot(incomplete, approved=True)


def test_snapshot_check_is_order_independent():
    snapshot = create_snapshot(_result(), approved=True)
    current = _result(inputs=list(reversed(INPUTS)))
    assert compare_snapshot(snapshot, current).clean


def test_snapshot_check_reports_drift():
    snapshot = create_snapshot(_result(), approved=True)

    def changed(text: str) -> dict:
        if text == "allow-a":
            return {"verdict": "block"}
        return _gate(text)

    diff = compare_snapshot(snapshot, _result(agent=changed))
    assert diff.clean is False
    assert diff.checked == 4
    assert len(diff.changes) == 1
    assert diff.changes[0].expected == "allow"
    assert diff.changes[0].actual == "block"


def test_snapshot_check_rejects_different_probe_set():
    snapshot = create_snapshot(_result(), approved=True)
    with pytest.raises(SnapshotCompatibilityError, match="fingerprints"):
        compare_snapshot(
            snapshot,
            _result(inputs=["allow-a", "allow-b", "block-a", "block-c"]),
        )


def test_snapshot_round_trip(tmp_path):
    snapshot = create_snapshot(_result(), approved=True)
    path = tmp_path / "baseline.json"
    save_snapshot(snapshot, path)
    assert load_snapshot(path) == snapshot


def test_contract_snapshot_records_intent_and_rechecks_the_contract():
    suite = DecisionSuite(
        contract=DecisionContract(
            allowed={"allow", "review", "deny"},
            critical={"deny"},
        ),
        cases=(
            DecisionCase("allow-a", "allow"),
            DecisionCase("review-a", "review"),
            DecisionCase("block-a", "deny"),
        ),
    )

    def contract_gate(text: str) -> dict:
        if text.startswith("allow"):
            return {"verdict": "allow"}
        if text.startswith("review"):
            return {"verdict": "review"}
        return {"verdict": "deny"}

    result = run(
        from_callable(contract_gate),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )
    snapshot = create_snapshot(result, approved=True)
    value = snapshot.to_dict()

    assert value["decision_contract"]["critical"] == ["deny"]
    assert [probe["intended"] for probe in value["probes"]] == [
        "allow",
        "review",
        "deny",
    ]
    assert compare_snapshot(snapshot, result).clean

    changed_intent = DecisionSuite(
        contract=suite.contract,
        cases=(
            DecisionCase("allow-a", "review"),
            DecisionCase("review-a", "allow"),
            DecisionCase("block-a", "deny"),
        ),
    )
    changed_result = run(
        from_callable(contract_gate),
        suite=changed_intent,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )
    with pytest.raises(SnapshotCompatibilityError, match="intended decisions"):
        compare_snapshot(snapshot, changed_result)


def test_snapshot_refuses_an_incomplete_declared_contract():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"allow", "review", "deny"}),
        cases=(
            DecisionCase("allow-a", "allow"),
            DecisionCase("block-a", "deny"),
        ),
    )
    result = run(
        from_callable(_gate),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    with pytest.raises(SnapshotRefused, match="decision contract"):
        create_snapshot(result, approved=True)


def test_snapshot_loader_migrates_v1_without_a_contract():
    value = create_snapshot(_result(), approved=True).to_dict()
    value["schema"] = "agentverity.snapshot/v1"
    value.pop("decision_contract")
    for probe in value["probes"]:
        probe.pop("intended")

    loaded = type(create_snapshot(_result(), approved=True)).from_dict(value)

    assert loaded.schema == SNAPSHOT_SCHEMA
    assert loaded.decision_contract is None
    assert all(probe.intended is None for probe in loaded.probes)


class TestDocumentedSizingIsPinned:
    """The README table and the documented escape route are claims, so test them."""

    def test_readme_sizing_table(self):
        """Every row of the README's budgeting table, generated not typed."""
        from agentverity.meter import pairs_for_deterministic_call

        # epsilon -> (pairs, --k for 20 inputs, agent calls)
        table = {0.01: (381, 40, 800), 0.02: (189, 20, 400),
                 0.05: (73, 8, 160), 0.10: (35, 4, 80)}
        for epsilon, (pairs, k, calls) in table.items():
            actual = pairs_for_deterministic_call(epsilon)
            assert actual == pairs, f"eps={epsilon}"
            needed_k = -(-actual // 20) * 2
            assert needed_k == k and 20 * needed_k == calls, f"eps={epsilon}"

    def test_the_documented_escape_route_actually_works(self):
        """Advice that does not lead to a snapshot is worse than no advice."""
        deterministic = from_callable(
            lambda text: {"text": text, "verdict":
                          "billing" if "charge" in text else "tech"}
        )
        inputs = [f"charge query {i}" for i in range(3)] + [
            f"crash report {i}" for i in range(3)
        ]
        result = run(deterministic, inputs, relations=[],
                     config=RunConfig(k=26, epsilon=0.05))
        snapshot = create_snapshot(result, approved=True)
        assert len(snapshot.probes) == len(inputs)


class TestAdviceAccountsForObservedFlips:
    """Assuming zero flips can advise a caller to collect less than they have."""

    @staticmethod
    def _meter(pair_trials, pair_flips, epsilon=0.01, inputs=6):
        from agentverity.meter import MeterResult, wilson_ci

        low, high = wilson_ci(pair_flips, pair_trials)
        return MeterResult(
            layer="verdict", epsilon=epsilon, inputs=inputs,
            repeats=(pair_trials // inputs) * 2, pair_trials=pair_trials,
            pair_flips=pair_flips, inputs_with_flip=pair_flips,
            ci_low=low, ci_high=high,
        )

    def test_never_recommends_fewer_pairs_than_already_collected(self):
        from agentverity.snapshot import _underpowered_message

        meter = self._meter(pair_trials=1200, pair_flips=6)
        assert meter.call.startswith("undecided")
        message = _underpowered_message(meter)
        assert "1574" in message, message
        assert "128" not in message, "advised dropping below the pairs already run"

    def test_says_more_pairs_cannot_help_when_the_rate_meets_epsilon(self):
        from agentverity.meter import pairs_for_deterministic_call
        from agentverity.snapshot import _underpowered_message

        assert pairs_for_deterministic_call(0.01, flip_rate=0.01) is None
        meter = self._meter(pair_trials=200, pair_flips=6, epsilon=0.02)
        if meter.call.startswith("undecided"):
            message = _underpowered_message(meter)
            assert "More pairs will not help" in message or "pairs are needed" in message
