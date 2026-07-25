"""Tests for evidence-gated snapshots."""

from __future__ import annotations

import pytest

from agentverity import from_callable, run
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
    assert "381 are needed" in message
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
    assert "381 are needed" not in str(excinfo.value)


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
