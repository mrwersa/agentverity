"""Versioned machine-readable reports for AgentVerity runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from agentverity.runner import RunResult

from .decision import Decision, NoDecision, OutcomeNotScorable

RUN_SCHEMA = "agentverity.run/v2"
JUNIT_SUITE_NAME = "agentverity"


def json_value(value: Any, *, strict: bool = False) -> Any:
    """Convert an observation key to a lossless JSON value.

    AgentVerity refuses unsupported objects rather than hiding them behind a
    lossy string representation. Callers can expose a string or tuple from
    their adapter when a provider returns a richer proprietary object.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item, strict=strict) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON observation mappings must have string keys")
        return {key: json_value(item, strict=strict) for key, item in value.items()}
    # A typed outcome serialises tagged, so a reader can tell a decision whose
    # label happens to be "refused" from a run that refused. See DESIGN.md ADR 2.
    #
    # The run report is regenerated from the run, so a new shape there costs a
    # reader nothing. Stored formats are different: `strict` is set by callers
    # that persist under a schema version which does not yet describe the tag,
    # and they refuse rather than writing a shape the version does not promise.
    if isinstance(value, Decision):
        if strict:
            raise OutcomeNotScorable(
                f"a typed Decision({value.label!r}) cannot be persisted yet. "
                "The evidence and snapshot schemas do not carry the tag, so "
                "storing it would write a shape the schema version does not "
                "describe. Pass the label as a plain string until the tagged "
                "schema lands. See DESIGN.md ADR 2."
            )
        return {"kind": "decision", "label": value.label}
    if isinstance(value, NoDecision):
        if strict:
            raise OutcomeNotScorable(
                f"a NoDecision({value.reason!r}) cannot be persisted yet. The "
                "evidence and snapshot schemas do not carry the tag, so a "
                "stored reason would be indistinguishable from a label a "
                "caller invented. See DESIGN.md ADR 2."
            )
        return {"kind": "no_decision", "reason": value.reason}
    if hasattr(value, "value"):
        return json_value(value.value, strict=strict)
    raise TypeError(
        f"observation key of type {type(value).__name__!r} is not JSON-compatible"
    )


def run_result_to_dict(result: RunResult) -> dict[str, Any]:
    """Return a stable, versioned representation without raw probe inputs."""
    meter = None
    if result.meter is not None:
        meter = {
            "layer": result.meter.layer,
            "epsilon": result.meter.epsilon,
            "inputs": result.meter.inputs,
            "repeats": result.meter.repeats,
            "max_repeats": result.meter.max_repeats,
            "pair_trials": result.meter.pair_trials,
            "pair_flips": result.meter.pair_flips,
            "inputs_with_flip": result.meter.inputs_with_flip,
            "flip_rate": result.meter.flip_rate,
            "ci_low": result.meter.ci_low,
            "ci_high": result.meter.ci_high,
            "call": result.meter.call,
            "advice": result.meter.advice,
        }

    blindness = None
    if result.blindness is not None:
        blindness = {
            "inputs": result.blindness.inputs,
            "layer": result.blindness.layer,
            "majority_verdict": json_value(result.blindness.majority_verdict),
            "skew": result.blindness.skew,
            "distinct": result.blindness.distinct,
            "threshold": result.blindness.threshold,
            "blind": result.blindness.blind,
            "warning": result.blindness.warning,
        }

    decision_contract = None
    if result.decision_coverage is not None:
        coverage = result.decision_coverage
        decision_contract = {
            **coverage.contract.to_dict(),
            "intended_counts": {
                item.decision: item.count
                for item in coverage.intended_counts
            },
            # Two readings, and only two. `observed_counts` counts primary
            # results and keeps the name it shipped with. `observed_case_counts`
            # counts the distinct cases that reached a decision on any repeat,
            # and it is the one `observed_coverage` and `missing_observed` are
            # computed from. See DESIGN.md ADR 1.
            "observed_counts": {
                item.decision: item.count
                for item in coverage.observed_counts
            },
            "observed_case_counts": {
                item.decision: item.count
                for item in coverage.observed_case_counts
            },
            "intended_coverage": coverage.intended_coverage,
            "observed_coverage": coverage.observed_coverage,
            "missing_intended": list(coverage.missing_intended),
            "missing_observed": list(coverage.missing_observed),
            "missing_critical": list(coverage.missing_critical),
            "under_cased": [list(row) for row in coverage.under_cased],
            "unknown_observed": list(coverage.unknown_observed),
            "satisfied": coverage.satisfied,
            "advice": coverage.advice,
        }

    route_stability = (
        result.route_stability.to_dict()
        if result.route_stability is not None
        else None
    )
    relation_coverage = (
        result.relation_coverage.to_dict()
        if result.relation_coverage is not None
        else None
    )

    return {
        "schema": RUN_SCHEMA,
        "status": result.status,
        "complete": result.complete,
        "caveats": list(result.caveats),
        "requested_inputs": result.requested_inputs,
        "input_fingerprints": list(result.input_fingerprints),
        "config": {
            "k": result.config.k,
            "epsilon": result.config.epsilon,
            "blindness_threshold": result.config.blindness_threshold,
            "layer": result.config.layer,
            "run_meter": result.config.run_meter,
            "run_blindness": result.config.run_blindness,
            "reuse_unchanged_calls": result.config.reuse_unchanged_calls,
            "max_workers": result.config.max_workers,
            "error_policy": result.config.error_policy,
        },
        "meter": meter,
        "blindness": blindness,
        "decision_contract": decision_contract,
        "route_stability": route_stability,
        "relation_coverage": relation_coverage,
        "route_plans": [plan.to_dict() for plan in result.route_plans],
        "relations": [
            {
                "name": relation.relation.name,
                "type": relation.relation.rtype,
                "total": relation.total,
                "held": relation.held,
                "violated": relation.violated,
                "skipped": relation.skipped,
                "errors": relation.errors,
                "exercised": relation.exercised,
                "violation_rate": relation.violation_rate,
                "vacuous": relation.is_vacuous,
            }
            for relation in result.relation_results
        ],
        "errors": [
            {
                "phase": error.phase,
                "input_index": error.input_index,
                "input_fingerprint": error.input_fingerprint,
                "relation": error.relation,
                "exception_type": error.exception_type,
                "message": error.message,
            }
            for error in result.errors
        ],
        "guidance": {
            "is_stochastic": result.is_stochastic,
            "is_blind": result.is_blind,
            "stochastic_routes": (
                len(result.route_stability.stochastic)
                if result.route_stability is not None
                else None
            ),
            "undecided_routes": (
                len(result.route_stability.undecided)
                if result.route_stability is not None
                else None
            ),
            "targeted_undecided_routes": len(result.targeted_undecided),
            "targeted_stochastic_routes": len(result.targeted_stochastic),
            "decision_contract_satisfied": (
                result.decision_coverage.satisfied
                if result.decision_coverage is not None
                else None
            ),
            "suite_is_meaningful": result.suite_is_meaningful,
        },
    }


