"""Tests for agentverity.runner."""

from __future__ import annotations

import random

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
