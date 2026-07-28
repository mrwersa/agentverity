"""Per-route stability, measured from the calls a run already made.

The pooled meter answers one question: across the whole probe set, how often
does the decision move? That number can be reassuring and wrong at the same
time. Five stable routes and one that flips constantly average out to an
interval somebody signs off.

This module splits the same observations by the decision each case was written
to exercise, so a route that misbehaves is named instead of averaged away. It
costs no extra calls. Every pair counted here was already counted by the
pooled meter.

Two things it deliberately does not do.

It does not claim every route is certified at once. Each interval is a separate
95% statement, and six of those together are not a 95% statement about the
whole suite. The report says how many routes carry evidence rather than
implying a family-wide guarantee.

It does not judge correctness. A flip pair records that the agent answered
``review`` once and ``deny`` once for the same input. Which answer was right is
a question for an evaluator or a reviewed assertion, so the output is a
flip-pair table and never a confusion matrix.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .meter import _hashable, classify_call, pairs_for_deterministic_call, wilson_ci
from .observation import Observation

# _hashable is shared with the pooled meter rather than reimplemented. If the
# two ever compared keys differently, per-route trials would silently stop
# reconciling with the pooled total, which is the one invariant this module
# promises.


def _label(value: Any) -> str:
    """Render an observation key for a flip-pair row."""
    return value if isinstance(value, str) else repr(_hashable(value))


@dataclass(frozen=True)
class RouteStability:
    """Stability evidence for the cases written to exercise one decision."""

    decision: str
    cases: int
    pair_trials: int
    pair_flips: int
    ci_low: float
    ci_high: float
    epsilon: float

    @property
    def call(self) -> str:
        """Tri-state result, from the confidence bound rather than the rate."""
        return classify_call(self.ci_low, self.ci_high, self.epsilon)

    @property
    def flip_rate(self) -> float:
        """Observed rate. An estimate, never the basis for the verdict."""
        return self.pair_flips / self.pair_trials if self.pair_trials else 0.0

    @property
    def decided(self) -> bool:
        return self.call != "undecided (add repeats or inputs)"

    @property
    def pairs_needed(self) -> int:
        """Pairs a clean route needs before it can be called deterministic."""
        return pairs_for_deterministic_call(self.epsilon)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "cases": self.cases,
            "pair_trials": self.pair_trials,
            "pair_flips": self.pair_flips,
            "flip_rate": self.flip_rate,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "call": self.call,
        }


@dataclass(frozen=True)
class FlipPair:
    """Two decisions the agent returned for one input, and how often."""

    decisions: tuple[str, str]
    count: int

    def render(self) -> str:
        left, right = self.decisions
        return f"{left} <-> {right}"

    def to_dict(self) -> dict[str, Any]:
        return {"decisions": list(self.decisions), "count": self.count}


@dataclass(frozen=True)
class StratifiedStability:
    """Per-route stability and the flip pairs behind it."""

    layer: str
    epsilon: float
    routes: tuple[RouteStability, ...]
    flip_pairs: tuple[FlipPair, ...]

    @property
    def stochastic(self) -> tuple[str, ...]:
        """Routes proven to move more than epsilon."""
        return tuple(
            route.decision for route in self.routes if route.call == "verdict-stochastic"
        )

    @property
    def undecided(self) -> tuple[str, ...]:
        """Routes without enough evidence to decide either way."""
        return tuple(route.decision for route in self.routes if not route.decided)

    @property
    def deterministic(self) -> tuple[str, ...]:
        """Routes proven to move less than epsilon."""
        return tuple(
            route.decision
            for route in self.routes
            if route.call == "verdict-deterministic"
        )

    @property
    def advice(self) -> str:
        """The next action, worst finding first.

        A stochastic route is a conclusion and needs repair. An undecided route
        is an absence of evidence and needs more of it. Reporting them the same
        way would hide the difference that matters.
        """
        if self.stochastic:
            return (
                "these routes move more than epsilon: " + ", ".join(self.stochastic)
            )
        if self.undecided:
            needed = max(
                (route.pairs_needed for route in self.routes if not route.decided),
                default=0,
            )
            return (
                "no route is proven unstable, but these lack the evidence to "
                "certify: " + ", ".join(self.undecided)
                + f" ({needed} pairs each at epsilon={self.epsilon})"
            )
        return "every route carries enough evidence and none moves more than epsilon"

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "epsilon": self.epsilon,
            "routes": [route.to_dict() for route in self.routes],
            "flip_pairs": [pair.to_dict() for pair in self.flip_pairs],
            "stochastic": list(self.stochastic),
            "undecided": list(self.undecided),
            "deterministic": list(self.deterministic),
        }


def stratify_runs(
    series: Sequence[tuple[str, Sequence[Observation]]],
    *,
    k: int,
    layer: str = "verdict",
    epsilon: float = 0.01,
) -> StratifiedStability:
    """Split already-collected repeat series by each case's intended decision.

    Args:
        series: One ``(intended decision, repeat series)`` pair per input. The
            intended decision comes from the reviewed suite, not from what the
            agent returned, so a route stays identifiable even when the agent
            answers it wrongly.
        k: Repeats per input, matching the pooled meter.
        layer: Observation layer to compare.
        epsilon: Flip-rate threshold.

    Pairs are disjoint and formed exactly as the pooled meter forms them, so
    the per-route trials sum to the pooled trials.
    """
    if k < 2:
        raise ValueError("k must be >= 2 to compare repeated runs")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")

    cases: dict[str, int] = {}
    trials: dict[str, int] = {}
    flips: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}

    for decision, observations in series:
        observations = list(observations)
        if len(observations) != k:
            raise ValueError(
                f"every repeat series must contain exactly k={k} observations"
            )
        cases[decision] = cases.get(decision, 0) + 1
        trials.setdefault(decision, 0)
        flips.setdefault(decision, 0)
        keys = [observation.key(layer) for observation in observations]
        for index in range(0, k - 1, 2):
            trials[decision] += 1
            left, right = keys[index], keys[index + 1]
            if _hashable(left) != _hashable(right):
                flips[decision] += 1
                # Unordered, so review-then-deny and deny-then-review are the
                # same finding rather than two.
                pair = tuple(sorted((_label(left), _label(right))))
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

    routes = []
    for decision in sorted(cases):
        low, high = wilson_ci(flips[decision], trials[decision])
        routes.append(
            RouteStability(
                decision=decision,
                cases=cases[decision],
                pair_trials=trials[decision],
                pair_flips=flips[decision],
                ci_low=low,
                ci_high=high,
                epsilon=epsilon,
            )
        )

    flip_pairs = tuple(
        FlipPair(decisions=pair, count=count)
        for pair, count in sorted(
            pair_counts.items(), key=lambda item: (-item[1], item[0])
        )
    )
    return StratifiedStability(
        layer=layer,
        epsilon=epsilon,
        routes=tuple(routes),
        flip_pairs=flip_pairs,
    )
