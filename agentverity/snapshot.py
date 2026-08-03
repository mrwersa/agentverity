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

from agentverity.decision_contract import DecisionContract
from agentverity.meter import MeterResult, pairs_for_deterministic_call
from agentverity.reporting import json_value
from agentverity.runner import RunResult

from .decision import comparison_key

SNAPSHOT_SCHEMA = "agentverity.snapshot/v3"


class SnapshotRefused(ValueError):
    """The available evidence does not support creating or checking a snapshot."""


class SnapshotCompatibilityError(ValueError):
    """The current probe or configuration is incompatible with the snapshot."""


@dataclass(frozen=True)
class SnapshotProbe:
    """One fingerprinted input and its approved reference observation."""

    input_fingerprint: str
    expected: Any
    intended: str | None = None


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
    decision_contract: DecisionContract | None
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
            "decision_contract": (
                self.decision_contract.to_dict()
                if self.decision_contract is not None
                else None
            ),
            "probes": [
                {
                    "input_fingerprint": probe.input_fingerprint,
                    "expected": probe.expected,
                    "intended": probe.intended,
                }
                for probe in self.probes
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Snapshot:
        """Parse and validate a snapshot dictionary."""
        schema = value.get("schema")
        if schema != SNAPSHOT_SCHEMA:
            raise SnapshotCompatibilityError(
                f"unsupported snapshot schema: {schema!r}; this build reads "
                f"{SNAPSHOT_SCHEMA}"
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
            raw_contract = value.get("decision_contract")
            decision_contract = (
                DecisionContract.from_dict(raw_contract)
                if raw_contract is not None
                else None
            )
            parsed_probes = tuple(
                SnapshotProbe(
                    input_fingerprint=str(probe["input_fingerprint"]),
                    expected=json_value(probe["expected"]),
                    intended=(
                        str(probe["intended"])
                        if probe.get("intended") is not None
                        else None
                    ),
                )
                for probe in probes
            )
            if decision_contract is not None and any(
                probe.intended is None for probe in parsed_probes
            ):
                raise SnapshotCompatibilityError(
                    "contract snapshot probes require intended decisions"
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
                decision_contract=decision_contract,
                probes=parsed_probes,
            )
        except SnapshotCompatibilityError:
            raise
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


def _underpowered_message(meter: MeterResult) -> str:
    """Explain how far the evidence fell short, not just that it did.

    "undecided" on its own reads like a bug when the agent is plainly
    deterministic. The gap is often an order of magnitude, so quantify it, and
    quantify it against the flip rate actually observed. Assuming zero flips
    can advise a caller who already has 1,200 pairs to drop to 128.
    """
    if meter.call == "verdict-stochastic":
        return (
            f"the verdict is stochastic at epsilon={meter.epsilon}: "
            f"{meter.pair_flips} of {meter.pair_trials} disjoint pairs "
            "disagreed. A baseline cannot be frozen against a decision that "
            "changes on rerun. Fix the agent, or snapshot a layer that is stable."
        )

    rate = meter.flip_rate
    needed = pairs_for_deterministic_call(meter.epsilon, flip_rate=rate)
    seen = (
        f"{meter.pair_trials} disjoint pairs with {meter.pair_flips} flips"
        if meter.pair_flips
        else f"{meter.pair_trials} disjoint pairs and no flips"
    )

    if needed is None:
        cheaper = pairs_for_deterministic_call(meter.epsilon * 5, flip_rate=rate)
        route = (
            f"about {cheaper} pairs at epsilon={meter.epsilon * 5:g}"
            if cheaper is not None
            else f"an epsilon above the observed rate of {rate:.2%}"
        )
        return (
            f"cannot certify determinism at epsilon={meter.epsilon}: {seen}, "
            f"a rate of {rate:.2%}. More pairs will not help, because the "
            "interval converges onto the observed rate rather than below it. "
            f"Either accept a deployment-relevant epsilon ({route}) or treat "
            "this layer as non-deterministic."
        )

    per_input = -(-needed // meter.inputs)
    return (
        f"not enough evidence to certify determinism at epsilon={meter.epsilon}: "
        f"{seen}, and about {needed} pairs are needed at that rate. Options: "
        f"raise --k to at least {per_input * 2} across {meter.inputs} inputs "
        f"(about {meter.inputs * per_input * 2} agent calls), add inputs, or set "
        "a deployment-relevant --epsilon."
    )


def _require_snapshot_evidence(result: RunResult) -> None:
    """Reject incomplete, underpowered, stochastic, or blind evidence."""
    if not result.complete:
        raise SnapshotRefused("run is incomplete; failed calls cannot enter a baseline")
    if result.meter is None:
        raise SnapshotRefused("the verdict-stochasticity meter must be enabled")
    if result.route_stability is not None and result.route_stability.stochastic:
        raise SnapshotRefused(
            "route-level evidence is stochastic for: "
            + ", ".join(result.route_stability.stochastic)
        )
    if result.targeted_undecided:
        raise SnapshotRefused(
            "declared route stability targets remain undecided for: "
            + ", ".join(result.targeted_undecided)
        )
    if result.meter.call != "verdict-deterministic":
        raise SnapshotRefused(_underpowered_message(result.meter))
    if result.meter.inputs != result.requested_inputs:
        raise SnapshotRefused("meter did not cover every requested input")
    if (
        result.decision_coverage is not None
        and not result.decision_coverage.satisfied
    ):
        raise SnapshotRefused(
            "declared decision contract is incomplete: "
            + result.decision_coverage.advice
        )
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
    intended = (
        result.intended_decisions
        if result.decision_coverage is not None
        else (None,) * len(result.input_fingerprints)
    )
    probes = tuple(
        SnapshotProbe(fingerprint, json_value(observed, strict=True), intended_decision)
        for fingerprint, observed, intended_decision in zip(
            result.input_fingerprints,
            result.observed_keys,
            intended,
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
        decision_contract=(
            result.decision_coverage.contract
            if result.decision_coverage is not None
            else None
        ),
        probes=probes,
    )



def _comparable(stored: Any) -> Any:
    """One comparison key for a stored outcome, whichever shape it is in.

    A snapshot may hold ``"refund"`` from before an adapter adopted the typed
    outcomes and ``{"kind": "no_decision", ...}`` from after. Comparison has to
    treat a bare label and a ``Decision`` as one decision, and keep a reason
    distinct from a label of the same name.
    """
    if isinstance(stored, dict) and stored.get("kind") == "no_decision":
        return ("no_decision", stored.get("reason"))
    return comparison_key(stored)


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
    current_contract = (
        result.decision_coverage.contract
        if result.decision_coverage is not None
        else None
    )
    if current_contract != snapshot.decision_contract:
        raise SnapshotCompatibilityError(
            "current decision contract does not match the snapshot"
        )

    # Normalised on both sides, so a baseline written before an adapter
    # adopted the types still matches the runs it makes afterwards. Without it
    # adoption would fail every existing baseline, which is the
    # string-versus-typed defect one layer further out.
    expected = {
        probe.input_fingerprint: probe.expected
        for probe in snapshot.probes
    }
    actual = {
        fingerprint: json_value(observed, strict=True)
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
    snapshot_intended = {
        probe.input_fingerprint: probe.intended
        for probe in snapshot.probes
    }
    current_intended = {
        fingerprint: intended
        for fingerprint, intended in zip(
            result.input_fingerprints,
            (
                result.intended_decisions
                if result.decision_coverage is not None
                else (None,) * len(result.input_fingerprints)
            ),
            strict=True,
        )
    }
    if current_intended != snapshot_intended:
        raise SnapshotCompatibilityError(
            "current intended decisions do not match the snapshot"
        )

    # Compared through one canonical key, reported as stored. A baseline
    # written before an adapter adopted the typed outcomes still matches the
    # runs it makes afterwards, and the diff still shows what is in the file.
    changes = tuple(
        SnapshotChange(fingerprint, expected[fingerprint], actual[fingerprint])
        for fingerprint in expected
        if _comparable(actual[fingerprint]) != _comparable(expected[fingerprint])
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
