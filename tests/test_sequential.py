"""Early stopping that does not invalidate what it stopped on. See ADR 7.

The design came out of measuring the obvious version rather than reasoning
about it: spending alpha evenly across looks in both directions costs 99 pairs
to certify where the fixed-sample interval needs 73, and its early looks never
certify anything at all.
"""

from __future__ import annotations

import random

import pytest

from agentverity.meter import pairs_for_deterministic_call
from agentverity.sequential import (
    DETERMINISTIC,
    STOCHASTIC,
    UNDECIDED,
    decide_sequentially,
    plan_sequential,
)


def _outcomes(rate: float, count: int, rng: random.Random):
    return [rng.random() < rate for _ in range(count)]


def test_certifying_costs_no_more_than_the_fixed_sample_path():
    """The point of testing certification once instead of at every look.

    An even split across four looks needs 99 pairs against the fixed sample's
    73, a 36% tax on every well-behaved route, and buys nothing: no attainable
    flip count certifies before the last checkpoint anyway.
    """
    plan = plan_sequential(0.05)

    assert plan.budget <= pairs_for_deterministic_call(0.05)
    assert plan.budget == 72


def test_an_obviously_unstable_route_stops_in_a_quarter_of_the_budget():
    plan = plan_sequential(0.05)
    rng = random.Random(20260803)

    spent = [
        decide_sequentially(plan, _outcomes(0.30, plan.budget, rng))[1]
        for _ in range(400)
    ]

    assert sum(spent) / len(spent) < plan.budget * 0.4


def test_the_false_certification_rate_is_the_closed_form_not_a_simulation():
    """Certification fires only on zero flips, and zero flips fires no look.

    So the two rules cannot interact and the error is exactly `(1 - p)^n`.
    Asserting the closed form is stronger than a simulation, which can only
    ever fail to notice a breach.
    """
    plan = plan_sequential(0.05)

    assert plan.certify_at_most == 0, "the guarantee below depends on this"
    exact = (1 - 0.05) ** plan.budget

    assert exact <= plan.alpha / 2
    assert exact == pytest.approx(0.02489, abs=1e-5)


def test_a_deterministic_agent_is_not_called_stochastic_by_the_extra_looks():
    """Four chances to be wrong in one direction, still inside the budget."""
    plan = plan_sequential(0.05)
    rng = random.Random(4471)

    wrong = sum(
        decide_sequentially(plan, _outcomes(0.0, plan.budget, rng))[0] == STOCHASTIC
        for _ in range(2000)
    )

    assert wrong == 0


def test_the_order_of_the_pairs_is_the_rule():
    """A decision reads the first n pairs, not the n that happened to finish.

    The same flips, moved to the front, stop the run at the first checkpoint.
    Left at the back they never fire one. If a decision read whatever had
    completed under concurrency, the analysed count would be random and the
    correction would no longer cover it.
    """
    plan = plan_sequential(0.05)
    flips = plan.stochastic_at_least[plan.checkpoints[0]]
    early = [True] * flips + [False] * (plan.budget - flips)
    late = [False] * (plan.budget - flips) + [True] * flips

    assert decide_sequentially(plan, early) == (STOCHASTIC, plan.checkpoints[0])
    assert decide_sequentially(plan, late)[1] == plan.budget


def test_a_checkpoint_nobody_declared_is_refused():
    """Choosing where to look after seeing the data is the peeking, renamed."""
    plan = plan_sequential(0.05)

    with pytest.raises(ValueError, match="not a declared checkpoint"):
        plan.call_at(plan.budget - 1, 0)


def test_an_impossible_flip_count_is_refused():
    plan = plan_sequential(0.05)

    with pytest.raises(ValueError, match="impossible"):
        plan.call_at(plan.budget, plan.budget + 1)


def test_running_out_of_pairs_is_undecided_rather_than_optimistic():
    plan = plan_sequential(0.05)

    call, seen = decide_sequentially(plan, [False] * (plan.budget - 1))

    assert call == UNDECIDED
    assert seen == plan.budget - 1


def test_a_perfect_run_certifies_at_the_last_checkpoint_and_not_before():
    plan = plan_sequential(0.05)

    assert decide_sequentially(plan, [False] * plan.budget) == (
        DETERMINISTIC, plan.budget,
    )
    for checkpoint in plan.checkpoints[:-1]:
        assert plan.call_at(checkpoint, 0) is None