def write_run_json(result: RunResult, path: str | Path) -> None:
    """Write a run report as formatted UTF-8 JSON."""
    Path(path).write_text(
        json.dumps(run_result_to_dict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _junit_case(
    parent: ET.Element,
    name: str,
    *,
    classname: str,
) -> ET.Element:
    return ET.SubElement(
        parent,
        "testcase",
        {"classname": classname, "name": name},
    )


def run_result_to_junit_xml(
    result: RunResult,
    *,
    suite_name: str = JUNIT_SUITE_NAME,
) -> str:
    """Return a JUnit XML report for existing CI report collectors.

    The XML mirrors AgentVerity's own interpretation. Stochasticity is guidance,
    not a failed test. Blind probes and violated relations are failures,
    incomplete evidence is an error, and relations that never changed an input
    are skipped rather than passed.
    """
    root = ET.Element(
        "testsuite",
        {"name": suite_name, "time": f"{result.duration_seconds:.3f}"},
    )
    failures = 0
    errors = 0
    skipped = 0

    execution = _junit_case(root, "evidence.complete", classname=suite_name)
    if not result.complete:
        errors += 1
        detail = f"{len(result.errors)} call or check failures made the run incomplete"
        ET.SubElement(execution, "error", {"message": detail}).text = detail
    if result.caveats:
        ET.SubElement(execution, "system-out").text = "\n".join(result.caveats)

    meter_case = _junit_case(
        root,
        "preflight.verdict_stability",
        classname=suite_name,
    )
    if result.meter is None:
        skipped += 1
        ET.SubElement(meter_case, "skipped", {"message": "meter disabled"})
    elif result.meter.call.startswith("undecided"):
        errors += 1
        detail = result.headline
        ET.SubElement(meter_case, "error", {"message": detail}).text = detail
    else:
        ET.SubElement(meter_case, "system-out").text = (
            f"call={result.meter.call} "
            f"flip_rate={result.meter.flip_rate:.6f} "
            f"ci=[{result.meter.ci_low:.6f},{result.meter.ci_high:.6f}] "
            f"epsilon={result.meter.epsilon}"
        )

    blindness_case = _junit_case(
        root,
        "preflight.probe_coverage",
        classname=suite_name,
    )
    if result.blindness is None:
        skipped += 1
        ET.SubElement(blindness_case, "skipped", {"message": "scan disabled"})
    elif result.blindness.blind:
        failures += 1
        detail = result.headline
        ET.SubElement(blindness_case, "failure", {"message": detail}).text = detail
    else:
        ET.SubElement(blindness_case, "system-out").text = (
            f"skew={result.blindness.skew:.6f} "
            f"distinct={result.blindness.distinct} "
            f"threshold={result.blindness.threshold}"
        )

    if result.decision_coverage is not None:
        coverage = result.decision_coverage
        contract_case = _junit_case(
            root,
            "preflight.declared_decision_coverage",
            classname=suite_name,
        )
        detail = (
            f"intended={coverage.intended_coverage:.6f} "
            f"observed={coverage.observed_coverage:.6f} "
            f"missing_intended={len(coverage.missing_intended)} "
            f"missing_observed={len(coverage.missing_observed)} "
            f"unknown_observed={len(coverage.unknown_observed)} "
            f"under_cased={len(coverage.under_cased)}"
        )
        if not coverage.satisfied:
            failures += 1
            ET.SubElement(
                contract_case,
                "failure",
                {"message": coverage.advice},
            ).text = detail
        else:
            ET.SubElement(contract_case, "system-out").text = detail

    if result.route_stability is not None:
        stability = result.route_stability
        route_case = _junit_case(
            root,
            "preflight.route_stability",
            classname=suite_name,
        )
        detail = (
            f"routes={len(stability.routes)} "
            f"deterministic={len(stability.deterministic)} "
            f"stochastic={len(stability.stochastic)} "
            f"undecided={len(stability.undecided)} "
            f"flips={sum(route.pair_flips for route in stability.routes)}"
        )
        if result.targeted_stochastic:
            failures += 1
            message = (
                "declared route stability targets were exceeded for: "
                + ", ".join(result.targeted_stochastic)
            )
            ET.SubElement(route_case, "failure", {"message": message}).text = detail
        elif result.targeted_undecided:
            errors += 1
            message = (
                "declared route stability targets remain undecided for: "
                + ", ".join(result.targeted_undecided)
            )
            ET.SubElement(route_case, "error", {"message": message}).text = detail
        else:
            ET.SubElement(route_case, "system-out").text = detail

    # A caller who passed no relations did not ask for this check, so reporting
    # it as skipped is noise in every consuming dashboard. Say nothing instead.
    if not result.relation_results:
        relation_coverage = None
    else:
        relation_coverage = _junit_case(
            root,
            "preflight.relation_coverage",
            classname=suite_name,
        )
    if relation_coverage is None:
        pass
    elif not any(relation.exercised for relation in result.relation_results):
        failures += 1
        detail = "no relation changed an input, so the catalogue tested nothing"
        ET.SubElement(
            relation_coverage,
            "failure",
            {"message": detail},
        ).text = detail
    else:
        detail = (
            f"exercised={sum(r.exercised for r in result.relation_results)} "
            f"vacuous={sum(r.is_vacuous for r in result.relation_results)}"
        )
        if result.relation_coverage is not None:
            detail += (
                f" routes={len(result.relation_coverage.routes)}"
                f" unprobed_routes={len(result.relation_coverage.unprobed)}"
            )
        ET.SubElement(relation_coverage, "system-out").text = detail

    for relation in result.relation_results:
        case = _junit_case(
            root,
            f"relation.{relation.relation.name}",
            classname=suite_name,
        )
        if relation.errors:
            errors += 1
            detail = f"{relation.errors}/{relation.total} relation checks failed"
            ET.SubElement(case, "error", {"message": detail}).text = detail
        elif relation.is_vacuous:
            skipped += 1
            ET.SubElement(
                case,
                "skipped",
                {"message": "transform did not change any input"},
            )
        elif relation.violated:
            failures += 1
            detail = (
                f"{relation.violated}/{relation.exercised} exercised pairs violated "
                f"the {relation.relation.rtype} relation"
            )
            ET.SubElement(case, "failure", {"message": detail}).text = detail
        else:
            ET.SubElement(case, "system-out").text = (
                f"held={relation.held} exercised={relation.exercised} "
                f"skipped={relation.skipped}"
            )

    root.set("tests", str(len(root)))
    root.set("failures", str(failures))
    root.set("errors", str(errors))
    root.set("skipped", str(skipped))
    ET.indent(root, space="  ")
    payload = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + payload + "\n"


def write_junit_xml(
    result: RunResult,
    path: str | Path,
    *,
    suite_name: str = JUNIT_SUITE_NAME,
) -> None:
    """Write a JUnit XML report without retaining raw probe text."""
    Path(path).write_text(
        run_result_to_junit_xml(result, suite_name=suite_name),
        encoding="utf-8",
    )
