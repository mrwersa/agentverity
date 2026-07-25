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
from agentverity.execution import (
    ErrorPolicy,
    ProgressCallback,
    RunError,
    input_fingerprint,
    map_indexed_inputs,
    map_inputs,
)
from agentverity.meter import (
    PRECISION_LEVELS,
    MeterResult,
    plan_repeats,
    resolve_epsilon,
    score_runs,
)
from agentverity.observation import Observation
from agentverity.relations import (
    Relation,
    builtin_relations,
)

AgentFn = Callable[[str], Observation]
RunStatus = Literal[
    "incomplete",
    "blind",
    "vacuous",
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
    spend, and ``precision``, how tight a flip rate you care about. ``k`` and
    ``epsilon`` remain available as exact overrides, and win when set.

    Attributes:
        budget: Optional cap on meter calls. ``None`` (default) spends what
            the chosen precision needs, so a default run reaches a decision
            instead of reporting "undecided". Ignored when ``k`` is given.
        precision: ``"cheap"`` (10%), ``"balanced"`` (5%, the default), or
            ``"strict"`` (1%). Ignored when ``epsilon`` is given.
        k: Repeated calls per input. ``None`` (default) sizes it from the
            budget. After a run, ``result.config.k`` holds the value used.
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
        relation_results: Per-relation results, in the order they were run.
        config: The RunConfig used.
        errors: Failures retained under the ``"record"`` error policy.
        input_fingerprints: SHA-256 identifiers for the ordered probe set.
        observed_keys: One source-layer value per input, when available.
        requested_inputs: Number of distinct inputs requested.
    """

    meter: MeterResult | None
    blindness: BlindnessResult | None
    relation_results: list[RelationResult]
    config: RunConfig
    errors: tuple[RunError, ...] = ()
    input_fingerprints: tuple[str, ...] = ()
    observed_keys: tuple[Any | None, ...] = ()
    requested_inputs: int = 0
    duration_seconds: float = 0.0

    @property
    def complete(self) -> bool:
        """Whether every requested piece of evidence completed successfully."""
        return not self.errors

    @property
    def is_stochastic(self) -> bool:
        """True if the meter determined the agent is verdict-stochastic."""
        return self.meter is not None and self.meter.call == "verdict-stochastic"

    @property
    def is_blind(self) -> bool:
        """True if the blindness detector determined the gate is near-constant."""
        return self.blindness is not None and self.blindness.blind

    @property
    def status(self) -> RunStatus:
        """Canonical machine interpretation of the run.

        Reporters and integrations should consume this property instead of
        reconstructing precedence from the component results.
        """
        if not self.complete:
            return "incomplete"
        if self.is_blind:
            return "blind"
        if self.relation_results and not self.suite_is_meaningful:
            return "vacuous"
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
        if self.meter.call == "verdict-stochastic":
            return (
                "TRUSTWORTHY WITH CARE - the verdict changed on "
                f"{self.meter.flip_rate:.0%} of identical reruns, so read "
                "relation rates against that noise, not against zero."
            )
        if self.meter.call == "verdict-deterministic":
            trailer = (
                f" {len(vacuous)} relation{'s' if len(vacuous) != 1 else ''} "
                "tested nothing and are marked n/a."
                if vacuous
                else ""
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

        if self.meter is not None:
            m = self.meter
            lines.append("1. VERDICT-STOCHASTICITY METER")
            lines.append(f"   call:        {m.call}")
            lines.append(f"   flip rate:   {m.flip_rate:.1%} ({m.pair_flips}/{m.pair_trials} pairs)")
            lines.append(f"   Wilson CI:   [{m.ci_low:.3f}, {m.ci_high:.3f}] at epsilon={m.epsilon}")
            lines.append(f"   inputs:      {m.inputs}, repeats: {m.repeats}, layer: {m.layer}")
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

        lines.append("3. ORACLE GUIDANCE")
        if self.is_blind:
            lines.append("   BLIND — green relation results may be vacuous.")
        elif self.meter is not None and self.meter.call == "verdict-deterministic":
            lines.append("   STABLE — prefer frozen-baseline diffing when a reference is available.")
        elif self.meter is not None and self.meter.call.startswith("undecided"):
            lines.append("   UNDECIDED — raise k or input count before choosing an oracle.")
        else:
            lines.append("   STOCHASTIC — interpret relation rates against unchanged-input noise.")
        lines.append("")

        if self.relation_results:
            lines.append("4. RELATION RESULTS")
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


def run(
    agent: AgentFn,
    inputs: Iterable[str],
    *,
    relations: list[Relation] | None = None,
    config: RunConfig | None = None,
    on_progress: ProgressCallback | None = None,
) -> RunResult:
    """Run the full measure-first diagnostic suite on an agent.

    The runner follows the measure-first discipline: meter and blindness first,
    then relations. The report leads with the diagnostics.

    Args:
        agent: An agent function ``run(input) -> Observation``.
        inputs: An iterable of input strings to test against.
        relations: Custom relation list. If None, uses :func:`builtin_relations`.
        config: Run configuration. If None, uses defaults.
        on_progress: Optional callback invoked after each input completes a
            meter, source-scan, or relation phase.

    Returns:
        A :class:`RunResult` with meter, blindness, and per-relation results.
    """
    started = time.perf_counter()
    config = _resolve(config or RunConfig(), inputs)
    inputs = list(inputs)
    if not inputs:
        raise ValueError("inputs must not be empty")
    _reject_duplicates(inputs)
    if relations is None:
        relations = builtin_relations()

    source_observations: list[Observation | None] = [None] * len(inputs)
    errors: list[RunError] = []

    # 1. Meter
    meter_result = None
    if config.run_meter:
        meter_work = map_inputs(
            inputs,
            lambda _index, text: [agent(text) for _ in range(config.k)],
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
        if complete_series:
            meter_result = score_runs(
                complete_series,
                k=config.k,
                layer=config.layer,
                epsilon=config.epsilon,
            )
        if config.reuse_unchanged_calls:
            for index, observations in enumerate(meter_work.values):
                if observations:
                    source_observations[index] = observations[0]

    # 2. Blindness
    blindness_result = None
    if config.run_blindness:
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
                phase="blindness",
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
        if available:
            blindness_result = blindness_score(
                available,
                layer=config.layer,
                threshold=config.blindness_threshold,
            )

    # 3. Relations
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

    return RunResult(
        meter=meter_result,
        blindness=blindness_result,
        relation_results=relation_results,
        config=config,
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
        requested_inputs=len(inputs),
        duration_seconds=time.perf_counter() - started,
    )
