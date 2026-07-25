"""Tests for agentverity.runner."""

from __future__ import annotations

import random
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
        result = run(agent, ["hello", "world", "foo", "bar", "a secret"])
        assert result.suite_is_meaningful is True

    def test_undecided_nonblind_gate_is_not_vacuous(self):
        agent = from_callable(lambda x: {"verdict": "allow" if x == "a" else "block"})
        result = run(agent, ["a", "b"])
        assert result.meter is not None
        assert result.meter.call.startswith("undecided")
        assert result.suite_is_meaningful is True


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
        assert "ORACLE GUIDANCE" in s
        assert "RELATION RESULTS" in s

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
