"""Verdict-stochasticity meter — the measure-first instrument.

Agents are non-deterministic, so before trusting any test you must know whether
the agent's *decision* actually varies across identical reruns, and at which
layer. Token-level variation (the final text wording) is common and mostly
harmless; what matters for testing is whether the **verdict** (the categorical
decision, or the tool trajectory) flips. If the verdict is stable and a
trusted reference is available, frozen-baseline diffing is the more sensitive
change detector.
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
from fractions import Fraction
from typing import Any

from agentverity.observation import Observation

from .decision import check_scorable, comparison_key

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


PRECISION_LEVELS: dict[str, float] = {
    "cheap": 0.10,
    "balanced": 0.05,
    "strict": 0.01,
}
"""Named flip-rate thresholds.

Nobody knows what epsilon to pick, but everybody knows how much they care.
``strict`` is the research-grade 1% that needs 381 pairs; ``balanced`` is 5%
and roughly 160 calls on a typical probe set; ``cheap`` is 10% for a smoke
test. Pass ``epsilon`` directly to override.
"""


def classify_call(ci_low: float, ci_high: float, epsilon: float) -> str:
    """Classify a flip rate from its confidence bound, never from the estimate.

    Shared by the pooled meter and the per-route view so the two cannot drift
    apart. The distinction matters more than it looks: one flip in thirteen
    pairs is an observed rate of 7.7%, which is above a 5% threshold, and the
    interval still runs from 0.014 to 0.333. Reading the point estimate as a
    verdict is the exact error this package exists to stop, so an interval
    straddling epsilon is ``undecided`` however suggestive the rate looks.
    """
    if ci_low > epsilon:
        return "verdict-stochastic"
    if ci_high < epsilon:
        return "verdict-deterministic"
    return "undecided (add repeats or inputs)"


def resolve_epsilon(precision: str, epsilon: float | None) -> float:
    """Return the flip-rate threshold, with an explicit epsilon winning.

    Raises:
        ValueError: If ``precision`` is not a known level, or ``epsilon`` is
            outside ``(0, 1)``.
    """
    if epsilon is not None:
        if not 0 < epsilon < 1:
            raise ValueError("epsilon must be between 0 and 1")
        return epsilon
    try:
        return PRECISION_LEVELS[precision]
    except KeyError:
        known = ", ".join(sorted(PRECISION_LEVELS))
        raise ValueError(
            f"unknown precision {precision!r}; expected one of {known}"
        ) from None


def plan_repeats(inputs: int, epsilon: float, budget: int | None = None) -> int:
    """Choose ``k`` so a run can answer, optionally under a call budget.

    Callers think in "how many calls can I afford", not "how many repeats per
    input". Each input yields ``floor(k / 2)`` disjoint pairs, so the repeats a
    decision needs fall as the probe set grows. This spends what the decision
    needs and no more.

    Two repeats per input is the structural floor, so a probe set of ``n``
    always costs at least ``2n`` calls. A budget below that floor is a
    contradiction rather than a preference, and is rejected.

    Args:
        inputs: Number of distinct probes.
        epsilon: Flip-rate threshold the run is testing against.
        budget: Optional cap on meter calls. ``None`` spends what the precision
            needs, which is the default because refusing to answer is worse
            than costing a predictable amount.

    Returns:
        An even ``k`` of at least 2.

    Raises:
        ValueError: If ``inputs`` is below one, or an explicit ``budget``
            cannot cover two repeats per input.
    """
    if inputs < 1:
        raise ValueError("inputs must be at least 1")
    needed = pairs_for_deterministic_call(epsilon)
    wanted = 2 * -(-needed // inputs) if needed is not None else 2
    if budget is None:
        return max(2, wanted)
    if budget < 2 * inputs:
        raise ValueError(
            f"budget of {budget} cannot cover {inputs} inputs; the meter needs "
            f"at least two repeats each, so {2 * inputs} calls. Raise the "
            "budget, use fewer inputs, or drop the budget to spend what the "
            "chosen precision needs."
        )
    affordable = (budget // inputs) // 2 * 2
    return max(2, min(wanted, affordable))


def pairs_for_deterministic_call(
    epsilon: float, z: float = 1.96, *, flip_rate: float = 0.0
) -> int | None:
    """Pairs needed to certify determinism under a projected fixed flip rate.

    A ``verdict-deterministic`` call needs the Wilson upper bound below
    ``epsilon``. With no flips observed the bound depends only on the pair
    count: 381 pairs at the default epsilon of 0.01.

    A nonzero ``flip_rate`` is a scenario assumption: it projects the same
    empirical rate at every candidate pair count. It does not describe the
    best possible continuation of already-observed counts; use
    :func:`best_case_admission_pairs` for that question.

    Args:
        epsilon: The flip-rate threshold being tested against.
        z: Z-value for the interval, matching :func:`wilson_ci`.
        flip_rate: Projected fixed flip rate. Zero is the best case and the
            cheapest scenario.

    Returns:
        The minimum pair count, or ``None`` when the projected rate is already
        at or above ``epsilon``.

    Raises:
        ValueError: If ``epsilon`` is outside ``(0, 1)``, ``z`` is not finite
            and positive, or ``flip_rate`` is outside ``[0, 1]``.
    """
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    if not math.isfinite(z) or z <= 0:
        raise ValueError("z must be a finite positive number")
    if not 0 <= flip_rate <= 1:
        raise ValueError("flip_rate must be between 0 and 1")
    if flip_rate >= epsilon:
        # The bound converges onto the projected rate from above.
        return None

    # Inverting the Wilson score test at epsilon gives the strict condition
    # n > z^2 * epsilon * (1 - epsilon) / (epsilon - p_hat)^2. Fractions avoid
    # rounding a mathematical integer boundary down into a false admission.
    epsilon_q = Fraction(epsilon)
    rate_q = Fraction(flip_rate)
    z_q = Fraction(z)
    threshold = z_q * z_q * epsilon_q * (1 - epsilon_q) / (epsilon_q - rate_q) ** 2
    return threshold.numerator // threshold.denominator + 1


def best_case_admission_pairs(
    epsilon: float,
    *,
    flips: int,
    pairs: int,
    max_pairs: int | None = None,
    z: float = 1.96,
) -> int | None:
    """Return the earliest best-case Wilson admission total for observed counts.

    The calculation holds ``flips`` fixed and assumes every additional pair
    agrees. It answers whether admission remains possible within a predeclared
    ``max_pairs``; it is not permission to inspect the interval repeatedly and
    stop when it passes. Admission still belongs at a fixed endpoint or to an
    anytime-valid/predeclared sequential procedure.

    Args:
        epsilon: The flip-rate threshold being tested against.
        flips: Flips already observed.
        pairs: Disjoint pairs already observed.
        max_pairs: Optional predeclared total pair budget. When supplied,
            return ``None`` if even an all-agree continuation cannot admit by
            that endpoint.
        z: Z-value for the interval, matching :func:`wilson_ci`.

    Returns:
        The earliest total pair count that could admit if no further flips
        occur, or ``None`` when that is impossible within ``max_pairs``.

    Raises:
        ValueError: If a probability or count is outside its valid range.
        TypeError: If a count is not an integer.
    """
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    if not math.isfinite(z) or z <= 0:
        raise ValueError("z must be a finite positive number")
    for name, value in (("flips", flips), ("pairs", pairs)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer")
    if pairs < 1:
        raise ValueError("pairs must be at least 1")
    if not 0 <= flips <= pairs:
        raise ValueError("flips must be between 0 and pairs")
    if max_pairs is not None:
        if not isinstance(max_pairs, int) or isinstance(max_pairs, bool):
            raise TypeError("max_pairs must be an integer")
        if max_pairs < pairs:
            raise ValueError("max_pairs must be at least pairs")

    epsilon_q = Fraction(epsilon)
    z_squared = Fraction(z) ** 2

    def could_admit(total: int) -> bool:
        # Wilson's upper endpoint is below epsilon exactly when the one-sided
        # score statistic exceeds z in the admission direction.
        gap = total * epsilon_q - flips
        return gap > 0 and gap * gap > (z_squared * total * epsilon_q * (1 - epsilon_q))

    if could_admit(pairs):
        return pairs
    if max_pairs is not None:
        if not could_admit(max_pairs):
            return None
        high = max_pairs
    else:
        high = pairs * 2
        while not could_admit(high):
            high *= 2

    low = pairs
    while low + 1 < high:
        middle = (low + high) // 2
        if could_admit(middle):
            high = middle
        else:
            low = middle
    return high


@dataclass(frozen=True)
class MeterResult:
    """The outcome of a verdict-stochasticity measurement.

    Attributes:
        layer: Which ``Observation`` layer was measured (``"verdict"``,
            ``"text"``, or ``"tools"``).
        epsilon: The flip-rate threshold below which a gate is considered
            deterministic.
        inputs: Number of distinct inputs probed.
        repeats: Minimum repeated calls across the inputs. This equals ``k``
            for an ordinary uniform run.
        max_repeats: Maximum repeated calls across the inputs. It differs from
            ``repeats`` when a decision contract allocates evidence by route.
        pair_trials: Total independent, disjoint comparisons across all inputs.
        pair_flips: Number of disjoint comparisons where the verdict differed.
        inputs_with_flip: Number of inputs that showed at least one flip.
        ci_low: Lower bound of the Wilson CI on the flip rate.
        ci_high: Upper bound of the Wilson CI on the flip rate.
        sequential_call: The decision a declared checkpoint took, when
            collection stopped early. `call` returns it in preference to the
            interval, because the interval did not choose the stopping point.
        sequential_pairs: Pairs the sequential plan read to decide, which is
            the count the decision rests on rather than however many were
            collected.
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
    max_repeats: int | None = None
    sequential_call: str | None = None
    sequential_pairs: int | None = None

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

            When collection stopped at a declared checkpoint, that decision is
            returned instead. Reading the Wilson interval at a stopping point
            it did not choose is the optional stopping the sequential design
            exists to avoid, so the interval below stays descriptive and the
            plan decides. See DESIGN.md ADR 7.
        """
        if self.sequential_call is not None:
            return self.sequential_call
        return classify_call(self.ci_low, self.ci_high, self.epsilon)

    @property
    def advice(self) -> str:
        """A human-readable recommendation based on the tri-state call."""
        c = self.call
        if c == "verdict-stochastic":
            return ("verdict varies across identical runs: use noise-robust "
                    "relations and compare violations to a measured baseline, "
                    "not zero.")
        if c == "verdict-deterministic":
            return ("verdict is stable: prefer frozen-baseline diffing when "
                    "a trusted reference is available.")
        return (
            "not enough evidence to choose a test strategy; "
            "raise K or input count."
        )


def measure(
    agent: AgentFn,
    inputs: Iterable[str],
    *,
    k: int = 5,
    layer: str = "verdict",
    epsilon: float = 0.01,
) -> MeterResult:
    """Measure the verdict-stochasticity of an agent.

    The agent is called ``k`` times on each input (with no transform applied).
    Consecutive outputs are compared in disjoint pairs, giving
    :math:`\\lfloor k/2 \\rfloor` independent comparisons per input. A Wilson
    confidence interval on that flip rate determines the tri-state call.

    Using every pair among the same ``k`` outputs would create
    :math:`\\binom{k}{2}` dependent comparisons and make the interval look
    more precise than the calls justify. An odd final repeat is retained for
    ``inputs_with_flip`` but does not enter the confidence interval.

    Args:
        agent: An agent function ``run(input) -> Observation``.
        inputs: An iterable of input strings to probe.
        k: Number of repeated calls per input (must be >= 2). The confidence
            interval uses ``floor(k / 2)`` disjoint pairs.
        layer: Which ``Observation`` layer to measure (``"verdict"``,
            ``"text"``, or ``"tools"``).
        epsilon: The flip-rate threshold below which a gate is considered
            deterministic (default 0.01, i.e. 1%).

    Returns:
        A :class:`MeterResult` with the flip rate, Wilson CI, and tri-state call.

    Raises:
        ValueError: If ``k`` is less than 2, inputs is empty, or epsilon is
            outside ``(0, 1)``.
    """
    if k < 2:
        raise ValueError("k must be >= 2 to compare repeated runs")
    inputs = list(inputs)
    if not inputs:
        raise ValueError("inputs must not be empty")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    runs: list[list[Observation]] = []
    for x in inputs:
        runs.append([agent(x) for _ in range(k)])
    return score_runs(runs, k=k, layer=layer, epsilon=epsilon)




def score_runs(
    runs: Iterable[Iterable[Observation]],
    *,
    k: int,
    layer: str = "verdict",
    epsilon: float = 0.01,
) -> MeterResult:
    """Score already-collected repeated observations.

    The runner uses this function after gathering one sequential repeat series
    per input, potentially in parallel across inputs. Direct callers normally
    use :func:`measure`.
    """
    if k < 2:
        raise ValueError("k must be >= 2 to compare repeated runs")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")

    runs = [list(observations) for observations in runs]
    if not runs:
        raise ValueError("runs must not be empty")

    lengths = [len(observations) for observations in runs]
    pair_trials = 0
    pair_flips = 0
    inputs_with_flip = 0
    for observations in runs:
        # Series may differ in length when a suite sizes repeats per route, so
        # pairs come from each series rather than from one k. Every series must
        # still carry at least one pair, otherwise it contributes no evidence
        # and silently weakens the interval.
        length = len(observations)
        if length < 2:
            raise ValueError(
                "every repeat series must contain at least two observations, "
                f"got {length}"
            )
        # Enforcement, not decoration. ADR 2 says a harness failure makes the
        # evidence incomplete; if the meter ignored that, repeated extraction
        # failures would compare equal and contribute zero-flip pairs, which
        # certifies the failure. And an outcome comparable to nothing cannot
        # take part in a pair at all.
        check_scorable(observations, layer)
        keys = [observation.key(layer) for observation in observations]
        if len({_hashable(v) for v in keys}) > 1:
            inputs_with_flip += 1
        for i in range(0, length - 1, 2):
            pair_trials += 1
            if pair_flipped(observations[i], observations[i + 1], layer):
                pair_flips += 1
    lo, hi = wilson_ci(pair_flips, pair_trials)
    return MeterResult(
        layer=layer,
        epsilon=epsilon,
        inputs=len(runs),
        repeats=min((len(observations) for observations in runs), default=k),
        pair_trials=pair_trials,
        pair_flips=pair_flips,
        inputs_with_flip=inputs_with_flip,
        ci_low=lo,
        ci_high=hi,
        max_repeats=max(lengths),
    )


def pair_flipped(first: Any, second: Any, layer: str = "verdict") -> bool:
    """Whether two observations of one input disagree at `layer`.

    One implementation, because two are how the pooled and per-route paths
    once disagreed about which series they would score. Sequential collection
    needs the same question answered pair by pair as it goes, and answering it
    a second way would let a run stop on one rule and be scored by another.
    """
    return _hashable(first.key(layer)) != _hashable(second.key(layer))


def _hashable(v: Any) -> Any:
    """Normalise a verdict value to a hashable comparison key.

    Verdicts may be strings, enums, or tuples (for tool trajectories).
    Lists are converted to tuples; enum values are extracted via ``.value``
    if present.
    """
    if isinstance(v, (list, tuple)):
        return tuple(v)
    # A bare label and a tagged one are the same decision. Comparing them
    # unequal reports a flip on a decision this package says is identical.
    v = comparison_key(v)
    return v.value if hasattr(v, "value") else v