@pytest.mark.parametrize("epsilon", [0.01, 0.05, 0.10, 0.25])
def test_the_budget_tracks_the_tolerance_it_was_asked_for(epsilon):
    plan = plan_sequential(epsilon)

    assert (1 - epsilon) ** plan.budget <= plan.alpha / 2
    assert (1 - epsilon) ** (plan.budget - 1) > plan.alpha / 2, "and no larger"


def test_more_looks_do_not_make_certification_more_expensive():
    """The asymmetry, stated as a test rather than left in the ADR."""
    budgets = {plan_sequential(0.05, looks=looks).budget for looks in (1, 2, 4, 8)}

    assert len(budgets) == 1


def test_more_looks_stop_an_unstable_route_sooner():
    rng = random.Random(99)
    spent = {}
    for looks in (1, 8):
        plan = plan_sequential(0.05, looks=looks)
        spent[looks] = sum(
            decide_sequentially(plan, _outcomes(0.30, plan.budget, rng))[1]
            for _ in range(400)
        )

    assert spent[8] < spent[1]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"epsilon": 0.0}, "epsilon"),
        ({"epsilon": 1.0}, "epsilon"),
        ({"epsilon": 0.05, "alpha": 0.0}, "alpha"),
        ({"epsilon": 0.05, "looks": 0}, "at least one look"),
        ({"epsilon": 0.05, "budget": 2, "looks": 4}, "cannot support"),
    ],
)
def test_a_plan_refuses_what_it_cannot_honour(kwargs, message):
    with pytest.raises(ValueError, match=message):
        plan_sequential(**kwargs)


def test_a_budget_too_small_to_certify_says_so_rather_than_pretending():
    """A caller who caps the spend below the tolerance gets `undecided`."""
    plan = plan_sequential(0.05, budget=20)

    assert plan.certify_at_most == -1
    assert decide_sequentially(plan, [False] * 20) == (UNDECIDED, 20)


def test_a_plan_built_by_hand_still_has_to_make_sense():
    """`plan_sequential` cannot produce these, and a caller constructing a
    plan directly can. Refused rather than failing later inside a decision."""
    from agentverity.sequential import SequentialPlan

    with pytest.raises(ValueError, match="at least one checkpoint"):
        SequentialPlan(0.05, 0.05, (), 0, {})
    with pytest.raises(ValueError, match="ascending and distinct"):
        SequentialPlan(0.05, 0.05, (50, 20), 0, {20: 5, 50: 8})


def test_running_out_before_the_first_look_is_undecided_too():
    """A run that stops early has decided nothing, wherever it stopped.

    The tail case was covered and the head case was not, and they return from
    different places.
    """
    plan = plan_sequential(0.05)
    short = plan.checkpoints[0] - 1

    assert decide_sequentially(plan, [False] * short) == (UNDECIDED, short)


@pytest.mark.parametrize(
    ("budget", "certify_at_most"), [(None, 0), (200, 3), (500, 15)]
)
def test_the_closed_form_is_a_property_of_the_default_not_of_the_design(
    budget, certify_at_most
):
    """The commit message for the first draft overstated this.

    Certifying at the default budget needs zero flips, so no early look can
    have fired and the rate is exactly `(1 - p) ** n`. A larger budget allows
    some flips, and then only the general argument holds: one exact binomial
    test at `alpha / 2`, which early stopping can only make less likely to be
    reached.
    """
    plan = plan_sequential(0.05, budget=budget)

    assert plan.certify_at_most == certify_at_most
    assert plan.certification_is_closed_form is (certify_at_most == 0)


@pytest.mark.parametrize("budget", [None, 200, 500])
def test_the_certification_test_stays_inside_its_budget_at_any_size(budget):
    """The general guarantee, asserted where the closed form does not reach."""
    from agentverity.sequential import _at_most

    plan = plan_sequential(0.05, budget=budget)

    assert _at_most(plan.budget, plan.certify_at_most, 0.05) <= plan.alpha / 2


def test_running_out_reports_what_was_collected_not_what_was_planned():
    """The docstring claimed the budget. A spend that did not happen."""
    plan = plan_sequential(0.05)

    assert decide_sequentially(plan, [False] * 40) == (UNDECIDED, 40)
