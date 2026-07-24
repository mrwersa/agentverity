"""Verdict-stochasticity meter — the measure-first instrument.

Agents are non-deterministic, so before trusting any test you must know whether
the agent's *decision* actually varies across identical reruns, and at which
layer. Token-level variation (the final text wording) is common and mostly
harmless; what matters for testing is whether the **verdict** (the categorical
decision, or the tool trajectory) flips. If the verdict is stable, a
frozen-output diff is the right oracle and metamorphic relations add little.
If it is stochastic, you need noise-robust relations and a measured baseline,
not zero-tolerance assertions.

The meter runs the agent ``k`` times on each unchanged input and reports a
tri-state call with a Wilson confidence interval, so an underfunded probe is
reported as ``"undecided"`` rather than mislabelled ``"deterministic"``.

Example::

    from agentverity.meter import measure
    from agentverity.adapters import from_callable

    agent = from_callable(my_agent_fn)
    result = measure(agent, inputs=["hello", "world"], k=5)
    print(result.call)       # "verdict-deterministic" / "verdict-stochastic" / "undecided"
    print(result.advice)     # human-readable recommendation
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from agentverity.observation import Observation

AgentFn = Callable[[str], Observation]


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Return the Wilson score interval for a binomial proportion.

    Args:
        successes: Number of successes observed.
        trials: Total number of trials.
        z: Z-value for the desired confidence level (default 1.96 for 95%).

    Returns:
        A ``(low, high)`` tuple with the lower and upper bounds of the
        confidence interval. Returns ``(0.0, 0.0)`` if ``trials`` is zero.
    """
    if trials == 0:
        return 0.0, 0.0
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


@dataclass(frozen=True)
class MeterResult:
    """The outcome of a verdict-stochasticity measurement.

    Attributes:
        layer: Which ``Observation`` layer was measured (``"verdict"``,
            ``"text"``, or ``"tools"``).
        epsilon: The flip-rate threshold below which a gate is considered
            deterministic.
        inputs: Number of distinct inputs probed.
        repeats: Number of repeated calls per input (``k``).
        pair_trials: Total pairwise comparisons made across all inputs.
        pair_flips: Number of pairwise comparisons where the verdict differed.
        inputs_with_flip: Number of inputs that showed at least one flip.
        ci_low: Lower bound of the Wilson CI on the flip rate.
        ci_high: Upper bound of the Wilson CI on the flip rate.
    """

    layer: str
    epsilon: float
    inputs: int
    repeats: int
    pair_trials: int
    pair_flips: int
    inputs_with_flip: int
    ci_low: float
    ci_high: float

    @property
    def flip_rate(self) -> float:
        """The observed pairwise flip rate (``pair_flips / pair_trials``)."""
        return self.pair_flips / self.pair_trials if self.pair_trials else 0.0

    @property
    def call(self) -> str:
        """The tri-state classification.

        Returns:
            ``"verdict-stochastic"`` if the CI lower bound is above epsilon,
            ``"verdict-deterministic"`` if the CI upper bound is below epsilon,
            or ``"undecided (add repeats or inputs)"`` if the interval straddles
            epsilon. A bare ``"deterministic"`` would conflate real stability
            with an underpowered probe, so an interval straddling epsilon is
            ``"undecided"``.
        """
        if self.ci_low > self.epsilon:
            return "verdict-stochastic"
        if self.ci_high < self.epsilon:
            return "verdict-deterministic"
        return "undecided (add repeats or inputs)"

    @property
    def advice(self) -> str:
        """A human-readable recommendation based on the tri-state call."""
        c = self.call
        if c == "verdict-stochastic":
            return ("verdict varies across identical runs: use noise-robust "
                    "relations and compare violations to a measured baseline, "
                    "not zero.")
        if c == "verdict-deterministic":
            return ("verdict is stable: a frozen-output diff is the strongest "
                    "oracle here; metamorphic relations add little.")
        return "not enough evidence to choose an oracle; raise K or input count."


def measure(
    agent: AgentFn,
    inputs: Iterable[str],
    *,
    k: int = 5,
    layer: str = "verdict",
    epsilon: float = 0.01,
) -> MeterResult:
    """Measure the verdict-stochasticity of an agent.

    The agent is called ``k`` times on each input (with no transform applied)
    and the pairwise flip rate is computed across all :math:`\\binom{k}{2}`
    pairs per input. A Wilson confidence interval on the flip rate determines
    the tri-state call.

    Args:
        agent: An agent function ``run(input) -> Observation``.
        inputs: An iterable of input strings to probe.
        k: Number of repeated calls per input (must be >= 2).
        layer: Which ``Observation`` layer to measure (``"verdict"``,
            ``"text"``, or ``"tools"``).
        epsilon: The flip-rate threshold below which a gate is considered
            deterministic (default 0.01, i.e. 1%).

    Returns:
        A :class:`MeterResult` with the flip rate, Wilson CI, and tri-state call.

    Raises:
        ValueError: If ``k`` is less than 2.
    """
    if k < 2:
        raise ValueError("k must be >= 2 to compare repeated runs")
    inputs = list(inputs)
    pair_trials = 0
    pair_flips = 0
    inputs_with_flip = 0
    for x in inputs:
        keys = [agent(x).key(layer) for _ in range(k)]
        if len({_hashable(v) for v in keys}) > 1:
            inputs_with_flip += 1
        for i, j in combinations(range(k), 2):
            pair_trials += 1
            if _hashable(keys[i]) != _hashable(keys[j]):
                pair_flips += 1
    lo, hi = wilson_ci(pair_flips, pair_trials)
    return MeterResult(
        layer=layer,
        epsilon=epsilon,
        inputs=len(inputs),
        repeats=k,
        pair_trials=pair_trials,
        pair_flips=pair_flips,
        inputs_with_flip=inputs_with_flip,
        ci_low=lo,
        ci_high=hi,
    )


def _hashable(v: Any) -> Any:
    """Normalise a verdict value to a hashable comparison key.

    Verdicts may be strings, enums, or tuples (for tool trajectories).
    Lists are converted to tuples; enum values are extracted via ``.value``
    if present.
    """
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return v.value if hasattr(v, "value") else v
