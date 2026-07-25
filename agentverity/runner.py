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

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from agentverity.blindness import BlindnessResult, detect
from agentverity.meter import MeterResult, measure
from agentverity.observation import Observation
from agentverity.relations import (
    Relation,
    builtin_relations,
)

AgentFn = Callable[[str], Observation]


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
    """

    k: int = 5
    epsilon: float = 0.01
    blindness_threshold: float = 0.9
    layer: str = "verdict"
    run_meter: bool = True
    run_blindness: bool = True


@dataclass(frozen=True)
class RelationResult:
    """The result of running one relation across all inputs.

    Attributes:
        relation: The relation that was run.
        total: Total number of source/follow-up pairs tested.
        held: Number of pairs where the relation held (no violation).
        violated: Number of pairs where the relation was violated.
    """

    relation: Relation
    total: int
    held: int
    violated: int

    @property
    def violation_rate(self) -> float:
        """The fraction of pairs that violated the relation."""
        return self.violated / self.total if self.total else 0.0


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
    def suite_is_meaningful(self) -> bool:
        """True if relation results are not vacuous under the skew scan.

        The meter determines how relation results should be interpreted, not
        whether they can express a useful requirement. A stable verdict may
        make frozen-baseline diffing more sensitive, while an undecided meter
        calls for more evidence. Only a blindness warning makes green relation
        results potentially vacuous.
        """
        return not self.is_blind

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
            lines.append(f"   {'relation':<30} {'type':<12} {'held':>6} {'violated':>10} {'rate':>8}")
            lines.append(f"   {'-' * 30} {'-' * 12} {'-' * 6} {'-' * 10} {'-' * 8}")
            for rr in self.relation_results:
                lines.append(
                    f"   {rr.relation.name:<30} {rr.relation.rtype:<12} "
                    f"{rr.held:>6} {rr.violated:>10} {rr.violation_rate:>7.1%}"
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

    # 1. Meter
    meter_result = None
    if config.run_meter:
        meter_result = measure(
            agent, inputs, k=config.k, layer=config.layer, epsilon=config.epsilon
        )

    # 2. Blindness
    blindness_result = None
    if config.run_blindness:
        blindness_result = detect(
            agent, inputs, layer=config.layer, threshold=config.blindness_threshold
        )

    # 3. Relations
    relation_results: list[RelationResult] = []
    for rel in relations:
        held = 0
        violated = 0
        for x in inputs:
            source_input = x
            followup_input = rel.transform(x)
            source_obs = agent(source_input)
            followup_obs = agent(followup_input)
            if rel.check(source_obs, followup_obs):
                held += 1
            else:
                violated += 1
        relation_results.append(
            RelationResult(relation=rel, total=len(inputs), held=held, violated=violated)
        )

    return RunResult(
        meter=meter_result,
        blindness=blindness_result,
        relation_results=relation_results,
        config=config,
    )
