#!/usr/bin/env python3
"""Summarise the committed evidence: stability beside correctness.

The point of the table this prints is that the two columns move
independently. A model can return the same tool every single time and be
wrong every single time, and a stability gate alone would wave it through.

Reads only the committed evidence files, so it costs nothing to re-run.
"""

from __future__ import annotations

import collections
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
FILES = ("evidence-nova.json", "evidence-gpt4o_mini.json", "evidence-mistral_small.json")


def main() -> int:
    suite = json.loads((HERE / "suite.json").read_text())
    expected = {c["input"]: c["expected"] for c in suite["cases"]}
    summary = []

    for name in FILES:
        evidence = json.loads((HERE / name).read_text())
        model = evidence["provenance"]["model"]
        print(f"\n=== {model} ===")
        print(f"  {'probe expects':24}{'most common answer':28}{'':4}outcomes")
        correct = single = 0
        for case in evidence["cases"]:
            counts = collections.Counter(case["observations"])
            top, _ = counts.most_common(1)[0]
            want = expected[case["input"]]
            ok = top == want
            correct += ok
            single += len(counts) == 1
            print(f"  {want:24}{top:28}{'ok' if ok else 'NO':4}{len(counts)}")
        provenance = evidence["provenance"]
        print(f"  correct {correct}/10, one outcome only {single}/10, "
              f"${provenance['observed_cost_usd']}, {provenance['wall_seconds']}s")
        summary.append((model, correct, single))

    print("\nstability and correctness are independent:")
    print(f"  {'model':46}{'correct':>9}{'always the same':>17}")
    for model, correct, single in summary:
        print(f"  {model:46}{correct:>6}/10{single:>14}/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
