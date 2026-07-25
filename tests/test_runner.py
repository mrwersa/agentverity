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
