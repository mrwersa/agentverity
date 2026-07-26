"""The README's evidence-gate output must match what the example prints.

The payment-dispute block is the strongest thing in the README: two suites,
both scoring 6/6, one refused. A stale copy of that output would undercut the
exact claim the library makes about vacuous green results.
"""

from __future__ import annotations

import pathlib
import runpy
import sys
from io import StringIO

from agentverity import pairs_for_deterministic_call, plan_repeats

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_readme_onboards_before_the_statistical_explanation():
    readme = (ROOT / "README.md").read_text()

    assert readme.index("## Try it") < readme.index(
        "## Why rerun counts are harder than they look"
    )
    assert "Use another evaluator for open-ended chat" in readme


def _run_example() -> str:
    # The example parses argv, so pytest's own flags must not reach it.
    captured_out, sys.stdout = sys.stdout, StringIO()
    captured_argv, sys.argv = sys.argv, ["payment_dispute_gate.py"]
    try:
        runpy.run_path(str(ROOT / "examples" / "payment_dispute_gate.py"),
                       run_name="__main__")
        return sys.stdout.getvalue().strip()
    finally:
        sys.stdout = captured_out
        sys.argv = captured_argv


def test_the_gate_actually_refuses_then_admits():
    """Guards the claim itself, not just the transcript."""
    printed = _run_example()
    assert "Exact-match evaluator: 6/6 correct" in printed
    assert "REFUSED" in printed
    assert "ADMITTED" in printed
    assert printed.index("REFUSED") < printed.index("ADMITTED")


def test_readme_comparison_table_matches_the_example():
    """The README table and the CI job summary come from one source.

    Both render `--markdown` from this example, so a drift here means the two
    published surfaces have started disagreeing about the same run.
    """
    import subprocess

    printed = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "payment_dispute_gate.py"),
         "--markdown"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    ).stdout
    rows = [line for line in printed.splitlines() if line.startswith("|")]
    assert rows, "example emitted no table"

    readme = (ROOT / "README.md").read_text()
    for row in rows:
        assert row in readme, f"README is missing table row: {row}"


def test_integration_call_budget_matches_the_planner():
    """Keep practical cost guidance tied to the executable planner."""
    inputs = 20
    cheap_calls = inputs + inputs * plan_repeats(inputs, 0.10)
    balanced_calls = inputs + inputs * plan_repeats(inputs, 0.05)
    guide = " ".join((ROOT / "docs" / "integrations.md").read_text().split())

    assert f"Twenty plan {cheap_calls}" in guide
    assert f"twenty cases plan {balanced_calls} calls" in guide


def test_stability_note_exposes_underpowered_as_not_stable():
    """The technical note's Boolean snippet must keep losing undecided.

    It is the small version a developer would write: correct interval
    arithmetic and no representation for insufficient evidence. Execute the
    exact self-contained block rather than helping it through the test
    namespace.
    """
    import re

    note = (ROOT / "docs" / "decision-stability.md").read_text()
    match = re.search(
        r"```python\n(import math\n\ndef looks_stable.*?)\n```",
        note,
        re.DOTALL,
    )
    assert match, "the decision-stability helper is missing"

    namespace: dict = {}
    exec(match.group(1), namespace)  # noqa: S102 - executing our own README

    def router(text: str) -> str:
        if "charg" in text:
            return "billing"
        return "refund" if "refund" in text else "tech"

    cases = [
        "card charged twice", "charged again", "where is my refund",
        "refund late", "app crashes", "cannot login",
    ]
    assert namespace["looks_stable"](router, cases) is False, (
        "the Boolean helper now passes, so the README's opening no longer holds"
    )
    assert pairs_for_deterministic_call(0.05) == 73
