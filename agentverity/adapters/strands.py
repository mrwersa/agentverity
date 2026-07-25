"""Strands adapters for stateful and isolated agent evaluation.

Strands is an AWS-backed agent framework (``strands-agents`` on PyPI). This
module extracts final response text, a structured verdict, and ordered tool
calls from a Strands result.

Strands agents retain conversation history between calls. Use
:func:`from_strands_factory` for repeated trials that must start from equivalent
state. Use :func:`from_strands` only when preserving one agent session is the
behaviour under test.

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

from collections.abc import Callable
from typing import Any

from agentverity.observation import Observation

AgentFactory = Callable[[], Any]
AgentInvoker = Callable[[Any, str], Any]


def from_strands(
    agent: Any,
    *,
    verdict_key: str | None = None,
) -> Callable[[str], Observation]:
    """Wrap a Strands ``Agent`` into ``run(input) -> Observation``.

    The same agent instance handles every call. Strands preserves conversation
    history on that instance, so this adapter is appropriate only when the
    session itself is under test. For independent repeated trials, use
    :func:`from_strands_factory`.

    Args:
        agent: A ``strands.agent.Agent`` instance (must be callable with
            ``agent(prompt: str)`` and return an ``AgentResult``).
        verdict_key: Optional field to read from structured output. By default,
            the adapter recognises ``verdict`` and ``decision``.

    Returns:
        A function ``(input: str) -> Observation`` that calls the agent and
        extracts the text, verdict, and tool trajectory from the result.
    """

    def run(x: str) -> Observation:
        result = agent(x)
        return _extract(result, verdict_key=verdict_key)

    return run


def from_strands_factory(
    factory: AgentFactory,
    *,
    invoke: AgentInvoker | None = None,
    verdict_key: str | None = None,
) -> Callable[[str], Observation]:
    """Build a fresh Strands agent for every independent trial.

    AgentVerity repeats identical inputs to measure decision stability. A
    factory prevents one trial's conversation history from changing the next
    trial's context. The factory may still reuse a stateless model client.

    Args:
        factory: Zero-argument callable returning a fresh Strands agent.
        invoke: Optional invocation hook. It receives the fresh agent and input
            text, and can request structured output or other per-call options.
            The default calls ``agent(prompt)``.
        verdict_key: Optional field to read from structured output. By default,
            the adapter recognises ``verdict`` and ``decision``.

    Returns:
        A function ``(input: str) -> Observation`` suitable for
        :func:`agentverity.run`.
    """

    def run(x: str) -> Observation:
        agent = factory()
        result = invoke(agent, x) if invoke is not None else agent(x)
        return _extract(result, verdict_key=verdict_key)

    return run


def _extract(
    result: Any,
    *,
    verdict_key: str | None = None,
) -> Observation:
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
            if verdict_key is not None:
                verdict = str(dump.get(verdict_key, "")) or None
            else:
                verdict = str(dump.get("verdict", dump.get("decision", ""))) or None
        elif isinstance(structured, dict):
            if verdict_key is not None:
                verdict = str(structured.get(verdict_key, "")) or None
            else:
                verdict = (
                    str(structured.get("verdict", structured.get("decision", "")))
                    or None
                )

    return Observation(
        text=text,
        verdict=verdict,
        tools=tuple(tool_names),
        raw=result,
    )
