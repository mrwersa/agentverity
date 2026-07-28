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

from collections.abc import Mapping, Sequence
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
        if self.pair_trials == 0:
            return "undecided (add repeats or inputs)"
        return classify_call(self.ci_low, self.ci_high, self.epsilon)

    @property
    def flip_rate(self) -> float:
        """Observed rate. An estimate, never the basis for the verdict."""
        return self.pair_flips / self.pair_trials if self.pair_trials else 0.0

    @property
    def decided(self) -> bool:
        return self.call != "undecided (add repeats or inputs)"

    @property
    def pairs_needed(self) -> int | None:
        """Pairs a quiet route needs before it can be called deterministic.

        Once a route has shown a flip, its future rate is unknown. Returning a
        clean-route budget there would understate the evidence it may need.
        """
        if self.pair_flips:
            return None
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
            "pairs_needed": self.pairs_needed,
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
            undecided = [route for route in self.routes if not route.decided]
            quiet_needed = {
                route.pairs_needed
                for route in undecided
                if route.pairs_needed is not None
            }
            advice = (
                "no route is proven unstable, but these lack the evidence to "
                "certify: " + ", ".join(self.undecided)
            )
            if quiet_needed:
                needed = max(quiet_needed)
                advice += (
                    f" (a route with no observed flips needs {needed} pairs "
                    f"total at epsilon={self.epsilon})"
                )
            if any(route.pair_flips for route in undecided):
                advice += (
                    "; routes already showing flips may need more evidence or "
                    "resolve as stochastic"
                )
            return advice
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
    series: Sequence[tuple[str, Sequence[Observation] | None]],
    *,
    k: int,
    layer: str = "verdict",
    epsilon: float = 0.01,
    targets: Mapping[str, float] | None = None,
) -> StratifiedStability:
    """Split already-collected repeat series by each case's intended decision.

    Args:
        series: One ``(intended decision, repeat series)`` pair per input. A
            missing series records a failed case with zero usable pairs. The
            intended decision comes from the reviewed suite, not from what the
            agent returned, so a route stays identifiable even when the agent
            answers it wrongly or fails.
        k: Repeats per input, matching the pooled meter.
        layer: Observation layer to compare.
        epsilon: Default flip-rate threshold.
        targets: Optional per-route thresholds. A route with a declared target
            is judged against it rather than against the run default, so a
            consequential decision can be held to a tighter bound.

    Pairs are disjoint and formed exactly as the pooled meter forms them, so
    the per-route trials sum to the pooled trials.
    """
    if k < 2:
        raise ValueError("k must be >= 2 to compare repeated runs")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    if not series:
        raise ValueError("series must not be empty")
    if layer not in {"verdict", "text", "tools"}:
        raise ValueError(f"unknown observation layer: {layer!r}")

    cases: dict[str, int] = {}
    trials: dict[str, int] = {}
    flips: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}

    for decision, observations in series:
        if not isinstance(decision, str) or not decision:
            raise ValueError("every intended decision must be a non-empty string")
        cases[decision] = cases.get(decision, 0) + 1
        trials.setdefault(decision, 0)
        flips.setdefault(decision, 0)
        if observations is None:
            continue
        observations = list(observations)
        length = len(observations)
        if length < 2:
            raise ValueError(
                "every repeat series must contain at least two observations, "
                f"got {length}"
            )
        keys = [observation.key(layer) for observation in observations]
        for index in range(0, length - 1, 2):
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
                epsilon=(targets or {}).get(decision, epsilon),
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


@dataclass(frozen=True)
class RoutePlan:
    """What one route needs, and what the current run would give it."""

    decision: str
    cases: int
    target: float
    pairs_needed: int
    repeats_each: int
    calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "cases": self.cases,
            "target": self.target,
            "pairs_needed": self.pairs_needed,
            "repeats_each": self.repeats_each,
            "calls": self.calls,
        }


