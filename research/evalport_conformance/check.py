"""Rehearse the reviewed synthetic EvalPort fixture profile, offline.

The public AgentVerity import surface does not consume EvalPort. This module
projects only the named synthetic suite below so the conformance review can
check what the declared fields support without claiming a general importer.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

from agentverity import EvidenceCase, EvidenceError, EvidenceSet, assess_evidence

HERE = Path(__file__).resolve().parent
CASE_INPUTS = {
    "case_a": "synthetic routing probe",
    "case_b": "synthetic secondary probe",
}
ISOLATION = {
    "fresh-session": "fresh-session",
    "fresh-instance": "fresh-instance",
    "shared-session": "shared-session",
    "shared": "shared-session",
}


def _project_review_fixture(document: dict[str, Any]) -> EvidenceSet:
    """Project this review's validated ResultSet fixtures to real evidence.

    The synthetic suite supplies case identity. The caller validates the
    document with EvalPort first. Additional refusals below are this review's
    consumer policy, rather than new EvalPort schema requirements.
    """
    if document.get("suite_id") != "suite_agentverity_repetition_review":
        raise EvidenceError("this rehearsal only supports its synthetic review suite")
    rows = document.get("results")
    if not isinstance(rows, list) or not rows:
        raise EvidenceError("EvalPort review requires individual Result observations")
    grouped: OrderedDict[str, dict[int, str]] = OrderedDict()
    for row in rows:
        case_id = row["test_case_id"]
        if case_id not in CASE_INPUTS:
            raise EvidenceError("EvalPort review contains an unreviewed case identity")
        if "error" in row:
            raise EvidenceError(
                "EvalPort review contains a recorded runner/provider failure; "
                "the collection is incomplete"
            )
        attempt = row.get("attempt")
        if type(attempt) is float and attempt.is_integer():
            attempt = int(attempt)
        if type(attempt) is not int or attempt < 1:
            raise EvidenceError("EvalPort review needs an explicit positive attempt")
        observations = grouped.setdefault(case_id, {})
        if attempt in observations:
            raise EvidenceError("EvalPort review contains a duplicate case/run/attempt")
        decision = row.get("actual_output")
        if not isinstance(decision, str) or not decision:
            raise EvidenceError("EvalPort review needs a non-empty actual_output decision")
        observations[attempt] = decision
    cases = []
    for case_id, observations in grouped.items():
        attempts = sorted(observations)
        if attempts != list(range(1, len(attempts) + 1)):
            raise EvidenceError("EvalPort review refuses gaps in the attempt schedule")
        cases.append(EvidenceCase(
            input=CASE_INPUTS[case_id],
            observations=tuple(observations[index] for index in attempts),
        ))
    declared = document.get("isolation")
    return EvidenceSet(
        cases=tuple(cases),
        layer="verdict",
        isolation=ISOLATION.get(declared, "unknown"),
        provenance={
            "harness": "evalport-conformance-review",
            "source_isolation": declared,
            "source_run_id": document["run_id"],
            "projection": "actual_output as a synthetic decision label",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evalport-root", type=Path, required=True)
    args = parser.parse_args()
    sdk = args.evalport_root.resolve() / "sdk" / "python"
    sys.path.insert(0, str(sdk))
    import openeval.validate as sdk_validator

    if not Path(sdk_validator.__file__).resolve().is_relative_to(sdk):
        raise RuntimeError("the validator did not load from the supplied EvalPort checkout")
    upstream_fixtures = args.evalport_root / "spec" / "conformance" / "fixtures"
    for name in (
        "multi_attempt_resultset_valid.json",
        "duplicate_attempt_collision_rejected.json",
    ):
        fixture = json.loads((upstream_fixtures / name).read_text())
        validation = sdk_validator.validate_result_set(fixture["document"])
        assert validation.valid == fixture["expect"]["valid"], validation.errors
        print(f"{name}: expected SDK validity {validation.valid}")
    expected_pairs = {
        "four_attempt_disagreement_valid.json": (2, 1),
        "interleaved_attempt_order_valid.json": (4, 0),
        "repeated_shared_session_valid.json": (4, 0),
    }
    for path in sorted((HERE / "fixtures").glob("*.json")):
        fixture = json.loads(path.read_text())
        document = fixture["document"]
        validation = sdk_validator.validate_result_set(document)
        assert validation.valid, validation.errors
        if path.name == "repeated_runner_error_valid.json":
            try:
                _project_review_fixture(document)
            except EvidenceError as exc:
                assert "incomplete" in str(exc)
                print(f"{path.name}: SDK valid; consumer refuses incomplete evidence")
            else:
                raise AssertionError("a runner failure was counted as decision evidence")
        else:
            evidence = _project_review_fixture(document)
            assert EvidenceSet.from_dict(evidence.to_dict()) == evidence
            result = assess_evidence(evidence)
            actual = (result.meter.pair_trials, result.meter.pair_flips)
            assert actual == expected_pairs[path.name], actual
            print(f"{path.name}: SDK valid; {actual[1]}/{actual[0]} pair flips; "
                  f"isolation={evidence.isolation}")
    print("PASS: structural checks and the bounded consumer rehearsal agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
