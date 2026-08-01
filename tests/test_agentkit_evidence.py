"""Pin the AgentKit write-up to the evidence it describes.

Three numbers in that README were wrong when it was first written: the wall
time appeared as 25 minutes in one place and 33 in another against a recorded
30.1, and a claim of prose on "two probes" described eight. A reviewer found
all three by re-running the files.

The evidence is committed, so nothing here costs a model call. A README that
drifts from the numbers beside it is the failure this whole directory exists
to argue about.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import pytest

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "agentkit"
README = (EVIDENCE / "README.md").read_text(encoding="utf-8")
MAIN_README = (Path(__file__).resolve().parents[1] / "README.md").read_text(
    encoding="utf-8"
)
SUITE = json.loads((EVIDENCE / "suite.json").read_text(encoding="utf-8"))
EXPECTED = {c["input"]: c["expected"] for c in SUITE["cases"]}
FILES = ("evidence-nova.json", "evidence-gpt4o_mini.json", "evidence-nemo.json")


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def score(evidence: dict) -> tuple[int, int]:
    """Correct answers and single-outcome probes, the README's two columns."""
    correct = single = 0
    for case in evidence["cases"]:
        counts = collections.Counter(case["observations"])
        correct += counts.most_common(1)[0][0] == EXPECTED[case["input"]]
        single += len(counts) == 1
    return correct, single


@pytest.mark.parametrize(
    ("name", "correct", "single"),
    [
        ("evidence-nova.json", 4, 1),
        ("evidence-gpt4o_mini.json", 7, 8),
        ("evidence-nemo.json", 5, 10),
    ],
)
def test_the_readme_table_matches_the_evidence(
    name: str, correct: int, single: int
) -> None:
    assert score(load(name)) == (correct, single)
    model = load(name)["provenance"]["model"]
    row = re.search(
        rf"^{re.escape(model)}\s+(\d+)/10\s+(\d+)/10$", README, flags=re.MULTILINE
    )
    assert row, f"{model} has no row in the README table"
    assert (int(row.group(1)), int(row.group(2))) == (correct, single)


@pytest.mark.parametrize("name", FILES)
def test_the_main_readme_quotes_the_same_table(name: str) -> None:
    """The front page carries these numbers too, so it drifts too."""
    evidence = load(name)
    correct, single = score(evidence)
    row = re.search(
        rf"^{re.escape(evidence['provenance']['model'])}\s+(\d+)/10\s+(\d+)/10$",
        MAIN_README,
        flags=re.MULTILINE,
    )

    assert row, f"{evidence['provenance']['model']} is not in the main README table"
    assert (int(row.group(1)), int(row.group(2))) == (correct, single)


def test_the_headline_holds() -> None:
    """The claim is that ranking on stability alone prefers the worse agent."""
    nemo_correct, nemo_single = score(load("evidence-nemo.json"))
    gpt_correct, gpt_single = score(load("evidence-gpt4o_mini.json"))

    assert nemo_single > gpt_single, "nemo should be the more stable"
    assert nemo_correct < gpt_correct, "and the less correct"


def test_the_quoted_cost_and_duration_match_provenance() -> None:
    # Three different durations appeared in the write-up before this existed.
    cost = sum(load(f)["provenance"]["observed_cost_usd"] for f in FILES)
    minutes = sum(load(f)["provenance"]["wall_seconds"] for f in FILES) / 60
    calls = sum(len(c["observations"]) for f in FILES for c in load(f)["cases"])

    assert f"{cost:.2f}" == "0.70", cost
    assert 29 <= minutes <= 31, minutes
    assert calls == 4380, calls
    assert "0.70 USD" in README
    assert "30 minutes" in README
    assert "4,380" in README


def test_the_unstable_routes_are_the_ones_named() -> None:
    """gpt-4o-mini is unstable on transfer and approve, and only those."""
    evidence = load("evidence-gpt4o_mini.json")
    unstable = {
        EXPECTED[c["input"]]
        for c in evidence["cases"]
        if len(set(c["observations"])) > 1
    }

    assert unstable == {"transfer", "approve"}
    # Both are declared critical, which is why the finding matters.
    assert unstable <= set(SUITE["contract"]["critical"])


def test_the_contract_wrinkle_is_disclosed() -> None:
    """`approve` is returned 98 times and reported as never observed.

    The contract reads the first verdict per case, the route table reads every
    repeat, and the two disagree on what "reached" means. A reader running the
    recommended command meets NOT TRUSTWORTHY, so the README has to prepare
    them for it.
    """
    approve = next(
        c for c in load("evidence-gpt4o_mini.json")["cases"]
        if EXPECTED[c["input"]] == "approve"
    )

    assert approve["observations"].count("approve") == 98
    assert approve["observations"][0] != "approve"
    assert "NOT TRUSTWORTHY" in README
    assert "first" in README and "98 times out of 146" in README


def test_nova_answered_with_prose_on_eight_probes() -> None:
    # The README said two. It was eight, and that understates the motivation
    # for naming the outcome rather than leaving the verdict unset.
    cases = load("evidence-nova.json")["cases"]
    with_prose = [c for c in cases if "no_tool_selected" in c["observations"]]

    assert len(with_prose) == 8
    assert "eight of ten probes" in README
