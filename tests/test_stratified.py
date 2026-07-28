"""Tests for per-route stability."""

from __future__ import annotations

import random

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    RunConfig,
    from_callable,
    run,
    stratify_runs,
)
from agentverity.observation import Observation


def series(decision: str, keys: list[str]) -> tuple[str, list[Observation]]:
    """One repeat series for a case whose intended decision is ``decision``."""
    return decision, [Observation(verdict=key, text=key, tools=()) for key in keys]


class TestTheVerdictComesFromTheBoundNotTheRate:
    """The whole package exists to stop a point estimate being read as a
    conclusion, so the per-route view must not reintroduce that error.

    One flip in thirteen pairs is an observed rate of 7.7%, above a 5%
    threshold, and the interval still spans 0.014 to 0.333. It is undecided.
    """

    @staticmethod
    def route_for(flips: int, pairs: int, epsilon: float = 0.05):
        # Two observations per pair, alternating to produce exactly `flips`.
        keys: list[str] = []
        for index in range(pairs):
            keys.extend(["a", "b"] if index < flips else ["a", "a"])
        result = stratify_runs(
            [series("approve", keys)], k=len(keys), epsilon=epsilon
        )
        return result.routes[0]

    @pytest.mark.parametrize(
        "flips, pairs, expected",
        [
            (0, 13, "undecided (add repeats or inputs)"),
            (1, 13, "undecided (add repeats or inputs)"),
            (2, 13, "undecided (add repeats or inputs)"),
            (3, 13, "verdict-stochastic"),
            (0, 73, "verdict-deterministic"),
        ],
    )
    def test_pinned_classifications(self, flips, pairs, expected):
        assert self.route_for(flips, pairs).call == expected

    def test_one_flip_in_thirteen_is_undecided_despite_the_rate(self):
        route = self.route_for(1, 13)
        assert route.flip_rate > route.epsilon
        assert route.decided is False

    def test_a_clean_route_reports_the_pairs_it_still_needs(self):
        route = self.route_for(0, 13)
        assert route.decided is False
        assert route.pairs_needed == 73


def test_per_route_trials_sum_to_the_pooled_trials():
    """Costing no extra calls is a claim, so it is checked rather than stated."""
    result = stratify_runs(
        [
            series("approve", ["a"] * 8),
            series("deny", ["d"] * 8),
            series("deny", ["d"] * 8),
        ],
        k=8,
        epsilon=0.05,
    )
    assert sum(route.pair_trials for route in result.routes) == 3 * 4


def test_routes_are_keyed_by_intended_decision_not_by_what_the_agent_returned():
    """A route stays identifiable even when the agent answers it wrongly,
    otherwise a badly broken route would vanish from the table."""
    result = stratify_runs([series("deny", ["approve"] * 4)], k=4, epsilon=0.05)

    assert [route.decision for route in result.routes] == ["deny"]
    assert result.routes[0].pair_flips == 0


def test_cases_are_counted_per_route():
    result = stratify_runs(
        [series("approve", ["a"] * 4), series("approve", ["a"] * 4), series("deny", ["d"] * 4)],
        k=4,
        epsilon=0.05,
    )
    counts = {route.decision: route.cases for route in result.routes}
    assert counts == {"approve": 2, "deny": 1}


class TestFlipPairs:
    def test_a_flip_records_both_observed_decisions(self):
        result = stratify_runs([series("review", ["review", "deny"])], k=2, epsilon=0.05)

        assert result.flip_pairs[0].decisions == ("deny", "review")
        assert result.flip_pairs[0].count == 1

    def test_pairs_are_unordered_so_one_finding_is_not_counted_twice(self):
        result = stratify_runs(
            [series("review", ["review", "deny", "deny", "review"])], k=4, epsilon=0.05
        )

        assert len(result.flip_pairs) == 1
        assert result.flip_pairs[0].count == 2

    def test_pairs_are_ordered_by_how_often_they_occur(self):
        result = stratify_runs(
            [
                series("review", ["review", "deny", "review", "deny"]),
                series("approve", ["approve", "escalate", "approve", "approve"]),
            ],
            k=4,
            epsilon=0.05,
        )

        assert [pair.render() for pair in result.flip_pairs] == [
            "deny <-> review",
            "approve <-> escalate",
        ]
        assert result.flip_pairs[0].count == 2

    def test_a_stable_run_reports_no_pairs(self):
        result = stratify_runs([series("approve", ["a"] * 4)], k=4, epsilon=0.05)
        assert result.flip_pairs == ()

    def test_render_names_both_sides(self):
        result = stratify_runs([series("review", ["review", "deny"])], k=2, epsilon=0.05)
        assert result.flip_pairs[0].render() == "deny <-> review"


