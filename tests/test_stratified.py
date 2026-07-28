"""Tests for per-route stability."""

from __future__ import annotations

import random
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    RunConfig,
    builtin_relations,
    from_callable,
    load_decision_suite,
    run,
    run_result_to_dict,
    run_result_to_junit_xml,
    run_result_to_otel_attributes,
    stratify_runs,
)
from agentverity.observation import Observation
from agentverity.snapshot import SnapshotRefused, create_snapshot
from agentverity.stratified import (
    plan_route_repeats,
    render_plan,
    stratify_relations,
)


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

    def test_a_route_with_a_flip_does_not_receive_a_clean_route_budget(self):
        route = self.route_for(1, 13)
        assert route.pairs_needed is None


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

    def test_a_flipping_but_undecided_route_gets_no_clean_route_budget(self):
        result = stratify_runs(
            [series("approve", ["a", "b"] + ["a"] * 24)],
            k=26,
            epsilon=0.05,
        )

        assert result.undecided == ("approve",)
        assert "may need more evidence or resolve as stochastic" in result.advice
        assert "73 pairs" not in result.advice

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

    def test_a_failed_meter_case_does_not_disappear_from_its_route(self):
        def agent(text):
            if text == "review":
                raise RuntimeError("provider unavailable")
            return {"verdict": "approve"}

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "review"},
            ),
            cases=(
                DecisionCase("approve", "approve"),
                DecisionCase("review", "review"),
            ),
        )
        result = run(
            from_callable(agent),
            suite=suite,
            relations=[],
            config=RunConfig(k=2, epsilon=0.5, error_policy="record"),
        )
        review = next(
            route
            for route in result.route_stability.routes
            if route.decision == "review"
        )

        assert result.status == "incomplete"
        assert review.cases == 1
        assert review.pair_trials == 0
        assert review.call == "undecided (add repeats or inputs)"

    def test_the_report_warns_that_intervals_are_not_joint(self):
        agent, suite = self.build()
        random.seed(3)
        result = run(agent, suite=suite, relations=[], config=RunConfig(k=10, epsilon=0.05))

        assert "separate 95% statement" in result.summary()

    def test_a_pooled_result_names_its_undecided_route_limit(self):
        suite = DecisionSuite(
            contract=DecisionContract(allowed={"approve", "review", "deny"}),
            cases=(
                DecisionCase("approve one", "approve"),
                DecisionCase("approve two", "approve"),
                DecisionCase("review one", "review"),
                DecisionCase("review two", "review"),
                DecisionCase("deny one", "deny"),
                DecisionCase("deny two", "deny"),
            ),
        )
        result = run(
            from_callable(lambda text: {"verdict": text.split()[0]}),
            suite=suite,
            relations=[],
            config=RunConfig(k=26, epsilon=0.05),
        )

        assert result.meter.call == "verdict-deterministic"
        assert result.route_stability.undecided == ("approve", "deny", "review")
        assert result.status == "deterministic"
        assert result.headline.startswith("TRUSTWORTHY AT POOLED LEVEL")

    def test_a_stochastic_route_overrides_a_deterministic_pool(self):
        calls: dict[str, int] = {}

        def agent(text):
            calls[text] = calls.get(text, 0) + 1
            if text == "review":
                verdict = "review" if calls[text] % 2 else "deny"
            else:
                verdict = "approve"
            return {"verdict": verdict}

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "review", "deny"},
                required={"approve", "review"},
            ),
            cases=(
                DecisionCase("approve one", "approve"),
                DecisionCase("approve two", "approve"),
                DecisionCase("approve three", "approve"),
                DecisionCase("review", "review"),
            ),
        )
        result = run(
            from_callable(agent),
            suite=suite,
            relations=[],
            config=RunConfig(
                k=26,
                epsilon=0.5,
                blindness_threshold=0.99,
            ),
        )

        assert result.meter.call == "verdict-deterministic"
        assert result.route_stability.stochastic == ("review",)
        assert result.is_stochastic
        assert result.status == "stochastic"
        assert "pooled evidence hides" in result.headline
        with pytest.raises(SnapshotRefused, match="review"):
            create_snapshot(result, approved=True)

    def test_a_declared_target_is_a_release_condition(self):
        calls: dict[str, int] = {}

        def agent(text):
            calls[text] = calls.get(text, 0) + 1
            if text == "deny" and calls[text] == 2:
                return {"verdict": "approve"}
            return {"verdict": text}

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "deny"},
                stability_targets={"deny": 0.05},
            ),
            cases=(
                DecisionCase("approve", "approve"),
                DecisionCase("deny", "deny"),
            ),
        )
        result = run(
            from_callable(agent),
            suite=suite,
            relations=[],
            config=RunConfig(k=2, epsilon=0.5),
        )

        assert result.meter.call == "verdict-deterministic"
        assert result.targeted_undecided == ("deny",)
        assert result.status == "undecided"
        assert result.headline.startswith("NO ANSWER YET")
        assert result.meter.repeats < result.meter.max_repeats
        assert "repeats:" in result.summary()
        assert "by route" in result.summary()
        with pytest.raises(SnapshotRefused, match="targets remain undecided"):
            create_snapshot(result, approved=True)

        report = run_result_to_dict(result)
        assert report["guidance"]["targeted_undecided_routes"] == 1
        assert report["route_plans"]
        assert report["meter"]["max_repeats"] == result.meter.max_repeats

        root = ET.fromstring(run_result_to_junit_xml(result))
        route_error = root.find(
            "./testcase[@name='preflight.route_stability']/error"
        )
        assert route_error is not None
        assert "deny" in route_error.attrib["message"]

        telemetry = run_result_to_otel_attributes(result)
        assert telemetry["agentverity.route_stability.targeted_undecided"] == 1
        assert telemetry["agentverity.route_plan.calls"] == sum(
            plan.calls for plan in result.route_plans
        )
        assert "deny" not in repr(telemetry)

    def test_a_settled_target_allows_the_normal_release_path(self):
        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "deny"},
                stability_targets={"deny": 0.2},
            ),
            cases=(
                DecisionCase("approve", "approve"),
                DecisionCase("deny", "deny"),
            ),
        )
        result = run(
            from_callable(lambda text: {"verdict": text}),
            suite=suite,
            relations=[],
            config=RunConfig(k=2, epsilon=0.5),
        )

        assert result.targeted_undecided == ()
        assert result.targeted_stochastic == ()
        assert result.status == "deterministic"
        assert create_snapshot(result, approved=True)

    def test_exceeding_a_declared_target_fails_the_release_policy(self):
        calls: dict[str, int] = {}

        def agent(text):
            calls[text] = calls.get(text, 0) + 1
            if text == "deny":
                return {"verdict": "deny" if calls[text] % 2 else "review"}
            return {"verdict": "approve"}

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "review", "deny"},
                required={"approve", "deny"},
                stability_targets={"deny": 0.2},
            ),
            cases=(
                DecisionCase("approve", "approve"),
                DecisionCase("deny", "deny"),
            ),
        )
        result = run(
            from_callable(agent),
            suite=suite,
            relations=[],
            config=RunConfig(k=2, epsilon=0.5),
        )

        assert result.targeted_stochastic == ("deny",)
        assert result.status == "target-failed"
        assert result.headline.startswith("NOT READY")
        root = ET.fromstring(run_result_to_junit_xml(result))
        assert root.find(
            "./testcase[@name='preflight.route_stability']/failure"
        ) is not None
        assert run_result_to_dict(result)["guidance"][
            "targeted_stochastic_routes"
        ] == 1
        assert run_result_to_otel_attributes(result)[
            "agentverity.route_stability.targeted_stochastic"
        ] == 1

    def test_an_explicit_budget_is_a_hard_cap_before_agent_calls(self):
        calls = 0

        def agent(text):
            nonlocal calls
            calls += 1
            return {"verdict": text}

        suite = DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "deny"},
                stability_targets={"deny": 0.05},
            ),
            cases=(
                DecisionCase("approve", "approve"),
                DecisionCase("deny", "deny"),
            ),
        )

        with pytest.raises(ValueError, match="above budget=10"):
            run(
                from_callable(agent),
                suite=suite,
                relations=[],
                config=RunConfig(budget=10, epsilon=0.5),
            )
        assert calls == 0

    def test_machine_reports_carry_route_evidence_without_labels_in_shared_surfaces(
        self,
    ):
        agent, suite = self.build()
        random.seed(3)
        result = run(
            agent,
            suite=suite,
            relations=[],
            config=RunConfig(k=26, epsilon=0.05),
        )

        report = run_result_to_dict(result)
        assert report["route_stability"]["stochastic"] == ["review"]
        assert report["guidance"]["stochastic_routes"] == 1
        assert report["status"] == "stochastic"

        junit = run_result_to_junit_xml(result)
        assert "preflight.route_stability" in junit
        route_case = ET.fromstring(junit).find(
            "./testcase[@name='preflight.route_stability']/system-out"
        )
        assert route_case is not None
        assert "stochastic=1" in route_case.text
        assert "review" not in route_case.text

        telemetry = run_result_to_otel_attributes(result)
        assert telemetry["agentverity.route_stability.stochastic"] == 1
        assert "review" not in repr(telemetry)


