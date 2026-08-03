"""Adapter for any bare callable agent: fn(input) -> str | dict | Observation.

The most general adapter, and the one used for non-library agents and tests.
Returns an AgentFn: (input:str) -> Observation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentverity.isolation import declare_isolation, isolation_of
from agentverity.observation import Observation


def from_callable(fn: Callable[[str], Any], *,
                  verdict_key: str | None = None,
                  tools_key: str | None = None):
    """Wrap `fn` so it yields an Observation.

    fn may return:
      - a str            -> becomes Observation.text
      - an Observation   -> passed through
      - a dict           -> read 'text'/'verdict'/'tools', or use verdict_key/
                            tools_key to name the fields to pull out.
    """
    def run(x: str) -> Observation:
        out = fn(x)
        if isinstance(out, Observation):
            return out
        if isinstance(out, str):
            return Observation(text=out)
        if isinstance(out, dict):
            text = str(out.get("text", ""))
            verdict = out.get(verdict_key) if verdict_key else out.get("verdict")
            raw_tools = out.get(tools_key) if tools_key else out.get("tools")
            tools = tuple(raw_tools) if isinstance(raw_tools, (list, tuple)) else ()
            return Observation(text=text,
                               verdict=(str(verdict) if verdict is not None else None),
                               tools=tools, raw=out)
        # anything else: stringify into text, keep raw
        return Observation(text=str(out), raw=out)

    # Carried through, not invented. This adapter reshapes a return value and
    # changes nothing about how trials are separated, so an underlying
    # declaration is still true afterwards. The CLI loads every agent through
    # here, and dropping it meant an adapter's statement died at the command
    # line: a Strands factory reported `unknown` and its baseline was admitted
    # on the caveat the whole policy exists to replace. A plain function still
    # declares nothing, because it has nothing to carry.
    return declare_isolation(run, isolation_of(fn))
