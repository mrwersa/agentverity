"""Runner — orchestrates meter, relations, and blindness into a single run.

The runner is the main entry point for programmatic use. It follows the
measure-first discipline:

1. **Meter** — probe the agent's verdict-stochasticity.
2. **Blindness** — scan for verdict skew that can make a pass vacuous.
3. **Relations** — run the relation catalogue with both diagnostics in hand.

The report leads with the two diagnostics (meter + blindness) and then
presents per-relation results. This order is the framework's identity:
diagnostics first, vehicle second.

Example::

    from agentverity.runner import run, RunConfig
    from agentverity.adapters import from_callable

    agent = from_callable(my_agent_fn)
    result = run(agent, inputs=["hello", "world", "foo"])
    print(result.summary())
"""

from __future__ import annotations

import textwrap
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any, Literal

from agentverity.blindness import BlindnessResult
from agentverity.blindness import score as blindness_score
from agentverity.decision_contract import (
    DecisionCoverageResult,
    DecisionSuite,
    assess_decision_coverage,
)
from agentverity.execution import (
    ErrorPolicy,
    ProgressCallback,
    RunError,
    input_fingerprint,
    map_indexed_inputs,
    map_inputs,
)
from agentverity.isolation import isolation_of
from agentverity.meter import (
    PRECISION_LEVELS,
    MeterResult,
    pair_flipped,
    plan_repeats,
    resolve_epsilon,
    score_runs,
)
from agentverity.observation import Observation
from agentverity.relations import (
    Relation,
    builtin_relations,
)
from agentverity.sequential import UNDECIDED as UNDECIDED_CALL
from agentverity.sequential import plan_sequential
from agentverity.stratified import (
    RelationCoverage,
    RoutePlan,
    StratifiedStability,
    plan_route_repeats,
    render_plan,
    stratify_relations,
    stratify_runs,
)

AgentFn = Callable[[str], Observation]
RunStatus = Literal[
    "incomplete",
    "contract",
    "blind",
    "vacuous",
    "target-failed",
    "undecided",
    "violations",
    "stochastic",
    "deterministic",
    "unmeasured",
]


def _reject_duplicates(inputs: list[str]) -> None:
    """Refuse a probe set containing the same input twice.

    Duplicates corrupt the skew scan whether or not calls are reused: the
    repeated input's verdict is counted once per copy, so the probe set
    reports its own composition rather than the agent's behaviour. Repeating
    a *measurement* is what ``k`` is for. Repeating an *input* is a
    defect in the probe set.

    Raises:
        ValueError: naming the duplicated inputs.
    """
    seen: set[str] = set()
    duplicated: list[str] = []
    for x in inputs:
        if x in seen and x not in duplicated:
            duplicated.append(x)
        seen.add(x)
    if duplicated:
        shown = ", ".join(repr(d) for d in duplicated[:3])
        more = f" and {len(duplicated) - 3} more" if len(duplicated) > 3 else ""
        raise ValueError(
            f"inputs must be distinct, found duplicates: {shown}{more}. "
            "Duplicate probes inflate the blindness skew by counting one "
            "verdict several times. Use k to repeat a measurement."
        )


@dataclass(frozen=True)
class RunConfig:
    """Configuration for a runner pass.

    Two knobs cover most use: ``budget``, how many agent calls the meter may
    spend, and ``precision``, how tight a flip rate you care about. ``epsilon``
    is an exact threshold override. ``k`` is an exact uniform repeat count for
    ordinary runs and a per-input floor when route targets are declared.

    Attributes:
        budget: Optional cap on meter calls. ``None`` (default) spends what
            the chosen precision needs, so a default run reaches a decision
            instead of reporting "undecided". Ignored when ``k`` is given.
        precision: ``"cheap"`` (10%), ``"balanced"`` (5%, the default), or
            ``"strict"`` (1%). Ignored when ``epsilon`` is given.
        k: Minimum repeated calls per input. ``None`` (default) sizes it from
            the budget. It is the exact uniform count unless a decision
            contract declares route-specific stability targets. In that case
            the route plan records any larger counts used.
        epsilon: Flip-rate threshold. ``None`` (default) takes it from
            ``precision``. After a run, ``result.config.epsilon`` holds the
            value used.
        blindness_threshold: Skew share above which the gate is blind (default 0.9).
        layer: Which Observation layer to measure and assert on (default "verdict").
        run_meter: If True, run the verdict-stochasticity meter (default True).
        run_blindness: If True, run the constant-gate-blindness detector (default True).
        reuse_unchanged_calls: If True (default), the first observation the meter
            draws for each unchanged input is reused by the blindness scan and as
            the source side of every relation, instead of calling the agent again
            for the same string. Set to False to give each phase its own
            independent draw, at roughly double the agent calls.
        sequential: If True, collect in rounds and stop at the first declared
            checkpoint that decides. `budget` still caps the calls, and a
            budget too small to reach a decision gives `undecided` here exactly
            as it does on the fixed-sample path. Off by default: the
            fixed-sample path is simpler and a caller who wants the simplest
            thing should keep getting it. See DESIGN.md ADR 7 for what the
            checkpoints buy and cost.
        max_workers: Maximum number of distinct inputs to process concurrently.
            Repeated calls for one input remain sequential. Defaults to one
            because stateful agents may not be thread-safe.
        error_policy: ``"raise"`` stops on the first failed call or check.
            ``"record"`` retains failures and marks the run incomplete.
    """

    budget: int | None = None
    precision: str = "balanced"
    k: int | None = None
    epsilon: float | None = None
    blindness_threshold: float = 0.9
    layer: str = "verdict"
    run_meter: bool = True
    run_blindness: bool = True
    reuse_unchanged_calls: bool = True
    sequential: bool = False
    max_workers: int = 1
    error_policy: ErrorPolicy = "raise"

    def __post_init__(self) -> None:
        """Validate configuration before any agent call is made."""
        if self.run_meter and self.k is not None and self.k < 2:
            raise ValueError("k must be >= 2 when the meter is enabled")
        if self.epsilon is not None and not 0 < self.epsilon < 1:
            raise ValueError("epsilon must be between 0 and 1")
        if self.epsilon is None and self.precision not in PRECISION_LEVELS:
            known = ", ".join(sorted(PRECISION_LEVELS))
            raise ValueError(
                f"unknown precision {self.precision!r}; expected one of {known}"
            )
        if self.k is None and self.budget is not None and self.budget < 1:
            raise ValueError("budget must be at least 1")
        if self.run_blindness and not 0 < self.blindness_threshold <= 1:
            raise ValueError("blindness_threshold must be between 0 and 1")
        if (self.run_meter or self.run_blindness) and self.layer not in {
            "verdict",
            "text",
            "tools",
        }:
            raise ValueError(f"unknown observation layer: {self.layer!r}")
        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if self.error_policy not in {"raise", "record"}:
            raise ValueError("error_policy must be 'raise' or 'record'")


