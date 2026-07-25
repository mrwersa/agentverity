"""Tests for versioned run reports that omit raw probe text."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

import pytest

from agentverity import Relation, from_callable, run
from agentverity.reporting import (
    JUNIT_SUITE_NAME,
    RUN_SCHEMA,
    json_value,
    run_result_to_dict,
    run_result_to_junit_xml,
    write_junit_xml,
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
    assert report["status"] == result.status
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


def test_junit_report_maps_blindness_and_vacuous_relations_without_raw_inputs():
    secret_input = "customer-card-token-123"
    no_op = Relation(
        name="deliberate-no-op",
        rtype="invariant",
        transform=lambda text: text,
        check=lambda source, followup: source.verdict == followup.verdict,
    )
    result = run(
        from_callable(lambda _text: {"verdict": "allow"}),
        [secret_input, "ordinary request"],
        relations=[no_op],
        config=RunConfig(k=4, epsilon=0.9),
    )

    payload = run_result_to_junit_xml(result)
    root = ET.fromstring(payload)
    assert root.attrib == {
        "name": JUNIT_SUITE_NAME,
        "tests": "5",
        "failures": "2",
        "errors": "0",
        "skipped": "1",
        # Emitted so report collectors show a duration instead of "NaNms".
        "time": f"{result.duration_seconds:.3f}",
    }
    assert root.find("./testcase[@name='preflight.probe_coverage']/failure") is not None
    assert root.find("./testcase[@name='preflight.relation_coverage']/failure") is not None
    assert root.find("./testcase[@name='relation.deliberate-no-op']/skipped") is not None
    assert secret_input not in payload


def test_junit_report_treats_stochasticity_as_guidance_not_failure():
    import itertools

    counter = itertools.count()
    result = run(
        from_callable(
            lambda _text: {"verdict": "allow" if next(counter) % 2 else "block"}
        ),
        ["a", "b", "c", "d"],
        relations=[],
        config=RunConfig(k=20, epsilon=0.05, run_blindness=False),
    )

    root = ET.fromstring(run_result_to_junit_xml(result))
    assert result.is_stochastic
    assert root.attrib["failures"] == "0"
    assert root.attrib["errors"] == "0"


def test_write_junit_xml_round_trips(tmp_path):
    result = run(
        from_callable(lambda text: {"verdict": text}),
        ["a", "b"],
        relations=[],
        config=RunConfig(k=2, epsilon=0.9),
    )
    path = tmp_path / "report.xml"
    write_junit_xml(result, path, suite_name="checkout-agent")
    root = ET.parse(path).getroot()
    assert root.attrib["name"] == "checkout-agent"
    assert {
        case.attrib["classname"] for case in root.findall("./testcase")
    } == {"checkout-agent"}


def test_junit_suite_carries_a_duration():
    """Report collectors compute NaN from a missing time attribute."""
    result = run(
        from_callable(lambda text: {"verdict": "A" if text.startswith("a") else "B"}),
        ["alpha", "bravo", "charlie", "apricot"],
        relations=[],
    )
    root = ET.fromstring(run_result_to_junit_xml(result))
    assert "time" in root.attrib
    assert float(root.attrib["time"]) >= 0.0


def test_relation_coverage_is_absent_when_no_relations_were_requested():
    """A check the caller opted out of should not appear as skipped noise."""
    result = run(
        from_callable(lambda text: {"verdict": "A" if text.startswith("a") else "B"}),
        ["alpha", "bravo", "charlie", "apricot"],
        relations=[],
    )
    root = ET.fromstring(run_result_to_junit_xml(result))
    assert root.find("./testcase[@name='preflight.relation_coverage']") is None
    assert root.attrib["skipped"] == "0"