def test_a_short_series_is_rejected():
    with pytest.raises(ValueError, match="k must be >= 2"):
        stratify_runs([series("approve", ["a"])], k=1, epsilon=0.05)


def test_a_series_carrying_no_pair_is_rejected():
    with pytest.raises(ValueError, match="at least two observations"):
        stratify_runs([series("approve", ["a"])], k=2, epsilon=0.05)


def test_routes_may_carry_different_repeat_counts():
    """Sizing repeats per route is the point of declaring targets, so series
    of differing length have to be first-class rather than an error."""
    result = stratify_runs(
        [series("approve", ["a"] * 4), series("deny", ["d"] * 10)],
        k=4,
        epsilon=0.05,
    )
    trials = {route.decision: route.pair_trials for route in result.routes}
    assert trials == {"approve": 2, "deny": 5}


def test_an_invalid_epsilon_is_rejected():
    with pytest.raises(ValueError, match="epsilon must be between"):
        stratify_runs([series("approve", ["a", "a"])], k=2, epsilon=1.5)


def test_an_invalid_layer_is_rejected_even_when_a_series_failed():
    with pytest.raises(ValueError, match="unknown observation layer"):
        stratify_runs([("approve", None)], k=2, layer="reasoning")


def test_empty_series_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        stratify_runs([], k=2, epsilon=0.05)


