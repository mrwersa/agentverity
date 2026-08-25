"""Tests for agentverity.runner."""

from __future__ import annotations

import random
import threading
import time
from typing import ClassVar

import pytest

from agentverity.adapters import from_callable
from agentverity.runner import RunConfig, run


class TestRunDeterministic:
    def test_deterministic_gate(self):
        """A deterministic gate should meter as deterministic with enough inputs."""
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        inputs = (
            [f"public input {i}" for i in range(100)]
            + [f"secret input {i}" for i in range(100)]
        )
        agent = from_callable(fn)
        result = run(agent, inputs)
        assert result.meter is not None
        assert result.meter.call == "verdict-deterministic"
        assert result.suite_is_meaningful is True

    def test_deterministic_gate_relations_all_hold(self):
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = run(agent, ["hello", "world", "foo"])
        assert all(rr.violated == 0 for rr in result.relation_results)


class TestRunStochastic:
    def test_stochastic_gate(self):
        """A stochastic gate should meter as stochastic and be meaningful."""
        rng = random.Random(42)

        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            if rng.random() < 0.3:
                v = "allow" if v == "block" else "block"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = run(agent, ["hello", "world", "foo", "bar", "a secret"])
        assert result.meter is not None
        assert result.meter.call == "verdict-stochastic"
        assert result.is_stochastic is True

    def test_stochastic_gate_suite_is_meaningful(self):
        rng = random.Random(42)

        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            if rng.random() < 0.3:
                v = "allow" if v == "block" else "block"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = run(
            agent,
            ["hello", "world", "foo", "bar", "a secret"],
            relations=[],
        )
        assert result.suite_is_meaningful is True
        assert result.status == "stochastic"

    def test_undecided_nonblind_gate_is_not_vacuous(self):
        """Undecided is now something you opt into, not the default outcome.

        Defaults size k to reach a decision, so an underpowered probe has to be
        asked for explicitly.
        """
        agent = from_callable(lambda x: {"verdict": "allow" if x == "a" else "block"})
        result = run(agent, ["a", "b"], config=RunConfig(k=2, precision="strict"))
        assert result.meter is not None
        assert result.meter.call.startswith("undecided")
        assert result.suite_is_meaningful is True
        assert result.status == "undecided"

    def test_defaults_reach_a_decision_on_a_deterministic_agent(self):
        """The regression this release exists to prevent.

        A zero-randomness function used to report "undecided" on a default run,
        which reads as a broken tool rather than an answer.
        """
        agent = from_callable(lambda x: {"verdict": "allow" if x == "a" else "block"})
        result = run(agent, ["a", "b"])
        assert result.meter is not None
        assert result.meter.call == "verdict-deterministic"


class TestRunBlind:
    def test_constant_gate_is_blind(self):
        """A constant gate should be flagged as blind and not meaningful."""
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        result = run(agent, ["hello", "world", "foo", "bar"])
        assert result.blindness is not None
        assert result.is_blind is True
        assert result.suite_is_meaningful is False
        assert result.status == "blind"

    def test_constant_gate_relations_all_hold_trivially(self):
        """All relations hold on a constant gate — but trivially (blindness warns)."""
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        result = run(agent, ["hello", "world", "foo", "bar"])
        assert all(rr.violated == 0 for rr in result.relation_results)
        assert result.is_blind is True


class TestRunConfig:
    def test_no_meter(self):
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        config = RunConfig(run_meter=False)
        result = run(agent, ["hello"], config=config)
        assert result.meter is None

    def test_no_blindness(self):
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        config = RunConfig(run_blindness=False)
        result = run(agent, ["hello"], config=config)
        assert result.blindness is None

    def test_custom_k(self):
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        config = RunConfig(k=10)
        result = run(agent, ["hello", "world"], config=config)
        assert result.meter is not None
        assert result.meter.repeats == 10

    def test_empty_relation_list_runs_no_relations(self):
        agent = from_callable(lambda x: {"verdict": "allow"})
        result = run(agent, ["hello"], relations=[])
        assert result.relation_results == []

    def test_empty_inputs_rejected(self):
        agent = from_callable(lambda x: {"verdict": "allow"})
        with pytest.raises(ValueError, match="inputs"):
            run(agent, [])

    def test_invalid_worker_count_rejected_before_calls(self):
        with pytest.raises(ValueError, match="max_workers"):
            RunConfig(max_workers=0)


