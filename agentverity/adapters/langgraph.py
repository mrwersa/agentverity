"""LangGraph adapters for stateful and isolated agent evaluation.

LangGraph compiles a graph you invoke with a state dict. What comes back is
the final state, and the interesting parts of it are the message list and,
when the graph keeps one, a structured decision.

The isolation problem is sharper here than with most frameworks, because it
has two independent sources.

A compiled graph is itself stateless: invoking it twice with the same input
gives two independent runs. But a graph compiled with a checkpointer keeps
state per thread, and reusing one ``thread_id`` across repeats means every
trial after the first sees the previous conversation. The repeats are then not
independent trials of the same question, they are turns in one conversation,
and the intervals AgentVerity reports assume independence. So
:func:`from_langgraph` gives every call a fresh ``thread_id`` by default, and
:func:`from_langgraph_thread` exists for the case where the conversation
itself is what is under test.

The adapter is an optional import: the core installs without ``langgraph``.
Install it with ``pip install "agentverity[langgraph]"``.

A decision stored as a bool arrives as ``"True"`` or ``"False"``, which is
Python's spelling rather than a normalised one. That is deliberate: the
decision label belongs to the application, and lower-casing it here would be
this package inventing a convention nobody declared. Stability is unaffected,
since both trials render the same way, and a declared contract listing
``true``/``false`` will report the mismatch loudly rather than hiding it.

Example::

    from langgraph.prebuilt import create_react_agent
    from agentverity.adapters.langgraph import from_langgraph

    graph = create_react_agent(model, tools=[search, refund])
    fn = from_langgraph(graph)
    obs = fn("I was charged twice for order 4471")
    print(obs.text, obs.verdict, obs.tools)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from agentverity.isolation import declare_isolation
from agentverity.observation import Observation

# Where a decision plausibly lives in a returned state, in the order tried.
# A graph that keeps one under a different key should pass `verdict_key`.
VERDICT_KEYS = ("verdict", "decision", "route", "classification")


def _messages(state: Any) -> list[Any]:
    if isinstance(state, dict):
        value = state.get("messages")
    else:
        value = getattr(state, "messages", None)
    return list(value) if isinstance(value, (list, tuple)) else []


def _text_of(message: Any) -> str:
    """Read the text of one message, whatever shape it arrived in."""
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        # Anthropic-style content blocks: text parts, tool_use parts, images.
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


def _tool_calls_of(message: Any) -> list[str]:
    """Read tool names off one message.

    Both shapes appear in the wild. LangChain message objects carry
    ``tool_calls``; a serialised dict carries the same list, and a ToolMessage
    records the name of the tool it is the result of. Reading the request
    rather than the result keeps the order the agent chose them in.
    """
    names: list[str] = []
    calls = (
        message.get("tool_calls")
        if isinstance(message, dict)
        else getattr(message, "tool_calls", None)
    )
    if isinstance(calls, (list, tuple)):
        for call in calls:
            if isinstance(call, dict):
                name = call.get("name") or (call.get("function") or {}).get("name")
            else:
                name = getattr(call, "name", None)
            if name:
                names.append(str(name))
    return names


def _verdict_of(state: Any, verdict_key: str | None) -> str | None:
    if not isinstance(state, dict):
        # A dataclass or plain object state exposes its fields here. A string
        # or a namedtuple has no __dict__ and carries no decision.
        state = getattr(state, '__dict__', None)
    if not isinstance(state, dict):
        return None
    if verdict_key is not None:
        value = state.get(verdict_key)
        return str(value) if value not in (None, "") else None
    for key in VERDICT_KEYS:
        value = state.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def extract(state: Any, *, verdict_key: str | None = None) -> Observation:
    """Turn a returned LangGraph state into an :class:`Observation`."""
    messages = _messages(state)

    tools: list[str] = []
    for message in messages:
        tools.extend(_tool_calls_of(message))

    # The last message with text is the answer. Walking backwards skips a
    # trailing ToolMessage, which is a result rather than a response.
    text = ""
    for message in reversed(messages):
        candidate = _text_of(message)
        if candidate.strip():
            text = candidate
            break
    if not text and not messages:
        text = str(state)

    return Observation(
        text=text,
        verdict=_verdict_of(state, verdict_key),
        tools=tuple(tools),
        raw=state,
    )


def from_langgraph(
    graph: Any,
    *,
    input_key: str = "messages",
    verdict_key: str | None = None,
    config: dict[str, Any] | None = None,
) -> Callable[[str], Observation]:
    """Wrap a compiled LangGraph graph, one independent run per call.

    Every call gets a fresh ``thread_id``. If the graph was compiled without a
    checkpointer that changes nothing; if it was compiled with one, this is
    what keeps repeated trials independent rather than turning them into
    successive turns of a single conversation.

    Args:
        graph: A compiled graph exposing ``invoke(state, config=...)``.
        input_key: The state key the input goes under. ``messages`` suits the
            prebuilt agents; a custom graph may use something else.
        verdict_key: State key holding the decision. By default the adapter
            tries ``verdict``, ``decision``, ``route``, then ``classification``.
        config: Extra config merged into every call, for recursion limits or
            callbacks. A ``thread_id`` given here is respected rather than
            replaced, which is how you opt out deliberately.

    Returns:
        A function ``(input: str) -> Observation``.
    """

    def run(x: str) -> Observation:
        merged: dict[str, Any] = {} if config is None else dict(config)
        configurable = dict(merged.get("configurable", {}))
        configurable.setdefault("thread_id", f"agentverity-{uuid.uuid4()}")
        merged["configurable"] = configurable

        state = (
            {input_key: [{"role": "user", "content": x}]}
            if input_key == "messages"
            else {input_key: x}
        )
        return extract(graph.invoke(state, config=merged), verdict_key=verdict_key)

    # Computed, not assumed. A caller-supplied thread_id is the documented way
    # to opt out, and every repeat then runs on that one thread. Declaring
    # `fresh-session` from the function name would assert independence exactly
    # where the caller had turned it off.
    pinned = "thread_id" in dict((config or {}).get("configurable", {}))
    return declare_isolation(run, "shared-session" if pinned else "fresh-session")


def from_langgraph_thread(
    graph: Any,
    thread_id: str,
    *,
    input_key: str = "messages",
    verdict_key: str | None = None,
    config: dict[str, Any] | None = None,
) -> Callable[[str], Observation]:
    """Wrap a graph so every call continues the same conversation.

    Use this only when the conversation is the thing under test. Repeated
    trials on one thread are not independent, and every interval AgentVerity
    reports assumes they are, so it will read narrower than the evidence
    supports. This adapter declares ``shared-session`` for you, so the report
    says so and a baseline collected this way is refused rather than admitted
    with a caveat.
    """

    def run(x: str) -> Observation:
        merged: dict[str, Any] = {} if config is None else dict(config)
        configurable = dict(merged.get("configurable", {}))
        configurable["thread_id"] = thread_id
        merged["configurable"] = configurable

        state = (
            {input_key: [{"role": "user", "content": x}]}
            if input_key == "messages"
            else {input_key: x}
        )
        return extract(graph.invoke(state, config=merged), verdict_key=verdict_key)

    # The whole point of this function. Evidence collected here is refused a
    # baseline, which is the documented consequence rather than a surprise:
    # repeats on one thread are successive turns, not independent trials.
    return declare_isolation(run, "shared-session")