@pytest.mark.parametrize("decision", ["", None])
def test_invalid_intended_decisions_are_rejected(decision):
    with pytest.raises(ValueError, match="non-empty string"):
        stratify_runs(
            [
                (
                    decision,
                    [Observation(verdict="a"), Observation(verdict="a")],
                )
            ],
            k=2,
        )


def test_a_failed_case_remains_visible_with_no_usable_pairs():
    result = stratify_runs(
        [
            series("approve", ["approve", "approve"]),
            ("review", None),
        ],
        k=2,
        epsilon=0.05,
    )
    review = next(route for route in result.routes if route.decision == "review")

    assert review.cases == 1
    assert review.pair_trials == 0
    assert review.call == "undecided (add repeats or inputs)"


def test_the_readme_example_reconciles_with_the_pooled_meter():
    """Pin every number in the public per-route example."""
    from agentverity.meter import score_runs

    stable_approve = [series("approve", ["approve"] * 26)[1] for _ in range(2)]
    stable_deny = [series("deny", ["deny"] * 26)[1] for _ in range(2)]
    flipping_review = [
        series("review", ["review", "deny"] * 5 + ["review"] * 16)[1]
        for _ in range(2)
    ]
    all_series = stable_approve + stable_deny + flipping_review
    stratified = stratify_runs(
        [
            *(("approve", observations) for observations in stable_approve),
            *(("deny", observations) for observations in stable_deny),
            *(("review", observations) for observations in flipping_review),
        ],
        k=26,
        epsilon=0.05,
    )
    pooled = score_runs(all_series, k=26, epsilon=0.05)
    routes = {route.decision: route for route in stratified.routes}

    assert pooled.pair_trials == 78
    assert pooled.pair_flips == 10
    assert pooled.flip_rate == pytest.approx(10 / 78)
    assert routes["approve"].ci_high == pytest.approx(0.128733, abs=0.000001)
    assert routes["deny"].ci_high == pytest.approx(0.128733, abs=0.000001)
    assert routes["review"].ci_low == pytest.approx(0.224284, abs=0.000001)
    assert routes["review"].ci_high == pytest.approx(0.574655, abs=0.000001)
    assert stratified.flip_pairs[0].count == 10


