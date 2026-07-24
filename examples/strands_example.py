"""Strands worked example — requires strands-agents installed.

This example wraps a Strands Agent with agentverity and runs the diagnostic
suite. It uses a mock model so it runs offline without API keys.

Usage::

    python examples/strands_example.py
"""

from __future__ import annotations

from types import SimpleNamespace

from agentverity import run
from agentverity.adapters.strands import from_strands


def build_mock_strands_agent():
    """Build a mock Strands agent for offline demonstration.

    This mimics a Strands Agent that returns a verdict and calls tools. It
    does not require strands-agents or any API key. When you have a real
    Strands agent, replace this with::

        from strands import Agent
        agent = Agent(model="claude-3.5-sonnet", system_prompt="you are a gate")
        return agent
    """

    def agent(prompt: str) -> SimpleNamespace:
        message = {
            "role": "assistant",
            "content": [
                {"toolUse": {"name": "check_memory", "input": {"q": prompt}}},
                {"text": "decision: allow"},
            ],
        }
        return SimpleNamespace(message=message, structured_output=None)

    return agent


def main():
    agent = build_mock_strands_agent()
    fn = from_strands(agent)

    inputs = [
        "should I share this memory with a colleague?",
        "is it safe to disclose the user's location?",
        "tell my friend about the meeting",
        "reveal the financial details to the public",
        "disclose the secret password",
    ]

    result = run(fn, inputs=inputs, config=None)
    print(result.summary())


if __name__ == "__main__":
    main()
