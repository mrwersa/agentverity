"""Pin the preregistered BFCL evaluation protocol and stopping boundary."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BFCL = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "bfcl"
SPEC = importlib.util.spec_from_file_location("bfcl_study", BFCL / "study.py")
assert SPEC is not None and SPEC.loader is not None
study = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = study
SPEC.loader.exec_module(study)

COLLECT_SPEC = importlib.util.spec_from_file_location(
    "bfcl_collect_study", BFCL / "collect_study.py"
)
assert COLLECT_SPEC is not None and COLLECT_SPEC.loader is not None
collect_study = importlib.util.module_from_spec(COLLECT_SPEC)
sys.modules[COLLECT_SPEC.name] = collect_study
COLLECT_SPEC.loader.exec_module(collect_study)


def test_protocol_freezes_confirmatory_cases_models_and_periods():
    protocol = study.load_protocol()

    assert len(protocol.case_ids) == 50
    assert set(protocol.case_ids).isdisjoint({f"multiple_{i}" for i in range(10)})
    assert len(protocol.full_budget_validation_case_ids) == 10
    assert len(protocol.models) == 3
    assert protocol.endpoint_pairs == 73
    assert protocol.endpoint_calls == 146
    assert protocol.epsilon == 0.05
    assert protocol.alpha == 0.05
    assert protocol.primary_mapping == "numeric"
    assert (protocol.periods[1][1] - protocol.periods[0][1]).days == 21


def test_validation_subset_is_selected_without_observing_outcomes(tmp_path):
    document = json.loads(study.DEFAULT_PROTOCOL.read_text(encoding="utf-8"))
    document["full_budget_validation_case_ids"][0] = "multiple_10"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 selection"):
        study.load_protocol(path)


def test_one_primary_flip_makes_qualification_impossible_at_73_pairs():
    protocol = study.load_protocol()
    observations = ['f({"value": 1})', 'f({"value": 2})']

    assert study.qualification_is_impossible(observations, protocol, "multiple_10")


def test_numeric_equivalence_does_not_create_a_flip():
    protocol = study.load_protocol()
    observations = ['f({"value": 1})', 'f({"value": 1.0})']

    assert not study.qualification_is_impossible(observations, protocol, "multiple_10")


def test_full_budget_validation_case_never_stops_early():
    protocol = study.load_protocol()
    case_id = next(iter(protocol.full_budget_validation_case_ids))
    observations = ['f({"value": 1})', 'f({"value": 2})']

    assert not study.qualification_is_impossible(observations, protocol, case_id)


def test_stopping_requires_a_complete_pair():
    protocol = study.load_protocol()

    with pytest.raises(ValueError, match="complete pair"):
        study.qualification_is_impossible(['f({"value": 1})'], protocol, "multiple_10")


def test_file_digest_detects_a_changed_receipt(tmp_path):
    receipt = tmp_path / "receipts.jsonl"
    receipt.write_text('{"trial": 0}\n', encoding="utf-8")
    before = study.sha256_file(receipt)
    receipt.write_text('{"trial": 1}\n', encoding="utf-8")

    assert study.sha256_file(receipt) != before


def _entry() -> dict:
    return {
        "id": "multiple_10",
        "question": [[{"role": "user", "content": "Choose."}]],
        "function": [
            {
                "name": "choose",
                "description": "Choose a value.",
                "parameters": {"type": "object", "properties": {}},
            }
        ],
    }


def _response(decision: str):
    def request(_messages, _tools, _key, _model):
        return {
            "requested_at": "2026-08-27T00:00:00+00:00",
            "finished_at": "2026-08-27T00:00:01+00:00",
            "latency_seconds": 1.0,
            "decision_exact": decision,
            "cost_usd": 0.001,
            "provider_response": {"id": "private-provider-id"},
        }

    return request


def test_non_validation_cell_stops_when_qualification_is_impossible(tmp_path):
    protocol = study.load_protocol()
    decisions = iter(['f({"value": 1})', 'f({"value": 2})'])

    def request(*_args):
        return _response(next(decisions))(*_args)

    summary = collect_study.collect_cell(
        entry=_entry(),
        model="test/model",
        period_id="period-1",
        protocol=protocol,
        output_dir=tmp_path,
        key="not-a-real-key",
        request_fn=request,
    )

    assert summary["qualification_outcome"] == "qualification_impossible"
    assert summary["pairs"] == 1
    assert summary["avoided_pairs"] == 72


def test_validation_cell_runs_to_the_fixed_budget(tmp_path):
    protocol = study.load_protocol()
    validation_case = next(iter(protocol.full_budget_validation_case_ids))
    entry = {**_entry(), "id": validation_case}

    summary = collect_study.collect_cell(
        entry=entry,
        model="test/model",
        period_id="period-1",
        protocol=protocol,
        output_dir=tmp_path,
        key="not-a-real-key",
        request_fn=_response('f({"value": 1})'),
    )

    assert summary["full_budget_validation"] is True
    assert summary["observations"] == 146
    assert summary["pairs"] == 73
    assert summary["qualification_outcome"] == "qualify"


def test_receipts_preserve_raw_response_and_manifest_detects_changes(tmp_path):
    protocol = study.load_protocol()
    collect_study.collect_cell(
        entry=_entry(),
        model="test/model",
        period_id="period-1",
        protocol=protocol,
        output_dir=tmp_path,
        key="not-a-real-key",
        request_fn=_response('f({"value": 1})'),
    )
    manifest = collect_study.build_manifest(tmp_path, "period-1", "test/model", protocol)
    receipt_path = tmp_path / "period-1" / "test_model" / "multiple_10.receipts.jsonl"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])

    assert receipt["provider_response"] == {"id": "private-provider-id"}
    assert any(item["path"] == receipt_path.name for item in manifest["files"])
    recorded = next(item for item in manifest["files"] if item["path"] == receipt_path.name)
    assert recorded["sha256"] == study.sha256_file(receipt_path)

    receipt_path.write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="sealed evidence changed"):
        collect_study.build_manifest(tmp_path, "period-1", "test/model", protocol)