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

from agentverity import load_decision_suite, pairs_for_deterministic_call, plan_repeats

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_readme_onboards_before_the_statistical_explanation():
    readme = (ROOT / "README.md").read_text()

    assert readme.index("## Try it") < readme.index(
        "## Why rerun counts are harder than they look"
    )
    assert "Use another evaluator for open-ended chat" in readme


def test_readme_shows_the_finding_before_positioning_itself():
    """Order is the thing this file protects, because order is what accretes.

    Every new section arrives with a reason to sit near the top, and the
    comparison tables won that argument twice before a reader had seen a
    single number the library produces. A developer deciding whether to spend
    ten minutes wants the failing route and the install line first.
    """
    readme = (ROOT / "README.md").read_text()

    problem = readme.index("## The 60-second problem")
    install = readme.index("## Try it without model calls")
    positioning = readme.index("| What you run | Question it answers |")

    assert problem < install < positioning
    # Nothing between the title and the problem except the badges and one
    # paragraph saying what this is.
    assert problem < 1200, f"{problem} characters of preamble before the problem"


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
    assert "route-level intervals remain undecided" in printed
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


def test_documented_decision_suite_is_valid():
    suite = load_decision_suite(ROOT / "examples" / "payment_decisions.json")

    assert len(suite.cases) == 6
    assert suite.missing_required_cases == ()
    assert suite.contract.critical == {"card_security"}


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


def test_the_docs_pin_names_the_current_minor_series() -> None:
    """A version in prose drifts, and this one already had twice.

    The README shipped `agentverity~=0.13.0` in the 0.14.0 release, and
    STABILITY.md still said `~=0.13.0` after the README was fixed, because the
    guard scanned one file. Every prose markdown file may carry the current-
    series pin and nothing else. The changelog and the release notes
    legitimately carry other versions, so they are excluded.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    version = re.search(
        r'^version = "([^"]+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    ).group(1)
    major, minor, _ = version.split(".")
    expected = f"{major}.{minor}.0"

    pinned = []
    for path in sorted(root.rglob("*.md")):
        if path.name in {"CHANGELOG.md", "RELEASING.md"}:
            continue
        pins = set(
            re.findall(r"agentverity~=([\d.]+)", path.read_text(encoding="utf-8"))
        )
        if pins:
            pinned.append((path, pins))

    assert pinned, "no prose markdown pins the current series"
    stale = [
        f"{path.relative_to(root)}: {sorted(pins)}"
        for path, pins in pinned
        if pins != {expected}
    ]
    assert not stale, f"docs pin {', '.join(stale)}; this release is {version}"


def test_every_cli_command_is_discoverable_from_the_readme() -> None:
    """A command the README never names is a command nobody finds.

    `compare-evidence` shipped as the 0.13.0 headline and reached 0.14.0
    without a single mention outside the roadmap.
    """
    from pathlib import Path

    from agentverity.cli import _build_parser

    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    commands = {
        name
        for action in _build_parser()._subparsers._group_actions
        for name in action.choices
    }
    missing = sorted(c for c in commands if c not in readme)

    assert not missing, f"the README never mentions: {', '.join(missing)}"


def test_the_new_reach_semantics_reach_every_output_surface():
    """The roadmap promised the AgentKit case pinned across surfaces.

    A semantic change that moves the terminal report and not the JSON one is
    the same class of defect the change was fixing: two readings in one
    product that disagree without saying so.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    evidence = root / "docs" / "evidence" / "agentkit"

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.json"
        subprocess.run(
            [sys.executable, "-m", "agentverity.cli", "assess",
             "--evidence", str(evidence / "evidence-gpt4o_mini.json"),
             "--suite", str(evidence / "suite.json"), "--json", str(out)],
            capture_output=True, text=True, cwd=root, check=False,
        )
        payload = json.loads(out.read_text())
    contract = payload["decision_contract"]

    # both readings present and named
    assert "approve" not in contract["observed_counts"], "primaries are unchanged"
    assert contract["observed_case_counts"]["approve"] == 1, "one case, 98 repeats"
    assert "approve" not in contract["missing_observed"]
    assert set(contract["missing_observed"]) == {
        "fetch_price", "get_balance", "get_portfolio",
    }
    # and the two agree: every required decision is either counted or missing
    required = set(contract["required"])
    counted = set(contract["observed_case_counts"])
    assert required - counted == set(contract["missing_observed"])

    text = subprocess.run(
        [sys.executable, "-m", "agentverity.cli", "assess",
         "--evidence", str(evidence / "evidence-gpt4o_mini.json"),
         "--suite", str(evidence / "suite.json")],
        capture_output=True, text=True, cwd=root, check=False,
    ).stdout
    section = text.split("3. DECLARED DECISION CONTRACT")[1][:400]
    assert "approve" not in section, "the terminal report agrees with the JSON one"


def test_every_changelog_version_has_a_matching_comparison_link() -> None:
    """The 0.15.0 release moved the sections and left the links behind.

    So `[Unreleased]` still compared against v0.14.0 and the changelog's own
    links said seventeen merged PRs were unreleased when they had shipped.
    This has drifted before: a previous release restored stale links by hand,
    which fixes the instance and not the class.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    sections = set(re.findall(r"^## \[([^\]]+)\]", changelog, re.MULTILINE))
    linked = set(re.findall(r"^\[([^\]]+)\]: https://", changelog, re.MULTILINE))

    assert sections - linked == set(), "changelog sections with no link"
    assert linked - sections == set(), "changelog links with no section"

    version = re.search(
        r'^version = "([^"]+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    ).group(1)
    def as_numbers(text: str) -> list[int]:
        return [int(part) for part in text.split(".")]

    released = {section for section in sections if section != "Unreleased"}
    latest = max(released, key=as_numbers)

    # Sorting versions as strings put 0.9.1 after 0.15.0, which made an
    # earlier disjunct here dead and its comment wrong about what it allowed.
    assert as_numbers(latest) >= as_numbers(version), (
        f"the changelog's newest section is {latest} and the package is "
        f"{version}; a released version with no section cannot be described"
    )
    assert f"compare/v{latest}...HEAD" in changelog, (
        "Unreleased must compare against the newest released version"
    )
