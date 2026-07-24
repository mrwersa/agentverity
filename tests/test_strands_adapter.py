"""Tests for agentverity.adapters.strands.

These tests use mock objects that mimic Strands' AgentResult and Message
structure, so they run without the strands-agents package installed.
"""

from __future__ import annotations

from types import SimpleNamespace

from agentverity.adapters.strands import from_strands
from agentverity.observation import Observation


def _make_message(content: list[dict]) -> dict:
    """Create a Strands-like message dict."""
    return {"role": "assistant", "content": content}


def _make_result(content: list[dict], structured_output=None) -> SimpleNamespace:
    """Create a Strands-like AgentResult."""
    return SimpleNamespace(
        message=_make_message(content),
        structured_output=structured_output,
    )


def _mock_strands_agent(result: SimpleNamespace):
    """Create a callable mock Strands agent that always returns result."""
    def agent_fn(prompt: str) -> SimpleNamespace:
        return result
    return agent_fn


class TestFromStrands:
    def test_text_extraction(self):
        result = _make_result([{"text": "hello world"}])
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert obs.text == "hello world"
        assert obs.verdict is None
        assert obs.tools == ()

    def test_tool_extraction(self):
        result = _make_result([
            {"toolUse": {"name": "search", "input": {"q": "test"}}},
            {"toolUse": {"name": "fetch", "input": {"url": "http://example.com"}}},
        ])
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert obs.tools == ("search", "fetch")

    def test_text_and_tool_mixed(self):
        result = _make_result([
            {"text": "Let me search."},
            {"toolUse": {"name": "search", "input": {}}},
            {"text": "Here are the results."},
        ])
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert obs.text == "Let me search.Here are the results."
        assert obs.tools == ("search",)

    def test_structured_output_verdict(self):
        """Structured output with a 'verdict' field should populate Observation.verdict."""
        class FakeStructured:
            def model_dump(self):
                return {"verdict": "block"}

        result = _make_result(
            [{"text": "blocked"}],
            structured_output=FakeStructured(),
        )
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert obs.verdict == "block"

    def test_structured_output_dict(self):
        """Structured output as a dict should also populate verdict."""
        result = _make_result(
            [{"text": "ok"}],
            structured_output={"decision": "allow"},
        )
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert obs.verdict == "allow"

    def test_no_message(self):
        """When no message is present, fall back to stringifying the result."""
        result = SimpleNamespace(message=None)
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert "message=None" in obs.text
        assert obs.raw is result

    def test_empty_content(self):
        """Empty content blocks produce empty text but non-crash."""
        result = _make_result([])
        agent = from_strands(_mock_strands_agent(result))
        obs = agent("hi")
        assert isinstance(obs, Observation)
