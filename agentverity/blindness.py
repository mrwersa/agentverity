"""Constant-gate-blindness detector — the honesty instrument.

A test suite can pass for the wrong reason: if the agent returns a near-constant
verdict across a diverse input set, many invariance and monotonicity checks can
be satisfied without exercising a decision boundary. A green suite can then say
more about verdict skew than about whether the agent reasons correctly.

This detector measures the agent's verdict **skew** on a probe set and warns
when a pass is likely trivial. It is the feature that makes the framework
honest about its own limits: it tells you when your passing metamorphic suite
is lying to you.

Example::

    from agentverity.blindness import detect
    from agentverity.adapters import from_callable

    agent = from_callable(my_constant_agent)
    result = detect(agent, inputs=["hello", "world", "foo", "bar"])
    if result.blind:
        print(result.warning)
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from agentverity.observation import Observation

AgentFn = Callable[[str], Observation]


@dataclass(frozen=True)
class BlindnessResult:
    """The outcome of a constant-gate-blindness scan.

    Attributes:
        inputs: Number of inputs probed.
        layer: Which ``Observation`` layer was measured.
        majority_verdict: The most common verdict value observed.
        skew: The share of inputs that returned the majority verdict.
        distinct: Number of distinct verdicts seen.
        threshold: The skew threshold above which the gate is considered blind.
    """

    inputs: int
    layer: str
    majority_verdict: Any
    skew: float
    distinct: int
    threshold: float

    @property
    def blind(self) -> bool:
        """``True`` if verdict skew can make green relation results vacuous."""
        return self.skew >= self.threshold

    @property
    def warning(self) -> str | None:
        """A human-readable warning if the gate is blind, ``None`` otherwise."""
        if not self.blind:
            return None
        return (
            f"constant-gate blindness: agent returns "
            f"{self.majority_verdict!r} on {self.skew:.0%} of inputs. "
            f"Relation passes may be trivial because the probe set rarely "
            f"exercises a decision boundary. A green suite is NOT evidence of "
            f"correct behaviour here."
        )


def detect(
    agent: AgentFn,
    inputs: Iterable[str],
    *,
    layer: str = "verdict",
    threshold: float = 0.9,
) -> BlindnessResult:
    """Detect whether an agent is near-constant and passes may be vacuous.

    The agent is called once on each input and the verdict distribution is
    measured. If a single verdict accounts for at least ``threshold`` of the
    inputs, the gate is flagged as blind. High skew makes relation passes
    vulnerable to being vacuous because few probes exercise a decision
    boundary. The detector is a warning about suite power, not a correctness
    judgement about the agent.

    Args:
        agent: An agent function ``run(input) -> Observation``.
        inputs: An iterable of input strings to probe. Use a diverse set;
            a narrow set inflates skew artificially.
        layer: Which ``Observation`` layer to measure (``"verdict"``,
            ``"text"``, or ``"tools"``).
        threshold: The skew share (0–1) above which the gate is considered
            blind (default 0.9, i.e. 90%).

    Returns:
        A :class:`BlindnessResult` with the skew, distinct-verdict count,
        and blind flag.

    Raises:
        ValueError: If inputs is empty or threshold is outside ``(0, 1]``.
    """
    inputs = list(inputs)
    if not inputs:
        raise ValueError("inputs must not be empty")
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    return score([agent(x) for x in inputs], layer=layer, threshold=threshold)


def score(
    observations: Iterable[Observation],
    *,
    layer: str = "verdict",
    threshold: float = 0.9,
) -> BlindnessResult:
    """Score already-collected observations for verdict skew.

    :func:`detect` calls the agent and then delegates here. Call this directly
    when the observations were gathered by an earlier phase, so a probe set does
    not have to be re-run purely to count its verdict distribution.

    Args:
        observations: One :class:`Observation` per input, already collected.
        layer: Which ``Observation`` layer to measure (``"verdict"``,
            ``"text"``, or ``"tools"``).
        threshold: The skew share (0–1) above which the gate is considered
            blind (default 0.9, i.e. 90%).

    Returns:
        A :class:`BlindnessResult` with the skew, distinct-verdict count,
        and blind flag.

    Raises:
        ValueError: If observations is empty or threshold is outside ``(0, 1]``.
    """
    observations = list(observations)
    if not observations:
        raise ValueError("observations must not be empty")
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    verdicts = [_hashable(obs.key(layer)) for obs in observations]
    c = Counter(verdicts)
    top, top_n = c.most_common(1)[0]
    n = len(verdicts)
    return BlindnessResult(
        inputs=n,
        layer=layer,
        majority_verdict=top,
        skew=top_n / n,
        distinct=len(c),
        threshold=threshold,
    )


def _hashable(v: Any) -> Any:
    """Normalise a verdict value to a hashable comparison key."""
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return v.value if hasattr(v, "value") else v
