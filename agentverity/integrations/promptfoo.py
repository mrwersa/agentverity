"""Translate a Promptfoo JSON export into AgentVerity evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentverity.decision_contract import DecisionSuite
from agentverity.evidence import EvidenceCase, EvidenceError, EvidenceSet


def _result_container(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EvidenceError("Promptfoo export root must be an object")
    value = payload.get("results")
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"results": value}
    raise EvidenceError(
        "Promptfoo export has no result rows; export JSON with "
        "'promptfoo eval --output results.json'"
    )


def _rows(payload: Any) -> list[dict[str, Any]]:
    container = _result_container(payload)
    value = container.get("results", container.get("outputs"))
    if not isinstance(value, list):
        raise EvidenceError(
            "Promptfoo export has no result rows; export JSON with "
            "'promptfoo eval --output results.json'"
        )
    if any(not isinstance(row, dict) for row in value):
        raise EvidenceError("Promptfoo result rows must be objects")
    return value


def _provider_id(row: dict[str, Any]) -> str:
    provider = row.get("provider")
    if isinstance(provider, dict):
        value = provider.get("id", provider.get("label"))
    else:
        value = provider
    return str(value) if value is not None else "unknown"


def _prompt_id(row: dict[str, Any]) -> str:
    value = row.get("promptId", row.get("promptIdx", "unknown"))
    return str(value)


def _path_value(value: Any, path: str | None, *, field: str = "output") -> str:
    if path is None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        raise EvidenceError(
            f"Promptfoo {field} is structured rather than a string; "
            "pass --decision-path, for example --decision-path route"
        )
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise EvidenceError(
                f"Promptfoo {field} is not JSON, so path {path!r} "
                "cannot be read"
            ) from exc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise EvidenceError(f"Promptfoo {field} has no path {path!r}")
        value = value[part]
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"Promptfoo {field} path {path!r} is not a string")
    return value.strip()


def evidence_from_promptfoo(
    payload: Any,
    suite: DecisionSuite,
    *,
    decision_path: str | None = None,
    input_path: str = "prompt.raw",
    provider: str | None = None,
    prompt_id: str | None = None,
    isolation: str = "unknown",
) -> EvidenceSet:
    """Convert one Promptfoo provider/prompt cell into repeated evidence.

    Promptfoo can evaluate a matrix of providers and prompts. Mixing those
    cells would make a model or prompt change look like stochasticity, so this
    function either selects one cell explicitly or refuses a mixed export.
    Assertion failures remain observations because correctness belongs to
    Promptfoo. Provider/runtime errors become incomplete AgentVerity evidence.
    """
    if not isinstance(suite, DecisionSuite):
        raise TypeError("Promptfoo import requires a DecisionSuite")
    if not isinstance(input_path, str) or not input_path.strip():
        raise EvidenceError("Promptfoo input path must be a non-empty string")
    rows = _rows(payload)
    selected = [
        row
        for row in rows
        if (provider is None or _provider_id(row) == provider)
        and (prompt_id is None or _prompt_id(row) == prompt_id)
    ]
    if not selected:
        raise EvidenceError("no Promptfoo rows match the requested provider/prompt")

    cells = {(_provider_id(row), _prompt_id(row)) for row in selected}
    if len(cells) != 1:
        shown = ", ".join(f"{p}/{q}" for p, q in sorted(cells)[:4])
        raise EvidenceError(
            "Promptfoo export contains multiple provider/prompt cells "
            f"({shown}). Assess one configuration at a time with --provider "
            "and --prompt-id."
        )
    selected_provider, selected_prompt = next(iter(cells))

    case_by_input = {case.input: index for index, case in enumerate(suite.cases)}
    grouped: dict[int, list[str]] = {}
    errors: dict[int, int] = {}
    for row_index, row in enumerate(selected):
        row_input = _path_value(row, input_path, field="row input")
        if row_input not in case_by_input:
            raise EvidenceError(
                f"Promptfoo row {row_index} input {row_input!r} does not match "
                "a reviewed decision-suite case. Use --input-path when the "
                "case input lives elsewhere in the export."
            )
        test_index = case_by_input[row_input]
        grouped.setdefault(test_index, [])
        errors.setdefault(test_index, 0)

        response = row.get("response")
        failure_reason = row.get("failureReason")
        row_error = row.get("error")
        response_error = response.get("error") if isinstance(response, dict) else None
        # Promptfoo puts a failed assertion's explanation in ``error`` and
        # marks it with failureReason=1. The returned output is still a valid
        # decision observation. Runtime/provider failures use reason 2, while
        # older exports may carry only an error string.
        assertion_failure = failure_reason == 1
        if (
            response_error
            or failure_reason == 2
            or (row_error and not assertion_failure)
        ):
            errors[test_index] += 1
            continue
        if not isinstance(response, dict) or "output" not in response:
            errors[test_index] += 1
            continue
        grouped[test_index].append(
            _path_value(response["output"], decision_path)
        )

    cases = []
    for index, declared in enumerate(suite.cases):
        observations = grouped.get(index, [])
        if len(observations) < 2:
            raise EvidenceError(
                f"Promptfoo case {index} ({declared.input!r}) has "
                f"{len(observations)} usable observation(s); run with "
                "--repeat 2 or higher"
            )
        cases.append(
            EvidenceCase(
                input=declared.input,
                observations=tuple(observations),
                expected=declared.expected,
                errors=errors.get(index, 0),
            )
        )

    provenance: dict[str, Any] = {
        "harness": "promptfoo",
        "input_path": input_path,
        "provider": selected_provider,
        "prompt_id": selected_prompt,
    }
    container = _result_container(payload)
    if "version" in container:
        provenance["export_version"] = container["version"]
    if "timestamp" in container:
        provenance["collected_at"] = container["timestamp"]
    return EvidenceSet(
        cases=tuple(cases),
        isolation=isolation,
        provenance=provenance,
    )


def load_promptfoo(
    path: str | Path,
    suite: DecisionSuite,
    **kwargs: Any,
) -> EvidenceSet:
    """Read and translate a Promptfoo JSON export."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot load Promptfoo export: {exc}") from exc
    return evidence_from_promptfoo(payload, suite, **kwargs)