class TestBoundedExecution:
    def test_repeated_calls_for_one_input_remain_sequential(self):
        lock = threading.Lock()
        active: set[str] = set()
        overlap: list[str] = []

        def fn(text: str) -> dict:
            with lock:
                if text in active:
                    overlap.append(text)
                active.add(text)
            time.sleep(0.003)
            with lock:
                active.remove(text)
            return {"verdict": "allow" if text.startswith("a") else "block"}

        result = run(
            from_callable(fn),
            ["alpha", "beta", "apricot", "banana"],
            relations=[],
            config=RunConfig(k=4, epsilon=0.5, max_workers=4),
        )
        assert result.complete
        assert overlap == []

    def test_recorded_relation_failure_is_not_a_pass(self):
        from agentverity.relations import INVARIANT, Relation

        relation = Relation(
            name="uppercase",
            rtype=INVARIANT,
            transform=str.upper,
            check=lambda source, followup: source.verdict == followup.verdict,
        )

        def fn(text: str) -> dict:
            if text == "BETA":
                raise RuntimeError("provider failed")
            return {"verdict": "allow" if text.lower().startswith("a") else "block"}

        events = []
        result = run(
            from_callable(fn),
            ["alpha", "beta"],
            relations=[relation],
            config=RunConfig(k=2, epsilon=0.9, error_policy="record"),
            on_progress=events.append,
        )
        relation_result = result.relation_results[0]
        assert result.complete is False
        assert relation_result.held == 1
        assert relation_result.errors == 1
        assert relation_result.violated == 0
        assert "INCOMPLETE EVIDENCE" in result.summary()
        relation_events = [event for event in events if event.phase == "relations"]
        assert [event.status for event in relation_events].count("error") == 1


class TestSummary:
    def test_summary_contains_meter_section(self):
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = run(agent, ["hello"])
        s = result.summary()
        assert "VERDICT-STOCHASTICITY METER" in s
        assert "CONSTANT-GATE-BLINDNESS DETECTOR" in s
        assert "WHAT TO DO NEXT" in s
        assert "RELATION RESULTS" in s
        assert "within-period disagreement probability" in s
        assert "across-period marginal disagreement probability" in s

    def test_summary_blind_warning(self):
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        result = run(agent, ["hello", "world"])
        s = result.summary()
        assert "BLIND" in s
        assert "vacuous" in s.lower()


class TestIdentityTransformsAreNotCountedAsPasses:
    """A transform that returns its input unchanged tests nothing."""

    @staticmethod
    def _ascii_agent():
        def fn(x: str) -> dict:
            return {"text": x, "verdict": "allow"}
        return from_callable(fn)

    def test_noop_relation_is_skipped_not_held(self):
        """normalisation-invariance is the identity on plain ASCII input."""
        result = run(self._ascii_agent(), ["alpha", "beta", "gamma"])
        by_name = {rr.relation.name: rr for rr in result.relation_results}
        norm = by_name["normalisation-invariance"]
        assert norm.skipped == 3
        assert norm.held == 0
        assert norm.violated == 0
        assert norm.exercised == 0
        assert norm.is_vacuous is True

    def test_real_transform_is_exercised(self):
        """case-invariance genuinely changes plain ASCII input."""
        result = run(self._ascii_agent(), ["alpha", "beta", "gamma"])
        by_name = {rr.relation.name: rr for rr in result.relation_results}
        case = by_name["case-invariance"]
        assert case.skipped == 0
        assert case.exercised == 3
        assert case.is_vacuous is False

    def test_transform_that_changes_only_some_inputs(self):
        """Accented input is transformed, plain ASCII is not."""
        result = run(self._ascii_agent(), ["cafe", "café", "naive", "naïve"])
        by_name = {rr.relation.name: rr for rr in result.relation_results}
        norm = by_name["normalisation-invariance"]
        assert norm.skipped == 2
        assert norm.exercised == 2
        assert norm.total == 4
        assert norm.is_vacuous is False

    def test_violation_rate_excludes_skipped_inputs(self):
        """A rate over exercised pairs, not over inputs that were never tested."""
        def fn(x: str) -> dict:
            return {"text": x, "verdict": "block" if x.isupper() else "allow"}

        result = run(from_callable(fn), ["cafe", "café"])
        by_name = {rr.relation.name: rr for rr in result.relation_results}
        norm = by_name["normalisation-invariance"]
        assert norm.exercised == 1
        assert norm.violation_rate == 0.0

        case = by_name["case-invariance"]
        assert case.exercised == 2
        assert case.violated == 2
        assert case.violation_rate == 1.0

    def test_vacuous_relations_are_named_in_the_summary(self):
        result = run(self._ascii_agent(), ["alpha", "beta"])
        summary = result.summary()
        assert "NOT EXERCISED" in summary
        assert "normalisation-invariance" in summary
        assert "n/a" in summary

    def test_suite_is_not_meaningful_when_every_relation_is_vacuous(self):
        from agentverity.relations import INVARIANT, Relation

        noop = Relation(
            name="noop",
            rtype=INVARIANT,
            transform=lambda s: s,
            check=lambda src, fol: True,
        )
        result = run(self._ascii_agent(), ["alpha", "beta"], relations=[noop])
        assert result.vacuous_relations
        assert result.suite_is_meaningful is False


