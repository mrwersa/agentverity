"""Versioned machine-readable reports for AgentVerity runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agentverity.runner import RunResult

RUN_SCHEMA = "agentverity.run/v1"


def json_value(value: Any) -> Any:
    """Convert an observation key to a lossless JSON value.

    AgentVerity refuses unsupported objects rather than hiding them behind a
    lossy string representation. Callers can expose a string or tuple from
    their adapter when a provider returns a richer proprietary object.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON observation mappings must have string keys")
        return {key: json_value(item) for key, item in value.items()}
    if hasattr(value, "value"):
        return json_value(value.value)
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

    return {
        "schema": RUN_SCHEMA,
        "complete": result.complete,
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
            "suite_is_meaningful": result.suite_is_meaningful,
        },
    }


def write_run_json(result: RunResult, path: str | Path) -> None:
    """Write a run report as formatted UTF-8 JSON."""
    Path(path).write_text(
        json.dumps(run_result_to_dict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
