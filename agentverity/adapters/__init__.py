"""Adapters turn a real agent into ``run(input) -> Observation``.

Only ``callable`` is imported here (zero deps). Library adapters (Strands,
LangGraph) are imported lazily from their own modules so the core installs
without those libraries present.

Available adapters:
    - :func:`from_callable` — wrap any ``fn(input) -> str | dict | Observation``.
    - :func:`from_strands` — wrap a Strands ``Agent`` (requires ``strands-agents``).
    - :func:`from_strands_factory` — isolate repeated Strands trials by
      constructing a fresh agent for every call.
    - :func:`from_langgraph` — wrap a compiled LangGraph graph, one independent
      run per call (requires ``langgraph``).
    - :func:`from_langgraph_thread` — keep every call on one thread, for when
      the conversation itself is under test.
"""

from agentverity.adapters.callable_adapter import from_callable

__all__ = ["from_callable"]
