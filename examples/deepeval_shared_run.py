"""Evaluate quality and evidence from one set of target calls.

Install the optional example dependency first:

    pip install "agentverity[showcase]"
"""

from __future__ import annotations

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from deepeval.metrics import ExactMatchMetric
from deepeval.test_case import LLMTestCase

from agentverity import (
    assess_evidence,
    evidence_from_deepeval,
    load_decision_suite,
)
from examples.promptfoo_bridge.router import route


def main() -> None:
    suite = load_decision_suite("examples/payment_decisions.json")
    repeated_cases = []

    # These are the only target calls. Both tools consume their outputs.
    for case in suite.cases:
        for _ in range(26):
            repeated_cases.append(
                LLMTestCase(
                    input=case.input,
                    actual_output=route(case.input),
                    expected_output=case.expected,
                )
            )

    quality_passes = 0
    for test_case in repeated_cases:
        metric = ExactMatchMetric()
        metric.measure(
            test_case,
            _show_indicator=False,
            _log_metric_to_confident=False,
        )
        quality_passes += int(metric.is_successful())

    evidence = evidence_from_deepeval(
        repeated_cases,
        isolation="fresh-session",
    )
    result = assess_evidence(evidence, suite, epsilon=0.05)

    print(f"DeepEval exact match: {quality_passes}/{len(repeated_cases)}")
    print(result.headline)


if __name__ == "__main__":
    main()