class TestUnchangedCallReuse:
    """The meter's draws are reused instead of re-asking the same question."""

    @staticmethod
    def _counting_agent():
        calls: list[str] = []

        def fn(x: str) -> dict:
            calls.append(x)
            return {"text": x, "verdict": "allow" if "a" in x else "block"}

        return from_callable(fn), calls

    def test_reuse_lowers_the_call_count(self):
        inputs = ["alpha", "beta", "gamma"]

        agent, without = self._counting_agent()
        run(agent, inputs, config=RunConfig(reuse_unchanged_calls=False))

        agent, with_reuse = self._counting_agent()
        run(agent, inputs, config=RunConfig(reuse_unchanged_calls=True))

        assert len(with_reuse) < len(without)

    def test_reuse_does_not_change_the_verdict_counts(self):
        """On a deterministic agent, reuse must be result-identical."""
        inputs = ["alpha", "beta", "gamma", "secret"]

        agent, _ = self._counting_agent()
        off = run(agent, inputs, config=RunConfig(reuse_unchanged_calls=False))

        agent, _ = self._counting_agent()
        on = run(agent, inputs, config=RunConfig(reuse_unchanged_calls=True))

        assert off.blindness is not None and on.blindness is not None
        assert off.blindness.skew == on.blindness.skew
        assert off.blindness.majority_verdict == on.blindness.majority_verdict
        assert [(rr.held, rr.violated, rr.skipped) for rr in off.relation_results] == [
            (rr.held, rr.violated, rr.skipped) for rr in on.relation_results
        ]

    def test_blindness_still_scans_every_input_when_the_meter_is_off(self):
        """With no meter there is nothing to reuse, so the scan must still run."""
        agent, calls = self._counting_agent()
        result = run(
            agent,
            ["alpha", "beta", "gamma"],
            relations=[],
            config=RunConfig(run_meter=False, reuse_unchanged_calls=True),
        )
        assert result.blindness is not None
        assert result.blindness.inputs == 3
        assert calls == ["alpha", "beta", "gamma"]


class TestDuplicateInputsAreRejected:
    """A probe set is a set. Duplicates measure the probe set, not the agent."""

    @staticmethod
    def _agent():
        return from_callable(lambda x: {"text": x, "verdict": "allow"})

    def test_duplicates_raise(self):
        with pytest.raises(ValueError, match="must be distinct"):
            run(self._agent(), ["alpha", "beta", "alpha"])

    def test_error_names_the_duplicate(self):
        with pytest.raises(ValueError, match="'alpha'"):
            run(self._agent(), ["alpha", "beta", "alpha"])

    def test_distinct_inputs_are_fine(self):
        result = run(self._agent(), ["alpha", "beta", "gamma"])
        assert result.blindness is not None
        assert result.blindness.inputs == 3

    def test_a_varying_agent_is_not_reported_constant(self):
        """The bug this guards: cached duplicates made a flipping agent BLIND.

        With reuse on, every copy of a duplicated input resolved to one cached
        observation, so an agent alternating A/B on four probes reported 100%
        skew and BLIND instead of 50% and ok.
        """
        import itertools

        counter = itertools.count()

        def flipping(x: str) -> dict:
            return {"text": x, "verdict": "A" if next(counter) % 2 == 0 else "B"}

        with pytest.raises(ValueError, match="must be distinct"):
            run(from_callable(flipping), ["same", "same", "same", "same"])


