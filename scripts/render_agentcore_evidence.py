"""Render the production-stack evidence card from a redacted real run."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "examples"
    / "production_stack"
    / "results"
    / "agentcore-canary.json"
)
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "agentcore-release-gate.svg"


def _text(x: int, y: int, value: str, *, css: str = "body") -> str:
    return f'<text x="{x}" y="{y}" class="{css}">{html.escape(value)}</text>'


def _card(
    *,
    x: int,
    eyebrow: str,
    headline: str,
    detail_1: str,
    detail_2: str,
    badge: str,
    accent: str,
) -> str:
    return "\n".join(
        [
            f'<rect x="{x}" y="244" width="344" height="250" rx="8" class="card"/>',
            f'<rect x="{x}" y="244" width="344" height="5" rx="2" fill="{accent}"/>',
            _text(x + 26, 286, eyebrow, css="eyebrow"),
            _text(x + 26, 338, headline, css="metric"),
            _text(x + 26, 382, detail_1, css="detail"),
            _text(x + 26, 414, detail_2, css="detail"),
            (
                f'<rect x="{x + 26}" y="446" width="192" height="30" '
                f'rx="4" fill="{accent}"/>'
            ),
            _text(x + 122, 467, badge, css="badge"),
        ]
    )


def render(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> str:
    """Render a dashboard-like SVG from sanitised canary evidence."""
    data: dict[str, Any] = json.loads(input_path.read_text(encoding="utf-8"))
    method = data["method"]
    cloud = data["agentcore"]
    failure = data["initial_failure"]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="690"
 viewBox="0 0 1200 690" role="img"
 aria-label="AgentVerity release gate from a real AgentCore payment-routing canary">
<style>
  .bg {{ fill: #0b1220; }}
  .card {{ fill: #111b2e; stroke: #314158; stroke-width: 1.5; }}
  .step {{ fill: #17243a; stroke: #426286; stroke-width: 1.5; }}
  text {{ font-family: Arial, sans-serif; }}
  .headline {{ fill: #f8fafc; font-size: 29px; font-weight: 700; }}
  .subhead {{ fill: #9fb0c7; font-size: 16px; font-weight: 400; }}
  .stepText {{ fill: #dbeafe; font-size: 15px; font-weight: 600;
    text-anchor: middle; }}
  .eyebrow {{ fill: #91a4bf; font-size: 13px; font-weight: 700; }}
  .metric {{ fill: #f8fafc; font-size: 31px; font-weight: 700; }}
  .detail {{ fill: #cbd5e1; font-size: 16px; font-weight: 400; }}
  .badge {{ fill: #07111f; font-size: 13px; font-weight: 700;
    text-anchor: middle; }}
  .flow {{ stroke: #64748b; stroke-width: 2; }}
  .lessonBox {{ fill: #182337; stroke: #f59e0b; stroke-width: 1.5; }}
  .lessonTitle {{ fill: #fbbf24; font-size: 13px; font-weight: 700; }}
  .lesson {{ fill: #e2e8f0; font-size: 17px; font-weight: 600; }}
  .footer {{ fill: #73849c; font-size: 13px; font-weight: 400; }}
</style>
<rect width="1200" height="690" class="bg"/>
{_text(54, 52, "A green agent test, qualified before release.", css="headline")}
{_text(54, 82, "Separate quality, evidence, and operational checks · combined only at release", css="subhead")}
<rect x="54" y="112" width="238" height="52" rx="6" class="step"/>
<rect x="357" y="112" width="238" height="52" rx="6" class="step"/>
<rect x="660" y="112" width="238" height="52" rx="6" class="step"/>
<rect x="963" y="112" width="183" height="52" rx="6" class="step"/>
{_text(173, 144, "6 REVIEWED CASES", css="stepText")}
{_text(476, 144, "AGENTCORE RUNTIME", css="stepText")}
{_text(779, 144, "3 SEPARATE CHECKS", css="stepText")}
{_text(1055, 144, "RELEASE POLICY", css="stepText")}
<line x1="309" y1="138" x2="337" y2="138" class="flow"/>
<path d="M 337 133 L 347 138 L 337 143 z" fill="#64748b"/>
<line x1="612" y1="138" x2="640" y2="138" class="flow"/>
<path d="M 640 133 L 650 138 L 640 143 z" fill="#64748b"/>
<line x1="915" y1="138" x2="943" y2="138" class="flow"/>
<path d="M 943 133 L 953 138 L 943 143 z" fill="#64748b"/>
{_text(54, 209, f"{method['planned_calls']} isolated cloud calls · {data['region_label']} ({data['region']}) · {data['model_id']}", css="subhead")}
{_card(
    x=54,
    eyebrow="QUALITY · DEEPEVAL",
    headline=f"{cloud['quality_passed']} / {cloud['quality_total']} correct",
    detail_1="Reviewed route labels",
    detail_2="Correctness checked once per case",
    badge="QUALITY PASSED",
    accent="#38bdf8",
)}
{_card(
    x=428,
    eyebrow="EVIDENCE · AGENTVERITY",
    headline=f"{cloud['pair_flips']} / {cloud['pair_trials']} route changes",
    detail_1=f"{cloud['distinct_routes']} of {method['reviewed_cases']} routes reached",
    detail_2="Decision stability and coverage checked",
    badge="BASELINE ADMITTED",
    accent="#4ade80",
)}
{_card(
    x=802,
    eyebrow="OPERATIONS · AGENTCORE",
    headline=f"{cloud['successful_invocations']} successful",
    detail_1=f"{cloud['errors']} errors · {cloud['throttles']} throttles",
    detail_2=f"Median end-to-end {cloud['end_to_end_p50_seconds']:.2f}s",
    badge="CANARY HEALTHY",
    accent="#a78bfa",
)}
<rect x="54" y="526" width="1092" height="98" rx="8" class="lessonBox"/>
{_text(80, 558, "WHAT THE FIRST RUN CAUGHT", css="lessonTitle")}
{_text(80, 590, f"Quality was {failure['quality_passed']}/{failure['quality_total']} while the decision was stable.", css="lesson")}
{_text(642, 590, failure["lesson"], css="lesson")}
{_text(54, 662, f"Redacted evidence · {data['captured_at']} · runtime median {cloud['runtime_p50_seconds']:.3f}s · end-to-end 95th percentile {cloud['end_to_end_p95_seconds']:.2f}s", css="footer")}
</svg>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return svg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(args.input, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
