"""Tests for versioned run reports that omit raw probe text."""

from __future__ import annotations

import json
from enum import Enum
from xml.etree import ElementTree as ET

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    Relation,
    from_callable,
    run,
)
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


def test_json_report_includes_relation_coverage_by_route():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"allow", "block"}),
        cases=(
            DecisionCase("allow this", "allow"),
            DecisionCase("block this", "block"),
        ),
    )
    relation = Relation(
        name="punctuation-invariance",
        rtype="invariant",
        transform=lambda text: text + "!",
        check=lambda source, followup: source.verdict == followup.verdict,
    )
    result = run(
        from_callable(
            lambda text: {
                "verdict": "allow" if text.startswith("allow") else "block"
            }
        ),
        suite=suite,
        relations=[relation],
        config=RunConfig(k=2, epsilon=0.9),
    )

    coverage = run_result_to_dict(result)["relation_coverage"]
    assert coverage["probed"] == ["allow", "block"]
    assert coverage["unprobed"] == []


def test_json_value_refuses_lossy_fallback():
    with pytest.raises(TypeError, match="not JSON-compatible"):
        json_value(object())


def test_json_value_preserves_supported_nested_values():
    class Decision(Enum):
        ALLOW = "allow"

    assert json_value({
        "route": Decision.ALLOW,
        "tools": ("search", "answer"),
    }) == {
        "route": "allow",
        "tools": ["search", "answer"],
    }


def test_json_value_rejects_non_string_mapping_keys():
    with pytest.raises(TypeError, match="string keys"):
        json_value({1: "allow"})


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


def test_declared_contract_is_reported_without_raw_case_inputs():
    sensitive = "customer account 123 should be reviewed"
    suite = DecisionSuite(
        contract=DecisionContract(
            allowed={"allow", "review", "deny"},
            critical={"deny"},
        ),
        cases=(
            DecisionCase("ordinary request", "allow"),
            DecisionCase(sensitive, "review"),
            DecisionCase("known attack", "deny"),
        ),
    )
    result = run(
        from_callable(
            lambda text: {
                "verdict": (
                    "deny" if "attack" in text
                    else "review" if "123" in text
                    else "allow"
                )
            }
        ),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    report = run_result_to_dict(result)
    contract = report["decision_contract"]
    assert contract["satisfied"] is True
    assert contract["intended_coverage"] == 1.0
    assert contract["observed_coverage"] == 1.0
    assert contract["critical"] == ["deny"]
    assert sensitive not in json.dumps(report)

    root = ET.fromstring(run_result_to_junit_xml(result))
    case = root.find(
        "./testcase[@name='preflight.declared_decision_coverage']"
    )
    assert case is not None
    assert case.find("failure") is None


def test_junit_contract_failure_is_a_failed_release_check():
    suite = DecisionSuite(
        contract=DecisionContract(allowed={"allow", "review", "deny"}),
        cases=(
            DecisionCase("ordinary", "allow"),
            DecisionCase("attack", "deny"),
        ),
    )
    result = run(
        from_callable(
            lambda text: {"verdict": "deny" if text == "attack" else "allow"}
        ),
        suite=suite,
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    root = ET.fromstring(run_result_to_junit_xml(result))
    case = root.find(
        "./testcase[@name='preflight.declared_decision_coverage']/failure"
    )
    assert result.status == "contract"
    assert root.attrib["failures"] == "1"
    assert case is not None
    assert "add reviewed cases" in case.attrib["message"]


def test_the_contract_block_carries_two_readings_and_no_duplicate():
    """Three keys where two were identical is the ambiguity this change removes.

    `observed_counts` is primaries and keeps the name it shipped with.
    `observed_case_counts` is distinct cases reaching a decision on any repeat,
    and is what the coverage percentage and `missing_observed` come from.
    """
    from agentverity import (
        DecisionCase,
        DecisionContract,
        DecisionSuite,
        RunConfig,
        run,
    )
    from agentverity.observation import Observation
    from agentverity.reporting import run_result_to_dict

    suite = DecisionSuite(
        contract=DecisionContract(
            allowed=frozenset({"refund", "escalate"}),
            required=frozenset({"refund", "escalate"}),
        ),
        cases=(
            DecisionCase(input="a", expected="refund"),
            DecisionCase(input="b", expected="escalate"),
        ),
    )
    routes = {"a": "refund", "b": "escalate"}
    result = run(
        lambda text: Observation(
            text="ok", verdict=routes.get(text.strip().lower()[:1], "refund")
        ),
        suite=suite,
        config=RunConfig(run_meter=False),
    )
    contract = run_result_to_dict(result)["decision_contract"]

    assert "primary_observed_counts" not in contract, "no byte-identical duplicate"
    assert "observed_counts" in contract
    assert "observed_case_counts" in contract
    # and the two readings must not contradict the summary they feed
    required = set(contract["required"])
    counted = set(contract["observed_case_counts"])
    assert required - counted == set(contract["missing_observed"])
