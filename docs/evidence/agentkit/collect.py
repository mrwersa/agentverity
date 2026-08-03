#!/usr/bin/env python3
"""Collect repeated tool selections and write an agentverity.evidence/v2 file.

Written rather than using `agentverity run` directly so the artefact is the
evidence itself. Anyone can then re-run `agentverity assess` against the
committed file for nothing, instead of paying for the calls again to check
the arithmetic.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from concurrent import futures

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import agent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repeats", type=int, default=146)
    # Six, because six is what produced the committed evidence and the wall
    # time quoted beside it. A default that differs from the documented run
    # makes `python collect.py` a third set of numbers.
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    suite = json.loads(pathlib.Path("suite.json").read_text())
    run = getattr(agent, args.factory)()
    started = time.time()
    cost = 0.0
    cases, errors_total = [], 0

    for case in suite["cases"]:
        observations, errors = [], 0

        # `case` is bound as a default rather than captured, because a
        # closure over the loop variable reads whatever the variable holds
        # when the thread runs, not when it was submitted.
        def once(_, text=case["input"]):
            return run(text)

        # A call that fails after its retries is recorded as an error and the
        # rest of the run continues. `pool.map` re-raises on iteration, which
        # threw away every observation collected so far the first time this
        # ran against a flaky gateway.
        with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = [pool.submit(once, i) for i in range(args.repeats)]
            for future in pending:
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                    errors += 1
                    print(f"    error: {type(exc).__name__}", flush=True)
                    continue
                observations.append(result.verdict)
                cost_here = (result.raw or {}).get("usage", {}).get("cost")
                if cost_here:
                    globals()["_cost"] = globals().get("_cost", 0.0) + float(cost_here)
        cases.append({
            "input": case["input"],
            "expected": case["expected"],
            "observations": observations,
            **({"errors": errors} if errors else {}),
        })
        errors_total += errors
        print(f"  {case['expected']:22} {len(observations)} observations", flush=True)

    cost = globals().get("_cost", 0.0)
    evidence = {
        "schema": "agentverity.evidence/v2",
        "layer": "verdict",
        # Every call is a fresh HTTP request with no conversation carried
        # between them, so the trials are independent in the way the
        # intervals assume.
        "isolation": "fresh-instance",
        "provenance": {
            "model": args.model,
            "gateway": "openrouter",
            "collected_at": time.strftime("%Y-%m-%d"),
            "repeats_per_case": args.repeats,
            # Recorded because it sets the wall time below, which the write-up
            # quotes. The committed files predate this field; they were
            # collected with six, and back-filling a value the code did not
            # emit would make an artefact claim an origin it does not have.
            "workers": args.workers,
            "tool_set": "coinbase-agentkit 0.7.4, seven providers wired by the Strands example",
            "observed_cost_usd": round(cost, 4),
            "wall_seconds": round(time.time() - started),
        },
        "cases": cases,
    }
    args.out.write_text(json.dumps(evidence, indent=2) + "\n")
    total = sum(len(c["observations"]) for c in cases)
    print(f"wrote {args.out.name}: {total} observations, "
          f"{errors_total} errors, ${cost:.4f}, {time.time()-started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
