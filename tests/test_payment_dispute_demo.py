"""Executable evidence-gate example tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from agentverity import (
    SnapshotRefused,
    create_snapshot,
    run_result_to_junit_xml,
)


def _load_demo():
    path = Path(__file__).parents[1] / "examples" / "payment_dispute_gate.py"
    spec = importlib.util.spec_from_file_location("payment_dispute_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_probe_sets_score_six_of_six():
    demo = _load_demo()
    assert demo._evaluate(demo.NARROW_CASES) == (6, 6)
    assert demo._evaluate(demo.DIVERSE_CASES) == (6, 6)
    quality = ET.fromstring(
        demo._quality_junit_xml("narrow-quality", demo.NARROW_CASES)
    )
    assert quality.attrib["tests"] == "1"
    assert quality.attrib["failures"] == "0"


def test_narrow_suite_is_refused_and_repaired_suite_is_admitted():
    demo = _load_demo()
    narrow = demo._run_suite(demo.NARROW_CASES)
    repaired = demo._run_suite(demo.DIVERSE_CASES)

    assert narrow.status == "blind"
    with pytest.raises(SnapshotRefused):
        create_snapshot(narrow, approved=True)

    assert repaired.status == "deterministic"
    assert create_snapshot(repaired, approved=True)

    narrow_xml = ET.fromstring(run_result_to_junit_xml(narrow))
    repaired_xml = ET.fromstring(run_result_to_junit_xml(repaired))
    assert narrow_xml.attrib["failures"] == "1"
    assert repaired_xml.attrib["failures"] == "0"