def test_the_result_serialises():
    payload = stratify_runs(
        [series("review", ["review", "deny"])], k=2, epsilon=0.05
    ).to_dict()

    assert payload["routes"][0]["decision"] == "review"
    assert payload["flip_pairs"][0]["decisions"] == ["deny", "review"]
    assert payload["epsilon"] == 0.05


class TestPerRouteTolerances:
    """A declared target is a numerical release policy for one route."""

    def test_a_route_is_judged_against_its_own_target(self):
        result = stratify_runs(
            [series("deny", ["d"] * 80), series("approve", ["a"] * 80)],
            k=80,
            epsilon=0.10,
            targets={"deny": 0.05},
        )
        by_route = {route.decision: route for route in result.routes}

        assert by_route["approve"].epsilon == 0.10
        assert by_route["deny"].epsilon == 0.05

    def test_the_same_evidence_can_clear_a_loose_target_and_not_a_tight_one(self):
        """40 pairs with no flips bounds the rate at 8.8%. That certifies at
        10% and does not at 5%, which is the whole reason targets exist."""
        both = stratify_runs(
            [series("approve", ["a"] * 80), series("deny", ["d"] * 80)],
            k=80,
            epsilon=0.10,
            targets={"deny": 0.05},
        )
        by_route = {route.decision: route for route in both.routes}

        assert by_route["approve"].call == "verdict-deterministic"
        assert by_route["deny"].decided is False

    def test_routes_without_a_target_use_the_run_default(self):
        result = stratify_runs(
            [series("approve", ["a"] * 4)], k=4, epsilon=0.2, targets={"deny": 0.01}
        )
        assert result.routes[0].epsilon == 0.2


class TestBudgetPlanning:
    """Sizing per route is what makes a tight target affordable."""

    def test_a_tight_target_costs_more_repeats_than_a_loose_one(self):
        plans = {
            plan.decision: plan
            for plan in plan_route_repeats(
                ["approve", "deny"], epsilon=0.05, targets={"deny": 0.01}
            )
        }
        assert plans["approve"].pairs_needed == 73
        assert plans["deny"].pairs_needed == 381
        assert plans["deny"].repeats_each > plans["approve"].repeats_each

    def test_more_cases_on_a_route_means_fewer_repeats_each(self):
        one = plan_route_repeats(["deny"], epsilon=0.05)[0]
        many = plan_route_repeats(["deny"] * 5, epsilon=0.05)[0]

        assert many.repeats_each < one.repeats_each
        assert many.cases == 5

    def test_more_cases_improve_breadth_not_total_call_cost(self):
        one = plan_route_repeats(["deny"], epsilon=0.01)[0]
        two = plan_route_repeats(["deny", "deny"], epsilon=0.01)[0]

        assert one.calls == 762
        assert two.calls == 764

    def test_repeats_are_even_because_a_pair_needs_two_calls(self):
        for plan in plan_route_repeats(["a", "b", "b"], epsilon=0.3):
            assert plan.repeats_each % 2 == 0
            assert plan.repeats_each >= 2

    def test_sizing_per_route_costs_less_than_one_uniform_k(self):
        """The claim the feature is sold on, so it is measured."""
        intended = ["approve"] * 5 + ["deny"]
        plans = plan_route_repeats(intended, epsilon=0.05, targets={"deny": 0.01})
        sized = sum(plan.calls for plan in plans)
        uniform = max(p.repeats_each for p in plans) * len(intended)

        assert sized < uniform

    def test_an_empty_suite_is_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            plan_route_repeats([], epsilon=0.05)

    def test_an_invalid_epsilon_is_rejected(self):
        with pytest.raises(ValueError, match="epsilon must be between"):
            plan_route_repeats(["a"], epsilon=0)

    def test_minimum_repeats_must_carry_a_pair(self):
        with pytest.raises(ValueError, match="at least 2"):
            plan_route_repeats(["a"], epsilon=0.05, minimum_repeats=1)

    @pytest.mark.parametrize("bad", ["0.05", True])
    def test_a_non_numeric_route_target_is_rejected(self, bad):
        with pytest.raises(TypeError, match="must be a number"):
            plan_route_repeats(["a"], epsilon=0.05, targets={"a": bad})

    @pytest.mark.parametrize("bad", [0, 1])
    def test_an_out_of_range_route_target_is_rejected(self, bad):
        with pytest.raises(ValueError, match="between 0 and 1"):
            plan_route_repeats(["a"], epsilon=0.05, targets={"a": bad})

    def test_the_table_names_every_route_and_totals_the_calls(self):
        plans = plan_route_repeats(["approve", "deny"], epsilon=0.05)
        table = render_plan(plans, compare_uniform=True)

        assert "approve" in table and "deny" in table
        assert "total" in table
        assert "if no pair changes decision" in table
        assert str(sum(plan.calls for plan in plans)) in table

    def test_the_run_floor_is_reflected_in_the_plan(self):
        plan = plan_route_repeats(
            ["approve"],
            epsilon=0.5,
            minimum_repeats=9,
        )[0]
        assert plan.repeats_each == 9
        assert plan.calls == 9

    def test_a_target_without_an_intended_case_is_rejected(self):
        with pytest.raises(ValueError, match="no intended cases"):
            plan_route_repeats(
                ["approve"],
                epsilon=0.05,
                targets={"deny": 0.01},
            )


