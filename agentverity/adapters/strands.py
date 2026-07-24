"""Strands adapter — wraps a Strands ``Agent`` into ``run(input) -> Observation``.

Strands is an AWS-backed agent framework (``strands-agents`` on PyPI). This
adapter calls the agent, extracts the final response text, the verdict (if
the agent returns a structured response), and the ordered tool-call names
from the message's tool-use blocks.

The adapter is an optional import: the core library installs without
``strands-agents``. Import this module only when working with Strands agents.

Example::

    from strands import Agent
    from agentverity.adapters.strands import from_strands

    agent = Agent(model="...", system_prompt="you are a gate")
    fn = from_strands(agent)
    obs = fn("should I share this?")
    print(obs.text, obs.verdict, obs.tools)
"""

from __future__ import annotations

from typing import Any

from agentverity.observation import Observation


def from_strands(agent: Any) -> callable:
    """Wrap a Strands ``Agent`` into ``run(input) -> Observation``.

    Args:
        agent: A ``strands.agent.Agent`` instance (must be callable with
            ``agent(prompt: str)`` and return an ``AgentResult``).

    Returns:
        A function ``(input: str) -> Observation`` that calls the agent and
        extracts the text, verdict, and tool trajectory from the result.
    """

    def run(x: str) -> Observation:
        result = agent(x)
        return _extract(result)

    return run


def _extract(result: Any) -> Observation:
    """Extract an :class:`Observation` from a Strands ``AgentResult``.

    Args:
        result: A Strands ``AgentResult`` (must have ``.message`` with
            ``content`` blocks).

    Returns:
        An :class:`Observation` with the final text, verdict (if any), and
        the ordered list of tool names called.
    """
    message = getattr(result, "message", None)
    if message is None:
        return Observation(text=str(result), raw=result)

    content = message.get("content", []) if isinstance(message, dict) else getattr(message, "content", [])

    text_parts: list[str] = []
    tool_names: list[str] = []

    for block in content:
        if isinstance(block, dict):
            if "text" in block:
                text_parts.append(str(block["text"]))
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                name = tool_use.get("name", "") if isinstance(tool_use, dict) else ""
                if name:
                    tool_names.append(name)
            elif "toolResult" in block:
                tool_result = block["toolResult"]
                name = tool_result.get("name", "") if isinstance(tool_result, dict) else ""
                if name:
                    tool_names.append(name)
        else:
            text_parts.append(str(block))

    text = "".join(text_parts) or str(result)
    structured = getattr(result, "structured_output", None)
    verdict = None
    if structured is not None:
        if hasattr(structured, "model_dump"):
            dump = structured.model_dump()
            verdict = str(dump.get("verdict", dump.get("decision", ""))) or None
        elif isinstance(structured, dict):
            verdict = str(structured.get("verdict", structured.get("decision", ""))) or None

    return Observation(
        text=text,
        verdict=verdict,
        tools=tuple(tool_names),
        raw=result,
    )
