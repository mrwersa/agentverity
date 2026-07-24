"""Tests for agentverity.adapters.callable_adapter."""

from __future__ import annotations

from agentverity.adapters import from_callable
from agentverity.observation import Observation


class TestFromCallable:
    def test_str_return(self):
        agent = from_callable(lambda x: "hello back")
        obs = agent("hi")
        assert isinstance(obs, Observation)
        assert obs.text == "hello back"
        assert obs.verdict is None
        assert obs.tools == ()

    def test_dict_return(self):
        def fn(x: str) -> dict:
            return {"text": "ok", "verdict": "allow", "tools": ["search", "fetch"]}
        agent = from_callable(fn)
        obs = agent("hi")
        assert obs.text == "ok"
        assert obs.verdict == "allow"
        assert obs.tools == ("search", "fetch")

    def test_dict_with_custom_keys(self):
        def fn(x: str) -> dict:
            return {"response": "ok", "decision": "allow", "called": ["search"]}
        agent = from_callable(fn, verdict_key="decision", tools_key="called")
        obs = agent("hi")
        assert obs.text == ""
        assert obs.verdict == "allow"
        assert obs.tools == ("search",)

    def test_observation_passthrough(self):
        def fn(x: str) -> Observation:
            return Observation(text="ok", verdict="allow")
        agent = from_callable(fn)
        obs = agent("hi")
        assert obs.text == "ok"
        assert obs.verdict == "allow"

    def test_other_type_stringified(self):
        agent = from_callable(lambda x: 42)
        obs = agent("hi")
        assert obs.text == "42"
        assert obs.raw == 42

    def test_dict_no_verdict(self):
        def fn(x: str) -> dict:
            return {"text": "ok"}
        agent = from_callable(fn)
        obs = agent("hi")
        assert obs.text == "ok"
        assert obs.verdict is None
        assert obs.tools == ()

    def test_dict_verdict_none(self):
        def fn(x: str) -> dict:
            return {"text": "ok", "verdict": None}
        agent = from_callable(fn)
        obs = agent("hi")
        assert obs.verdict is None
