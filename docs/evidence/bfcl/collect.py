#!/usr/bin/env python3
"""Collect repeated function-call decisions over BFCL v4 cases.

Mirrors ../agentkit/collect.py: repeated decoded tool choices per case,
written straight as agentverity.evidence/v2. The categorical label per trial
is the called function name. Ground-truth function names from the BFCL
possible_answer file become the intended decisions, enabling contract
checking.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent import futures

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
ROOT = pathlib.Path(__file__).resolve().parent


def safe_name(name: str) -> str:
    # BFCL uses namespaced names such as math.factorial, which OpenAI-style
    # tool APIs reject (names must match ^[A-Za-z0-9_-]+$). Alias them
    # deterministically; the alias is applied identically to tools, ground
    # truth, and observed labels, so nothing is lost at the stability layer.
    import re as _re
    return _re.sub(r"[^A-Za-z0-9_-]", "_", name)


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def to_openai_tool(fn: dict) -> dict:
    params = fn.get("parameters", {"type": "object", "properties": {}})
    if isinstance(params, dict) and params.get("type") == "dict":
        params = dict(params)
        params["type"] = "object"
    return {
        "type": "function",
        "function": {"name": safe_name(fn["name"]), "description": fn.get("description", ""), "parameters": params},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=pathlib.Path, required=True,
                        help="BFCL v4 data JSONL (question + function docs)")
    parser.add_argument("--answers", type=pathlib.Path, required=True,
                        help="BFCL possible_answer JSONL (ground truth by id)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--num-cases", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=146)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    key = os.environ["OPENROUTER_API_KEY"]
    entries = load_jsonl(args.cases)[: args.num_cases]
    answers = {row["id"]: row["ground_truth"] for row in load_jsonl(args.answers)}
    missing = [e["id"] for e in entries if e["id"] not in answers]
    if missing:
        raise SystemExit(f"no ground truth for: {missing}")

    started = time.time()
    cost = 0.0
    cases_out, errors_total = [], []

    for entry in entries:
        tools = [to_openai_tool(fn) for fn in entry["function"]]
        gt_names = sorted({safe_name(name) for call in answers[entry["id"]] for name in call})
        # BFCL nests `question` as a list of turns, each a list of messages.
        flat_questions = [
            message for turn in entry["question"] for message in (turn if isinstance(turn, list) else [turn])
        ]
        messages = [
            {"role": "system", "content": (
                "You are a function-calling assistant. Choose exactly one function "
                "to answer the user, and call it. Do not ask clarifying questions."
            )},
            *flat_questions,
        ]

        def once(_: int, messages=messages, tools=tools, key=key, model=args.model) -> tuple[str, float]:
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "required",
            }
            request = urllib.request.Request(
                ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mrwersa/agentverity",
                    "X-Title": "agentverity-evidence",
                },
            )
            for attempt in range(6):
                try:
                    with urllib.request.urlopen(request, timeout=180) as response:
                        body = json.loads(response.read())
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code not in (408, 409, 429, 500, 502, 503, 504) or attempt == 5:
                        raise
                    time.sleep(random.uniform(0, min(30, 2 ** attempt)))
                except (urllib.error.URLError, TimeoutError, OSError):
                    if attempt == 5:
                        raise
                    time.sleep(random.uniform(0, min(30, 2 ** attempt)))
            else:  # pragma: no cover
                raise RuntimeError("unreachable")
            usage = body.get("usage") or {}
            spent = (usage.get("cost") or 0.0)
            name = next(
                (c["function"]["name"] for c in body["choices"][0]["message"].get("tool_calls") or []
                 if c.get("function")),
                "no_call",
            )
            return name, spent

        observations = []
        errors = []
        with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = [pool.submit(once, i) for i in range(args.repeats)]
            for future in futures.as_completed(pending):
                try:
                    name, _ = future.result()
                except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                    errors.append(str(exc)[:120])
                    errors_total.append(str(exc)[:120])
                    observations.append("collection_error")
                    continue
                observations.append(name)

        valid = [o for o in observations if isinstance(o, str)]
        counts = Counter(valid)
        cases_out.append({
            "input": entry["id"],
            "intended": gt_names[0] if len(gt_names) == 1 else gt_names,
            "observations": valid,
            "errors": len(errors),
        })
        print(f"  {entry['id']}: {len(valid)} observations, top={counts.most_common(2)}")

    out_doc = {
        "schema": "agentverity.evidence/v2",
        "layer": "verdict",
        "isolation": "unknown",
        "provenance": {
            "collected_at": time.strftime("%Y-%m-%d"),
            "gateway": "openrouter",
            "model": args.model,
            "repeats_per_case": args.repeats,
            "source": "berkeley-function-call-leaderboard v4",
            "categories": args.cases.name,
            "wall_seconds": round(time.time() - started, 1),
            "observed_cost_usd": round(cost, 4),
        },
        "cases": cases_out,
    }
    args.out.write_text(json.dumps(out_doc, indent=2))
    print(f"wrote {args.out}: {sum(len(c['observations']) for c in cases_out)} observations, "
          f"{len(errors_total)} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
