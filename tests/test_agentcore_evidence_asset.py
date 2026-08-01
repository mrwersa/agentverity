from __future__ import annotations

import json
from pathlib import Path

from scripts.render_agentcore_evidence import (
    DEFAULT_INPUT,
    DEFAULT_OUTPUT,
    render,
)


def test_agentcore_evidence_asset_matches_sanitised_results(tmp_path: Path) -> None:
    output = tmp_path / "evidence.svg"
    svg = render(DEFAULT_INPUT, output)
    data = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))

    assert output.read_text(encoding="utf-8") == svg
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == svg
    assert "6 / 6 correct" in svg
    assert "0 / 36 route changes" in svg
    assert "78 successful" in svg
    assert "POOLED RULE PASSED" in svg
    assert "Pooled 10% rule and route reach checked" in svg
    assert "AGENTCORE RUNTIME" in svg
    assert "3 SEPARATE CHECKS" in svg
    assert "3 INDEPENDENT CHECKS" not in svg
    assert "RELEASE POLICY" in svg
    assert "Median end-to-end" in svg
    assert "Quality was 5/6 while the decision was stable." in svg
    assert data["region"] in svg
    assert "arn:aws:" not in svg
    assert "agentRuntimeArn" not in svg
