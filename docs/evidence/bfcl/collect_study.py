#!/usr/bin/env python3
"""Run the preregistered BFCL repeated evaluation.

Raw provider receipts stay under the ignored ``private`` directory. Each cell
is resumable until a summary seals it. A run manifest then hashes the protocol,
receipts and summaries so later reduction cannot silently change the evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent import futures
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collect import ENDPOINT, load_jsonl, to_openai_tool
from reduce import count_flips
from study import (
    DEFAULT_PROTOCOL,
    StudyProtocol,
    load_protocol,
    mapped_observations,
    qualification_is_impossible,
    sha256_file,
)

from agentverity.meter import classify_call, wilson_ci

RequestFn = Callable[[list[dict], list[dict], str, str], dict]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_messages(entry: dict) -> list[dict]:
    flat_questions = [
        message
        for turn in entry["question"]
        for message in (turn if isinstance(turn, list) else [turn])
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are a function-calling assistant. Choose exactly one function "
                "to answer the user, and call it. Do not ask clarifying questions."
            ),
        },
        *flat_questions,
    ]


def decision_from_response(body: dict) -> str:
    calls = [
        {
            "name": call["function"]["name"],
            "arguments": json.dumps(
                json.loads(call["function"].get("arguments") or "{}"),
                sort_keys=True,
            ),
        }
        for call in body["choices"][0]["message"].get("tool_calls") or []
        if call.get("function")
    ]
    return "|".join(
        f"{call['name']}({call['arguments']})" for call in calls
    ) or "no_call"


def request_once(messages: list[dict], tools: list[dict], key: str, model: str) -> dict:
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
    requested_at = utc_now()
    started = time.monotonic()
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 409, 429, 500, 502, 503, 504) or attempt == 5:
                raise
            time.sleep(random.uniform(0, min(30, 2**attempt)))
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 5:
                raise
            time.sleep(random.uniform(0, min(30, 2**attempt)))
    else:  # pragma: no cover
        raise RuntimeError("unreachable")
    usage = body.get("usage") or {}
    return {
        "requested_at": requested_at,
        "finished_at": utc_now(),
        "latency_seconds": round(time.monotonic() - started, 6),
        "decision_exact": decision_from_response(body),
        "cost_usd": usage.get("cost") or 0.0,
        "provider_response": body,
    }


def _append_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_receipts(path: Path, protocol: StudyProtocol, case_id: str, model: str) -> list[dict]:
    if not path.exists():
        return []
    receipts = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for receipt in receipts:
        expected = (protocol.digest, case_id, model)
        actual = (receipt["protocol_sha256"], receipt["case_id"], receipt["model"])
        if actual != expected:
            raise ValueError(f"receipt provenance mismatch in {path}")
    successful = [receipt for receipt in receipts if receipt["status"] == "observed"]
    if [item["trial_index"] for item in successful] != list(range(len(successful))):
        raise ValueError(f"non-contiguous trial order in {path}")
    return receipts


def _qualification_outcome(flips: int, pairs: int, protocol: StudyProtocol) -> str:
    low, high = wilson_ci(flips, pairs, z=protocol.z)
    call = classify_call(low, high, protocol.epsilon)
    return {
        "verdict-deterministic": "qualify",
        "verdict-stochastic": "exceeds_tolerance",
        "undecided (add repeats or inputs)": "undecided",
    }[call]


def collect_cell(
    *,
    entry: dict,
    model: str,
    period_id: str,
    protocol: StudyProtocol,
    output_dir: Path,
    key: str,
    request_fn: RequestFn = request_once,
) -> dict:
    case_id = entry["id"]
    cell_dir = output_dir / period_id / model.replace("/", "_")
    receipt_path = cell_dir / f"{case_id}.receipts.jsonl"
    summary_path = cell_dir / f"{case_id}.summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["receipt_sha256"] != sha256_file(receipt_path):
            raise ValueError(f"sealed receipts changed for {case_id}")
        return summary

    receipts = _load_receipts(receipt_path, protocol, case_id, model)
    observations = [
        receipt["decision_exact"]
        for receipt in receipts
        if receipt["status"] == "observed"
    ]
    terminal_errors = sum(receipt["status"] == "error" for receipt in receipts)
    tools = [to_openai_tool(function) for function in entry["function"]]
    messages = build_messages(entry)
    stopped = False

    while len(observations) < protocol.endpoint_calls:
        trial_index = len(observations)
        base = {
            "schema": "agentverity.bfcl-provider-receipt/v1",
            "protocol_sha256": protocol.digest,
            "evaluation_period": period_id,
            "model": model,
            "case_id": case_id,
            "trial_index": trial_index,
        }
        try:
            observed = request_fn(messages, tools, key, model)
        except Exception as exc:
            terminal_errors += 1
            receipt = {
                **base,
                "status": "error",
                "finished_at": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            _append_receipt(receipt_path, receipt)
            receipts.append(receipt)
            if terminal_errors >= protocol.maximum_terminal_errors_per_cell:
                raise RuntimeError(f"{case_id} reached its terminal-error limit") from exc
            continue

        receipt = {**base, "status": "observed", **observed}
        _append_receipt(receipt_path, receipt)
        receipts.append(receipt)
        observations.append(receipt["decision_exact"])
        if len(observations) % 2 == 0 and qualification_is_impossible(
            observations, protocol, case_id
        ):
            stopped = True
            break

    mapped = mapped_observations(observations, protocol.primary_mapping)
    pairs = len(mapped) // 2
    flips = count_flips(mapped)
    summary = {
        "schema": "agentverity.bfcl-cell-summary/v1",
        "protocol_sha256": protocol.digest,
        "evaluation_period": period_id,
        "model": model,
        "case_id": case_id,
        "full_budget_validation": case_id in protocol.full_budget_validation_case_ids,
        "observations": len(observations),
        "pairs": pairs,
        "flips": flips,
        "qualification_outcome": (
            "qualification_impossible"
            if stopped
            else _qualification_outcome(flips, pairs, protocol)
        ),
        "stopping_pair": pairs if stopped else None,
        "avoided_pairs": protocol.endpoint_pairs - pairs if stopped else 0,
        "terminal_errors": terminal_errors,
        "cost_usd": round(
            sum(
                float(receipt.get("cost_usd", 0.0))
                for receipt in receipts
                if receipt["status"] == "observed"
            ),
            8,
        ),
        "receipt_file": receipt_path.name,
        "receipt_sha256": sha256_file(receipt_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def build_manifest(output_dir: Path, period_id: str, model: str, protocol: StudyProtocol) -> dict:
    cell_dir = output_dir / period_id / model.replace("/", "_")
    path = cell_dir / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            recorded = cell_dir / item["path"]
            if recorded.stat().st_size != item["bytes"] or sha256_file(recorded) != item["sha256"]:
                raise ValueError(f"sealed evidence changed: {recorded}")
        return manifest

    files = sorted([*cell_dir.glob("*.receipts.jsonl"), *cell_dir.glob("*.summary.json")])
    manifest = {
        "schema": "agentverity.bfcl-run-manifest/v1",
        "protocol_sha256": protocol.digest,
        "evaluation_period": period_id,
        "model": model,
        "sealed_at": utc_now(),
        "files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in files
        ],
    }
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--private-dir", type=Path, default=ROOT / "private")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    protocol = load_protocol(args.protocol)
    model = protocol.model_endpoint(args.model_key)
    not_before = protocol.period_not_before(args.period)
    if datetime.now(timezone.utc).date() < not_before:
        raise SystemExit(f"{args.period} cannot start before {not_before.isoformat()}")

    entries = {
        row["id"]: row
        for row in load_jsonl(ROOT / protocol.source["dataset"]["cases_file"])
    }
    missing = [case_id for case_id in protocol.case_ids if case_id not in entries]
    if missing:
        raise SystemExit(f"protocol cases missing from corpus: {missing}")

    print(
        f"{args.period} {model}: {len(protocol.case_ids)} cases, "
        f"{len(protocol.full_budget_validation_case_ids)} full-budget validation cases, "
        f"at most {len(protocol.case_ids) * protocol.endpoint_calls} calls"
    )
    if args.dry_run:
        print(f"protocol_sha256={protocol.digest}")
        return 0

    key = os.environ["OPENROUTER_API_KEY"]
    summaries = []
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {
            pool.submit(
                collect_cell,
                entry=entries[case_id],
                model=model,
                period_id=args.period,
                protocol=protocol,
                output_dir=args.private_dir,
                key=key,
            ): case_id
            for case_id in protocol.case_ids
        }
        for future in futures.as_completed(pending):
            summary = future.result()
            summaries.append(summary)
            print(
                f"  {summary['case_id']}: {summary['qualification_outcome']}, "
                f"{summary['pairs']}/{protocol.endpoint_pairs} pairs"
            )

    if len(summaries) != len(protocol.case_ids):
        raise RuntimeError("run ended without one summary per protocol case")
    manifest = build_manifest(args.private_dir, args.period, model, protocol)
    print(f"sealed {len(manifest['files'])} files under protocol {protocol.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())