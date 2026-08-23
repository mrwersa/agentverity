"""Tests for agentverity.meter."""

from __future__ import annotations

import pytest

from agentverity.adapters import from_callable
from agentverity.meter import (
    best_case_admission_pairs,
    measure,
    pairs_for_deterministic_call,
    score_runs,
    wilson_ci,
)
from agentverity.observation import Observation


class TestWilsonCI:
    def test_zero_trials(self):
        lo, hi = wilson_ci(0, 0)
        assert lo == 0.0
        assert hi == 0.0

    def test_all_successes(self):
        lo, hi = wilson_ci(10, 10)
        assert lo > 0.5
        assert hi <= 1.0

    def test_all_failures(self):
        lo, hi = wilson_ci(0, 10)
        assert lo == 0.0
        assert hi < 0.5

    def test_half(self):
        lo, hi = wilson_ci(5, 10)
        assert lo < 0.5 < hi

    def test_bounds_in_unit_interval(self):
        for s in range(11):
            lo, hi = wilson_ci(s, 10)
            assert 0.0 <= lo <= hi <= 1.0


class TestAdmissionPlanning:
    def test_fixed_rate_projection_does_not_round_candidate_flip_counts(self):
        """The advertised minimum must not rely on a saw-toothed rounded rate."""
        assert pairs_for_deterministic_call(0.05, flip_rate=2 / 73) == 358

    @pytest.mark.parametrize(
        ("flips", "expected"),
        [(0, 73), (1, 110), (3, 173), (4, 202), (8, 311)],
    )
    def test_best_case_planning_holds_the_observed_flip_count_fixed(
        self, flips, expected
    ):
        """The paper's canonical continuation examples use the library rule."""
        assert best_case_admission_pairs(0.05, flips=flips, pairs=73) == expected

    def test_best_case_planning_respects_a_predeclared_pair_budget(self):
        """A caller can reject early only when the endpoint cannot admit."""
        assert best_case_admission_pairs(0.05, flips=4, pairs=73, max_pairs=201) is None
        assert best_case_admission_pairs(0.05, flips=4, pairs=73, max_pairs=202) == 202

    def test_best_case_minima_match_the_wilson_interval(self):
        """The score inversion and the interval implementation share a boundary."""
        for epsilon in (0.01, 0.05, 0.1):
            for z in (1.64, 1.96, 2.58):
                for flips in range(11):
                    observed = max(11, flips)
                    needed = best_case_admission_pairs(
                        epsilon, flips=flips, pairs=observed, z=z
                    )
                    assert needed is not None
                    assert wilson_ci(flips, needed, z)[1] < epsilon
                    if needed > observed:
                        assert wilson_ci(flips, needed - 1, z)[1] >= epsilon

    @pytest.mark.parametrize(
        ("kwargs", "error", "message"),
        [
            ({"epsilon": 0.0, "flips": 0, "pairs": 1}, ValueError, "epsilon"),
            ({"epsilon": 0.05, "flips": -1, "pairs": 1}, ValueError, "flips"),
            ({"epsilon": 0.05, "flips": 2, "pairs": 1}, ValueError, "flips"),
            ({"epsilon": 0.05, "flips": 0, "pairs": 0}, ValueError, "pairs"),
            (
                {"epsilon": 0.05, "flips": 0, "pairs": 2, "max_pairs": 1},
                ValueError,
                "max_pairs",
            ),
            ({"epsilon": 0.05, "flips": 0.5, "pairs": 1}, TypeError, "flips"),
        ],
    )
    def test_best_case_planning_refuses_invalid_counts(self, kwargs, error, message):
        """Counts and budgets describe real observed pairs, not approximations."""
        with pytest.raises(error, match=message):
            best_case_admission_pairs(**kwargs)


class TestMeasure:
    def test_deterministic_agent(self):
        """A deterministic agent should meter as deterministic with enough inputs."""
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        inputs = [f"input_{i}" for i in range(200)]
        inputs.append("a secret")
        agent = from_callable(fn)
        result = measure(agent, inputs, k=5)
        assert result.pair_flips == 0
        assert result.call == "verdict-deterministic"
        assert result.flip_rate == 0.0

    def test_stochastic_agent(self):
        """A stochastic agent should meter as stochastic."""
        import random
        rng = random.Random(42)

        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            if rng.random() < 0.3:
                v = "allow" if v == "block" else "block"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = measure(agent, ["hello", "world", "foo"], k=5)
        assert result.pair_flips > 0
        assert result.call == "verdict-stochastic"

    def test_k_must_be_at_least_2(self):
        def fn(x: str) -> str:
            return "ok"

        agent = from_callable(fn)
        with pytest.raises(ValueError, match="k must be >= 2"):
            measure(agent, ["hi"], k=1)

    def test_empty_inputs_rejected(self):
        agent = from_callable(lambda x: "ok")
        with pytest.raises(ValueError, match="inputs"):
            measure(agent, [])

    def test_invalid_epsilon_rejected(self):
        agent = from_callable(lambda x: "ok")
        with pytest.raises(ValueError, match="epsilon"):
            measure(agent, ["hi"], epsilon=0)

    def test_ci_uses_disjoint_pairs(self):
        agent = from_callable(lambda x: {"verdict": "allow"})
        result = measure(agent, ["a", "b", "c"], k=5)
        assert result.pair_trials == 6

    def test_inputs_with_flip(self):
        """inputs_with_flip counts inputs that had at least one flip."""
        import random
        rng = random.Random(99)

        def fn(x: str) -> dict:
            # only flip on "secret"
            if "secret" in x.lower():
                v = "block" if rng.random() < 0.5 else "allow"
            else:
                v = "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = measure(agent, ["hello", "a secret"], k=6)
        assert result.inputs_with_flip >= 1

    def test_layer_text(self):
        """Measuring on the text layer picks up token-level variation."""
        import random
        rng = random.Random(7)

        def fn(x: str) -> dict:
            # verdict is stable, text varies
            v = "allow"
            suffix = str(rng.randint(0, 99))
            return {"text": f"allow_{suffix}", "verdict": v}

        agent = from_callable(fn)
        result_text = measure(agent, ["hello"], k=5, layer="text")
        result_verdict = measure(agent, ["hello"], k=5, layer="verdict")
        assert result_text.pair_flips > 0
        assert result_verdict.pair_flips == 0


class TestScoreRuns:
    def test_scores_precollected_series(self):
        result = score_runs(
            [
                [Observation(verdict="allow"), Observation(verdict="allow")],
                [Observation(verdict="allow"), Observation(verdict="block")],
            ],
            k=2,
            epsilon=0.1,
        )
        assert result.pair_trials == 2
        assert result.pair_flips == 1
        assert result.inputs_with_flip == 1

    def test_rejects_a_series_carrying_no_pair(self):
        """Series lengths may differ so a suite can size repeats per route, but
        one observation yields no comparison and would quietly weaken the
        interval rather than failing."""
        with pytest.raises(ValueError, match="at least two observations"):
            score_runs(
                [[Observation(verdict="allow")]],
                k=2,
            )

    def test_accepts_series_of_differing_lengths(self):
        result = score_runs(
            [
                [Observation(verdict="allow")] * 2,
                [Observation(verdict="allow")] * 6,
            ],
            k=2,
        )
        assert result.pair_trials == 1 + 3
