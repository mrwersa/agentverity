"""Compare two evidence sets collected at different times.

A run tells you whether a decision is repeatable now. It cannot tell you
whether last month's answer was the same, and that is usually the question
after a model version changes, a prompt is edited, or a provider silently
reroutes traffic.

What this reports and what it deliberately does not:

- Route intervals, decision distributions, flip-pair structure, decisions that
  appeared or disappeared, and any provenance difference between the two files.
- It never claims agreement between two windows proves trials were independent
  within either one. Two correlated runs agree with each other very
  comfortably. Independence is a property of how each window was collected,
  recorded in ``isolation``, and no amount of comparison recovers it.

Drift here means the evidence moved. Whether that is a regression, an
improvement, or a relabelled taxonomy is a judgement this package does not make.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceSet
from .meter import classify_call, wilson_ci
from .stratified import StratifiedStability, stratify_runs

WIDER = "wider"
TIGHTER = "tighter"
UNCHANGED = "unchanged"
INCOMPARABLE = "incomparable"


@dataclass(frozen=True)
class RouteDrift:
    """How one route's evidence moved between two windows."""

    decision: str
    before_flips: int
    before_trials: int
    after_flips: int
    after_trials: int
    before_call: str
    after_call: str
    epsilon: float

    @property
    def before_rate(self) -> float | None:
        return self.before_flips / self.before_trials if self.before_trials else None

    @property
    def after_rate(self) -> float | None:
        return self.after_flips / self.after_trials if self.after_trials else None

    @property
    def verdict_changed(self) -> bool:
        """Whether the tri-state result moved, which is the reportable event.

        A rate that drifts from 2% to 3% inside the same conclusion is noise.
        A route that moves from deterministic to stochastic is a release event.
        """
        return self.before_call != self.after_call

    @property
    def direction(self) -> str:
        if self.before_trials == 0 or self.after_trials == 0:
            return INCOMPARABLE
        before = self.before_rate or 0.0
        after = self.after_rate or 0.0
        if before == after:
            return UNCHANGED
        return WIDER if after > before else TIGHTER

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "before": {
                "flips": self.before_flips,
                "trials": self.before_trials,
                "call": self.before_call,
            },
            "after": {
                "flips": self.after_flips,
                "trials": self.after_trials,
                "call": self.after_call,
            },
            "verdict_changed": self.verdict_changed,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class EvidenceDrift:
    """The difference between two independently collected evidence windows."""

    routes: tuple[RouteDrift, ...]
    gained_decisions: tuple[str, ...]
    lost_decisions: tuple[str, ...]
    gained_flip_pairs: tuple[str, ...]
    lost_flip_pairs: tuple[str, ...]
    provenance_changes: tuple[tuple[str, Any, Any], ...]
    isolation_before: str
    isolation_after: str

    @property
    def changed_routes(self) -> tuple[str, ...]:
        """Routes whose tri-state result moved."""
        return tuple(r.decision for r in self.routes if r.verdict_changed)

    @property
    def drifted(self) -> bool:
        return bool(
            self.changed_routes
            or self.gained_decisions
            or self.lost_decisions
            or self.provenance_changes
        )

    @property
    def independence_note(self) -> str:
        """The caveat that must travel with every comparison."""
        return (
            "agreement between two windows does not establish that trials were "
            "independent within either one. Two correlated runs agree "
            f"comfortably. Isolation was {self.isolation_before!r} then "
            f"{self.isolation_after!r}."
        )

    def render(self) -> str:
        lines = ["evidence drift"]
        if not self.routes:
            lines.append("  no routes in common")
        else:
            lines.append(
                f"  {'route':<18}{'before':>14}{'after':>14}  result"
            )
            for route in self.routes:
                before = f"{route.before_flips}/{route.before_trials}"
                after = f"{route.after_flips}/{route.after_trials}"
                if route.verdict_changed:
                    note = (
                        f"{route.before_call.replace('verdict-', '')} -> "
                        f"{route.after_call.replace('verdict-', '')}"
                    )
                else:
                    note = f"{route.direction}"
                lines.append(f"  {route.decision:<18}{before:>14}{after:>14}  {note}")

        for label, values in (
            ("decisions gained", self.gained_decisions),
            ("decisions lost", self.lost_decisions),
            ("flip pairs gained", self.gained_flip_pairs),
            ("flip pairs lost", self.lost_flip_pairs),
        ):
            if values:
                lines.append(f"  {label}: " + ", ".join(values))

        if self.provenance_changes:
            lines.append("  provenance:")
            for key, before, after in self.provenance_changes:
                lines.append(f"    {key}: {before!r} -> {after!r}")

        lines.append("")
        lines.append(
            f"verdict: {'DRIFTED' if self.drifted else 'NO CHANGE'}"
        )
        lines.append(f"note: {self.independence_note}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "drifted": self.drifted,
            "changed_routes": list(self.changed_routes),
            "routes": [route.to_dict() for route in self.routes],
            "gained_decisions": list(self.gained_decisions),
            "lost_decisions": list(self.lost_decisions),
            "gained_flip_pairs": list(self.gained_flip_pairs),
            "lost_flip_pairs": list(self.lost_flip_pairs),
            "provenance_changes": [
                {"key": key, "before": before, "after": after}
                for key, before, after in self.provenance_changes
            ],
            "isolation": {
                "before": self.isolation_before,
                "after": self.isolation_after,
            },
            "independence_note": self.independence_note,
        }


