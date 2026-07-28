"""Evidence-gate demo using one payment router and two probe sets.

Both probe sets score 6/6 against their expected routes. The narrow set only
exercises one verdict, so AgentVerity refuses to freeze it as a system-wide
baseline. The repaired set crosses the router's decision boundary and is
admitted.

Run from the repository root:

    python examples/payment_dispute_gate.py
    python examples/payment_dispute_gate.py --output-dir /tmp/agentverity-demo

Use ``--otel`` inside an existing OpenTelemetry process to emit one aggregate
span for each suite.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from agentverity import (
    DecisionCase,
    DecisionContract,
    DecisionSuite,
    RunResult,
    SnapshotRefused,
    create_snapshot,
    from_callable,
    record_otel_run,
    run,
    save_snapshot,
    write_junit_xml,
)

Case = tuple[str, str]

NARROW_CASES: tuple[Case, ...] = (
    ("My card was charged twice for the same order.", "duplicate_charge"),
    ("The same restaurant payment appears twice.", "duplicate_charge"),
    ("I can see duplicate identical card transactions.", "duplicate_charge"),
    ("A payment was duplicated on my statement.", "duplicate_charge"),
    ("The merchant billed me twice.", "duplicate_charge"),
    ("There is a duplicate charge for one purchase.", "duplicate_charge"),
)

DIVERSE_CASES: tuple[Case, ...] = (
    ("My card was charged twice for the same order.", "duplicate_charge"),
    ("The shop promised a refund but it has not arrived.", "refund_delay"),
    ("I do not recognise this card purchase.", "card_security"),
    ("The merchant charged more than the agreed amount.", "merchant_dispute"),
    ("Cash came out of my balance but the ATM dispensed nothing.", "cash_withdrawal"),
    ("The transfer is still pending after two days.", "transfer_delay"),
)

DECISION_CONTRACT = DecisionContract(
    allowed={expected for _, expected in DIVERSE_CASES},
    critical={"card_security"},
)


def route_dispute(text: str) -> dict[str, str]:
    """Route a synthetic payment dispute to a categorical queue."""
    lowered = text.lower()
    if any(term in lowered for term in ("twice", "duplicate", "duplicated")):
        verdict = "duplicate_charge"
    elif "refund" in lowered:
        verdict = "refund_delay"
    elif any(term in lowered for term in ("do not recognise", "stolen")):
        verdict = "card_security"
    elif any(term in lowered for term in ("more than", "wrong amount")):
        verdict = "merchant_dispute"
    elif any(term in lowered for term in ("atm", "cash")):
        verdict = "cash_withdrawal"
    else:
        verdict = "transfer_delay"
    return {"text": f"route: {verdict}", "verdict": verdict}


def build_agent():
    """Factory used by the AgentVerity CLI."""
    return route_dispute


def _evaluate(cases: tuple[Case, ...]) -> tuple[int, int]:
    correct = sum(route_dispute(text)["verdict"] == expected for text, expected in cases)
    return correct, len(cases)


def _run_suite(cases: tuple[Case, ...]):
    suite = DecisionSuite(
        contract=DECISION_CONTRACT,
        cases=tuple(
            DecisionCase(input=text, expected=expected)
            for text, expected in cases
        ),
    )
    return run(from_callable(route_dispute), suite=suite, relations=[])


def _quality_junit_xml(suite_name: str, cases: tuple[Case, ...]) -> str:
    """Return one exact-match evaluator result in JUnit form."""
    correct, total = _evaluate(cases)
    failures = int(correct != total)
    root = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": "1",
            "failures": str(failures),
            "errors": "0",
            "skipped": "0",
            # Without this, report collectors render the duration as "NaNms".
            "time": "0.000",
        },
    )
    case = ET.SubElement(
        root,
        "testcase",
        {"classname": suite_name, "name": "exact_match_routes"},
    )
    detail = f"{correct}/{total} routes matched their reviewed labels"
    if failures:
        ET.SubElement(case, "failure", {"message": detail}).text = detail
    else:
        ET.SubElement(case, "system-out").text = detail
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def _print_suite(
    name: str,
    cases: tuple[Case, ...],
    result,
    snapshot_state: str,
) -> None:
    correct, total = _evaluate(cases)
    verdicts = Counter(route_dispute(text)["verdict"] for text, _ in cases)
    mix = ", ".join(f"{verdict}={count}" for verdict, count in verdicts.items())
    print(f"{name}")
    print("-" * len(name))
    print(f"Exact-match evaluator: {correct}/{total} correct")
    print(f"Verdict mix: {mix}")
    print(f"AgentVerity: {result.headline}")
    print(f"Baseline: {snapshot_state}")
    print()


def _markdown_row(label: str, result: RunResult, cases: tuple[Case, ...]) -> str:
    """One probe set as a single comparison row."""
    correct, total = _evaluate(cases)
    stability = result.meter.call if result.meter else "not measured"
    assert result.decision_coverage is not None
    observed = len(DECISION_CONTRACT.required or ()) - len(
        result.decision_coverage.missing_observed
    )
    required = len(DECISION_CONTRACT.required or ())
    coverage = (
        f"✅ {observed}/{required} required routes"
        if result.decision_coverage.satisfied
        else f"❌ {observed}/{required} required routes"
    )
    baseline = (
        "✅ ADMITTED"
        if result.decision_coverage.satisfied and not result.is_blind
        else "❌ REFUSED"
    )
    return (
        f"| {label} | ✅ {correct}/{total} | ✅ {stability} | {coverage} "
        f"| {baseline} |"
    )


def _markdown_report(narrow: RunResult, repaired: RunResult) -> str:
    """Render the gate result as one comparison table.

    Both probe sets side by side in a single table, because the finding is the
    contrast between them. Two separate tables make the reader hold one set of
    numbers in their head while they read the other.

    Deliberately unnumbered and unheaded: this block leads a CI job summary
    whose detailed reports carry their own numbered titles, and duplicating
    that numbering reads as four sections rather than two.
    """
    return "\n".join([
        "| Probe set | Exact-match | Verdict stability | Declared coverage | Baseline |",
        "|---|---|---|---|---|",
        _markdown_row("Narrow, 6 duplicate-charge cases", narrow, NARROW_CASES),
        _markdown_row("Repaired, 6 dispute categories", repaired, DIVERSE_CASES),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write JUnit reports and the admitted snapshot to this directory.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print the gate result as a Markdown table for a README or a CI "
             "job summary.",
    )
    parser.add_argument(
        "--otel",
        action="store_true",
        help="Emit aggregate spans through the configured OpenTelemetry provider.",
    )
    args = parser.parse_args()

    narrow = _run_suite(NARROW_CASES)
    repaired = _run_suite(DIVERSE_CASES)

    try:
        create_snapshot(narrow, approved=True)
    except SnapshotRefused as exc:
        narrow_state = f"REFUSED - {exc}"
    else:  # pragma: no cover - a regression guard, not an expected branch
        narrow_state = "ADMITTED (unexpected)"

    repaired_snapshot = create_snapshot(repaired, approved=True)
    repaired_state = (
        "ADMITTED - evidence is complete, stable, and covers the contract"
    )

    print("PAYMENT-DISPUTE ROUTER: THE EVIDENCE GATE")
    print("=" * 42)
    print()
    _print_suite("BEFORE: narrow probe set", NARROW_CASES, narrow, narrow_state)
    _print_suite("AFTER: repaired probe set", DIVERSE_CASES, repaired, repaired_state)

    if args.markdown:
        print()
        print(_markdown_report(narrow, repaired))

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        # Suite names have to say which probe set they came from. Both reports
        # land in one Actions summary, and a pair of suites both called
        # "agentverity" leaves a reader unable to tell refused from admitted.
        write_junit_xml(
            narrow,
            args.output_dir / "narrow-agentverity.xml",
            suite_name="narrow-probes.agentverity",
        )
        write_junit_xml(
            repaired,
            args.output_dir / "repaired-agentverity.xml",
            suite_name="repaired-probes.agentverity",
        )
        (args.output_dir / "narrow-quality.xml").write_text(
            _quality_junit_xml("narrow-probes.exact-match", NARROW_CASES),
            encoding="utf-8",
        )
        (args.output_dir / "repaired-quality.xml").write_text(
            _quality_junit_xml("repaired-probes.exact-match", DIVERSE_CASES),
            encoding="utf-8",
        )
        save_snapshot(repaired_snapshot, args.output_dir / "repaired-snapshot.json")
        print(f"Artifacts written to {args.output_dir}")

    if args.otel:
        record_otel_run(narrow, span_name="agentverity.payment_dispute.narrow")
        record_otel_run(repaired, span_name="agentverity.payment_dispute.repaired")


if __name__ == "__main__":
    main()
