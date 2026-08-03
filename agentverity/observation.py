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

from .decision import Decision, NoDecision, Outcome


@dataclass(frozen=True)
class Observation:
    """One run of an agent on one input.

    Attributes:
        text: The agent's final response as a string. Always present.
        verdict: An optional extracted categorical decision (e.g.
            ``"allow"``/``"block"``, ``"safe"``/``"unsafe"``). Supplied by a
            user verdict-extractor when the agent is a gate or classifier.
            ``None`` for open-ended agents.

            It may also be a :class:`~agentverity.decision.NoDecision`, which
            is how an adapter says the agent did not choose and why, without
            inventing a label. See DESIGN.md ADR 2.
        tools: The ordered tool names the agent called (its trajectory).
            Empty tuple if the agent uses no tools or the adapter cannot
            see them.
        raw: The underlying result object, for user-defined custom relations.
    """

    text: str = ""
    verdict: str | Outcome | None = None
    tools: tuple[str, ...] = ()
    raw: Any = None

    @property
    def outcome(self) -> Outcome:
        """The categorical result of this run, typed.

        A `NoDecision` verdict is returned as it stands. A string verdict is a
        `Decision`. An unset verdict on an agent that produced text is
        open-ended, which is comparable to nothing on a categorical layer.
        """
        if isinstance(self.verdict, (Decision, NoDecision)):
            return self.verdict
        if isinstance(self.verdict, str) and self.verdict:
            return Decision(self.verdict)
        return NoDecision("open_ended")

    @property
    def is_incomplete(self) -> bool:
        """Whether the harness failed rather than the agent answering."""
        return self.outcome.is_incomplete

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
            # A typed absence compares on its reason, so two reworded refusals
            # are one decision. A bare string keeps its meaning. Only a truly
            # unset verdict still falls back to the text, which is the old
            # behaviour and the reason ADR 2 exists.
            if isinstance(self.verdict, (Decision, NoDecision)):
                return self.verdict
            # An empty string is not a decision. Treating it as one made this
            # path disagree with `outcome`, which called it open-ended. Other
            # non-string verdicts, such as a sequence, keep their old meaning.
            if isinstance(self.verdict, str) and not self.verdict:
                return self.text
            return self.verdict if self.verdict is not None else self.text
        if on == "text":
            return self.text
        if on == "tools":
            return self.tools
        raise ValueError(f"unknown observation layer: {on!r}")
