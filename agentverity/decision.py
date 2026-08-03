"""What an agent decided, or why it did not decide.

A categorical layer needs one comparison key per run. The old rule was "the
verdict, or the text if there is no verdict", which compares two reworded
refusals as different decisions. That measures wording rather than choice.

The obvious repair, a single ``UNSET`` sentinel, is worse. At least six
distinct events reach an unset verdict, and folding them together makes a run
of extraction failures look like a perfectly stable decision. On the AgentKit
nova run, one probe returns no tool 80 times out of 146; a sentinel would score
that as strong agreement about nothing.

So the absence of a decision is typed and carries its reason, and the reasons
split into two groups that the evidence treats differently. See DESIGN.md
ADR 2.

Example::

    from agentverity.decision import Decision, NoDecision

    Decision("refund") == Decision("refund")            # True
    NoDecision("refused") == NoDecision("refused")      # True, however worded
    NoDecision("refused") == Decision("refused")        # False
    NoDecision("extraction_failed").is_incomplete       # True
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final


class OutcomeNotScorable(ValueError):
    """This evidence cannot be scored as it stands, and the message says why.

    Raised wherever a typed outcome reaches a consumer that cannot honestly
    account for it: a repeat series holding a harness failure, a series with
    too few comparable observations, or a contract that cannot yet declare a
    no-decision outcome.

    It subclasses ``ValueError`` because that is what the meter already raised
    for unscorable evidence, and because the neighbouring refusals in this
    package (``EvidenceError``, ``SnapshotRefused``) do the same. One type for
    one condition, so a caller catching it catches every path.
    """


#: Reasons an agent did not produce a decision. Closed set, versioned with the
#: evidence schema, because a stored reason has to mean the same thing later.
NO_DECISION_REASONS: Final[frozenset[str]] = frozenset(
    {
        # Things the agent did. A contract may declare these as allowed
        # outcomes, and then they are ordinary categorical results.
        "no_tool_selected",
        "refused",
        # The layer is categorical and the answer was not. Comparable to
        # nothing, so it is excluded from pairs rather than counted as one.
        "open_ended",
        # Things the harness could not do. These make the evidence incomplete,
        # because certifying stability over them would certify the failure.
        "extraction_failed",
        "malformed_response",
        "runtime_error",
    }
)

#: Reasons that mean the harness failed rather than the agent answering.
INCOMPLETE_REASONS: Final[frozenset[str]] = frozenset(
    {"extraction_failed", "malformed_response", "runtime_error"}
)

#: Reasons a contract may declare as allowed categorical outcomes.
DECLARABLE_REASONS: Final[frozenset[str]] = frozenset(
    {"no_tool_selected", "refused"}
)


@dataclass(frozen=True, slots=True)
class Decision:
    """The agent chose, and ``label`` is the choice."""

    label: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("a Decision needs a non-empty string label")

    @property
    def is_incomplete(self) -> bool:
        return False

    @property
    def comparable(self) -> bool:
        """Whether this result can take part in a paired comparison."""
        return True

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True, slots=True)
class NoDecision:
    """The agent did not choose, and ``reason`` says why.

    Two ``NoDecision`` values are equal when their reasons match, which is what
    makes two differently worded refusals one decision again. A ``NoDecision``
    is never equal to a ``Decision``, even one whose label is the same string.
    """

    reason: str

    def __post_init__(self) -> None:
        if self.reason not in NO_DECISION_REASONS:
            raise ValueError(
                f"unknown no-decision reason {self.reason!r}; "
                f"expected one of {', '.join(sorted(NO_DECISION_REASONS))}"
            )

    @property
    def is_incomplete(self) -> bool:
        """Whether this means the harness failed rather than the agent answered.

        An incomplete result must not be scored as a stable decision. Certifying
        stability over repeated extraction failures certifies the failure.
        """
        return self.reason in INCOMPLETE_REASONS

    @property
    def comparable(self) -> bool:
        """Open-ended output is comparable to nothing on a categorical layer."""
        return self.reason != "open_ended"

    def __str__(self) -> str:
        return f"<no decision: {self.reason}>"


#: Either shape, wherever one run's categorical result is passed around.
Outcome = Decision | NoDecision


def as_outcome(value: object) -> Outcome:
    """Read an outcome from a stored or user-supplied value.

    A bare string is a `Decision`, because that is what it meant when it was
    written. Evidence recorded before ADR 2 stored the reason strings that
    adapters invented, and reading them as `NoDecision` now would change the
    meaning of committed files. The schema version, not this function, is what
    distinguishes the two.
    """
    if isinstance(value, (Decision, NoDecision)):
        return value
    if isinstance(value, str) and value:
        return Decision(value)
    raise ValueError(f"cannot read an outcome from {value!r}")


def check_scorable(observations: Sequence[object], layer: str = "verdict") -> None:
    """Refuse a repeat series that cannot honestly be scored for stability.

    One helper, called from both pooled and per-route scoring, because two
    implementations of the same rule is how the per-route path silently
    accepted repeated extraction failures while the pooled path refused them.

    Args:
        observations: One repeat series. Anything exposing ``key(layer)``.
        layer: The comparison layer. Only ``"verdict"`` carries typed outcomes.

    Raises:
        OutcomeNotScorable: If the series holds a harness failure, or any
            open-ended result.
    """
    if layer != "verdict":
        return
    for observation in observations:
        key = observation.key(layer) if hasattr(observation, "key") else observation
        if not isinstance(key, NoDecision):
            continue
        if key.is_incomplete:
            raise OutcomeNotScorable(
                f"a repeat series contains {key}, which means the harness "
                "failed rather than the agent answering. Evidence containing "
                "it is incomplete and must not be scored for stability."
            )
        if not key.comparable:
            raise OutcomeNotScorable(
                f"a repeat series contains {key}. Categorical stability is "
                "undefined when a run produced no decision, and dropping those "
                "runs while keeping the repeat count would report stability "
                "over reruns that did not decide anything. Measure a "
                "conditional rate deliberately, or fix the probe."
            )


def comparison_key(value: object) -> object:
    """Normalise one observation key so equal decisions compare equal.

    A v2 evidence file may legitimately hold a bare ``"refund"`` written by an
    adapter that has not adopted the types, beside a ``Decision("refund")``
    written by one that has. Those are the same decision, and comparing them
    unequal reports a flip on a decision this package elsewhere says is
    identical. That is the same "two readings that disagree" defect ADR 2
    exists to remove, at the string-versus-typed seam.

    Normalising here rather than in ``Observation.key`` is deliberate. ``key``
    feeds reporting, blindness and snapshot storage, and snapshots refuse a
    tagged value, so promoting there would refuse every ordinary string
    verdict. Comparison is the only place that needs one key.
    """
    if isinstance(value, str):
        return Decision(value) if value else value
    return value
