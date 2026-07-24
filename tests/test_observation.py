"""Tests for agentverity.observation.Observation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agentverity.observation import Observation


class TestObservationConstruction:
    def test_defaults(self):
        obs = Observation()
        assert obs.text == ""
        assert obs.verdict is None
        assert obs.tools == ()
        assert obs.raw is None

    def test_full(self):
        obs = Observation(text="allow", verdict="allow", tools=("search",), raw={"x": 1})
        assert obs.text == "allow"
        assert obs.verdict == "allow"
        assert obs.tools == ("search",)
        assert obs.raw == {"x": 1}

    def test_frozen(self):
        obs = Observation(text="hi")
        with pytest.raises(FrozenInstanceError):
            obs.text = "no"
