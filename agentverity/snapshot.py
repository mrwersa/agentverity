"""Evidence-gated frozen baselines.

A snapshot may be created only when the exact observation layer is
deterministic at the configured epsilon, the probe set is not blind, every
call completed, and a human explicitly approves the reference outputs.
Stability is a precondition for snapshot testing. It is not correctness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from agentverity.reporting import json_value
from agentverity.runner import RunResult

SNAPSHOT_SCHEMA = "agentverity.snapshot/v1"


class SnapshotRefused(ValueError):
    """The available evidence does not support creating or checking a snapshot."""


class SnapshotCompatibilityError(ValueError):
    """The current probe or configuration is incompatible with the snapshot."""


@dataclass(frozen=True)
class SnapshotProbe:
    """One fingerprinted input and its approved reference observation."""

    input_fingerprint: str
    expected: Any


@dataclass(frozen=True)
class Snapshot:
    """A versioned, approved baseline plus the evidence that admitted it."""

    schema: str
    created_at: str
    agentverity_version: str
    layer: str
    epsilon: float
    k: int
    blindness_threshold: float
    meter_pair_trials: int
    meter_ci_high: float
    blindness_skew: float
    blindness_distinct: int
    probes: tuple[SnapshotProbe, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible snapshot representation."""
        return {
            "schema": self.schema,
            "created_at": self.created_at,
            "agentverity_version": self.agentverity_version,
            "config": {
                "layer": self.layer,
                "epsilon": self.epsilon,
                "k": self.k,
                "blindness_threshold": self.blindness_threshold,
            },
            "admission_evidence": {
                "meter_call": "verdict-deterministic",
                "meter_pair_trials": self.meter_pair_trials,
                "meter_ci_high": self.meter_ci_high,
                "blindness_skew": self.blindness_skew,
                "blindness_distinct": self.blindness_distinct,
                "reference_approved": True,
            },
            "probes": [
                {
                    "input_fingerprint": probe.input_fingerprint,
                    "expected": probe.expected,
                }
                for probe in self.probes
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Snapshot:
        """Parse and validate a snapshot dictionary."""
        if value.get("schema") != SNAPSHOT_SCHEMA:
            raise SnapshotCompatibilityError(
                f"unsupported snapshot schema: {value.get('schema')!r}"
            )
        config = value.get("config")
        evidence = value.get("admission_evidence")
        probes = value.get("probes")
        if not isinstance(config, dict) or not isinstance(evidence, dict):
            raise SnapshotCompatibilityError("snapshot config or evidence is missing")
        if not isinstance(probes, list) or not probes:
            raise SnapshotCompatibilityError("snapshot probes must be a non-empty list")
        if evidence.get("reference_approved") is not True:
            raise SnapshotCompatibilityError("snapshot reference is not approved")
        if evidence.get("meter_call") != "verdict-deterministic":
            raise SnapshotCompatibilityError(
                "snapshot was not admitted by deterministic-at-epsilon evidence"
            )
        try:
            parsed_probes = tuple(
                SnapshotProbe(
                    input_fingerprint=str(probe["input_fingerprint"]),
                    expected=json_value(probe["expected"]),
                )
                for probe in probes
            )
            return cls(
                schema=SNAPSHOT_SCHEMA,
                created_at=str(value["created_at"]),
                agentverity_version=str(value["agentverity_version"]),
                layer=str(config["layer"]),
                epsilon=float(config["epsilon"]),
                k=int(config["k"]),
                blindness_threshold=float(config["blindness_threshold"]),
                meter_pair_trials=int(evidence["meter_pair_trials"]),
                meter_ci_high=float(evidence["meter_ci_high"]),
                blindness_skew=float(evidence["blindness_skew"]),
                blindness_distinct=int(evidence["blindness_distinct"]),
                probes=parsed_probes,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SnapshotCompatibilityError(
                f"invalid snapshot structure: {exc}"
            ) from exc


@dataclass(frozen=True)
class SnapshotChange:
    """One approved output that changed."""

    input_fingerprint: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class SnapshotDiff:
    """Comparison of current observations against an approved snapshot."""

    changes: tuple[SnapshotChange, ...]
    checked: int

    @property
    def clean(self) -> bool:
        """Whether every current observation matches its reference."""
        return not self.changes


def _package_version() -> str:
    try:
        return version("agentverity")
    except PackageNotFoundError:
        return "0+unknown"


def _require_snapshot_evidence(result: RunResult) -> None:
    """Reject incomplete, underpowered, stochastic, or blind evidence."""
    if not result.complete:
        raise SnapshotRefused("run is incomplete; failed calls cannot enter a baseline")
    if result.meter is None:
        raise SnapshotRefused("the verdict-stochasticity meter must be enabled")
    if result.meter.call != "verdict-deterministic":
        raise SnapshotRefused(
            "observation layer is not deterministic at the configured epsilon: "
            f"{result.meter.call}"
        )
    if result.meter.inputs != result.requested_inputs:
        raise SnapshotRefused("meter did not cover every requested input")
    if result.blindness is None:
        raise SnapshotRefused("the constant-gate-blindness detector must be enabled")
    if result.blindness.inputs != result.requested_inputs:
        raise SnapshotRefused("blindness scan did not cover every requested input")
    if result.blindness.blind:
        raise SnapshotRefused("probe set is blind; add inputs that cross a decision boundary")
    if len(result.observed_keys) != result.requested_inputs:
        raise SnapshotRefused("source observations are incomplete")
    if any(value is None for value in result.observed_keys):
        raise SnapshotRefused("source observations are incomplete")


def create_snapshot(result: RunResult, *, approved: bool) -> Snapshot:
    """Create a snapshot only from sufficient evidence and explicit approval."""
    _require_snapshot_evidence(result)
    if not approved:
        raise SnapshotRefused(
            "reference outputs require explicit approval; stability is not correctness"
        )
    assert result.meter is not None
    assert result.blindness is not None
    probes = tuple(
        SnapshotProbe(fingerprint, json_value(observed))
        for fingerprint, observed in zip(
            result.input_fingerprints,
            result.observed_keys,
            strict=True,
        )
    )
    return Snapshot(
        schema=SNAPSHOT_SCHEMA,
        created_at=datetime.now(timezone.utc).isoformat(),
        agentverity_version=_package_version(),
        layer=result.config.layer,
        epsilon=result.config.epsilon,
        k=result.config.k,
        blindness_threshold=result.config.blindness_threshold,
        meter_pair_trials=result.meter.pair_trials,
        meter_ci_high=result.meter.ci_high,
        blindness_skew=result.blindness.skew,
        blindness_distinct=result.blindness.distinct,
        probes=probes,
    )


def compare_snapshot(snapshot: Snapshot, result: RunResult) -> SnapshotDiff:
    """Compare a current, independently admitted run to an approved snapshot."""
    _require_snapshot_evidence(result)
    expected_config = (
        snapshot.layer,
        snapshot.epsilon,
        snapshot.k,
        snapshot.blindness_threshold,
    )
    actual_config = (
        result.config.layer,
        result.config.epsilon,
        result.config.k,
        result.config.blindness_threshold,
    )
    if actual_config != expected_config:
        raise SnapshotCompatibilityError(
            "current run configuration does not match the snapshot"
        )

    expected = {
        probe.input_fingerprint: probe.expected
        for probe in snapshot.probes
    }
    actual = {
        fingerprint: json_value(observed)
        for fingerprint, observed in zip(
            result.input_fingerprints,
            result.observed_keys,
            strict=True,
        )
    }
    if actual.keys() != expected.keys():
        raise SnapshotCompatibilityError(
            "current probe fingerprints do not match the snapshot"
        )

    changes = tuple(
        SnapshotChange(fingerprint, expected[fingerprint], actual[fingerprint])
        for fingerprint in expected
        if actual[fingerprint] != expected[fingerprint]
    )
    return SnapshotDiff(changes=changes, checked=len(expected))


def save_snapshot(snapshot: Snapshot, path: str | Path) -> None:
    """Write a snapshot as formatted UTF-8 JSON."""
    Path(path).write_text(
        json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_snapshot(path: str | Path) -> Snapshot:
    """Load a versioned snapshot from disk."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotCompatibilityError(f"cannot load snapshot: {exc}") from exc
    if not isinstance(value, dict):
        raise SnapshotCompatibilityError("snapshot root must be a JSON object")
    return Snapshot.from_dict(value)