def test_a_route_plan_serialises():
    payload = plan_route_repeats(["deny"], epsilon=0.05, targets={"deny": 0.01})[0].to_dict()

    assert payload["decision"] == "deny"
    assert payload["target"] == 0.01
    assert payload["pairs_needed"] == 381
    assert payload["calls"] == payload["repeats_each"] * payload["cases"]


class TestTheDocumentedNumbersAreReal:
    """docs/route-evidence.md quotes specific figures. A doc that drifts from
    the code teaches the wrong thing confidently, so the figures are generated
    here rather than trusted."""

    def test_the_evidence_table(self):
        from agentverity.meter import classify_call, wilson_ci

        table = {
            (0, 13): "undecided",
            (1, 13): "undecided",
            (3, 13): "verdict-stochastic",
            (0, 36): "undecided",
            (0, 73): "verdict-deterministic",
        }
        for (flips, pairs), expected in table.items():
            low, high = wilson_ci(flips, pairs)
            assert classify_call(low, high, 0.05).startswith(expected)

    def test_the_budget_comparison(self):
        plans = plan_route_repeats(
            ["approve", "review", "deny"], epsilon=0.05, targets={"deny": 0.01}
        )
        sized = sum(plan.calls for plan in plans)
        uniform = max(plan.repeats_each for plan in plans) * 3

        assert sized == 1054
        assert uniform == 2286

    def test_adding_a_second_case_shares_pairs_without_cutting_total_calls(self):
        one = plan_route_repeats(["card"], epsilon=0.01)[0]
        two = plan_route_repeats(["card", "card"], epsilon=0.01)[0]

        assert one.repeats_each == 762
        assert two.repeats_each == 382
        assert two.calls >= one.calls

    def test_twenty_six_pairs_bounds_the_rate_at_the_documented_value(self):
        from agentverity.meter import wilson_ci

        assert round(wilson_ci(0, 26)[1], 3) == 0.129

    def test_the_documented_plan_is_generated_from_the_bundled_suite(self):
        root = Path(__file__).parents[1]
        suite = load_decision_suite(root / "examples/route_stability_plan.json")
        plans = plan_route_repeats(
            suite.expected,
            epsilon=0.05,
            targets=suite.contract.stability_targets,
        )
        shown = "agentverity — zero-flip call plan\n" + render_plan(
            plans,
            compare_uniform=True,
        )

        assert shown in (root / "docs/route-evidence.md").read_text(
            encoding="utf-8"
        )


