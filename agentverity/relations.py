"""Typed metamorphic relations for agent testing.

Relations are inherited from the metamorphic-testing tradition (Chen et al.)
and the semantic-invariance transforms of CheckList and LLMORPH. They are
typed ``INVARIANT`` / ``MONOTONE`` / ``DIRECTIONAL`` because on a
non-deterministic agent the types have different noise robustness: monotone
and directional relations can be less noise-sensitive than equality checks,
while invariance relations are often fragile. The framework reports the type
so users can interpret it against the meter.

The built-in catalogue is intentionally small and covers normalisation, case,
whitespace, and tool-selection invariance. Users define their own
agent-specific relations via the :class:`Relation` dataclass.

The relations are **not** the innovation — the diagnostics (meter, blindness)
are. They are the vehicle, presented as CheckList-lineage.

Example::

    from agentverity.relations import Relation, builtin_relations

    custom = Relation(
        name="my-monotone",
        rtype="monotone",
        transform=lambda s: s + " urgent",
        check=lambda src, fol: (
            {"allow": 0, "review": 1, "block": 2}[decision_label(src.key("verdict"))]
            <= {"allow": 0, "review": 1, "block": 2}[decision_label(fol.key("verdict"))]
        ),
    )
    relations = builtin_relations() + [custom]
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from agentverity.observation import Observation

from .decision import comparison_key

AgentFn = Callable[[str], Observation]

#: The relation types the report and the coverage table understand. A
#: relation declaring anything else would be counted and rendered under a name
#: no reader can interpret, so the set is closed and checked on construction.
RELATION_TYPES: frozenset[str] = frozenset({"invariant", "monotone", "directional"})

INVARIANT = "invariant"
MONOTONE = "monotone"
DIRECTIONAL = "directional"


@dataclass(frozen=True)
class Relation:
    """A metamorphic relation: a transform + a check between source and follow-up.

    Attributes:
        name: Human-readable identifier for the report.
        rtype: Relation type — ``"invariant"``, ``"monotone"``, or
            ``"directional"``.
        transform: Maps a source input string to a follow-up input string.
        check: Given ``(source_obs, followup_obs)``, return ``True`` if the
            relation holds (no violation), ``False`` if it is violated.
        description: Optional one-line summary for the report.
    """

    name: str
    rtype: str
    transform: Callable[[str], str]
    check: Callable[[Observation, Observation], bool]
    description: str = ""

    def __post_init__(self) -> None:
        """Refuse a relation that cannot be run or reported.

        Checked here rather than mid-run, because a relation is discovered to
        be broken after the source calls have been made and paid for. The same
        reason the CLI refuses a bad `--agent` before loading probes.

        Raises:
            ValueError: If the name is empty or the type is not one the report
                understands.
            TypeError: If the transform or the check is not callable.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("a relation needs a non-empty name for the report")
        if self.rtype not in RELATION_TYPES:
            raise ValueError(
                f"unknown relation type {self.rtype!r}; expected one of "
                + ", ".join(sorted(RELATION_TYPES))
            )
        for role, value in (("transform", self.transform), ("check", self.check)):
            if not callable(value):
                raise TypeError(
                    f"relation {self.name!r} needs a callable {role}, got "
                    f"{type(value).__name__}"
                )


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _normalise(text: str) -> str:
    """Invariance transform: strip accents and normalise whitespace."""
    return re.sub(r"\s+", " ", _strip_accents(text)).strip()


def _change_case(text: str) -> str:
    """Invariance transform: invert the case of every alphabetic character."""
    return "".join(c.swapcase() if c.isalpha() else c for c in text)


def _insert_whitespace(text: str) -> str:
    """Invariance transform: add a leading newline and trailing spaces."""
    return "\n" + text + "  "


def _verdict_invariant(source: Observation, followup: Observation) -> bool:
    """Invariance check: the verdict (or text fallback) must not change."""
    return comparison_key(source.key("verdict")) == comparison_key(
        followup.key("verdict")
    )


def _tools_invariant(source: Observation, followup: Observation) -> bool:
    """Tool-selection check: the tool trajectory must not change."""
    return source.key("tools") == followup.key("tools")


def builtin_relations() -> list[Relation]:
    """Return the built-in relation catalogue.

    The catalogue covers three text-level invariance transforms and one
    agent-level tool-selection invariance. Users extend it by constructing
    their own :class:`Relation` instances.

    Returns:
        A list of four :class:`Relation` objects.
    """
    return [
        Relation(
            name="normalisation-invariance",
            rtype=INVARIANT,
            transform=_normalise,
            check=_verdict_invariant,
            description="Accent stripping and whitespace normalisation must not change the verdict.",
        ),
        Relation(
            name="case-invariance",
            rtype=INVARIANT,
            transform=_change_case,
            check=_verdict_invariant,
            description="Inverting letter case must not change the verdict.",
        ),
        Relation(
            name="whitespace-invariance",
            rtype=INVARIANT,
            transform=_insert_whitespace,
            check=_verdict_invariant,
            description="Leading newline and trailing spaces must not change the verdict.",
        ),
        Relation(
            name="tool-selection-invariance",
            rtype=INVARIANT,
            transform=_normalise,
            check=_tools_invariant,
            description="Normalising the request must not change which tool the agent calls.",
        ),
    ]