class TestVacuousRelationHasNoRate:
    """A relation that never ran has no rate, and must not report 0.0."""

    def test_violation_rate_is_none_when_nothing_exercised(self):
        result = run(
            from_callable(lambda x: {"text": x, "verdict": "x"}), ["alpha", "beta"]
        )
        vacuous = [rr for rr in result.relation_results if rr.is_vacuous]
        assert vacuous, "expected normalisation-invariance to be a no-op here"
        for rr in vacuous:
            assert rr.violation_rate is None

    def test_exercised_relation_still_reports_a_float(self):
        result = run(
            from_callable(lambda x: {"text": x, "verdict": "x"}), ["alpha", "beta"]
        )
        exercised = [rr for rr in result.relation_results if not rr.is_vacuous]
        assert exercised
        for rr in exercised:
            assert isinstance(rr.violation_rate, float)

    def test_summary_renders_without_formatting_a_none(self):
        result = run(
            from_callable(lambda x: {"text": x, "verdict": "x"}), ["alpha", "beta"]
        )
        assert "n/a" in result.summary()


class TestSuiteIsMeaningfulSemantics:
    """Pin the difference between "no relations asked for" and "none ran"."""

    @staticmethod
    def _splitting_agent():
        """Verdict genuinely splits, so the blindness detector stays quiet."""
        return from_callable(
            lambda x: {"text": x, "verdict": "A" if x.startswith("a") else "B"}
        )

    INPUTS: ClassVar[list[str]] = ["apple", "banana", "cherry", "apricot"]

    def test_no_relations_requested_is_meaningful(self):
        """A diagnostics-only run produced no green result to distrust."""
        result = run(self._splitting_agent(), self.INPUTS, relations=[])
        assert result.is_blind is False
        assert result.relation_results == []
        assert result.suite_is_meaningful is True

    def test_relations_that_ran_but_tested_nothing_are_not_meaningful(self):
        """Asked for, ran, exercised nothing. That is the vacuous case."""
        from agentverity.relations import INVARIANT, Relation

        noop = Relation(
            name="noop", rtype=INVARIANT, transform=lambda s: s,
            check=lambda src, fol: True,
        )
        result = run(self._splitting_agent(), self.INPUTS, relations=[noop])
        assert result.is_blind is False
        assert result.vacuous_relations
        assert result.suite_is_meaningful is False

    def test_partially_exercised_catalogue_is_meaningful(self):
        """Two of the four built-ins are no-ops on ASCII, two are not."""
        result = run(self._splitting_agent(), self.INPUTS)
        assert result.is_blind is False
        assert result.vacuous_relations
        assert any(rr.exercised for rr in result.relation_results)
        assert result.suite_is_meaningful is True


class TestHeadline:
    """One sentence should answer "can I trust this?" before any detail."""

    INPUTS: ClassVar[list[str]] = ["apple", "banana", "cherry", "apricot"]

    def test_blind_agent_is_not_trustworthy(self):
        result = run(from_callable(lambda x: {"verdict": "same"}), self.INPUTS)
        assert result.headline.startswith("NOT TRUSTWORTHY")
        assert "100%" in result.headline

    def test_deterministic_and_varied_is_trustworthy(self):
        agent = from_callable(
            lambda x: {"verdict": "A" if x.startswith("a") else "B"}
        )
        result = run(agent, self.INPUTS)
        assert result.headline.startswith("TRUSTWORTHY")
        assert "NOT TRUSTWORTHY" not in result.headline

    def test_stochastic_says_read_against_noise(self):
        import itertools

        counter = itertools.count()
        agent = from_callable(
            lambda x: {"verdict": "A" if next(counter) % 3 else "B"}
        )
        result = run(agent, self.INPUTS)
        assert result.headline.startswith("TRUSTWORTHY WITH CARE")

    def test_underpowered_says_no_answer_yet(self):
        agent = from_callable(
            lambda x: {"verdict": "A" if x.startswith("a") else "B"}
        )
        result = run(agent, self.INPUTS, config=RunConfig(k=2, precision="strict"))
        assert result.headline.startswith("NO ANSWER YET")

    def test_headline_leads_the_summary(self):
        result = run(from_callable(lambda x: {"verdict": "same"}), self.INPUTS)
        body = result.summary()
        assert result.headline.split(" - ")[0] in body
        assert body.index("NOT TRUSTWORTHY") < body.index("VERDICT-STOCHASTICITY")