def plan_route_repeats(
    intended: Sequence[str],
    *,
    epsilon: float,
    targets: Mapping[str, float] | None = None,
    minimum_repeats: int = 2,
) -> tuple[RoutePlan, ...]:
    """Plan the zero-flip evidence budget for each route.

    Uniform repeats spend the same evidence on every case. A route represented
    by one case therefore receives fewer pairs than a route represented by
    five. Sizing from each declared target fixes that allocation without
    inflating the whole suite to the tightest tolerance.

    Args:
        intended: The intended decision of every case, in suite order.
        epsilon: The run's default tolerance, used where no target is declared.
        targets: Optional per-route tolerances from the decision contract.
        minimum_repeats: Per-input floor imposed by the run configuration.

    Returns:
        One plan per route, ordered by decision. ``pairs_needed`` is the
        best-case requirement when no pair flips. ``repeats_each`` also
        respects ``minimum_repeats``.
    """
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    if not intended:
        raise ValueError("intended must not be empty")
    if minimum_repeats < 2:
        raise ValueError("minimum_repeats must be at least 2")

    targets = dict(targets or {})
    counts: dict[str, int] = {}
    for decision in intended:
        counts[decision] = counts.get(decision, 0) + 1
    unknown = sorted(set(targets) - set(counts))
    if unknown:
        raise ValueError(
            "stability targets have no intended cases: " + ", ".join(unknown)
        )
    for decision, target in targets.items():
        if not isinstance(target, (int, float)) or isinstance(target, bool):
            raise TypeError(f"stability target for {decision!r} must be a number")
        if not 0 < float(target) < 1:
            raise ValueError(
                f"stability target for {decision!r} must be between 0 and 1"
            )

    plans = []
    for decision in sorted(counts):
        cases = counts[decision]
        target = targets.get(decision, epsilon)
        needed = pairs_for_deterministic_call(target)
        # Ceiling division, then doubled: each case contributes floor(k/2)
        # pairs, so k must be even and cover its share of the route's need.
        per_case_pairs = -(-needed // cases)
        repeats = max(minimum_repeats, per_case_pairs * 2)
        plans.append(
            RoutePlan(
                decision=decision,
                cases=cases,
                target=target,
                pairs_needed=needed,
                repeats_each=repeats,
                calls=repeats * cases,
            )
        )
    return tuple(plans)


def render_plan(
    plans: Sequence[RoutePlan],
    *,
    compare_uniform: bool = False,
) -> str:
    """Render an actionable route budget without implying a guarantee."""
    header = (
        f"  {'route':<18}{'cases':>6}{'target':>9}{'pairs*':>7}"
        f"{'repeats':>9}{'calls':>8}"
    )
    lines = [header]
    for plan in plans:
        lines.append(
            f"  {plan.decision:<18}{plan.cases:>6}{plan.target:>9.3f}"
            f"{plan.pairs_needed:>7}{plan.repeats_each:>9}{plan.calls:>8}"
        )
    total = sum(plan.calls for plan in plans)
    lines.append(f"  {'total':<18}{'':>6}{'':>9}{'':>7}{'':>9}{total:>8}")
    lines.append("  * minimum pairs needed if no pair changes decision")
    if compare_uniform:
        uniform = max(plan.repeats_each for plan in plans) * sum(
            plan.cases for plan in plans
        )
        lines.append("")
        lines.append(
            f"  sized per route: {total} calls. "
            f"one uniform k for every route: {uniform} calls."
        )
        if uniform > total:
            lines.append(
                f"  sizing per route saves {uniform - total} calls by not "
                "buying a tight bound where nothing needs one."
            )
    return "\n".join(lines)


@dataclass(frozen=True)
class RouteRelationCoverage:
    """Whether one route's cases were genuinely perturbed by any relation.

    A relation whose transform hands the agent back its own input has not
    tested anything. It reports a pass because the follow-up is byte-identical
    to the source, which measures rerun stability rather than the relation.
    Counted per route, that becomes a specific and answerable question: was
    this decision ever actually probed, or only appeared to be?
    """

    decision: str
    cases: int
    exercised: int
    skipped: int
    held: int
    violated: int
    errors: int = 0

    @property
    def probed(self) -> bool:
        """Whether any relation produced a real source/follow-up pair here."""
        return self.exercised > 0

    @property
    def violation_rate(self) -> float | None:
        """Violations among genuinely exercised pairs, or None if none were.

        Returning 0.0 for an unprobed route would hand a caller the same false
        green the report refuses to print.
        """
        if not self.exercised:
            return None
        return self.violated / self.exercised

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "cases": self.cases,
            "exercised": self.exercised,
            "skipped": self.skipped,
            "held": self.held,
            "violated": self.violated,
            "errors": self.errors,
            "probed": self.probed,
            "violation_rate": self.violation_rate,
        }


@dataclass(frozen=True)
class RelationCoverage:
    """Which routes the relation suite actually perturbed."""

    routes: tuple[RouteRelationCoverage, ...]

    @property
    def unprobed(self) -> tuple[str, ...]:
        """Routes where every relation left the input unchanged."""
        return tuple(route.decision for route in self.routes if not route.probed)

    @property
    def probed(self) -> tuple[str, ...]:
        return tuple(route.decision for route in self.routes if route.probed)

    @property
    def advice(self) -> str:
        if not self.routes:
            return "no relations were run"
        if self.unprobed:
            return (
                "every relation left these routes unchanged, so their relation "
                "results are vacuous: " + ", ".join(self.unprobed)
            )
        violating = [route.decision for route in self.routes if route.violated]
        if violating:
            return "relations were violated on: " + ", ".join(sorted(violating))
        return "every route was genuinely perturbed and held"

    def to_dict(self) -> dict[str, Any]:
        return {
            "routes": [route.to_dict() for route in self.routes],
            "unprobed": list(self.unprobed),
            "probed": list(self.probed),
        }


def stratify_relations(
    intended: Sequence[str],
    outcomes: Sequence[Sequence[str] | None],
) -> RelationCoverage:
    """Group per-input relation outcomes by each case's intended decision.

    Args:
        intended: The intended decision of every case, in suite order.
        outcomes: One list of outcomes per input, each entry being ``held``,
            ``violated``, ``skipped``, or ``error``, in relation order. A
            ``None`` entry marks an input whose relation phase failed outright.

    Returns:
        Probing coverage per route, ordered by decision.
    """
    if len(intended) != len(outcomes):
        raise ValueError("outcomes must align with intended decisions")

    tally: dict[str, dict[str, int]] = {}
    for decision, per_input in zip(intended, outcomes, strict=True):
        if not isinstance(decision, str) or not decision:
            raise ValueError("every intended decision must be a non-empty string")
        bucket = tally.setdefault(
            decision,
            {"cases": 0, "held": 0, "violated": 0, "skipped": 0, "error": 0},
        )
        bucket["cases"] += 1
        for outcome in per_input or ():
            if not isinstance(outcome, str) or outcome not in {
                "held",
                "violated",
                "skipped",
                "error",
            }:
                raise ValueError(f"unknown relation outcome: {outcome!r}")
            bucket[outcome] += 1

    routes = tuple(
        RouteRelationCoverage(
            decision=decision,
            cases=bucket["cases"],
            exercised=bucket["held"] + bucket["violated"],
            skipped=bucket["skipped"],
            held=bucket["held"],
            violated=bucket["violated"],
            errors=bucket["error"],
        )
        for decision, bucket in sorted(tally.items())
    )
    return RelationCoverage(routes=routes)
