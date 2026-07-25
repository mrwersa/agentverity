"""Tests for agentverity.blindness."""

from __future__ import annotations

import pytest

from agentverity.adapters import from_callable
from agentverity.blindness import detect


class TestDetect:
    def test_constant_gate_is_blind(self):
        """A gate that always returns the same verdict is blind."""
        def fn(x: str) -> dict:
            return {"text": "allow", "verdict": "allow"}

        agent = from_callable(fn)
        result = detect(agent, ["hello", "world", "foo", "bar"])
        assert result.blind is True
        assert result.skew == 1.0
        assert result.distinct == 1
        assert result.warning is not None

    def test_balanced_gate_is_not_blind(self):
        """A gate that splits 50/50 is not blind."""
        def fn(x: str) -> dict:
            v = "block" if "secret" in x.lower() else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = detect(agent, ["hello", "world", "a secret", "foo", "bar", "another secret"])
        assert result.blind is False
        assert result.skew < 0.9
        assert result.distinct == 2
        assert result.warning is None

    def test_near_constant_gate_is_blind(self):
        """A gate that returns the same verdict on 95% of inputs is blind at 0.9."""
        inputs = [f"input_{i}" for i in range(20)]
        inputs[3] = "secret"  # only 1/20 = 5% is different

        def fn(x: str) -> dict:
            v = "block" if "secret" == x else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result = detect(agent, inputs, threshold=0.9)
        assert result.blind is True
        assert result.skew == 19 / 20

    def test_custom_threshold(self):
        """A 80% skew is blind at 0.8 but not at 0.9."""
        inputs = [f"input_{i}" for i in range(10)]
        inputs[0] = "secret"

        def fn(x: str) -> dict:
            v = "block" if "secret" == x else "allow"
            return {"text": v, "verdict": v}

        agent = from_callable(fn)
        result_low = detect(agent, inputs, threshold=0.8)
        result_high = detect(agent, inputs, threshold=0.95)
        assert result_low.blind is True
        assert result_high.blind is False

    def test_empty_inputs_rejected(self):
        agent = from_callable(lambda x: "ok")
        with pytest.raises(ValueError, match="inputs"):
            detect(agent, [])

    def test_invalid_threshold_rejected(self):
        agent = from_callable(lambda x: "ok")
        with pytest.raises(ValueError, match="threshold"):
            detect(agent, ["hello"], threshold=0)
