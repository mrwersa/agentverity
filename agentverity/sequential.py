"""Stop collecting once the answer is in, without invalidating the answer.

A 5% claim needs 73 zero-flip pairs per route. A route that flips on a third
of its pairs is obvious after a handful, and paying for the other sixty is
waste. The tempting fix is to recompute the Wilson interval after every pair
and stop when it crosses `epsilon`, which is optional stopping: the interval
stops meaning what it says.

This buys early stopping with checkpoints declared before collection starts,
and it spends the error budget asymmetrically, because the two directions do
not cost the same thing. Certification is tested once, at the last checkpoint,
so it carries no multiplicity penalty and costs no more pairs than the
fixed-sample path. The earlier looks only ever declare stochasticity, and they
split the other half of the budget between them.

See DESIGN.md ADR 7, including why spending evenly was measured and rejected.

Example::

    from agentverity.sequential import plan_sequential, decide_sequentially

    plan = plan_sequential(epsilon=0.05)
    call, pairs = decide_sequentially(plan, flip_outcomes)
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

#: The three answers, matching what the pooled meter already reports.
DETERMINISTIC = "verdict-deterministic"
STOCHASTIC = "verdict-stochastic"
UNDECIDED = "undecided"


def _at_most(pairs: int, flips: int, p: float) -> float:
    """P(X <= flips) for X binomial with `pairs` trials at rate `p`."""
    return math.fsum(
        math.comb(pairs, i) * p**i * (1 - p) ** (pairs - i)
        for i in range(flips + 1)
    )


def _at_least(pairs: int, flips: int, p: float) -> float:
    """P(X >= flips) for X binomial with `pairs` trials at rate `p`."""
    return math.fsum(
        math.comb(pairs, i) * p**i * (1 - p) ** (pairs - i)
        for i in range(flips, pairs + 1)
    )


@dataclass(frozen=True)
class SequentialPlan:
    """Checkpoints and thresholds, all fixed before a single call is made.

    Attributes:
        epsilon: The flip rate being tested against.
        alpha: Total error budget, split half to each direction.
        checkpoints: Ascending pair counts at which a decision may be taken.
            The last is where certification is tested, and the only one.
        certify_at_most: Flips at the final checkpoint that still certify.
            `-1` when no count can, which happens when the budget is too small
            for the tolerance.
        stochastic_at_least: Flips at each checkpoint that prove stochasticity.
    """

    epsilon: float
    alpha: float
    checkpoints: tuple[int, ...]
    certify_at_most: int
    stochastic_at_least: dict[int, int]

    def __post_init__(self) -> None:
        if not self.checkpoints:
            raise ValueError("a plan needs at least one checkpoint")
        if list(self.checkpoints) != sorted(set(self.checkpoints)):
            raise ValueError("checkpoints must be ascending and distinct")

    @property
    def budget(self) -> int:
        """The most pairs this plan will ever ask for."""
        return self.checkpoints[-1]

    def call_at(self, checkpoint: int, flips: int) -> str | None:
        """The decision at one checkpoint, or None to keep collecting.

        Args:
            checkpoint: A pair count from `checkpoints`.
            flips: Flips among exactly the first `checkpoint` pairs, in
                collection order. Not among however many have finished, which
                would make the analysed count random and put the correction
                back in doubt.

        Returns:
            `DETERMINISTIC`, `STOCHASTIC`, `UNDECIDED` at the final checkpoint,
            or None when there is another checkpoint to reach.

        Raises:
            ValueError: If the checkpoint is not one this plan declared, or
                the flip count cannot have come from that many pairs.
        """
        if checkpoint not in self.stochastic_at_least:
            raise ValueError(
                f"{checkpoint} is not a declared checkpoint; this plan looks "
                f"at {', '.join(str(point) for point in self.checkpoints)}. A "
                "checkpoint chosen after seeing the data is the peeking this "
                "avoids, wearing a different hat."
            )
        if not 0 <= flips <= checkpoint:
            raise ValueError(f"{flips} flips is impossible in {checkpoint} pairs")
        if flips >= self.stochastic_at_least[checkpoint]:
            return STOCHASTIC
        if checkpoint != self.budget:
            return None
        return DETERMINISTIC if flips <= self.certify_at_most else UNDECIDED


def plan_sequential(
    epsilon: float, *, alpha: float = 0.05, looks: int = 4, budget: int | None = None
) -> SequentialPlan:
    """Declare the checkpoints and thresholds before collection starts.

    Args:
        epsilon: The flip-rate threshold to test against.
        alpha: Total error budget. Half funds the single certification test and
            half is split across every look for the stochastic direction.
        looks: How many checkpoints, including the final one. More looks stop
            an unstable route sooner and cost nothing in the other direction,
            because certification is tested once whatever this is.
        budget: Final checkpoint. Defaults to the smallest count that can
            certify with no flips, which is what makes this cost no more than
            the fixed-sample path.

    Returns:
        A `SequentialPlan`.

    Raises:
        ValueError: If epsilon or alpha is outside (0, 1), looks is below 1, or
            the budget is smaller than the number of looks.
    """
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if looks < 1:
        raise ValueError("a plan needs at least one look")

    certification = alpha / 2
    if budget is None:
        # The count at which zero flips certifies. Tested once, so no
        # correction, which is why this lands at or below the fixed-sample
        # requirement rather than above it.
        budget = math.ceil(math.log(certification) / math.log(1 - epsilon))
    if budget < looks:
        raise ValueError(f"a budget of {budget} pairs cannot support {looks} looks")

    early = tuple(
        sorted({max(1, round(budget * index / looks)) for index in range(1, looks)})
    )
    checkpoints = (*(point for point in early if point < budget), budget)
    per_look = (alpha / 2) / len(checkpoints)

    return SequentialPlan(
        epsilon=epsilon,
        alpha=alpha,
        checkpoints=checkpoints,
        certify_at_most=max(
            (
                flips
                for flips in range(budget + 1)
                if _at_most(budget, flips, epsilon) <= certification
            ),
            default=-1,
        ),
        stochastic_at_least={
            point: min(
                (
                    flips
                    for flips in range(point + 1)
                    if _at_least(point, flips, epsilon) <= per_look
                ),
                default=point + 1,
            )
            for point in checkpoints
        },
    )


def decide_sequentially(
    plan: SequentialPlan, outcomes: Iterable[bool]
) -> tuple[str, int]:
    """Read pair outcomes in order and stop at the first checkpoint that decides.

    The ordering is the rule rather than a convenience. Each decision reads
    exactly the first `n` pairs, so concurrency overshooting a boundary is kept
    as evidence and never changes a call, and the count a decision rests on is
    fixed in advance.

    Args:
        plan: The checkpoints, declared before collection started.
        outcomes: One boolean per disjoint pair, True when the pair disagreed,
            in the order the pairs were collected.

    Returns:
        The call, and how many pairs it took. `UNDECIDED` with the full budget
        when the outcomes run out early, because a short run has not settled
        anything.
    """
    flips = seen = 0
    remaining = iter(outcomes)
    *early, final = plan.checkpoints

    def collect(target: int) -> bool:
        nonlocal flips, seen
        while seen < target:
            outcome = next(remaining, None)
            if outcome is None:
                return False
            flips += bool(outcome)
            seen += 1
        return True

    for checkpoint in early:
        if not collect(checkpoint):
            return UNDECIDED, seen
        call = plan.call_at(checkpoint, flips)
        if call is not None:
            return call, seen

    # The final checkpoint always answers, so it sits outside the loop rather
    # than behind an unreachable fallback that reads like a case someone
    # thought about.
    if not collect(final):
        return UNDECIDED, seen
    answer = plan.call_at(final, flips)
    assert answer is not None
    return answer, seen
