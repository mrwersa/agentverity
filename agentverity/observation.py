"""The uniform shape an agent produces, that relations and the meter assert over.

An adapter turns any agent (Strands, LangGraph, a bare callable) into a function
``run(input) -> Observation``. Relations and diagnostics never touch the agent
library directly; they only see Observation. This is what keeps the core
library-agnostic.

Example::

    from agentverity.observation import Observation
    obs = Observation(text="allow", verdict="allow", tools=("search",))
    assert obs.key("verdict") == "allow"
    assert obs.key("tools") == ("search",)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Observation:
    """One run of an agent on one input.

    Attributes:
        text: The agent's final response as a string. Always present.
        verdict: An optional extracted categorical decision (e.g.
            ``"allow"``/``"block"``, ``"safe"``/``"unsafe"``). Supplied by a
            user verdict-extractor when the agent is a gate or classifier.
            ``None`` for open-ended agents.
        tools: The ordered tool names the agent called (its trajectory).
            Empty tuple if the agent uses no tools or the adapter cannot
            see them.
        raw: The underlying result object, for user-defined custom relations.
    """

    text: str = ""
    verdict: str | None = None
    tools: tuple[str, ...] = ()
    raw: Any = None

    def key(self, on: str = "verdict") -> Any:
        """Return the comparison key for a relation or the meter.

        Args:
            on: Which layer to compare on. ``"verdict"`` (the categorical
                decision, falling back to ``text`` if no verdict is set),
                ``"text"`` (exact final text), or ``"tools"`` (the tool-call
                sequence).

        Returns:
            A hashable value suitable for equality comparison.

        Raises:
            ValueError: If ``on`` is not one of the supported layers.
        """
        if on == "verdict":
            return self.verdict if self.verdict is not None else self.text
        if on == "text":
            return self.text
        if on == "tools":
            return self.tools
        raise ValueError(f"unknown observation layer: {on!r}")
