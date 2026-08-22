"""Generate durable-format fixtures with a selected AgentVerity release.

Run this outside the repository root with the selected release installed so
the checkout cannot shadow the wheel under test. The committed v0.16.0 files
are historical inputs: do not regenerate them with the current package.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentverity import (
    DECISION_SUITE_SCHEMA,
    EVIDENCE_SCHEMA,
    SNAPSHOT_SCHEMA,
    Decision,
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceCase,
    EvidenceSet,
    NoDecision,
    Snapshot,
    SnapshotProbe,
    __version__,
    plan_repeats,
    save_decision_suite,
    save_evidence,
    save_snapshot,
)
from agentverity.meter import wilson_ci


def generate(output: Path, expected_version: str) -> None:
    """Write deterministic fixtures, refusing the wrong installed release."""
    if __version__ != expected_version:
        raise SystemExit(
            f"expected agentverity {expected_version}, imported {__version__}; "
            "run from outside the repository with the historical wheel installed"
        )

    output.mkdir(parents=True, exist_ok=True)
    contract = DecisionContract(
        allowed={"approve", "review"},
        allowed_no_decisions={"refused"},
    )
    suite = DecisionSuite(
        contract=contract,
        cases=(
            DecisionCase("routine request", "approve"),
            DecisionCase("ambiguous request", "review"),
        ),
    )
    evidence = EvidenceSet(
        cases=(
            EvidenceCase(
                "routine request",
                (Decision("approve"), Decision("approve")),
                expected="approve",
            ),
            EvidenceCase(
                "ambiguous request",
                (NoDecision("refused"), NoDecision("refused")),
                expected="review",
            ),
        ),
        isolation="fresh-session",
        provenance={"fixture": "cross-version", "producer": expected_version},
    )
    repeats = plan_repeats(2, epsilon=0.05)
    pair_trials = 2 * (repeats // 2)
    snapshot = Snapshot(
        schema=SNAPSHOT_SCHEMA,
        created_at="2026-08-01T00:00:00+00:00",
        agentverity_version=expected_version,
        layer="verdict",
        epsilon=0.05,
        k=repeats,
        blindness_threshold=0.9,
        meter_pair_trials=pair_trials,
        meter_ci_high=wilson_ci(0, pair_trials)[1],
        blindness_skew=0.5,
        blindness_distinct=2,
        decision_contract=contract,
        probes=(
            # SnapshotProbe receives the JSON-safe values create_snapshot
            # would have derived from the typed outcomes.
            SnapshotProbe("a" * 64, "approve", "approve"),
            SnapshotProbe(
                "b" * 64,
                {"kind": "no_decision", "reason": "refused"},
                "review",
            ),
        ),
        isolation="fresh-session",
    )

    save_decision_suite(suite, output / "decision-suite.json")
    save_evidence(evidence, output / "evidence.json")
    save_snapshot(snapshot, output / "snapshot.json")
    manifest = {
        "producer": f"agentverity=={expected_version}",
        "schemas": {
            "decision_suite": DECISION_SUITE_SCHEMA,
            "evidence": EVIDENCE_SCHEMA,
            "snapshot": SNAPSHOT_SCHEMA,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Parse the target directory and expected installed release."""
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    generate(args.output, args.expected_version)


if __name__ == "__main__":
    main()