class TestProbeCoverage:
    """A relation whose transform returns the input unchanged has tested
    nothing. Counted per route, that becomes an answerable question: was this
    decision ever actually probed, or only appeared to be?"""

    def test_a_route_every_relation_left_alone_is_not_probed(self):
        coverage = stratify_relations(
            ["approve", "deny"],
            [["held", "held"], ["skipped", "skipped"]],
        )
        by_route = {route.decision: route for route in coverage.routes}

        assert by_route["approve"].probed is True
        assert by_route["deny"].probed is False
        assert coverage.unprobed == ("deny",)

    def test_an_unprobed_route_has_no_violation_rate_rather_than_zero(self):
        """Zero would hand a caller the same false green the report refuses
        to print."""
        coverage = stratify_relations(["deny"], [["skipped", "skipped"]])

        assert coverage.routes[0].violation_rate is None
        assert coverage.routes[0].exercised == 0

    def test_violation_rate_counts_only_genuinely_exercised_pairs(self):
        coverage = stratify_relations(
            ["approve"], [["held", "violated", "skipped", "skipped"]]
        )
        route = coverage.routes[0]

        assert route.exercised == 2
        assert route.skipped == 2
        assert route.violation_rate == 0.5

    def test_the_advice_names_vacuous_routes_before_violations(self):
        coverage = stratify_relations(
            ["approve", "deny"],
            [["violated"], ["skipped"]],
        )
        assert "vacuous" in coverage.advice
        assert "deny" in coverage.advice

    def test_violations_are_reported_when_everything_was_probed(self):
        coverage = stratify_relations(["approve"], [["violated"]])
        assert coverage.advice == "relations were violated on: approve"

    def test_a_fully_probed_holding_suite_says_so(self):
        coverage = stratify_relations(["approve"], [["held"]])
        assert coverage.advice == "every route was genuinely perturbed and held"

    def test_no_relations_at_all_is_reported_as_such(self):
        assert stratify_relations([], []).advice == "no relations were run"

    def test_a_failed_input_does_not_count_as_probing(self):
        coverage = stratify_relations(["approve"], [None])
        assert coverage.routes[0].probed is False
        assert coverage.routes[0].cases == 1

    def test_errors_are_counted_and_never_count_as_held(self):
        coverage = stratify_relations(["approve"], [["error", "held"]])
        route = coverage.routes[0]

        assert route.errors == 1
        assert route.exercised == 1

    def test_misaligned_outcomes_are_rejected(self):
        with pytest.raises(ValueError, match="align with intended"):
            stratify_relations(["approve", "deny"], [["held"]])

    def test_probe_coverage_serialises(self):
        payload = stratify_relations(["deny"], [["skipped"]]).to_dict()
        assert payload["unprobed"] == ["deny"]
        assert payload["routes"][0]["probed"] is False


class TestProbeCoverageThroughARun:
    """The scenario this exists for: relations that no-op on plain ASCII while
    the pooled table reports a flawless pass."""

    @staticmethod
    def build():
        rels = [
            relation
            for relation in builtin_relations()
            if relation.name
            in {"normalisation-invariance", "tool-selection-invariance"}
        ]

        def agent(text):
            if "prohibited" in text:
                return {"verdict": "deny"}
            if "caf" in text:
                return {"verdict": "review"}
            return {"verdict": "approve"}

        suite = DecisionSuite(
            contract=DecisionContract(allowed={"approve", "review", "deny"}),
            cases=(
                DecisionCase("routine request", "approve"),
                DecisionCase("café dispute", "review"),
                DecisionCase("prohibited request", "deny"),
            ),
        )
        return from_callable(agent), suite, rels

    def test_pooled_relations_look_clean_while_two_routes_were_never_probed(self):
        agent, suite, rels = self.build()
        result = run(agent, suite=suite, relations=rels, config=RunConfig(k=4, epsilon=0.5))

        assert all(r.violation_rate in (None, 0.0) for r in result.relation_results)
        assert set(result.probe_coverage.unprobed) == {"approve", "deny"}

    def test_the_next_step_names_the_unprobed_routes(self):
        agent, suite, rels = self.build()
        result = run(agent, suite=suite, relations=rels, config=RunConfig(k=4, epsilon=0.5))
        summary = result.summary()

        assert "NOT PROBED" in summary
        assert "NOT EXERCISED" in summary

    def test_a_run_without_a_suite_has_no_probe_coverage(self):
        result = run(
            from_callable(lambda text: {"verdict": "approve"}),
            ["a", "b"],
            config=RunConfig(k=4, epsilon=0.5),
        )
        assert result.probe_coverage is None