@dataclass(frozen=True)
class RelationResult:
    """The result of running one relation across all inputs.

    Attributes:
        relation: The relation that was run.
        total: Number of inputs the relation was offered.
        held: Number of exercised pairs where the relation held.
        violated: Number of exercised pairs where the relation was violated.
        skipped: Number of inputs where the transform returned the input
            unchanged, so no metamorphic pair existed to test.
        errors: Number of inputs where transformation, execution, or checking
            failed. Errors never count as held relations.
    """

    relation: Relation
    total: int
    held: int
    violated: int
    skipped: int = 0
    errors: int = 0

    @property
    def exercised(self) -> int:
        """Number of inputs that produced a genuine source/follow-up pair."""
        return self.held + self.violated

    @property
    def violation_rate(self) -> float | None:
        """The fraction of *exercised* pairs that violated the relation.

        Inputs the transform left unchanged are excluded, because a
        byte-identical follow-up tests rerun stability rather than the
        relation. Measuring rerun stability is the meter's job.

        Returns ``None`` when nothing was exercised. A relation that never ran
        has no rate, and returning ``0.0`` would hand a programmatic caller the
        same false green the text report refuses to print.
        """
        if not self.exercised:
            return None
        return self.violated / self.exercised

    @property
    def is_vacuous(self) -> bool:
        """``True`` if the transform was the identity on every input.

        A relation like ``normalisation-invariance`` is a no-op on plain ASCII
        with ordinary spacing. It then reports a perfect pass without ever
        having sent the agent a different string.
        """
        return self.total > 0 and self.exercised == 0 and self.errors == 0


