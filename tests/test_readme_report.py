"""The README image must stay generated from the executable example."""

from __future__ import annotations

from scripts.render_readme_report import render


def test_readme_report_renders_real_diagnostics(tmp_path):
    output = tmp_path / "report.svg"
    svg = render(output)
    assert output.read_text() == svg
    assert "100.0% · one verdict" in svg
    assert "66.7% (8/12)" in svg
    assert "BLIND" in svg
    assert "STOCHASTIC" in svg
