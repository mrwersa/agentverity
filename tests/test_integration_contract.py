"""All in-tree importers satisfy one raw-evidence contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    evidence_from_deepeval,
    evidence_from_jsonl,
    evidence_from_promptfoo,
)
from tests.integration_contract import ImporterHarness, assert_importer_conforms


def _suite() -> DecisionSuite:
    return DecisionSuite(
        contract=DecisionContract(allowed={"approve", "review"}),
        cases=(
            DecisionCase("routine request", "approve"),
            DecisionCase("ambiguous request", "review"),
        ),
    )


def _jsonl_harness() -> ImporterHarness:
    def import_runs(rows):
        return evidence_from_jsonl(
            (json.dumps(row) for row in rows),
            suite=_suite(),
            isolation="fresh-session",
            provenance={"harness": "jsonl"},
        )

    def import_aggregate(summary):
        row = {"input": summary["input"], "decision": summary["counts"]}
        return evidence_from_jsonl((json.dumps(row), json.dumps(row)))

    return ImporterHarness("jsonl", import_runs, import_aggregate)


@dataclass
class _DeepEvalCase:
    input: str
    actual_output: Any


def _deepeval_harness() -> ImporterHarness:
    def import_runs(rows):
        return evidence_from_deepeval(
            (_DeepEvalCase(row["input"], row["decision"]) for row in rows),
            isolation="fresh-session",
        )

    def import_aggregate(summary):
        return evidence_from_deepeval(
            (
                _DeepEvalCase(summary["input"], summary["counts"]),
                _DeepEvalCase(summary["input"], summary["counts"]),
            )
        )

    return ImporterHarness("deepeval", import_runs, import_aggregate)


def _promptfoo_harness() -> ImporterHarness:
    def export(rows):
        return {
            "version": 4,
            "timestamp": "2026-08-22T00:00:00Z",
            "results": [
                {
                    "testIdx": index,
                    "promptIdx": 0,
                    "promptId": "contract",
                    "provider": {"id": "fixture"},
                    "prompt": {"raw": row["input"]},
                    "response": {"output": row["decision"]},
                    "failureReason": 0,
                }
                for index, row in enumerate(rows)
            ],
        }

    def import_runs(rows):
        return evidence_from_promptfoo(
            export(rows), _suite(), isolation="fresh-session"
        )

    def import_aggregate(summary):
        return evidence_from_promptfoo(
            {"version": 4, "metrics": summary["counts"]}, _suite()
        )

    return ImporterHarness("promptfoo", import_runs, import_aggregate)


@pytest.mark.parametrize(
    "harness",
    [_jsonl_harness(), _deepeval_harness(), _promptfoo_harness()],
    ids=lambda harness: harness.name,
)
def test_importer_satisfies_the_shared_evidence_contract(harness):
    """Order, provenance, isolation, round trips, and refusal stay aligned."""
    assert_importer_conforms(harness)
