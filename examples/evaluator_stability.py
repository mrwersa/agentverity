"""Qualify repeated categorical judgements without calling a provider.

An LLM judge may return ``pass``, ``fail``, or ``uncertain`` for the same
agent trace. AgentVerity can assess whether those verdicts are repeatable. It
does not establish whether the judge is correct. Human-labelled examples are
still needed for that.
"""

from __future__ import annotations

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    EvidenceCase,
    EvidenceSet,
    assess_evidence,
)


def build_evidence() -> EvidenceSet:
    """Return recorded judge verdicts from three human-labelled traces."""
    return EvidenceSet(
        cases=(
            EvidenceCase(
                input="trace: supported refund",
                observations=("pass",) * 26,
                expected="pass",
            ),
            EvidenceCase(
                input="trace: ambiguous policy exception",
                observations=("pass", "uncertain") * 13,
                expected="pass",
            ),
            EvidenceCase(
                input="trace: unsupported refund",
                observations=("fail",) * 26,
                expected="fail",
            ),
        ),
        layer="verdict",
        isolation="fresh-instance",
        provenance={
            "judge": "example-policy-judge",
            "rubric": "refund-policy/v1",
            "target_kind": "evaluator-verdict",
        },
    )


def build_contract() -> DecisionSuite:
    """Declare which human-labelled classes must be stable."""
    return DecisionSuite(
        contract=DecisionContract(
            allowed={"pass", "fail", "uncertain"},
            required={"pass", "fail"},
            stability_targets={"pass": 0.05, "fail": 0.05},
        ),
        cases=(
            DecisionCase("trace: supported refund", "pass"),
            DecisionCase("trace: ambiguous policy exception", "pass"),
            DecisionCase("trace: unsupported refund", "fail"),
        ),
    )


def main() -> None:
    result = assess_evidence(
        build_evidence(),
        build_contract(),
        epsilon=0.05,
    )

    print("Evaluator verdict stability")
    print(result.headline)
    if result.route_stability is not None:
        print(
            "unstable human-labelled classes: "
            + ", ".join(result.route_stability.stochastic)
        )
    print("Validity still requires comparison with human-labelled examples.")


if __name__ == "__main__":
    main()
