"""Render the README diagnostic image from the executable bug-fix example."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from agentverity import from_callable, run
from examples.bugfix_pipeline import BUG_REPORTS, make_supervisor, triage_agent

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "diagnostic-report.svg"


def _text(x: int, y: int, value: str, *, css: str = "body") -> str:
    return f'<text x="{x}" y="{y}" class="{css}">{html.escape(value)}</text>'


def _panel(
    *,
    x: int,
    title: str,
    badge: str,
    badge_class: str,
    meter: str,
    flip_rate: str,
    skew: str,
    oracle: str,
    action: str,
) -> str:
    rows = [
        _text(x + 32, 234, title, css="eyebrow"),
        (
            f'<rect x="{x + 340}" y="207" width="142" height="34" '
            f'rx="5" class="{badge_class}"/>'
        ),
        _text(x + 411, 230, badge, css="badge"),
        _text(x + 32, 285, "VERDICT METER", css="label"),
        _text(x + 32, 316, meter, css="value"),
        _text(x + 32, 360, "PAIRWISE FLIP RATE", css="label"),
        _text(x + 32, 391, flip_rate, css="value"),
        _text(x + 270, 360, "VERDICT SKEW", css="label"),
        _text(x + 270, 391, skew, css="value"),
        _text(x + 32, 447, "TEST DECISION", css="label"),
        _text(x + 32, 480, oracle, css="decision"),
        f'<line x1="{x + 32}" y1="512" x2="{x + 488}" y2="512" class="rule"/>',
        _text(x + 32, 548, "NEXT ACTION", css="label"),
        _text(x + 32, 579, action, css="action"),
    ]
    return "\n".join(rows)


def render(output: Path = DEFAULT_OUTPUT) -> str:
    """Run the real example and render its current diagnostic values."""
    triage = run(from_callable(triage_agent), BUG_REPORTS)
    pipeline = run(from_callable(make_supervisor(seed=1)), BUG_REPORTS)
    assert triage.meter and triage.blindness
    assert pipeline.meter and pipeline.blindness

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="660"
 viewBox="0 0 1200 660" role="img"
 aria-label="AgentVerity diagnostic report for a toy multi-agent bug-fix pipeline">
<style>
  .bg {{ fill: #0b1220; }}
  .panel {{ fill: #111b2e; stroke: #314158; stroke-width: 1.5; }}
  .route {{ fill: #17243a; stroke: #3b82f6; stroke-width: 1.5; }}
  text {{ font-family: Arial, sans-serif; }}
  .routeText {{ fill: #dbeafe; font-size: 17px; font-weight: 600;
    text-anchor: middle; }}
  .flow {{ stroke: #64748b; stroke-width: 2; }}
  .headline {{ fill: #f8fafc; font-size: 29px; font-weight: 700; }}
  .subhead {{ fill: #94a3b8; font-size: 16px; font-weight: 400; }}
  .eyebrow {{ fill: #f8fafc; font-size: 19px; font-weight: 700; }}
  .label {{ fill: #7f91ab; font-size: 12px; font-weight: 700; }}
  .value {{ fill: #f1f5f9; font-size: 22px; font-weight: 600; }}
  .decision {{ fill: #93c5fd; font-size: 21px; font-weight: 700; }}
  .action {{ fill: #cbd5e1; font-size: 16px; font-weight: 500; }}
  .badge {{ fill: #ffffff; font-size: 13px; font-weight: 700;
    text-anchor: middle; }}
  .danger {{ fill: #dc2626; }}
  .warning {{ fill: #d97706; }}
  .rule {{ stroke: #314158; stroke-width: 1; }}
  .footer {{ fill: #64748b; font-size: 13px; font-weight: 400; }}
</style>
<rect width="1200" height="660" class="bg"/>
{_text(54, 54, "AgentVerity asks whether the test is trustworthy first.", css="headline")}
{_text(54, 84, "One executable example. Two defects. Two different testing decisions.", css="subhead")}
<rect x="54" y="114" width="226" height="52" rx="6" class="route"/>
<rect x="364" y="114" width="226" height="52" rx="6" class="route"/>
<rect x="674" y="114" width="226" height="52" rx="6" class="route"/>
<rect x="984" y="114" width="162" height="52" rx="6" class="route"/>
{_text(167, 147, "REPEAT VERDICTS", css="routeText")}
{_text(477, 147, "SCAN FOR SKEW", css="routeText")}
{_text(787, 147, "CHOOSE TEST", css="routeText")}
{_text(1065, 147, "TEST", css="routeText")}
<line x1="298" y1="140" x2="338" y2="140" class="flow"/>
<path d="M 338 135 L 348 140 L 338 145 z" fill="#64748b"/>
<line x1="608" y1="140" x2="648" y2="140" class="flow"/>
<path d="M 648 135 L 658 140 L 648 145 z" fill="#64748b"/>
<line x1="918" y1="140" x2="958" y2="140" class="flow"/>
<path d="M 958 135 L 968 140 L 958 145 z" fill="#64748b"/>
<rect x="54" y="190" width="520" height="414" rx="7" class="panel"/>
<rect x="626" y="190" width="520" height="414" rx="7" class="panel"/>
{_panel(
    x=54,
    title="TRIAGE STEP",
    badge="BLIND",
    badge_class="danger",
    meter=triage.meter.call.replace(" (add repeats or inputs)", ""),
    flip_rate=(
        f"{triage.meter.flip_rate:.1%} "
        f"({triage.meter.pair_flips}/{triage.meter.pair_trials})"
    ),
    skew=f"{triage.blindness.skew:.1%} · one verdict",
    oracle="Do not trust green relations",
    action="Vary test inputs before adding checks",
)}
{_panel(
    x=626,
    title="FULL SUPERVISOR PIPELINE",
    badge="STOCHASTIC",
    badge_class="warning",
    meter=pipeline.meter.call,
    flip_rate=(
        f"{pipeline.meter.flip_rate:.1%} "
        f"({pipeline.meter.pair_flips}/{pipeline.meter.pair_trials})"
    ),
    skew=f"{pipeline.blindness.skew:.1%} · two verdicts",
    oracle="Use noise-robust relations",
    action="Calibrate against unchanged-input noise",
)}
{_text(54, 636, "Generated from examples/bugfix_pipeline.py · seed 1 · six bug reports", css="footer")}
</svg>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    return svg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
