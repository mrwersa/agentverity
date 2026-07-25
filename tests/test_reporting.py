"""Tests for versioned run reports that omit raw probe text."""

from __future__ import annotations

import json

import pytest

from agentverity import from_callable, run
from agentverity.reporting import (
    RUN_SCHEMA,
    json_value,
    run_result_to_dict,
    write_run_json,
)
from agentverity.runner import RunConfig


def test_run_report_is_versioned_and_does_not_retain_raw_inputs():
    secret_input = "customer-card-token-123"
    result = run(
        from_callable(
            lambda text: {
                "verdict": "block" if "token" in text else "allow",
                "text": text,
            }
        ),
        [secret_input, "ordinary request"],
        relations=[],
        config=RunConfig(k=2, epsilon=0.9),
    )
    report = run_result_to_dict(result)
    encoded = json.dumps(report)
    assert report["schema"] == RUN_SCHEMA
    assert secret_input not in encoded
    assert len(report["input_fingerprints"]) == 2


def test_recorded_error_makes_machine_report_incomplete():
    def failing(text: str) -> dict:
        if text == "bad":
            raise RuntimeError("down")
        return {"verdict": "allow" if text == "a" else "block"}

    result = run(
        from_callable(failing),
        ["a", "bad", "b"],
        relations=[],
        config=RunConfig(k=2, epsilon=0.9, error_policy="record"),
    )
    report = run_result_to_dict(result)
    assert report["complete"] is False
    assert report["errors"]
    assert report["errors"][0]["exception_type"] == "RuntimeError"


def test_write_run_json_round_trips(tmp_path):
    result = run(
        from_callable(lambda text: {"verdict": text}),
        ["a", "b"],
        relations=[],
        config=RunConfig(k=2, epsilon=0.9),
    )
    path = tmp_path / "report.json"
    write_run_json(result, path)
    assert json.loads(path.read_text())["schema"] == RUN_SCHEMA


def test_json_value_refuses_lossy_fallback():
    with pytest.raises(TypeError, match="not JSON-compatible"):
        json_value(object())
