#!/usr/bin/env python3
"""Apply a declared equivalence relation to collected BFCL decisions.

The stability rule classifies a flip rate over categorical decisions and takes
the categorisation as given. Which decisions count as *the same* decision is a
separate choice, and on this evidence it decides one of the calls. This script
makes that choice explicit, applies it deterministically, and writes the result
out so the counterfactual is an artifact rather than a sentence in a note.

Two reductions are reported side by side:

``exact``
    The collected decision string, unchanged.
``numeric``
    Integer-valued floats collapsed onto their integer form, so ``10.0``
    and ``10`` are the same value. Nothing else is touched. In particular
    case, spacing, key order and non-integral floats are left alone.

Both reductions read the same observations in the same order. The script
asserts that, rather than trusting it: the reduction is applied pointwise to a
sequence whose length and order are checked against the input.

Usage:
    python3 reduce.py                 # rewrite reduction-report.json
    python3 reduce.py --check         # fail if the committed report is stale
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence-bfcl-multiple-gpt4o_mini.json"
REPORT = ROOT / "reduction-report.json"

SCHEMA = "agentverity.reduction-report/v1"
EPSILON = 0.05
Z = 1.959963984540054  # two-sided 95%

# An integer-valued float, not preceded by a word character or a dot so that
# version-like and dotted-name tokens are left alone. `10.0` and `10.000`
# collapse to `10`. `10.5` does not match. `v1.0` does not match.
_INT_FLOAT = re.compile(r"(?<![\w.])(\d+)\.0+(?![\d])")


def reduce_exact(decision: str) -> str:
    """Identity. Named so the two reductions are symmetric at the call site."""
    return decision


def reduce_numeric(decision: str) -> str:
    """Collapse integer-valued floats onto their integer form."""
    return _INT_FLOAT.sub(r"\1", decision)


REDUCTIONS = {"exact": reduce_exact, "numeric": reduce_numeric}


def wilson(flips: int, pairs: int, z: float = Z) -> tuple[float, float]:
    if pairs == 0:
        return 0.0, 1.0
    p = flips / pairs
    denom = 1.0 + z * z / pairs
    centre = (p + z * z / (2 * pairs)) / denom
    half = z * math.sqrt(p * (1 - p) / pairs + z * z / (4 * pairs * pairs)) / denom
    return centre - half, centre + half


def call(flips: int, pairs: int, epsilon: float = EPSILON) -> str:
    low, high = wilson(flips, pairs)
    if high < epsilon:
        return "admit"
    if low > epsilon:
        return "reject"
    return "undecided"


def disjoint_pairs(observations: list[str]) -> list[tuple[str, str]]:
    """Consecutive non-overlapping pairs, dropping a trailing odd observation.

    Overlapping every-against-every comparison would reuse observations and
    invalidate the Bernoulli interval, so the pairing is fixed here.
    """
    usable = len(observations) // 2 * 2
    return [
        (observations[i], observations[i + 1]) for i in range(0, usable, 2)
    ]


def count_flips(observations: list[str]) -> int:
    return sum(1 for a, b in disjoint_pairs(observations) if a != b)


def analyse(evidence: dict) -> dict:
    cases = evidence["cases"]
    per_case: list[dict] = []
    pooled = {name: {"flips": 0, "pairs": 0} for name in REDUCTIONS}

    for case in cases:
        observed = case["observations"]
        entry: dict = {
            "input": case["input"],
            "observations": len(observed),
            "pairs": len(observed) // 2,
            "reductions": {},
        }
        for name, fn in REDUCTIONS.items():
            mapped = [fn(o) for o in observed]
            # The reduction must be pointwise on the collected order. Anything
            # that reordered or dropped an observation would silently change
            # the pairing, which is the one thing this artifact has to rule out.
            assert len(mapped) == len(observed), "reduction changed the count"
            flips = count_flips(mapped)
            pairs = len(mapped) // 2
            low, high = wilson(flips, pairs)
            entry["reductions"][name] = {
                "flips": flips,
                "pairs": pairs,
                "distinct_values": len(set(mapped)),
                "interval": [round(low, 6), round(high, 6)],
                "call": call(flips, pairs),
            }
            pooled[name]["flips"] += flips
            pooled[name]["pairs"] += pairs
        entry["call_changed"] = (
            entry["reductions"]["exact"]["call"]
            != entry["reductions"]["numeric"]["call"]
        )
        per_case.append(entry)

    pooled_out = {}
    for name, agg in pooled.items():
        low, high = wilson(agg["flips"], agg["pairs"])
        pooled_out[name] = {
            **agg,
            "interval": [round(low, 6), round(high, 6)],
            "call": call(agg["flips"], agg["pairs"]),
        }

    changed = [c["input"] for c in per_case if c["call_changed"]]
    rejects_under_both = [
        c["input"]
        for c in per_case
        if c["reductions"]["exact"]["call"] == "reject"
        and c["reductions"]["numeric"]["call"] == "reject"
    ]

    return {
        "schema": SCHEMA,
        "source_evidence": EVIDENCE.name,
        "provenance": evidence.get("provenance", {}),
        "epsilon": EPSILON,
        "confidence": 0.95,
        "reductions_declared": {
            "exact": "collected decision string, unchanged",
            "numeric": "integer-valued floats collapsed onto integer form",
        },
        "per_case": per_case,
        # Pooled figures are reported for completeness and are NOT a call the
        # rule licenses: each request is qualified on its own, so a pooled
        # interval mixes heterogeneous requests and can hide a rejecting one.
        "pooled_not_a_call": pooled_out,
        "call_changed_by_reduction": changed,
        "rejects_under_both_reductions": rejects_under_both,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed report differs")
    args = ap.parse_args()

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    report = analyse(evidence)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not REPORT.exists():
            print(f"FAIL  {REPORT.name} is missing")
            return 1
        if REPORT.read_text(encoding="utf-8") != rendered:
            print(f"FAIL  {REPORT.name} is stale, rerun without --check")
            return 1
        print(f"PASS  {REPORT.name} matches the evidence")
        return 0

    REPORT.write_text(rendered, encoding="utf-8")
    print(f"wrote {REPORT.name}")
    for case in report["per_case"]:
        e = case["reductions"]["exact"]
        n = case["reductions"]["numeric"]
        mark = "  <-- call changed" if case["call_changed"] else ""
        print(f"  {case['input']:<12} {e['flips']:>3} {e['call']:<9}"
              f" -> {n['flips']:>3} {n['call']:<9}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
