"""Capture stable observable return semantics at AgentVerity's main boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import agentverity
from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceCase,
    EvidenceSet,
    Relation,
    RunConfig,
    assess_evidence,
    compare_evidence,
    compare_snapshot,
    create_snapshot,
    from_callable,
    plan_repeats,
    run,
    run_result_to_dict,
    run_result_to_junit_xml,
    run_result_to_otel_attributes,
)

AUDIT_SCHEMA = "agentverity.return-semantics-audit/v1"


def _type(value: Any) -> str:
    return type(value).__name__


def _suite() -> DecisionSuite:
    return DecisionSuite(
        contract=DecisionContract(allowed={"allow", "review"}),
        cases=(
            DecisionCase("alpha", "allow"),
            DecisionCase("alpha-two", "allow"),
            DecisionCase("beta", "review"),
        ),
    )


def _agent(text: str) -> dict[str, str]:
    return {
        "text": text.upper(),
        "verdict": "allow" if text.startswith("alpha") else "review",
    }


def _stable_result():
    return run(
        from_callable(_agent),
        suite=_suite(),
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )


def _status_contract() -> dict[str, dict[str, Any]]:
    stable = _stable_result()
    blind = run(
        from_callable(lambda _text: {"verdict": "allow"}),
        ["alpha", "beta"],
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )

    def failing(text: str) -> dict[str, str]:
        if text == "beta":
            raise RuntimeError("provider unavailable")
        return {"verdict": "allow"}

    incomplete = run(
        from_callable(failing),
        ["alpha", "beta"],
        relations=[],
        config=RunConfig(k=2, epsilon=0.9, error_policy="record"),
    )

    undecided = run(
        from_callable(_agent),
        ["alpha", "beta"],
        relations=[],
        config=RunConfig(k=2, epsilon=0.05),
    )
    stochastic_calls = 0

    def stochastic_agent(_text: str) -> dict[str, str]:
        nonlocal stochastic_calls
        stochastic_calls += 1
        return {"verdict": "allow" if stochastic_calls % 2 else "review"}

    stochastic = run(
        from_callable(stochastic_agent),
        ["alpha", "beta"],
        relations=[],
        config=RunConfig(k=20, epsilon=0.05, run_blindness=False),
    )
    curtailed_calls = 0

    def curtailed_agent(_text: str) -> dict[str, str]:
        nonlocal curtailed_calls
        curtailed_calls += 1
        return {"verdict": "allow" if curtailed_calls % 2 else "review"}

    curtailed = run(
        from_callable(curtailed_agent),
        ["alpha"],
        relations=[],
        config=RunConfig(
            k=146,
            epsilon=0.05,
            curtail=True,
            run_blindness=False,
        ),
    )
    contract = run(
        from_callable(lambda _text: {"verdict": "allow"}),
        suite=_suite(),
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )
    violated_relation = Relation(
        name="always-fails",
        rtype="invariant",
        transform=lambda text: text + "!",
        check=lambda _source, _followup: False,
    )
    violations = run(
        from_callable(_agent),
        ["alpha", "beta"],
        relations=[violated_relation],
        config=RunConfig(k=4, epsilon=0.5),
    )
    vacuous_relation = Relation(
        name="identity",
        rtype="invariant",
        transform=lambda text: text,
        check=lambda _source, _followup: True,
    )
    vacuous = run(
        from_callable(_agent),
        ["alpha", "beta"],
        relations=[vacuous_relation],
        config=RunConfig(k=4, epsilon=0.5),
    )
    unmeasured = run(
        from_callable(_agent),
        ["alpha", "beta"],
        relations=[],
        config=RunConfig(run_meter=False, run_blindness=False),
    )
    target_calls: dict[str, int] = {}

    def target_agent(text: str) -> dict[str, str]:
        target_calls[text] = target_calls.get(text, 0) + 1
        if text == "deny":
            return {"verdict": "deny" if target_calls[text] % 2 else "review"}
        return {"verdict": "approve"}

    target_suite = DecisionSuite(
        contract=DecisionContract(
            allowed={"approve", "review", "deny"},
            required={"approve", "deny"},
            stability_targets={"deny": 0.2},
        ),
        cases=(
            DecisionCase("approve", "approve"),
            DecisionCase("deny", "deny"),
        ),
    )
    target_failed = run(
        from_callable(target_agent),
        suite=target_suite,
        relations=[],
        config=RunConfig(k=2, epsilon=0.5),
    )
    entries = {
        "deterministic": stable,
        "blind": blind,
        "incomplete": incomplete,
        "undecided": undecided,
        "stochastic": stochastic,
        "curtailed": curtailed,
        "contract": contract,
        "violations": violations,
        "vacuous": vacuous,
        "unmeasured": unmeasured,
        "target-failed": target_failed,
    }
    return {
        name: {
            "type": _type(result),
            "status": result.status,
            "complete": result.complete,
            "is_stochastic": result.is_stochastic,
            "is_blind": result.is_blind,
            "error_count": len(result.errors),
        }
        for name, result in entries.items()
    }


def _run_contract() -> dict[str, Any]:
    result = _stable_result()
    assert result.meter is not None
    assert result.blindness is not None
    assert result.decision_coverage is not None
    return {
        "type": _type(result),
        "status": result.status,
        "complete": result.complete,
        "meter": {
            "type": _type(result.meter),
            "call": result.meter.call,
            "inputs": result.meter.inputs,
            "repeats": result.meter.repeats,
            "pair_trials": result.meter.pair_trials,
            "pair_flips": result.meter.pair_flips,
            "flip_rate": result.meter.flip_rate,
        },
        "blindness": {
            "type": _type(result.blindness),
            "blind": result.blindness.blind,
            "inputs": result.blindness.inputs,
            "distinct": result.blindness.distinct,
            "skew": result.blindness.skew,
        },
        "decision_coverage": {
            "type": _type(result.decision_coverage),
            "satisfied": result.decision_coverage.satisfied,
            "intended_coverage": result.decision_coverage.intended_coverage,
            "observed_coverage": result.decision_coverage.observed_coverage,
        },
        "collection_types": {
            "errors": _type(result.errors),
            "input_fingerprints": _type(result.input_fingerprints),
            "observed_keys": _type(result.observed_keys),
            "relation_results": _type(result.relation_results),
        },
    }


def _assessment_contract() -> dict[str, Any]:
    evidence = EvidenceSet(
        cases=(
            EvidenceCase("alpha", ("allow",) * 4, expected="allow"),
            EvidenceCase("alpha-two", ("allow",) * 4, expected="allow"),
            EvidenceCase("beta", ("review",) * 4, expected="review"),
        ),
        isolation="fresh-session",
    )
    result = assess_evidence(evidence, _suite(), epsilon=0.5)
    return {
        "type": _type(result),
        "status": result.status,
        "complete": result.complete,
        "isolation": result.isolation,
        "relation_results": list(result.relation_results),
        "requested_inputs": result.requested_inputs,
    }


def _drift_contract() -> dict[str, Any]:
    before = EvidenceSet(
        cases=(
            EvidenceCase("alpha", ("allow",) * 26, expected="allow"),
            EvidenceCase("beta", ("review",) * 26, expected="review"),
        ),
        isolation="fresh-session",
        provenance={"model": "v1"},
    )
    after = EvidenceSet(
        cases=(
            EvidenceCase(
                "alpha",
                tuple(["allow", "review"] * 9 + ["allow", "allow"] * 4),
                expected="allow",
            ),
            EvidenceCase("beta", ("review",) * 26, expected="review"),
        ),
        isolation="fresh-instance",
        provenance={"model": "v2"},
    )
    drift = compare_evidence(before, after, epsilon=0.05)
    return {
        "type": _type(drift),
        "drifted": drift.drifted,
        "changed_routes": list(drift.changed_routes),
        "isolation_changed": drift.isolation_changed,
        "gained_flip_pairs": list(drift.gained_flip_pairs),
        "provenance_changes": [list(change) for change in drift.provenance_changes],
        "route_types": [_type(route) for route in drift.routes],
        "serialized_keys": sorted(drift.to_dict()),
    }


def _snapshot_contract() -> dict[str, Any]:
    result = _stable_result()
    snapshot = create_snapshot(result, approved=True)
    clean = compare_snapshot(snapshot, result)

    def changed(text: str) -> dict[str, str]:
        value = _agent(text)
        if text == "alpha":
            value["verdict"] = "review"
        return value

    changed_result = run(
        from_callable(changed),
        suite=_suite(),
        relations=[],
        config=RunConfig(k=4, epsilon=0.5),
    )
    changed_diff = compare_snapshot(snapshot, changed_result)
    payload = snapshot.to_dict()
    return {
        "type": _type(snapshot),
        "schema": snapshot.schema,
        "probe_type": _type(snapshot.probes[0]),
        "probe_count": len(snapshot.probes),
        "stored_expected": [probe.expected for probe in snapshot.probes],
        "serialized_sections": sorted(payload),
        "clean_diff": {
            "type": _type(clean),
            "clean": clean.clean,
            "checked": clean.checked,
            "changes": len(clean.changes),
        },
        "changed_diff": {
            "type": _type(changed_diff),
            "clean": changed_diff.clean,
            "checked": changed_diff.checked,
            "changes": len(changed_diff.changes),
            "change_type": _type(changed_diff.changes[0]),
            "expected": changed_diff.changes[0].expected,
            "actual": changed_diff.changes[0].actual,
        },
    }


def _report_contract() -> dict[str, Any]:
    result = _stable_result()
    report = run_result_to_dict(result)
    junit = ET.fromstring(run_result_to_junit_xml(result))
    telemetry = run_result_to_otel_attributes(result)
    return {
        "json": {
            "type": _type(report),
            "schema": report["schema"],
            "status": report["status"],
            "complete": report["complete"],
            "top_level_keys": sorted(report),
        },
        "junit": {
            "type": _type(run_result_to_junit_xml(result)),
            "root": junit.tag,
            "tests": int(junit.attrib["tests"]),
            "failures": int(junit.attrib["failures"]),
            "errors": int(junit.attrib["errors"]),
            "skipped": int(junit.attrib["skipped"]),
        },
        "opentelemetry": {
            "type": _type(telemetry),
            "schema": telemetry["agentverity.schema"],
            "status": telemetry["agentverity.status"],
            "complete": telemetry["agentverity.complete"],
            "attribute_keys": sorted(telemetry),
        },
    }


def collect_return_semantics() -> dict[str, Any]:
    """Collect deterministic behavior without timestamps or package versions."""
    return {
        "schema": AUDIT_SCHEMA,
        "planning": {
            "return_type": _type(plan_repeats(2, 0.05)),
            "repeats": plan_repeats(2, 0.05),
        },
        "run": _run_contract(),
        "statuses": _status_contract(),
        "assessment": _assessment_contract(),
        "drift": _drift_contract(),
        "snapshot": _snapshot_contract(),
        "reports": _report_contract(),
    }


def main() -> None:
    """Write a fixture only from the explicitly named installed release."""
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    if agentverity.__version__ != args.expected_version:
        raise SystemExit(
            f"expected agentverity {args.expected_version}, imported "
            f"{agentverity.__version__}; run outside the repository with the "
            "named wheel installed"
        )
    payload = {
        "producer": f"agentverity=={args.expected_version}",
        "semantics": collect_return_semantics(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
