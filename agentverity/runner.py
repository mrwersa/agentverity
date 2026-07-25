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
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from agentverity.blindness import BlindnessResult, detect
from agentverity.blindness import score as blindness_score
from agentverity.meter import MeterResult, measure
from agentverity.observation import Observation
from agentverity.relations import (
    Relation,
    builtin_relations,
)

AgentFn = Callable[[str], Observation]


class _FirstCallRecorder:
    """Wrap an agent and keep the first observation seen for each input.

    The meter calls the agent ``k`` times on every unchanged input. Recording
    the first of those draws lets the blindness scan and each relation's source
    side reuse a real sample rather than spending another agent call on a
    string the run has already asked about.
    """

    def __init__(self, agent: AgentFn) -> None:
        self._agent = agent
        self.first: dict[str, Observation] = {}

    def __call__(self, text: str) -> Observation:
        obs = self._agent(text)
        self.first.setdefault(text, obs)
        return obs


def _cached_for(
    recorder: _FirstCallRecorder | None, inputs: list[str]
) -> list[Observation] | None:
    """Return one recorded observation per input, or None if any is missing."""
    if recorder is None:
        return None
    if not all(x in recorder.first for x in inputs):
        return None
    return [recorder.first[x] for x in inputs]


@dataclass(frozen=True)
class RunConfig:
    """Configuration for a runner pass.

    Attributes:
        k: Number of repeated calls per input for the meter (default 5).
        epsilon: Flip-rate threshold for the tri-state meter call (default 0.01).
        blindness_threshold: Skew share above which the gate is blind (default 0.9).
        layer: Which Observation layer to measure and assert on (default "verdict").
        run_meter: If True, run the verdict-stochasticity meter (default True).
        run_blindness: If True, run the constant-gate-blindness detector (default True).
        reuse_unchanged_calls: If True (default), the first observation the meter
            draws for each unchanged input is reused by the blindness scan and as
            the source side of every relation, instead of calling the agent again
            for the same string. Set to False to give each phase its own
            independent draw, at roughly double the agent calls.
    """

    k: int = 5
    epsilon: float = 0.01
    blindness_threshold: float = 0.9
    layer: str = "verdict"
    run_meter: bool = True
    run_blindness: bool = True
    reuse_unchanged_calls: bool = True


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
    """

    relation: Relation
    total: int
    held: int
    violated: int
    skipped: int = 0

    @property
    def exercised(self) -> int:
        """Number of inputs that produced a genuine source/follow-up pair."""
        return self.held + self.violated

    @property
    def violation_rate(self) -> float:
        """The fraction of *exercised* pairs that violated the relation.

        Inputs the transform left unchanged are excluded, because a
        byte-identical follow-up tests rerun stability rather than the
        relation. Measuring rerun stability is the meter's job.
        """
        return self.violated / self.exercised if self.exercised else 0.0

    @property
    def is_vacuous(self) -> bool:
        """``True`` if the transform was the identity on every input.

        A relation like ``normalisation-invariance`` is a no-op on plain ASCII
        with ordinary spacing. It then reports a perfect pass without ever
        having sent the agent a different string.
        """
        return self.total > 0 and self.exercised == 0


@dataclass(frozen=True)
class RunResult:
    """The complete outcome of a runner pass.

    Attributes:
        meter: The verdict-stochasticity meter result, or None if not run.
        blindness: The constant-gate-blindness result, or None if not run.
        relation_results: Per-relation results, in the order they were run.
        config: The RunConfig used.
    """

    meter: MeterResult | None
    blindness: BlindnessResult | None
    relation_results: list[RelationResult]
    config: RunConfig

    @property
    def is_stochastic(self) -> bool:
        """True if the meter determined the agent is verdict-stochastic."""
        return self.meter is not None and self.meter.call == "verdict-stochastic"

    @property
    def is_blind(self) -> bool:
        """True if the blindness detector determined the gate is near-constant."""
        return self.blindness is not None and self.blindness.blind

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
        """
        if self.is_blind:
            return False
        nothing_exercised = self.relation_results and not any(
            rr.exercised for rr in self.relation_results
        )
        return not nothing_exercised

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
                f"   {'relation':<30} {'type':<12} {'held':>6} {'violated':>10} "
                f"{'skipped':>8} {'rate':>8}"
            )
            lines.append(
                f"   {'-' * 30} {'-' * 12} {'-' * 6} {'-' * 10} {'-' * 8} {'-' * 8}"
            )
            for rr in self.relation_results:
                rate = "n/a" if rr.is_vacuous else f"{rr.violation_rate:.1%}"
                lines.append(
                    f"   {rr.relation.name:<30} {rr.relation.rtype:<12} "
                    f"{rr.held:>6} {rr.violated:>10} {rr.skipped:>8} {rate:>8}"
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
            lines.append("")

        return "\n".join(lines)


def run(
    agent: AgentFn,
    inputs: Iterable[str],
    *,
    relations: list[Relation] | None = None,
    config: RunConfig | None = None,
) -> RunResult:
    """Run the full measure-first diagnostic suite on an agent.

    The runner follows the measure-first discipline: meter and blindness first,
    then relations. The report leads with the diagnostics.

    Args:
        agent: An agent function ``run(input) -> Observation``.
        inputs: An iterable of input strings to test against.
        relations: Custom relation list. If None, uses :func:`builtin_relations`.
        config: Run configuration. If None, uses defaults.

    Returns:
        A :class:`RunResult` with meter, blindness, and per-relation results.
    """
    config = config or RunConfig()
    inputs = list(inputs)
    if not inputs:
        raise ValueError("inputs must not be empty")
    if relations is None:
        relations = builtin_relations()

    # Every phase below needs the agent's answer to the *unchanged* input. The
    # meter already draws k of them per input, so without reuse the blindness
    # scan and each relation's source side pay for the same string again.
    recorder = _FirstCallRecorder(agent) if config.reuse_unchanged_calls else None
    probe: AgentFn = recorder if recorder is not None else agent

    # 1. Meter
    meter_result = None
    if config.run_meter:
        meter_result = measure(
            probe, inputs, k=config.k, layer=config.layer, epsilon=config.epsilon
        )

    # 2. Blindness
    blindness_result = None
    if config.run_blindness:
        cached = _cached_for(recorder, inputs)
        if cached is not None:
            blindness_result = blindness_score(
                cached, layer=config.layer, threshold=config.blindness_threshold
            )
        else:
            blindness_result = detect(
                probe, inputs, layer=config.layer, threshold=config.blindness_threshold
            )

    # 3. Relations
    relation_results: list[RelationResult] = []
    for rel in relations:
        held = 0
        violated = 0
        skipped = 0
        for x in inputs:
            followup_input = rel.transform(x)
            if followup_input == x:
                # The transform is the identity on this input, so there is no
                # metamorphic pair. Re-asking the agent the same question would
                # measure rerun stability, which the meter already reports.
                skipped += 1
                continue
            source_obs = recorder.first[x] if recorder and x in recorder.first else probe(x)
            followup_obs = probe(followup_input)
            if rel.check(source_obs, followup_obs):
                held += 1
            else:
                violated += 1
        relation_results.append(
            RelationResult(
                relation=rel,
                total=len(inputs),
                held=held,
                violated=violated,
                skipped=skipped,
            )
        )

    return RunResult(
        meter=meter_result,
        blindness=blindness_result,
        relation_results=relation_results,
        config=config,
    )
