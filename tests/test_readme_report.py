"""The README image must stay generated from the executable example."""

from __future__ import annotations

from scripts.render_readme_report import render


def test_readme_report_renders_real_diagnostics(tmp_path):
    output = tmp_path / "report.svg"
    svg = render(output)
    assert output.read_text() == svg
    # Pinned to what the committed example actually produces at defaults, so a
    # change in sizing cannot quietly leave a stale picture in the README.
    assert "100.0% · one verdict" in svg   # triage is blind
    assert "42.3% (33/78)" in svg          # pipeline flips, measured over 78 pairs
    assert "BLIND" in svg
    assert "STOCHASTIC" in svg
