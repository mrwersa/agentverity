"""Reusable conformance checks for raw-run evidence importers.

An importer test supplies two small callables that translate the neutral
fixtures into its source format. Keeping the assertions here means a new
bridge cannot quietly weaken ordering, provenance, isolation, or aggregate
refusal while still producing an ``EvidenceSet``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentverity.evidence import EvidenceError, EvidenceSet

FIXTURES = Path(__file__).parent / "fixtures" / "integration_contract"


@dataclass(frozen=True)
class ImporterHarness:
    """Source-specific translators around the shared contract fixtures."""

    name: str
    import_runs: Callable[[Sequence[dict[str, str]]], EvidenceSet]
    import_aggregate: Callable[[dict[str, Any]], EvidenceSet]


def ordered_runs() -> tuple[dict[str, str], ...]:
    """Load raw observations in their production order."""
    return tuple(
        json.loads(line)
        for line in (FIXTURES / "ordered-runs.jsonl").read_text().splitlines()
        if line.strip()
    )


def aggregate() -> dict[str, Any]:
    """Load a summary that cannot recover individual ordered observations."""
    return json.loads((FIXTURES / "aggregate.json").read_text())


def assert_importer_conforms(harness: ImporterHarness) -> None:
    """Exercise the evidence properties every repository importer must keep."""
    evidence = harness.import_runs(ordered_runs())

    assert evidence.inputs == ("routine request", "ambiguous request")
    assert evidence.cases[0].observations == ("approve", "review")
    assert evidence.cases[1].observations == ("review", "review")
    assert evidence.isolation == "fresh-session"
    assert evidence.provenance["harness"] == harness.name
    assert EvidenceSet.from_dict(evidence.to_dict()) == evidence

    try:
        harness.import_aggregate(aggregate())
    except EvidenceError:
        pass
    else:
        raise AssertionError(
            f"{harness.name} accepted aggregate counts without raw observations"
        )
