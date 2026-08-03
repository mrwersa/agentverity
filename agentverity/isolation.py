"""How an adapter says what it did to keep repeated trials apart.

ADR 5 made isolation decide whether evidence may certify a baseline, and then
had nothing to read on a live run: the runner set nothing, so every baseline
and every later check said `unknown` and the policy never fired.

The knowledge existed and was discarded. An adapter that builds a new agent
per trial, or gives every call a fresh conversation thread, knows that as a
mechanical fact. This is how it says so, and how `run` reads it.

The declaration describes what the adapter did, not which function the caller
reached for. `from_langgraph` respects a caller-supplied `thread_id`, and a
declaration keyed on the function name would claim `fresh-session` exactly
where the caller had turned it off. See DESIGN.md ADR 6.
"""

from __future__ import annotations

from typing import Any, TypeVar

from .evidence import ISOLATION_LEVELS

#: Where a declaration is stored on the callable. Private by name, because it
#: is a contract between the adapters and the runner rather than an API.
ISOLATION_ATTRIBUTE = "__agentverity_isolation__"

F = TypeVar("F")


def declare_isolation(agent: F, level: str) -> F:
    """Record what an adapter did to separate repeated trials.

    Args:
        agent: The wrapped callable the adapter is about to return.
        level: One of `ISOLATION_LEVELS`. Say what happened, not what was
            wanted: an adapter that shares a session declares
            `shared-session`, and that evidence is then refused a baseline.

    Returns:
        The same callable, so a wrapper can `return declare_isolation(run, ...)`.

    Raises:
        ValueError: If the level is not one the evidence format defines.
    """
    if level not in ISOLATION_LEVELS:
        raise ValueError(
            f"unknown isolation {level!r}; expected one of "
            + ", ".join(ISOLATION_LEVELS)
        )
    try:
        setattr(agent, ISOLATION_ATTRIBUTE, level)
    except AttributeError:  # a builtin or a slotted object
        return agent
    return agent


def isolation_of(agent: Any) -> str:
    """Read what an agent declared, or `unknown` when it declared nothing.

    A plain function says nothing about what happens inside it, and `unknown`
    is the honest answer rather than a permissive one: it is admitted with a
    caveat, and only a stated `shared-session` is refused.
    """
    level = getattr(agent, ISOLATION_ATTRIBUTE, None)
    return level if level in ISOLATION_LEVELS else "unknown"