@dataclass(frozen=True)
class RunResult:
    """The complete outcome of a runner pass.

    Attributes:
        meter: The verdict-stochasticity meter result, or None if not run.
        blindness: The constant-gate-blindness result, or None if not run.
        route_stability: Per-route stability split from the same observations
            the pooled meter used, or None when no suite was declared or the
            meter was disabled. Costs no extra calls.
        decision_coverage: Declared decision-contract result, or None when the
            caller supplied ordinary unlabelled inputs.
        relation_coverage: Per-route relation exercise, or None when no suite
            or no relations were supplied.
        relation_results: Per-relation results, in the order they were run.
        config: The RunConfig used.
        errors: Failures retained under the ``"record"`` error policy.
        caveats: Evidence limitations that do not invalidate the arithmetic
            but must travel with its interpretation.
        input_fingerprints: SHA-256 identifiers for the ordered probe set.
        observed_keys: One source-layer value per input, when available.
        intended_decisions: One reviewed intended decision per input for a
            declared suite, otherwise an empty tuple.
        requested_inputs: Number of distinct inputs requested.
        isolation: How repeated trials were separated. `unknown` unless the
            evidence states it, because the library cannot observe it. See
            DESIGN.md ADR 5 for what each level admits.
    """

    meter: MeterResult | None
    blindness: BlindnessResult | None
    relation_results: list[RelationResult]
    config: RunConfig
    decision_coverage: DecisionCoverageResult | None = None
    route_stability: StratifiedStability | None = None
    route_plans: tuple[RoutePlan, ...] = ()
    relation_coverage: RelationCoverage | None = None
    errors: tuple[RunError, ...] = ()
    caveats: tuple[str, ...] = ()
    input_fingerprints: tuple[str, ...] = ()
    observed_keys: tuple[Any | None, ...] = ()
    intended_decisions: tuple[str, ...] = ()
    requested_inputs: int = 0
    duration_seconds: float = 0.0
    isolation: str = "unknown"

    @property
    def complete(self) -> bool:
        """Whether every requested piece of evidence completed successfully."""
        return not self.errors

    @property
    def is_stochastic(self) -> bool:
        """True if pooled or per-route evidence proves stochasticity."""
        pooled = self.meter is not None and self.meter.call == "verdict-stochastic"
        stratified = (
            self.route_stability is not None
            and bool(self.route_stability.stochastic)
        )
        return pooled or stratified

    @property
    def is_blind(self) -> bool:
        """True if the blindness detector determined the gate is near-constant."""
        return self.blindness is not None and self.blindness.blind

    @property
    def targeted_undecided(self) -> tuple[str, ...]:
        """Declared stability targets that the run did not settle."""
        if self.decision_coverage is None or self.route_stability is None:
            return ()
        targets = self.decision_coverage.contract.stability_targets
        return tuple(
            route.decision
            for route in self.route_stability.routes
            if route.decision in targets and not route.decided
        )

    @property
    def targeted_stochastic(self) -> tuple[str, ...]:
        """Declared stability targets the observed route exceeded."""
        if self.decision_coverage is None or self.route_stability is None:
            return ()
        targets = self.decision_coverage.contract.stability_targets
        return tuple(
            route.decision
            for route in self.route_stability.routes
            if route.decision in targets
            and route.call == "verdict-stochastic"
        )

    @property
    def status(self) -> RunStatus:
        """Canonical machine interpretation of the run.

        Reporters and integrations should consume this property instead of
        reconstructing precedence from the component results.
        """
        if not self.complete:
            return "incomplete"
        if (
            self.decision_coverage is not None
            and not self.decision_coverage.satisfied
        ):
            return "contract"
        if self.is_blind:
            return "blind"
        if self.relation_results and not self.suite_is_meaningful:
            return "vacuous"
        if self.targeted_stochastic:
            return "target-failed"
        if (
            self.route_stability is not None
            and self.route_stability.stochastic
        ):
            return "stochastic"
        if self.targeted_undecided:
            return "undecided"
        if self.meter is not None and self.meter.call.startswith("undecided"):
            return "undecided"
        if any(relation.violated for relation in self.relation_results):
            return "violations"
        if self.is_stochastic:
            return "stochastic"
        if self.meter is not None:
            return "deterministic"
        return "unmeasured"

    @property
    def vacuous_relations(self) -> list[RelationResult]:
        """Relations whose transform was the identity on every input.

        These report a perfect pass without ever sending the agent a different
        string, so their green rows are not evidence of anything.
        """
        return [rr for rr in self.relation_results if rr.is_vacuous]

    @property
    def suite_is_meaningful(self) -> bool:
        """True if relation results are not vacuous.

        The meter determines how relation results should be interpreted, not
        whether they can express a useful requirement. A stable verdict may
        make frozen-baseline diffing more sensitive, while an undecided meter
        calls for more evidence.

        Two things make green relation results vacuous: a blindness warning,
        and a relation catalogue where no transform actually changed any input.

        Running with ``relations=[]`` returns ``True``. That is deliberate. The
        property asks whether a green relation result can be trusted, and a run
        that deliberately requested no relations produced none to distrust.
        Returning ``False`` there would fail a legitimate diagnostics-only run,
        where the caller wants the meter and the skew scan and nothing else.
        The vacuous case this guards against is different: relations that were
        asked for, ran, and turned out to test nothing.
        """
        if self.is_blind:
            return False
        nothing_exercised = self.relation_results and not any(
            rr.exercised for rr in self.relation_results
        )
        return not nothing_exercised

    @property
    def headline(self) -> str:
        """One plain sentence answering "can I trust these test results?".

        The detail below it matters, but a reader should not have to assemble
        the verdict from four numbered sections to learn whether their suite
        means anything.
        """
        if not self.complete:
            failed = len(self.errors)
            return (
                f"INCOMPLETE - {failed} call{'s' if failed != 1 else ''} failed, "
                "so this run is not evidence of anything."
            )
        if (
            self.decision_coverage is not None
            and not self.decision_coverage.satisfied
        ):
            return (
                "NOT TRUSTWORTHY - the declared decision contract is "
                f"incomplete: {self.decision_coverage.advice}."
            )
        if self.is_blind and self.blindness is not None:
            return (
                "NOT TRUSTWORTHY - the agent answered "
                f"{self.blindness.majority_verdict!r} on "
                f"{self.blindness.skew:.0%} of the probes, so a pass says more "
                "about the probe set than about the agent."
            )
        vacuous = self.vacuous_relations
        if vacuous and not any(rr.exercised for rr in self.relation_results):
            return (
                "NOT TRUSTWORTHY - no relation changed a single input, so "
                "nothing was actually tested."
            )
        if self.meter is None:
            return "NO VERDICT MEASURED - the meter was disabled for this run."
        if self.targeted_stochastic:
            routes = ", ".join(self.targeted_stochastic)
            return (
                "NOT READY - decision changes exceed declared stability "
                f"targets for: {routes}."
            )
        if self.route_stability is not None and self.route_stability.stochastic:
            routes = ", ".join(self.route_stability.stochastic)
            if self.meter.call == "verdict-deterministic":
                return (
                    "TRUSTWORTHY WITH CARE - pooled evidence hides decision "
                    f"changes above tolerance on these routes: {routes}."
                )
            return (
                "TRUSTWORTHY WITH CARE - decision changes above tolerance "
                f"are concentrated on these routes: {routes}."
            )
        if self.targeted_undecided:
            routes = ", ".join(self.targeted_undecided)
            return (
                "NO ANSWER YET - declared stability targets remain undecided "
                f"for: {routes}."
            )
        if self.meter.call == "verdict-stochastic":
            return (
                "TRUSTWORTHY WITH CARE - the verdict changed on "
                f"{self.meter.flip_rate:.0%} of identical reruns, so read "
                "relation rates against that noise, not against zero."
            )
        if self.meter.call == "verdict-deterministic":
            if (
                self.route_stability is not None
                and self.route_stability.undecided
            ):
                routes = ", ".join(self.route_stability.undecided)
                contract = ""
                if self.decision_coverage is not None:
                    required = len(
                        self.decision_coverage.contract.required or ()
                    )
                    contract = (
                        f" and all {required} required decisions were "
                        "represented and observed"
                    )
                return (
                    "TRUSTWORTHY AT POOLED LEVEL - the verdict held across "
                    f"the combined reruns{contract}, but route-level evidence "
                    f"remains undecided for: {routes}."
                )
            trailer = (
                f" {len(vacuous)} relation{'s' if len(vacuous) != 1 else ''} "
                "tested nothing and are marked n/a."
                if vacuous
                else ""
            )
            if self.decision_coverage is not None:
                required = len(self.decision_coverage.contract.required or ())
                return (
                    "TRUSTWORTHY - the verdict held across every identical "
                    f"rerun and all {required} required decisions were "
                    f"represented and observed.{trailer}"
                )
            return (
                "TRUSTWORTHY - the verdict held across every identical rerun "
                f"and the probes cross a decision boundary.{trailer}"
            )
        return (
            "NO ANSWER YET - "
            f"{self.meter.pair_trials} pairs cannot settle a "
            f"{self.meter.epsilon:.0%} flip rate. Raise the budget, add inputs, "
            "or choose a lower precision."
        )

    def summary(self) -> str:
        """Return a human-readable summary of the run.

        The summary leads with the diagnostics (meter + blindness) and then
        lists per-relation results. This order is the framework's identity.
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("agentverity — suite-quality report")
        lines.append("=" * 60)
        lines.append("")
        lines.extend(
            textwrap.wrap(self.headline, width=58, initial_indent="  ",
                          subsequent_indent="  ")
        )
        lines.append("")

        if self.errors:
            lines.append("INCOMPLETE EVIDENCE")
            lines.append(
                f"   {len(self.errors)} call or check failure"
                f"{'s' if len(self.errors) != 1 else ''} recorded."
            )
            lines.append("   Failed work is never converted into a passing verdict.")
            for error in self.errors[:5]:
                relation = f", relation={error.relation}" if error.relation else ""
                lines.append(
                    f"   input #{error.input_index}, phase={error.phase}{relation}: "
                    f"{error.exception_type}: {error.message}"
                )
            if len(self.errors) > 5:
                lines.append(f"   ... and {len(self.errors) - 5} more.")
            lines.append("")

        if self.caveats:
            lines.append("EVIDENCE CAVEATS")
            for caveat in self.caveats:
                lines.extend(
                    textwrap.wrap(
                        caveat,
                        width=55,
                        initial_indent="   - ",
                        subsequent_indent="     ",
                    )
                )
            lines.append("")

        if self.meter is not None:
            m = self.meter
            lines.append("1. VERDICT-STOCHASTICITY METER")
            lines.append(f"   call:        {m.call}")
            lines.append(f"   flip rate:   {m.flip_rate:.1%} ({m.pair_flips}/{m.pair_trials} pairs)")
            lines.append(f"   Wilson CI:   [{m.ci_low:.3f}, {m.ci_high:.3f}] at epsilon={m.epsilon}")
            if m.sequential_call is not None:
                # Said plainly, because the interval above is computed over
                # every pair collected while the decision read only the first
                # n. Leaving the reader to assume the interval decided is the
                # optional stopping this design avoids, believed rather than
                # done.
                lines.append(
                    f"   decided by:  a declared checkpoint at "
                    f"{m.sequential_pairs} pairs, not the interval above"
                )
            repeats = (
                str(m.repeats)
                if m.max_repeats in {None, m.repeats}
                else f"{m.repeats}-{m.max_repeats} by route"
            )
            lines.append(
                f"   inputs:      {m.inputs}, repeats: {repeats}, layer: {m.layer}"
            )
            lines.append(f"   advice:      {m.advice}")
            lines.append("")

        if self.blindness is not None:
            b = self.blindness
            lines.append("2. CONSTANT-GATE-BLINDNESS DETECTOR")
            lines.append(f"   call:        {'BLIND' if b.blind else 'ok'}")
            lines.append(f"   skew:        {b.skew:.1%} ({b.majority_verdict!r} on {b.inputs} inputs)")
            lines.append(f"   distinct:    {b.distinct} verdict{'s' if b.distinct != 1 else ''}")
            if b.blind:
                lines.append(f"   warning:     {b.warning}")
            lines.append("")

        next_section = 3
        if self.decision_coverage is not None:
            coverage = self.decision_coverage
            lines.append("3. DECLARED DECISION CONTRACT")
            lines.append(
                f"   call:        {'SATISFIED' if coverage.satisfied else 'INCOMPLETE'}"
            )
            lines.append(
                f"   intended:    {coverage.intended_coverage:.0%} of required decisions"
            )
            lines.append(
                f"   observed:    {coverage.observed_coverage:.0%} of required "
                "decisions, counted over cases that reached them on any repeat"
            )
            if coverage.missing_intended:
                lines.append(
                    "   missing cases: "
                    + ", ".join(coverage.missing_intended)
                )
            if coverage.missing_observed:
                lines.append(
                    "   not observed:  "
                    + ", ".join(coverage.missing_observed)
                )
            if coverage.unknown_observed:
                lines.append(
                    "   unknown:       "
                    + ", ".join(coverage.unknown_observed)
                )
            if coverage.under_cased:
                lines.append(
                    "   under-cased:   "
                    + ", ".join(
                        f"{decision} {have}/{want}"
                        for decision, have, want in coverage.under_cased
                    )
                )
            if coverage.missing_critical:
                lines.append(
                    "   critical:      "
                    + ", ".join(coverage.missing_critical)
                )
            lines.append(f"   advice:      {coverage.advice}")
            lines.append("")
            next_section = 4

        if self.route_plans:
            lines.append(f"{next_section}. CALLS BY ROUTE")
            lines.append(
                "   declared targets size repeat counts before execution"
            )
            lines.append(render_plan(self.route_plans))
            lines.append("")
            next_section += 1

        if self.relation_coverage is not None and self.relation_coverage.routes:
            probing = self.relation_coverage
            lines.append(f"{next_section}. RELATION PROBING BY ROUTE")
            lines.append(
                "   a transform that returns the input unchanged tests nothing"
            )
            lines.append(
                f"   {'route':<18}{'cases':>6}{'probed':>8}{'no-op':>7}"
                f"{'violated':>10}  result"
            )
            for route in probing.routes:
                rate = (
                    "  -" if route.violation_rate is None
                    else f"{route.violation_rate:.0%}"
                )
                verdict = "exercised" if route.probed else "NOT EXERCISED"
                lines.append(
                    f"   {route.decision:<18}{route.cases:>6}{route.exercised:>8}"
                    f"{route.skipped:>7}{rate:>10}  {verdict}"
                )
            lines.append(f"   advice:      {probing.advice}")
            lines.append("")
            next_section += 1

        if self.route_stability is not None and self.route_stability.routes:
            stability = self.route_stability
            lines.append(f"{next_section}. STABILITY BY ROUTE")
            lines.append(
                "   split from the same calls, so this costs nothing extra"
            )
            lines.append(
                f"   {'route':<18}{'cases':>6}{'pairs':>7}{'flips':>7}"
                f"  {'95% CI':<18}result"
            )
            for route in stability.routes:
                interval = f"[{route.ci_low:.3f}, {route.ci_high:.3f}]"
                verdict = (
                    "undecided" if not route.decided
                    else route.call.replace("verdict-", "")
                )
                lines.append(
                    f"   {route.decision:<18}{route.cases:>6}{route.pair_trials:>7}"
                    f"{route.pair_flips:>7}  {interval:<18}{verdict}"
                )
            if stability.flip_pairs:
                lines.append("   flip pairs:")
                for pair in stability.flip_pairs:
                    lines.append(f"     {pair.render()}  x{pair.count}")
            lines.append(f"   advice:      {stability.advice}")
            # Each interval is its own 95% statement. Six of them together are
            # not a 95% statement about the suite, and a reader who assumes
            # otherwise would over-trust a clean table.
            lines.append(
                "   note:        each interval is a separate 95% statement, "
                "not a joint one"
            )
            lines.append("")
            next_section += 1

        lines.append(f"{next_section}. WHAT TO DO NEXT")
        if (
            self.decision_coverage is not None
            and not self.decision_coverage.satisfied
        ):
            lines.append(
                "   CONTRACT — repair the declared suite or out-of-contract "
                "agent decision before saving a baseline."
            )
        elif self.targeted_stochastic:
            lines.append(
                "   TARGET — declared tolerances were exceeded for: "
                + ", ".join(self.targeted_stochastic)
                + ". Repair or change the policy before release."
            )
        elif self.route_stability is not None and self.route_stability.stochastic:
            lines.append(
                "   ROUTE — these routes move more than epsilon: "
                + ", ".join(self.route_stability.stochastic)
                + ". Repair them before reading any relation result."
            )
        elif self.targeted_undecided:
            lines.append(
                "   TARGET — declared tolerances remain undecided for: "
                + ", ".join(self.targeted_undecided)
                + ". Do not freeze a baseline yet."
            )
        elif self.relation_coverage is not None and self.relation_coverage.unprobed:
            lines.append(
                "   NOT PROBED — every relation left these routes unchanged, so "
                "their green relation results prove nothing: "
                + ", ".join(self.relation_coverage.unprobed)
                + ". Add a relation that perturbs them."
            )
        elif self.is_blind:
            lines.append("   BLIND — green relation results may be vacuous.")
        elif self.meter is not None and self.meter.call == "verdict-deterministic":
            lines.append("   STABLE — prefer frozen-baseline diffing when a reference is available.")
        elif self.meter is not None and self.meter.call.startswith("undecided"):
            lines.append(
                "   UNDECIDED — raise k or input count before choosing a test strategy."
            )
        else:
            lines.append("   STOCHASTIC — interpret relation rates against unchanged-input noise.")
        lines.append("")

        if self.relation_results:
            lines.append(f"{next_section + 1}. RELATION RESULTS")
            lines.append(
                f"   {'relation':<28} {'type':<11} {'held':>5} {'violated':>8} "
                f"{'skipped':>7} {'errors':>6} {'rate':>7}"
            )
            lines.append(
                f"   {'-' * 28} {'-' * 11} {'-' * 5} {'-' * 8} "
                f"{'-' * 7} {'-' * 6} {'-' * 7}"
            )
            for rr in self.relation_results:
                rate = (
                    "n/a"
                    if rr.violation_rate is None
                    else f"{rr.violation_rate:.1%}"
                )
                lines.append(
                    f"   {rr.relation.name:<28} {rr.relation.rtype:<11} "
                    f"{rr.held:>5} {rr.violated:>8} {rr.skipped:>7} "
                    f"{rr.errors:>6} {rate:>7}"
                )
            vacuous = self.vacuous_relations
            if vacuous:
                lines.append("")
                names = ", ".join(rr.relation.name for rr in vacuous)
                lines.extend(
                    textwrap.wrap(
                        f"NOT EXERCISED: {names}. The transform returned every "
                        "input unchanged, so the agent was never asked a "
                        "different question. Rows marked n/a are not evidence "
                        "of anything. Add inputs the transform actually changes.",
                        width=72,
                        initial_indent="   ",
                        subsequent_indent="   ",
                    )
                )
            skipped_some = [
                rr for rr in self.relation_results if rr.skipped and not rr.is_vacuous
            ]
            if skipped_some:
                lines.append("")
                for rr in skipped_some:
                    lines.append(
                        f"   PARTIAL: {rr.relation.name} ran on "
                        f"{rr.exercised}/{rr.total} inputs "
                        f"({rr.skipped} left unchanged by the transform)."
                    )
            failed_some = [rr for rr in self.relation_results if rr.errors]
            if failed_some:
                lines.append("")
                for rr in failed_some:
                    lines.append(
                        f"   INCOMPLETE: {rr.relation.name} failed on "
                        f"{rr.errors}/{rr.total} inputs."
                    )
            lines.append("")

        return "\n".join(lines)


def _resolve(config: RunConfig, inputs: Iterable[str]) -> RunConfig:
    """Turn budget and precision into the concrete k and epsilon a run uses.

    Everything downstream, snapshots included, reads ``config.k`` and
    ``config.epsilon`` and needs real numbers. Resolving once here means the
    rest of the codebase never sees the ``None`` that means "work it out".
    """
    probes = list(inputs)
    if not probes:
        return config
    epsilon = resolve_epsilon(config.precision, config.epsilon)
    k = config.k if config.k is not None else plan_repeats(
        len(probes), epsilon, config.budget
    )
    return replace(config, k=k, epsilon=epsilon)


def _collect_sequentially(
    agent: AgentFn,
    inputs: list[str],
    config: RunConfig,
    on_progress: ProgressCallback | None,
) -> tuple[list[list[Observation]], list[RunError], str, int]:
    """Collect two repeats per input per round, stopping at the first decision.

    A round adds exactly one pair to every input, so pairs arrive in a defined
    order: input index within a round, rounds in the order they ran. Declared
    in advance and deterministic, which is what the checkpoints need. Under
    `max_workers > 1` it is not literal completion order, and it does not need
    to be: what matters is that the order cannot depend on the results.

    `config.budget` is honoured. It caps meter calls, and a cap is compatible
    with stopping early in a way a second *sizing* rule is not, which is why
    declared route targets are refused here and a budget is not. A round that
    would cross the cap is not started, so a caller who sizes a budget below
    what certification needs gets `undecided` from this path exactly as they
    would from the fixed-sample one.

    Args:
        agent: The agent under measurement.
        inputs: The probe set.
        config: The run configuration, already resolved.
        on_progress: Optional progress callback.

    Returns:
        The repeat series per input, any recorded errors, the call the plan
        took, and the pairs that call rests on.
    """
    plan = plan_sequential(config.epsilon)
    series: list[list[Observation]] = [[] for _ in inputs]
    outcomes: list[bool] = []
    errors: list[RunError] = []
    failed: set[int] = set()
    remaining = list(plan.checkpoints)
    spent = 0

    while remaining and len(failed) < len(inputs):
        live = [(index, text) for index, text in enumerate(inputs)
                if index not in failed]
        if config.budget is not None and spent + 2 * len(live) > config.budget:
            break
        spent += 2 * len(live)
        round_work = map_indexed_inputs(
            live,
            lambda index, text: [agent(text), agent(text)],
            phase="meter",
            max_workers=config.max_workers,
            error_policy=config.error_policy,
            on_progress=on_progress,
        )
        errors.extend(round_work.errors)
        for (index, _), pair in zip(live, round_work.values, strict=True):
            if pair is None:
                failed.add(index)
                continue
            series[index].extend(pair)
            outcomes.append(pair_flipped(pair[0], pair[1], config.layer))
        # A checkpoint is reached, not stepped past: the decision reads exactly
        # the first n pairs, so extra pairs from this round wait for the next
        # one rather than moving the boundary.
        while remaining and len(outcomes) >= remaining[0]:
            checkpoint = remaining.pop(0)
            call = plan.call_at(checkpoint, sum(outcomes[:checkpoint]))
            if call is not None:
                return series, errors, call, checkpoint

    return series, errors, UNDECIDED_CALL, len(outcomes)


def run(
    agent: AgentFn,
    inputs: Iterable[str] | None = None,
    *,
    suite: DecisionSuite | None = None,
    relations: list[Relation] | None = None,
    config: RunConfig | None = None,
    on_progress: ProgressCallback | None = None,
) -> RunResult:
    """Run the full measure-first diagnostic suite on an agent.

    The runner follows the measure-first discipline: meter and blindness first,
    then relations. The report leads with the diagnostics.

    Args:
        agent: An agent function ``run(input) -> Observation``.
        inputs: An iterable of input strings to test against. Mutually
            exclusive with ``suite``.
        suite: A declared decision contract and its reviewed cases. The
            contract applies to the ``verdict`` layer and is assessed without
            replacing per-case correctness evaluation.
        relations: Custom relation list. If None, uses :func:`builtin_relations`.
        config: Run configuration. If None, uses defaults.
        on_progress: Optional callback invoked after each input completes a
            meter, source-scan, or relation phase.

    Returns:
        A :class:`RunResult` with meter, blindness, and per-relation results.
    """
    started = time.perf_counter()
    # Read once, before anything wraps or replaces the callable, so the value
    # is the adapter's own statement rather than something a later layer lost.
    declared = isolation_of(agent)
    if (inputs is None) == (suite is None):
        raise ValueError("provide exactly one of inputs or suite")
    if suite is not None:
        inputs = list(suite.inputs)
        intended_decisions = suite.expected
    else:
        inputs = list(inputs or ())
        intended_decisions = ()
    if not inputs:
        raise ValueError("inputs must not be empty")
    _reject_duplicates(inputs)
    requested_config = config or RunConfig()
    config = _resolve(requested_config, inputs)
    if suite is not None and config.layer != "verdict":
        raise ValueError("decision contracts require the verdict observation layer")
    if relations is None:
        relations = builtin_relations()

    source_observations: list[Observation | None] = [None] * len(inputs)
    repeated_observations: list[Observation] = []
    # One group per input, position preserved. `complete_series` drops failed
    # entries and is right to, because the meter needs complete series. Reach
    # is per case, so a dropped entry there would shift every later case onto
    # the wrong contract row.
    case_series: list[tuple[Observation, ...]] = [() for _ in inputs]
    route_stability: StratifiedStability | None = None
    errors: list[RunError] = []

    # 1. Meter
    meter_result = None
    # Repeats are uniform unless the contract declares per-route targets. That
    # keeps the default path exactly as it was, and makes the extra spend an
    # explicit consequence of asking for a tighter bound on a named route.
    repeats_per_input = [config.k] * len(inputs)
    route_plans: tuple[RoutePlan, ...] = ()
    if (
        config.run_meter
        and suite is not None
        and suite.contract.stability_targets
    ):
        route_plans = plan_route_repeats(
            intended_decisions,
            epsilon=config.epsilon,
            targets=suite.contract.stability_targets,
            minimum_repeats=config.k,
        )
        planned = {plan.decision: plan.repeats_each for plan in route_plans}
        repeats_per_input = [
            planned.get(decision, config.k) for decision in intended_decisions
        ]
        planned_calls = sum(repeats_per_input)
        if (
            requested_config.k is None
            and requested_config.budget is not None
            and planned_calls > requested_config.budget
        ):
            raise ValueError(
                "declared route stability targets need at least "
                f"{planned_calls} meter calls in the zero-flip best case, "
                f"above budget={requested_config.budget}. Run "
                "'agentverity plan --suite ...' before execution, raise the "
                "budget, or choose deployment-relevant targets."
            )

    sequential_call: str | None = None
    sequential_pairs: int | None = None
    if config.run_meter and config.sequential:
        if suite is not None and suite.contract.stability_targets:
            raise ValueError(
                "sequential collection and declared route stability targets "
                "size the same run two different ways. Targets already fix the "
                "repeats each route needs, so choose one: drop sequential=True, "
                "or drop the targets and let the checkpoints decide."
            )
        series, meter_errors, sequential_call, sequential_pairs = (
            _collect_sequentially(agent, list(inputs), config, on_progress)
        )
        errors.extend(meter_errors)
        complete_series = [run_series for run_series in series if len(run_series) >= 2]
        for index, run_series in enumerate(series):
            if len(run_series) >= 2:
                case_series[index] = tuple(run_series)
        repeated_observations = [
            observation for run_series in complete_series for observation in run_series
        ]
        if complete_series:
            meter_result = replace(
                score_runs(
                    complete_series,
                    k=2,
                    layer=config.layer,
                    epsilon=config.epsilon,
                ),
                sequential_call=sequential_call,
                sequential_pairs=sequential_pairs,
            )
        if suite is not None:
            # Parity with the fixed path. A suite run that loses its route
            # table because collection stopped early has lost the analysis
            # most callers came for, and the series are right here.
            route_stability = stratify_runs(
                list(zip(intended_decisions, series, strict=True)),
                k=2,
                layer=config.layer,
                epsilon=config.epsilon,
                targets=suite.contract.stability_targets,
            )
        if config.reuse_unchanged_calls:
            for index, run_series in enumerate(series):
                if run_series:
                    source_observations[index] = run_series[0]
    elif config.run_meter:
        meter_work = map_inputs(
            inputs,
            lambda index, text: [agent(text) for _ in range(repeats_per_input[index])],
            phase="meter",
            max_workers=config.max_workers,
            error_policy=config.error_policy,
            on_progress=on_progress,
        )
        errors.extend(meter_work.errors)
        complete_series = [
            observations
            for observations in meter_work.values
            if observations is not None
        ]
        for index, observations in enumerate(meter_work.values):
            if observations is not None:
                case_series[index] = tuple(observations)
        repeated_observations = [
            observation
            for observations in complete_series
            for observation in observations
        ]
        if complete_series:
            meter_result = score_runs(
                complete_series,
                k=config.k,
                layer=config.layer,
                epsilon=config.epsilon,
            )
        if suite is not None:
            # Carry failed series too. They count as cases with no usable pairs,
            # rather than disappearing from the route table.
            route_stability = stratify_runs(
                list(zip(intended_decisions, meter_work.values, strict=True)),
                k=config.k,
                layer=config.layer,
                epsilon=config.epsilon,
                targets=suite.contract.stability_targets,
            )
        if config.reuse_unchanged_calls:
            for index, observations in enumerate(meter_work.values):
                if observations:
                    source_observations[index] = observations[0]

    # 2. Blindness
    blindness_result = None
    if config.run_blindness or suite is not None:
        if not config.reuse_unchanged_calls:
            source_observations = [None] * len(inputs)
        missing = [
            (index, text)
            for index, (text, observation) in enumerate(
                zip(inputs, source_observations, strict=True)
            )
            if observation is None
        ]
        if missing:
            source_work = map_indexed_inputs(
                missing,
                lambda _index, text: agent(text),
                phase="blindness" if config.run_blindness else "decision_contract",
                max_workers=config.max_workers,
                error_policy=config.error_policy,
                on_progress=on_progress,
            )
            errors.extend(source_work.errors)
            for (index, _text), observation in zip(
                missing, source_work.values, strict=True
            ):
                if observation is not None:
                    source_observations[index] = observation
        available = [
            observation
            for observation in source_observations
            if observation is not None
        ]
        if available and config.run_blindness:
            blindness_result = blindness_score(
                available,
                layer=config.layer,
                threshold=config.blindness_threshold,
            )

    # 3. Relations
    relation_coverage: RelationCoverage | None = None
    relation_results = [
        RelationResult(relation=relation, total=len(inputs), held=0, violated=0)
        for relation in relations
    ]
    if relations:
        def run_relations_for_input(
            input_index: int,
            text: str,
        ) -> tuple[list[str], list[RunError]]:
            outcomes: list[str] = []
            local_errors: list[RunError] = []
            for relation in relations:
                try:
                    followup_input = relation.transform(text)
                    if followup_input == text:
                        outcomes.append("skipped")
                        continue
                    source = (
                        source_observations[input_index]
                        if config.reuse_unchanged_calls
                        else None
                    )
                    if source is None:
                        source = agent(text)
                    followup = agent(followup_input)
                    outcomes.append(
                        "held" if relation.check(source, followup) else "violated"
                    )
                except Exception as exc:
                    if config.error_policy == "raise":
                        raise
                    outcomes.append("error")
                    local_errors.append(
                        RunError(
                            phase="relations",
                            input_index=input_index,
                            input_fingerprint=input_fingerprint(text),
                            exception_type=type(exc).__name__,
                            message=str(exc),
                            relation=relation.name,
                        )
                    )
            return outcomes, local_errors

        relation_work = map_inputs(
            inputs,
            run_relations_for_input,
            phase="relations",
            max_workers=config.max_workers,
            error_policy=config.error_policy,
            on_progress=on_progress,
            status_of=lambda value: "error" if value[1] else "ok",
        )
        errors.extend(relation_work.errors)
        counts = [
            {"held": 0, "violated": 0, "skipped": 0, "error": 0}
            for _relation in relations
        ]
        for value in relation_work.values:
            if value is None:
                continue
            outcomes, local_errors = value
            errors.extend(local_errors)
            for index, outcome in enumerate(outcomes):
                counts[index][outcome] += 1
        if suite is not None:
            relation_coverage = stratify_relations(
                intended_decisions,
                [
                    None if value is None else value[0]
                    for value in relation_work.values
                ],
            )
        relation_results = [
            RelationResult(
                relation=relation,
                total=len(inputs),
                held=counts[index]["held"],
                violated=counts[index]["violated"],
                skipped=counts[index]["skipped"],
                errors=counts[index]["error"],
            )
            for index, relation in enumerate(relations)
        ]

    observed_keys = tuple(
        observation.key(config.layer) if observation is not None else None
        for observation in source_observations
    )
    decision_coverage = (
        assess_decision_coverage(
            suite,
            observed_keys,
            all_observed=tuple(
                observation.key(config.layer)
                for observation in repeated_observations
            )
            + observed_keys,
            per_case=tuple(
                tuple(observation.key(config.layer) for observation in observations)
                if observations
                else ((key,) if key is not None else ())
                for observations, key in zip(case_series, observed_keys)
            ),
        )
        if suite is not None
        else None
    )

    return RunResult(
        meter=meter_result,
        blindness=blindness_result,
        relation_results=relation_results,
        config=config,
        decision_coverage=decision_coverage,
        route_stability=route_stability,
        route_plans=route_plans,
        relation_coverage=relation_coverage,
        errors=tuple(
            sorted(
                errors,
                key=lambda error: (
                    error.input_index,
                    error.phase,
                    error.relation or "",
                ),
            )
        ),
        input_fingerprints=tuple(input_fingerprint(text) for text in inputs),
        observed_keys=observed_keys,
        intended_decisions=intended_decisions,
        requested_inputs=len(inputs),
        duration_seconds=time.perf_counter() - started,
        isolation=declared,
    )
