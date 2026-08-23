"""Pin the reduction counterfactual to the evidence it is computed from.

The claim that a declared equivalence relation can decide a qualification call
lived only in prose for a while: the note said one thing, the evidence said
another, and nothing recomputed either. An earlier version of that note also
decomposed the flips using minority *value* counts rather than flip counts,
which is how a 29 became a 39.

So the counterfactual is an artifact now, and this pins it. Nothing here costs
a model call, because the observations are committed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BFCL = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "bfcl"
REDUCE = BFCL / "reduce.py"
REPORT = json.loads((BFCL / "reduction-report.json").read_text(encoding="utf-8"))
EVIDENCE = json.loads(
    (BFCL / "evidence-bfcl-multiple-gpt4o_mini.json").read_text(encoding="utf-8")
)
FINDINGS = (BFCL / "FINDINGS.md").read_text(encoding="utf-8")

BY_CASE = {c["input"]: c for c in REPORT["per_case"]}


def test_committed_report_matches_the_evidence():
    """The artifact is regenerable. A stale report is a silent wrong claim."""
    done = subprocess.run(
        [sys.executable, str(REDUCE), "--check"],
        capture_output=True,
        text=True,
        cwd=BFCL,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_exactly_one_request_changes_call_under_the_reduction():
    assert REPORT["call_changed_by_reduction"] == ["multiple_6"]


def test_the_changing_request_goes_reject_to_admit():
    case = BY_CASE["multiple_6"]
    assert case["reductions"]["exact"]["call"] == "reject"
    assert case["reductions"]["exact"]["flips"] == 29
    assert case["reductions"]["numeric"]["call"] == "admit"
    assert case["reductions"]["numeric"]["flips"] == 0
    # The admission lands on the zero-flip floor the rule derives for
    # epsilon = 0.05, so it is the budget doing the work and not a wide interval.
    assert case["pairs"] == 73


def test_a_second_request_rejects_under_both_reductions():
    """Canonicalising is not a way to admit anything.

    This is the counterweight the write-up has to carry. Without it a reader
    concludes that relabelling makes instability go away.
    """
    assert "multiple_7" in REPORT["rejects_under_both_reductions"]
    case = BY_CASE["multiple_7"]
    assert case["reductions"]["exact"]["flips"] == 24
    assert case["reductions"]["numeric"]["flips"] == 24


def test_pooled_figures_are_labelled_as_not_a_call():
    """Pooling heterogeneous requests is not a call the rule licenses.

    The pooled numeric interval admits while multiple_7 rejects, which is
    exactly the hazard: a pooled admit conceals a rejecting request.
    """
    pooled = REPORT["pooled_not_a_call"]
    assert pooled["exact"]["call"] == "reject"
    assert pooled["numeric"]["call"] == "admit"
    assert BY_CASE["multiple_7"]["reductions"]["numeric"]["call"] == "reject"


@pytest.mark.parametrize("case", EVIDENCE["cases"])
def test_reduction_preserves_count_and_order(case):
    """No observation is added, dropped or reordered by the relabelling."""
    sys.path.insert(0, str(BFCL))
    import reduce as reducer

    observed = case["observations"]
    for fn in (reducer.reduce_exact, reducer.reduce_numeric):
        mapped = [fn(o) for o in observed]
        assert len(mapped) == len(observed)
        # Pointwise means position i depends only on observation i.
        for i, o in enumerate(observed):
            assert mapped[i] == fn(o)


def test_numeric_reduction_touches_only_integer_valued_floats():
    sys.path.insert(0, str(BFCL))
    import reduce as reducer

    assert reducer.reduce_numeric('f({"a": 10.0})') == 'f({"a": 10})'
    assert reducer.reduce_numeric('f({"a": 10.000})') == 'f({"a": 10})'
    assert reducer.reduce_numeric('f({"a": [-2.0, {"b": 3.0}]})') == (
        'f({"a": [-2, {"b": 3}]})'
    )
    # Non-integral floats, strings, casing and dotted names are left alone.
    assert reducer.reduce_numeric('f({"a": 10.5})') == 'f({"a": 10.5})'
    assert reducer.reduce_numeric('f({"a": "10.0"})') == 'f({"a": "10.0"})'
    assert reducer.reduce_numeric('f({"a": "Washington"})') == (
        'f({"a": "Washington"})'
    )
    assert reducer.reduce_numeric('f({"a": "Washington State"})') == (
        'f({"a": "Washington State"})'
    )
    assert reducer.reduce_numeric("v1.0.0") == "v1.0.0"


def test_numeric_reduction_handles_multiple_calls_and_embedded_pipes():
    sys.path.insert(0, str(BFCL))
    import reduce as reducer

    decision = 'first({"value": 1.0})|second({"text": "a|b", "value": 2.0})'
    assert reducer.reduce_numeric(decision) == (
        'first({"value": 1})|second({"text": "a|b", "value": 2})'
    )


def test_findings_note_states_the_flip_counts_it_computed():
    """Flip counts, not value counts. This is the error that was shipped once.

    The note originally read "roughly 39 canonicalisation artefacts and 13
    real", which are the counts of the minority *value* in each case rather
    than the number of disagreeing pairs. The interval consumes flips.
    """
    run2 = FINDINGS.split("## Run 2")[1]
    assert "**29**" in run2
    assert "**24**" in run2
    assert "39 canonicalisation" not in run2
    assert "13 real" not in run2


def test_findings_names_the_entry_ids_it_is_talking_about():
    """The note numbers cases from one, the evidence ids them from zero.

    Case 7 in the note is entry multiple_6 in the evidence. Leaving that
    implicit is how an off-by-one becomes a wrong quotation.
    """
    run2 = FINDINGS.split("## Run 2")[1]
    assert "multiple_6" in run2
    assert "multiple_7" in run2


def test_reserialisation_alone_changes_nothing_on_this_evidence():
    """The numeric collapse accounts for the whole effect.

    ``reduce_numeric`` re-serialises with sorted keys, which normalises key
    order and whitespace as well as numeric rendering. Both notes and the
    workshop appendix say the change of *numeric labelling alone* moves
    multiple_6 from reject to admit. That sentence is only true while the
    re-serialisation contributes nothing, so it is pinned rather than assumed.
    """
    sys.path.insert(0, str(BFCL))
    import reduce as reducer

    def reserialise_only(decision: str) -> str:
        parts = []
        for item in reducer._split_calls(decision):
            name, separator, encoded = item.partition("(")
            if not separator or not encoded.endswith(")"):
                parts.append(item)
                continue
            parts.append(f"{name}({json.dumps(json.loads(encoded[:-1]), sort_keys=True)})")
        return "|".join(parts)

    for case in EVIDENCE["cases"]:
        observed = case["observations"]
        assert reducer.count_flips(
            [reserialise_only(o) for o in observed]
        ) == reducer.count_flips(observed), case["input"]