class TestBudgetAndPrecision:
    """Two knobs people actually think in: what it costs and how much I care."""

    INPUTS: ClassVar[list[str]] = [f"probe {i}" for i in range(10)]

    @staticmethod
    def _counting_agent():
        calls: list[str] = []

        def fn(text: str) -> dict:
            calls.append(text)
            return {"verdict": "A" if text.endswith(("0", "1", "2")) else "B"}

        return from_callable(fn), calls

    def test_precision_selects_epsilon(self):
        agent, _ = self._counting_agent()
        for precision, expected in (("cheap", 0.10), ("balanced", 0.05), ("strict", 0.01)):
            result = run(agent, self.INPUTS, config=RunConfig(precision=precision))
            assert result.config.epsilon == expected

    def test_explicit_epsilon_beats_precision(self):
        agent, _ = self._counting_agent()
        result = run(agent, self.INPUTS,
                     config=RunConfig(precision="cheap", epsilon=0.02))
        assert result.config.epsilon == 0.02

    def test_cheaper_precision_costs_fewer_calls(self):
        agent_cheap, cheap_calls = self._counting_agent()
        run(agent_cheap, self.INPUTS, relations=[], config=RunConfig(precision="cheap"))
        agent_strict, strict_calls = self._counting_agent()
        run(agent_strict, self.INPUTS, relations=[], config=RunConfig(precision="strict"))
        assert len(cheap_calls) < len(strict_calls)

    def test_budget_caps_the_repeats(self):
        agent, calls = self._counting_agent()
        run(agent, self.INPUTS, relations=[],
            config=RunConfig(precision="strict", budget=100))
        assert len(calls) <= 100

    def test_budget_below_the_structural_floor_is_rejected(self):
        agent, _ = self._counting_agent()
        with pytest.raises(ValueError, match="cannot cover"):
            run(agent, self.INPUTS, config=RunConfig(budget=5))

    def test_explicit_k_wins_over_budget(self):
        agent, _ = self._counting_agent()
        result = run(agent, self.INPUTS, config=RunConfig(k=4, budget=10_000))
        assert result.config.k == 4

    def test_resolved_values_are_visible_after_the_run(self):
        """Downstream code and snapshots read concrete numbers, never None."""
        agent, _ = self._counting_agent()
        result = run(agent, self.INPUTS)
        assert isinstance(result.config.k, int)
        assert isinstance(result.config.epsilon, float)


class TestReachWithoutTheMeter:
    """Coverage must survive the meter being off, and partial meter failure.

    Both were runtime blockers found in review. `complete_series` is assigned
    only inside the meter branch, and it drops failed entries, so building
    per-case groups from it crashed with the meter off and silently shifted
    every later case onto the wrong contract row when one case failed.
    """

    def _suite(self):
        from agentverity import DecisionCase, DecisionContract, DecisionSuite

        return DecisionSuite(
            contract=DecisionContract(
                allowed=frozenset({"refund", "escalate"}),
                required=frozenset({"refund", "escalate"}),
            ),
            cases=(
                DecisionCase(input="a", expected="refund"),
                DecisionCase(input="b", expected="escalate"),
                DecisionCase(input="c", expected="refund"),
            ),
        )

    def test_a_contract_suite_runs_with_the_meter_disabled(self):
        from agentverity import RunConfig, run
        from agentverity.observation import Observation

        # relations mutate the input, so route on the normalised form
        routes = {"a": "refund", "b": "escalate", "c": "refund"}
        result = run(
            lambda text: Observation(
                text="ok", verdict=routes.get(text.strip().lower()[:1], "refund")
            ),
            suite=self._suite(),
            config=RunConfig(run_meter=False),
        )

        assert result.decision_coverage is not None
        assert result.decision_coverage.missing_observed == ()

    def test_a_failure_in_the_first_case_does_not_shift_the_others(self):
        """The alignment bug: drop case one and case two takes its row."""
        from agentverity import RunConfig, run
        from agentverity.observation import Observation

        routes = {"a": "refund", "b": "escalate", "c": "refund"}

        def agent(text: str) -> Observation:
            key = text.strip().lower()[:1]
            if key == "a":
                raise RuntimeError("first case fails")
            return Observation(text="ok", verdict=routes.get(key, "refund"))

        result = run(
            agent,
            suite=self._suite(),
            config=RunConfig(budget=30, error_policy="record"),
        )

        counts = {
            c.decision: c.count
            for c in result.decision_coverage.observed_case_counts
        }
        # b and c kept their own routes rather than inheriting a's row
        assert counts.get("escalate") == 1
        assert counts.get("refund") == 1
        assert result.errors
