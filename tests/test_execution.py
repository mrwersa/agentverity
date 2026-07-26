"""Tests for bounded execution and progress reporting."""

from __future__ import annotations

import threading
import time

import pytest

from agentverity.execution import input_fingerprint, map_inputs


def test_parallel_work_preserves_input_order():
    delays = {"slow": 0.03, "fast": 0.001, "middle": 0.01}

    def worker(_index: int, text: str) -> str:
        time.sleep(delays[text])
        return text.upper()

    result = map_inputs(
        ["slow", "fast", "middle"],
        worker,
        phase="test",
        max_workers=3,
        error_policy="raise",
    )
    assert result.values == ("SLOW", "FAST", "MIDDLE")


def test_distinct_inputs_can_execute_concurrently():
    lock = threading.Lock()
    active = 0
    high_watermark = 0

    def worker(_index: int, text: str) -> str:
        nonlocal active, high_watermark
        with lock:
            active += 1
            high_watermark = max(high_watermark, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return text

    map_inputs(
        ["a", "b", "c"],
        worker,
        phase="test",
        max_workers=3,
        error_policy="raise",
    )
    assert high_watermark > 1


def test_record_policy_retains_failure_without_inventing_a_value():
    events = []

    def worker(_index: int, text: str) -> str:
        if text == "bad":
            raise RuntimeError("provider unavailable")
        return text

    result = map_inputs(
        ["good", "bad"],
        worker,
        phase="meter",
        max_workers=2,
        error_policy="record",
        on_progress=events.append,
    )
    assert result.values == ("good", None)
    assert len(result.errors) == 1
    assert result.errors[0].exception_type == "RuntimeError"
    assert result.errors[0].input_fingerprint == input_fingerprint("bad")
    assert [event.status for event in events].count("error") == 1
    assert all("good" not in repr(event) and "bad" not in repr(event) for event in events)


def test_raise_policy_propagates_original_exception():
    with pytest.raises(RuntimeError, match="provider unavailable"):
        map_inputs(
            ["bad"],
            lambda _index, _text: (_ for _ in ()).throw(
                RuntimeError("provider unavailable")
            ),
            phase="meter",
            max_workers=1,
            error_policy="raise",
        )


@pytest.mark.parametrize(
    ("max_workers", "error_policy", "message"),
    [
        (0, "raise", "max_workers"),
        (1, "ignore", "error_policy"),
    ],
)
def test_invalid_execution_configuration_is_rejected(
    max_workers,
    error_policy,
    message,
):
    with pytest.raises(ValueError, match=message):
        map_inputs(
            ["case"],
            lambda _index, text: text,
            phase="meter",
            max_workers=max_workers,
            error_policy=error_policy,
        )
