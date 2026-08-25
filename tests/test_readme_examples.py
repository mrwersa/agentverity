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
        "## Stop when more runs cannot help"
    )
    assert "Use another evaluator for open-ended chat" in readme


def test_readme_explains_the_two_separate_reference_gates() -> None:
    """The front page must not turn repeatability into correctness."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    prose = " ".join(readme.split())

    assert "AgentVerity is a local Python library" in readme
    assert "A regression reference needs two separate yeses" in prose
    assert "repeatability qualified" in readme
    assert "expected behaviour is acceptable" in prose
    assert "A **flip** is a pairwise disagreement" in readme


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
    positioning = readme.index("| Layer | Question |")

    assert problem < install < positioning
    # Nothing between the title and the problem except the badges and one
    # paragraph saying what this is.
    assert problem < 1200, f"{problem} characters of preamble before the problem"


def test_readme_python_quickstart_runs_without_relation_violations() -> None:
    """The first Python example should not teach through a distracting failure."""
    import re

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(
        r"Plain Python callables.*?```python\n(.*?)\n```", readme, re.DOTALL
    )
    assert match, "README Python quickstart is missing"

    namespace: dict = {}
    exec(match.group(1), namespace)  # noqa: S102 - execute our own documentation
    result = namespace["result"]

    assert result.status == "deterministic"
    assert all(item.violated == 0 for item in result.relation_results)


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

    stability = (root / "STABILITY.md").read_text(encoding="utf-8")
    assert f"accepts compatible `{major}.{minor}.x` fixes" in stability


def test_public_positioning_and_machine_terms_are_kept_separate() -> None:
    """Entry points should explain the method without renaming API values."""
    root = pathlib.Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    positioning = (
        "Qualify repeated categorical AI-agent evidence before it becomes a "
        "regression reference"
    )
    assert positioning in pyproject
    assert "regression reference" in readme
    assert "regression reference" in roadmap
    assert "flakiness" in readme
    assert "`plan --observed FLIPS/PAIRS`" in roadmap
    assert "Do not add `--windows`" in roadmap
    for current, explanatory in (
        ("`deterministic`", "repeatability qualified"),
        ("`stochastic`", "repeatability rejected"),
        ("`undecided`", "inconclusive"),
    ):
        assert current in roadmap
        assert explanatory in roadmap


def test_the_roadmap_opener_tracks_the_current_release_series() -> None:
    """The roadmap's release framing should not lag the package version.

    This caught the 0.15 -> 0.16 drift in the release branch: the roadmap
    opener still described the 0.15.0 picture and item 5 as half shipped after
    the release had moved on.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    version = re.search(
        r'^version = "([^"]+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    ).group(1)

    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")

    assert f"As of {version}" in roadmap
    assert f"released {version} picture" in roadmap
    # Which items are shipped is prose that legitimately changes as they ship,
    # and a guard asserting the sentence verbatim fails for the right reason
    # only once. After that it is edited to match, which teaches the habit of
    # editing guards. The version is derivable and is what can drift silently.


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


def test_every_name_the_docs_import_from_the_package_actually_exists() -> None:
    """A doc that teaches a name the package does not export is a doc that
    fails on the first line a reader runs.

    `docs/api.md` taught `declare_isolation` in a file where every other
    example imports from the top-level package, and it was only reachable as
    `agentverity.isolation.declare_isolation`. Prose is scanned as well as code
    blocks, because the sentence is what a reader copies.

    The first version stopped at a newline, so the one parenthesised import in
    that file contributed a lone `(` and its four names went unchecked while
    the test still claimed to check every import. Both forms are read now.
    """
    import re
    from pathlib import Path

    import agentverity

    root = Path(__file__).resolve().parents[1]
    pattern = re.compile(
        r"from agentverity import \s*(?:\(([^)]*)\)|([^\n(]+))", re.MULTILINE
    )
    missing, checked = [], 0
    for path in sorted(root.glob("docs/*.md")) + [root / "README.md"]:
        text = path.read_text(encoding="utf-8")
        for parenthesised, inline in pattern.findall(text):
            block = parenthesised or inline
            for name in re.split(r"[,\s]+", block.replace("\\", "").strip()):
                if not name or not name.isidentifier():
                    continue
                checked += 1
                if not hasattr(agentverity, name):
                    missing.append(f"{path.name}: {name}")

    assert not missing, f"docs import names the package does not export: {missing}"
    assert checked >= 15, (
        f"only {checked} imported names found, so the scan is not reading the "
        "docs it claims to"
    )


def test_the_documented_schema_versions_are_the_ones_the_code_writes() -> None:
    """`STABILITY.md` names the schemas a stored file must match.

    It shipped in 0.16.0 saying `agentverity.snapshot/v3` while the release
    wrote v4 and refused v3 outright, so the document told a reader their
    stored baseline was readable by the one version that rejects it. The
    version pins beside it were guarded and the schema list was not, which is
    how a paragraph can be half-checked and read as wholly checked.
    """
    from pathlib import Path

    from agentverity.decision_contract import DECISION_SUITE_SCHEMA
    from agentverity.evidence import EVIDENCE_SCHEMA
    from agentverity.reporting import RUN_SCHEMA
    from agentverity.snapshot import SNAPSHOT_SCHEMA
    from agentverity.telemetry import TELEMETRY_SCHEMA

    stability = (
        Path(__file__).resolve().parents[1] / "STABILITY.md"
    ).read_text(encoding="utf-8")

    shipped = {
        RUN_SCHEMA,
        TELEMETRY_SCHEMA,
        SNAPSHOT_SCHEMA,
        EVIDENCE_SCHEMA,
        DECISION_SUITE_SCHEMA,
    }
    for schema in shipped:
        assert f"`{schema}`" in stability, f"STABILITY.md never names {schema}"

    # And no superseded number is still being advertised as current.
    families = {schema.rsplit("/", 1)[0] for schema in shipped}
    stale = [
        f"{family}/v{number}"
        for family in families
        for number in range(1, 10)
        if f"`{family}/v{number}`" in stability
        and f"{family}/v{number}" not in shipped
    ]
    assert not stale, f"STABILITY.md still advertises: {stale}"


def test_the_docs_import_from_the_shallowest_path_that_works() -> None:
    """Two import paths for one name teaches a convention that is not one.

    `docs/custom-relations.md` and `examples/custom_relation.py` reached for
    `agentverity.relations.builtin_relations` in the same file that imported
    `Relation` from the top level, while both are exported from the top level.
    A reader copying that learns the deep path is sometimes required, and it
    never is when a re-export exists.

    The neighbouring guard checks that a documented name exists. This one
    checks it is documented at the path a reader should use.
    """
    import re
    from pathlib import Path

    import agentverity

    root = Path(__file__).resolve().parents[1]
    deeper = []
    for path in (
        [*sorted(root.glob("docs/*.md")), root / "README.md"]
        + sorted(root.glob("examples/*.py"))
    ):
        text = path.read_text(encoding="utf-8")
        for module, names in re.findall(
            r"from agentverity\.([a-z_.]+) import ([^\n(]+)", text
        ):
            for name in re.split(r"[,\s]+", names.strip()):
                if name and name.isidentifier() and hasattr(agentverity, name):
                    deeper.append(
                        f"{path.name}: agentverity.{module}.{name} is also "
                        f"agentverity.{name}"
                    )

    assert not deeper, "docs reach past a top-level export: " + "; ".join(deeper)


def test_every_example_is_named_somewhere_a_reader_looks() -> None:
    """An example nobody links to is an example nobody finds.

    The same argument as `compare-evidence`, which shipped as the 0.13.0
    headline and reached 0.14.0 mentioned only in the roadmap. Five examples
    were reachable only by browsing the directory.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    prose = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            *sorted(root.glob("docs/*.md")),
            root / "README.md",
            root / "examples" / "README.md",
        ]
    )

    missing = sorted(
        path.name
        for path in sorted(root.glob("examples/*"))
        if path.name not in {"README.md", "__pycache__"}
        and path.name not in prose
    )

    assert not missing, f"examples nothing points at: {missing}"


def test_the_release_trigger_matches_the_sibling_project_word_for_word() -> None:
    """One rule in two repositories drifts unless something compares them.

    The section exists because the absence of a release trigger produced two
    opposite failures, seventeen unreleased pull requests here and a four-day
    unreleased fix there. Wording that diverges is how one of them quietly
    grows an exception. Only the opening paragraph differs, because each
    repository names its own history first.

    Skipped when the sibling is not checked out, since it is a separate
    repository and not a dependency.
    """
    from pathlib import Path

    import pytest

    sibling = Path.home() / "code" / "agentmandate" / "RELEASING.md"
    if not sibling.is_file():
        pytest.skip("agentmandate is not checked out beside this repository")

    def rule(text: str) -> str:
        start = text.index("## When to cut one")
        body = text[start : text.index("## Cut a release", start)]
        # Drop the opening paragraph: each repository leads with its own
        # history, and the rule is everything after it.
        return body.split("\n\n", 2)[2]

    here = rule(Path(__file__).resolve().parents[1].joinpath("RELEASING.md")
                .read_text(encoding="utf-8"))
    there = rule(sibling.read_text(encoding="utf-8"))

    assert here == there, "the release trigger has drifted between the projects"
