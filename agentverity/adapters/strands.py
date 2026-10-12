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

from collections.abc import Callable, Mapping
from typing import Any

from agentverity.decision import NO_DECISION_REASONS, Decision, NoDecision
from agentverity.isolation import declare_isolation
from agentverity.observation import Observation

AgentFactory = Callable[[], Any]
AgentInvoker = Callable[[Any, str], Any]


def _coerce_verdict(value: Any) -> Any:
    """Preserve a typed outcome; stringify a scalar; None/'' stay absent.

    A serialised outcome is reconstructed rather than stringified: a Pydantic
    ``model_dump`` of ``NoDecision("runtime_error")`` is
    ``{"reason": "runtime_error"}``, and ``str()`` of that is a stable label
    that scores the harness failure as a decision. Any other mapping is not a
    label and is dropped rather than turned into one.
    """
    if isinstance(value, (Decision, NoDecision)):
        return value
    if isinstance(value, Mapping):
        reason = value.get("reason")
        if isinstance(reason, str) and reason in NO_DECISION_REASONS:
            return NoDecision(reason)
        label = value.get("label")
        if isinstance(label, str) and label:
            return Decision(label)
        return None
    if value is None:
        return None
    text = str(value)
    return text or None


def _verdict_field(mapping: Any, verdict_key: str | None) -> Any:
    """Read a verdict from a serialised mapping, preserving a typed outcome."""
    keys = (verdict_key,) if verdict_key is not None else ("verdict", "decision")
    for key in keys:
        parsed = _coerce_verdict(mapping.get(key))
        if parsed is not None:
            return parsed
    return None


def _attribute_verdict(structured: Any, verdict_key: str | None) -> Any:
    """Read a verdict from live attributes, before any serialisation.

    A Pydantic model holds the typed outcome on its field. ``model_dump()``
    recursively serialises that field into a plain dict, so
    ``NoDecision("runtime_error")`` arrives as ``{"reason": "runtime_error"}``
    and the adapter stringifies it into a dictionary string. Reading the
    attribute first keeps the type. A callable attribute of the same name is a
    method, not a decision, so it is skipped rather than stringified.
    """
    if isinstance(structured, dict):
        return None
    keys = (verdict_key,) if verdict_key is not None else ("verdict", "decision")
    for key in keys:
        if not hasattr(structured, key):
            continue
        value = getattr(structured, key)
        if callable(value):
            continue
        parsed = _coerce_verdict(value)
        if parsed is not None:
            return parsed
    return None


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

    # One instance across every repeat, and Strands keeps conversation history
    # on it. The docstring has always said so; now the evidence carries it and
    # a baseline built from it is refused rather than quietly admitted.
    return declare_isolation(run, "shared-session")


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

    # A new agent per trial. `fresh-instance` rather than `fresh-session`,
    # because the factory may legitimately reuse a stateless model client and
    # this names what the adapter controls.
    return declare_isolation(run, "fresh-instance")


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
        # Live attributes first: a Pydantic model's model_dump() would already
        # have serialised a typed outcome into a dict by this point.
        verdict = _attribute_verdict(structured, verdict_key)
        if verdict is None:
            if hasattr(structured, "model_dump"):
                verdict = _verdict_field(structured.model_dump(), verdict_key)
            elif isinstance(structured, dict):
                verdict = _verdict_field(structured, verdict_key)

    return Observation(
        text=text,
        verdict=verdict,
        tools=tuple(tool_names),
        raw=result,
    )