class TestMinimumCases:
    """Repeats establish that one input's decision is stable. Distinct cases
    establish that a route was approached from more than one angle. Nothing in
    the statistics can infer the second from the first."""

    @staticmethod
    def suite_with(minimum, cases):
        return DecisionSuite(
            contract=DecisionContract(
                allowed={"approve", "deny"},
                critical={"deny"},
                minimum_cases=minimum,
            ),
            cases=cases,
        )

    def test_a_route_below_its_declared_minimum_is_reported(self):
        suite = self.suite_with(
            {"deny": 3},
            (DecisionCase("routine", "approve"), DecisionCase("prohibited", "deny")),
        )
        result = run(
            from_callable(lambda t: {"verdict": "deny" if "proh" in t else "approve"}),
            suite=suite,
            relations=[],
            config=RunConfig(k=4, epsilon=0.5),
        )
        coverage = result.decision_coverage

        assert coverage.under_cased == (("deny", 1, 3),)
        assert coverage.satisfied is False
        assert "deny has 1 of 3" in coverage.advice

    def test_meeting_the_minimum_satisfies_the_contract(self):
        suite = self.suite_with(
            {"deny": 2},
            (
                DecisionCase("routine", "approve"),
                DecisionCase("prohibited one", "deny"),
                DecisionCase("prohibited two", "deny"),
            ),
        )
        result = run(
            from_callable(lambda t: {"verdict": "deny" if "proh" in t else "approve"}),
            suite=suite,
            relations=[],
            config=RunConfig(k=4, epsilon=0.5),
        )

        assert result.decision_coverage.under_cased == ()
        assert result.decision_coverage.satisfied is True

    def test_the_shortfall_is_counted_from_reviewed_cases_not_observations(self):
        """An agent answering a route often does not mean the suite explores
        it, so the count comes from the cases that were written."""
        suite = self.suite_with(
            {"approve": 2},
            (DecisionCase("routine", "approve"), DecisionCase("prohibited", "deny")),
        )
        # The agent answers `approve` for both inputs, but only one case
        # intends it.
        result = run(
            from_callable(lambda t: {"verdict": "approve"}),
            suite=suite,
            relations=[],
            config=RunConfig(k=4, epsilon=0.5),
        )

        assert result.decision_coverage.under_cased == (("approve", 1, 2),)


def test_the_probing_walkthrough_in_the_docs_still_holds():
    """docs/route-evidence.md shows two of three routes unprobed with a clean
    pooled table. A doc that drifts from the code teaches the wrong thing."""
    rels = [
        relation
        for relation in builtin_relations()
        if relation.name in {"normalisation-invariance", "tool-selection-invariance"}
    ]

    def agent(text):
        if "prohibited" in text:
            return {"verdict": "deny"}
        if "caf" in text:
            return {"verdict": "review"}
        return {"verdict": "approve"}

    suite = DecisionSuite(
        contract=DecisionContract(allowed={"approve", "review", "deny"}),
        cases=(
            DecisionCase("routine request", "approve"),
            DecisionCase("café dispute", "review"),
            DecisionCase("prohibited request", "deny"),
        ),
    )
    result = run(from_callable(agent), suite=suite, relations=rels,
                 config=RunConfig(k=4, epsilon=0.5))

    by_route = {r.decision: r for r in result.probe_coverage.routes}
    assert by_route["approve"].exercised == 0 and by_route["approve"].skipped == 2
    assert by_route["deny"].exercised == 0 and by_route["deny"].skipped == 2
    assert by_route["review"].exercised == 2 and by_route["review"].skipped == 0
    assert all(r.violation_rate in (None, 0.0) for r in result.relation_results)