def _stability(evidence: EvidenceSet, epsilon: float) -> StratifiedStability | None:
    intended = [case.expected for case in evidence.cases]
    if any(value is None for value in intended):
        return None
    series = [case.to_observations(evidence.layer) for case in evidence.cases]
    return stratify_runs(
        list(zip([value or "" for value in intended], series, strict=True)),
        k=min(len(item) for item in series),
        layer=evidence.layer,
        epsilon=epsilon,
    )


def compare_evidence(
    before: EvidenceSet,
    after: EvidenceSet,
    *,
    epsilon: float = 0.05,
) -> EvidenceDrift:
    """Compare two evidence windows collected independently.

    Only routes present in both windows are compared. A route that appears or
    disappears is reported as gained or lost rather than compared against
    nothing, because a missing route is a different finding from a moving one.

    Raises:
        ValueError: If either window lacks the intended decisions needed to
            split evidence by route.
    """
    lhs = _stability(before, epsilon)
    rhs = _stability(after, epsilon)
    if lhs is None or rhs is None:
        raise ValueError(
            "both evidence sets need an intended decision on every case; "
            "without them there are no routes to compare"
        )

    lhs_routes = {route.decision: route for route in lhs.routes}
    rhs_routes = {route.decision: route for route in rhs.routes}
    shared = sorted(set(lhs_routes) & set(rhs_routes))

    routes = []
    for decision in shared:
        left, right = lhs_routes[decision], rhs_routes[decision]
        low_l, high_l = wilson_ci(left.pair_flips, left.pair_trials)
        low_r, high_r = wilson_ci(right.pair_flips, right.pair_trials)
        routes.append(
            RouteDrift(
                decision=decision,
                before_flips=left.pair_flips,
                before_trials=left.pair_trials,
                after_flips=right.pair_flips,
                after_trials=right.pair_trials,
                before_call=classify_call(low_l, high_l, epsilon),
                after_call=classify_call(low_r, high_r, epsilon),
                epsilon=epsilon,
            )
        )

    lhs_pairs = {pair.render() for pair in lhs.flip_pairs}
    rhs_pairs = {pair.render() for pair in rhs.flip_pairs}

    keys = set(before.provenance) | set(after.provenance)
    provenance_changes = tuple(
        (key, before.provenance.get(key), after.provenance.get(key))
        for key in sorted(keys)
        if before.provenance.get(key) != after.provenance.get(key)
    )

    return EvidenceDrift(
        routes=tuple(routes),
        gained_decisions=tuple(sorted(set(rhs_routes) - set(lhs_routes))),
        lost_decisions=tuple(sorted(set(lhs_routes) - set(rhs_routes))),
        gained_flip_pairs=tuple(sorted(rhs_pairs - lhs_pairs)),
        lost_flip_pairs=tuple(sorted(lhs_pairs - rhs_pairs)),
        provenance_changes=provenance_changes,
        isolation_before=before.isolation,
        isolation_after=after.isolation,
    )