class TestAdviceRanksAConclusionAboveAnAbsence:
    """A stochastic route is a finding. An undecided route is missing
    evidence. Presenting them alike would hide the difference that decides
    what a reader does next."""

    def test_a_stochastic_route_is_named_first(self):
        result = stratify_runs(
            [
                series("review", ["review", "deny"] * 20),
                series("approve", ["a"] * 40),
            ],
            k=40,
            epsilon=0.05,
        )
        assert result.stochastic == ("review",)
        assert "move more than epsilon" in result.advice

    def test_undecided_routes_are_reported_with_the_evidence_they_need(self):
        result = stratify_runs([series("approve", ["a"] * 26)], k=26, epsilon=0.05)

        assert result.undecided == ("approve",)
        assert "lack the evidence" in result.advice
        assert "73 pairs" in result.advice

    def test_a_fully_certified_suite_says_so(self):
        result = stratify_runs([series("approve", ["a"] * 150)], k=150, epsilon=0.05)

        assert result.deterministic == ("approve",)
        assert result.advice.startswith("every route carries enough evidence")


class TestRunIntegration:
    """The feature has to appear without anyone opting in, and it must not
    change what the pooled meter reports."""

    @staticmethod
    def build():
        def agent(text):
            if text.startswith("routine"):
                return {"verdict": "approve"}
            if text.startswith("prohibited"):
                return {"verdict": "deny"}
            return {"verdict": random.choice(["review", "deny"])}

        suite = DecisionSuite(
            contract=DecisionContract(allowed={"approve", "review", "deny"}),
            cases=(
                DecisionCase("routine one", "approve"),
                DecisionCase("ambiguous one", "review"),
                DecisionCase("prohibited one", "deny"),
            ),
        )
        return from_callable(agent), suite

    def test_a_suite_produces_route_stability_with_no_extra_flag(self):
        agent, suite = self.build()
        random.seed(3)
        result = run(agent, suite=suite, relations=[], config=RunConfig(k=10, epsilon=0.05))

        assert result.route_stability is not None
        assert len(result.route_stability.routes) == 3

    def test_the_unstable_route_is_named_where_the_pooled_meter_cannot(self):
        agent, suite = self.build()
        random.seed(3)
        result = run(agent, suite=suite, relations=[], config=RunConfig(k=26, epsilon=0.05))

        assert result.route_stability.stochastic == ("review",)
        assert "review" in result.summary()

    def test_too_few_pairs_leaves_a_coin_flip_route_undecided_not_clean(self):
        """At k=10 the `review` case yields five pairs, and a genuinely 50/50
        route can show zero flips across them by luck. Reporting that as
        deterministic would be the failure this package is named for."""
        agent, suite = self.build()
        random.seed(3)
        result = run(agent, suite=suite, relations=[], config=RunConfig(k=10, epsilon=0.05))

        route = next(
            r for r in result.route_stability.routes if r.decision == "review"
        )
        assert route.pair_flips == 0
        assert route.pair_trials == 5
        assert route.decided is False

    def test_route_trials_reconcile_with_the_pooled_meter(self):
        agent, suite = self.build()
        random.seed(3)
        result = run(agent, suite=suite, relations=[], config=RunConfig(k=10, epsilon=0.05))

        assert sum(r.pair_trials for r in result.route_stability.routes) == (
            result.meter.pair_trials
        )
        assert sum(r.pair_flips for r in result.route_stability.routes) == (
            result.meter.pair_flips
        )

    def test_a_run_without_a_suite_has_no_route_stability(self):
        result = run(
            from_callable(lambda text: {"verdict": "approve"}),
            ["a", "b"],
            relations=[],
            config=RunConfig(k=4, epsilon=0.5),
        )
        assert result.route_stability is None

    def test_the_report_warns_that_intervals_are_not_joint(self):
        agent, suite = self.build()
        random.seed(3)
        result = run(agent, suite=suite, relations=[], config=RunConfig(k=10, epsilon=0.05))

        assert "separate 95% statement" in result.summary()


def test_a_short_series_is_rejected():
    with pytest.raises(ValueError, match="k must be >= 2"):
        stratify_runs([series("approve", ["a"])], k=1, epsilon=0.05)


def test_a_series_that_does_not_match_k_is_rejected():
    with pytest.raises(ValueError, match="exactly k=4"):
        stratify_runs([series("approve", ["a", "a"])], k=4, epsilon=0.05)


def test_an_invalid_epsilon_is_rejected():
    with pytest.raises(ValueError, match="epsilon must be between"):
        stratify_runs([series("approve", ["a", "a"])], k=2, epsilon=1.5)


def test_the_result_serialises():
    payload = stratify_runs(
        [series("review", ["review", "deny"])], k=2, epsilon=0.05
    ).to_dict()

    assert payload["routes"][0]["decision"] == "review"
    assert payload["flip_pairs"][0]["decisions"] == ["deny", "review"]
    assert payload["epsilon"] == 0.05
