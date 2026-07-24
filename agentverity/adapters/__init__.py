"""Adapters turn a real agent into ``run(input) -> Observation``.

Only ``callable`` is imported here (zero deps). Library adapters (Strands,
LangGraph) are imported lazily from their own modules so the core installs
without those libraries present.

Available adapters:
    - :func:`from_callable` — wrap any ``fn(input) -> str | dict | Observation``.
    - :func:`from_strands` — wrap a Strands ``Agent`` (requires ``strands-agents``).
"""

from agentverity.adapters.callable_adapter import from_callable

__all__ = ["from_callable"]
