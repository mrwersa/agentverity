"""A domain relation the built-in catalogue cannot express.

The catalogue covers text normalisation, case, and tool selection. It does not
know that in a payments product `GBP 40` and `£40` are the same amount written
two ways, and that a router treating them differently is a defect.

Run it::

    agentverity run --agent examples.toy_agent:deterministic_gate \\
        --inputs probes.txt \\
        --relations examples/custom_relation.py:catalogue

The function takes no arguments and returns relations, which is the same shape
`builtin_relations` has. It replaces the built-in catalogue rather than adding
to it, so include them yourself when you want both.
"""

from __future__ import annotations

from agentverity import Relation
from agentverity.relations import builtin_relations


def currency_symbol_invariance() -> Relation:
    """Writing an amount with a symbol must not change the route."""
    return Relation(
        name="currency-symbol-invariance",
        rtype="invariant",
        transform=lambda text: text.replace("GBP ", "£"),
        check=lambda source, followup: source.verdict == followup.verdict,
        description="`GBP 40` and `£40` are one amount, so one route.",
    )


def catalogue() -> list[Relation]:
    """The built-in relations plus the domain one above.

    A transform that leaves an input unchanged is counted as skipped rather
    than as a pass, so a relation that does not apply to most of a probe set
    reports as partial instead of quietly reading as evidence.
    """
    return [*builtin_relations(), currency_symbol_invariance()]


def domain_only() -> Relation:
    """Just the domain relation, for a run that wants nothing else."""
    return currency_symbol_invariance()
