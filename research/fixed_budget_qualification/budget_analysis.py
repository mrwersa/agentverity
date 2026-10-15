#!/usr/bin/env python3
"""Budget design and deterministic curtailment under independent pair indicators."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import NormalDist

from validate_method import maximum_qualifying_disagreements

HERE = Path(__file__).resolve().parent
EPSILON = 0.05
ALPHA = 0.05
Z = NormalDist().inv_cdf(1 - ALPHA / 2)


def boundaries(budget: int, epsilon: float = EPSILON, z: float = Z) -> tuple[int, int]:
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ValueError("budget must be a positive integer")
    if not 0 < epsilon < 1 or not math.isfinite(z) or z <= 0:
        raise ValueError("epsilon must be in (0, 1) and z must be positive")
    f = maximum_qualifying_disagreements(budget, epsilon, z)
    g = math.floor(budget * epsilon + z * math.sqrt(budget * epsilon * (1 - epsilon))) + 1
    return f, g


def binomial_mass(n: int, q: float) -> list[float]:
    """Mode-centred recurrence avoids underflow from starting in a thin tail."""
    if not 0 <= q <= 1 or n < 0:
        raise ValueError("q must be in [0, 1] and n non-negative")
    if q == 0:
        return [1.0] + [0.0] * n
    if q == 1:
        return [0.0] * n + [1.0]
    mode = min(n, math.floor((n + 1) * q))
    mass = [0.0] * (n + 1)
    mass[mode] = 1.0
    for k in range(mode, 0, -1):
        mass[k - 1] = mass[k] * k / (n - k + 1) * (1 - q) / q
    for k in range(mode, n):
        mass[k + 1] = mass[k] * (n - k) / (k + 1) * q / (1 - q)
    total = math.fsum(mass)
    return [p / total for p in mass]


def qualification_probability(budget: int, q: float, epsilon: float = EPSILON,
                              z: float = Z) -> float:
    f, _ = boundaries(budget, epsilon, z)
    mass = binomial_mass(budget, q)
    return math.fsum(mass[:f + 1]) if f >= 0 else 0.0


def first_budget(q: float, target: float, ceiling: int = 1200) -> int | None:
    if not 0 <= q < EPSILON or not 0 < target < 1 or ceiling < 1:
        raise ValueError("invalid planning rate, probability target or ceiling")
    # Do not binary-search: probability can fall between threshold changes.
    for budget in range(1, ceiling + 1):
        if qualification_probability(budget, q) >= target:
            return budget
    return None


def collection_result(budget: int, n: int, count: int, mode: str,
                      epsilon: float = EPSILON, z: float = Z) -> dict:
    """Return an operational record, never an interval for a partial sample."""
    f, g = boundaries(budget, epsilon, z)
    if not isinstance(n, int) or not isinstance(count, int) or not 0 <= count <= n <= budget:
        raise ValueError("invalid observed counts")
    if mode not in ("admission", "diagnostic"):
        raise ValueError("unknown collection mode")
    status, classification, reason = "collecting", None, "decision_not_fixed"
    if f < 0:
        if n:
            raise ValueError("infeasible qualification design must be rejected before collection")
        status, reason = "infeasible", "budget_cannot_qualify"
    elif n == budget:
        status, reason = "complete", "budget_reached"
        classification = "qualify" if count <= f else "exceeds_tolerance" if count >= g else "undecided"
    elif mode == "admission" and count > f:
        status, reason = "curtailed", "qualification_impossible"
    elif mode == "diagnostic" and count >= g:
        status, classification, reason = "curtailed", "exceeds_tolerance", "full_budget_result_fixed"
    elif mode == "diagnostic" and count > f and count + budget - n < g:
        status, classification, reason = "curtailed", "undecided", "full_budget_result_fixed"
    return {"budget": budget, "epsilon": epsilon, "z": z, "mode": mode,
            "pairs_observed": n, "disagreements": count, "status": status,
            "classification": classification, "reason": reason}


def operating_characteristics(budget: int, q: float, epsilon: float = EPSILON,
                              z: float = Z, distributions: bool = False) -> dict:
    f, g = boundaries(budget, epsilon, z)
    mass = binomial_mass(budget, q)
    outcomes = {
        "qualify": math.fsum(mass[:f + 1]) if f >= 0 else 0.0,
        "exceeds_tolerance": math.fsum(mass[g:]),
        "undecided": math.fsum(mass[max(0, f + 1):g]),
    }
    result = {"budget": budget, "q": q, "F": f, "G": g,
              "full_budget_probabilities": outcomes, "modes": {}}
    for mode in ("admission", "diagnostic"):
        survival = []
        for n in range(budget):
            pmf = binomial_mass(n, q)
            survival.append(0.0 if f < 0 else math.fsum(
                p for k, p in enumerate(pmf)
                if (k <= f if mode == "admission" else
                    k < g and (k <= f or k + budget - n >= g))))
        # P(N > n) for n < B. Include N=0 for infeasible designs.
        lengths = [1.0 - survival[0]]
        lengths += [max(0.0, survival[n - 1] - survival[n]) for n in range(1, budget)]
        lengths += [survival[-1]]
        expected = math.fsum(survival)
        result["modes"][mode] = {
            "expected_pairs": expected,
            "saving_fraction": 1 - expected / budget,
            "probability_stop_before_budget": 1 - survival[-1],
            "infeasible": f < 0,
        }
        if distributions:
            result["modes"][mode]["length_probabilities_0_to_B"] = lengths
    return result


def build_report() -> dict:
    budgets = (73, 146, 292)
    rates = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.1)
    designs = []
    for q in (0.01, 0.02, 0.03):
        for target in (0.8, 0.9):
            budget = first_budget(q, target)
            designs.append({"q0": q, "target": target, "budget": budget,
                            "achieved": qualification_probability(budget, q)})
    return {
        "schema": "anonymous.budget-analysis/v1", "epsilon": EPSILON,
        "alpha": ALPHA, "z": Z, "design_search_ceiling": 1200,
        "assumption": "Independent Bernoulli disagreement indicators at one fixed rate",
        "designs": designs,
        "operating_characteristics": [operating_characteristics(b, q, distributions=True)
                                      for b in budgets for q in rates],
        "curves": [operating_characteristics(b, i / 400)
                   for b in budgets for i in range(41)],
        "examples": [collection_result(146, 55, 3, "admission"),
                     collection_result(146, 137, 3, "diagnostic"),
                     collection_result(146, 20, 13, "diagnostic"),
                     collection_result(146, 146, 2, "admission"),
                     collection_result(146, 146, 3, "diagnostic"),
                     collection_result(146, 146, 13, "diagnostic"),
                     collection_result(146, 2, 0, "admission"),
                     collection_result(10, 0, 0, "admission")],
        "example_scope": "Illustrative records, not recovered maintenance sequences",
    }


def aligned_integers(values: list[int]) -> list[str]:
    """Format one centred column so its digits line up.

    Each entry gets a thousands separator and an invisible copy of the
    leading characters it lacks, so every entry has the same width.
    """
    texts = [f"{value:,}" for value in values]
    widest = max(texts, key=len)
    cells = []
    for text in texts:
        pad = widest[:len(widest) - len(text)].replace(",", "{,}")
        cell = text.replace(",", "{,}")
        cells.append(f"\\phantom{{{pad}}}{cell}" if pad else cell)
    return cells


def render_table(report: dict) -> str:
    lines = [r"% Generated by artifact/budget_analysis.py. Do not edit.",
             r"\begin{table}[ht]", r"\centering\small",
             r"\caption{First pair budget attaining the target qualification probability",
             r"under independent pairs, at $\epsilon=0.05$ and 95\% confidence.",
             r"Each pair requires two runs.}", r"\label{tab:budget-design}",
             r"\begin{tabular}{lcc}\toprule",
             r"Planned rate $q_0$ & 80\% probability & 90\% probability\\\midrule"]
    designs = report["designs"]
    first = aligned_integers([d["budget"] for d in designs[0::2]])
    second = aligned_integers([d["budget"] for d in designs[1::2]])
    for design, low, high in zip(designs[0::2], first, second):
        lines.append(f"{100*design['q0']:.0f}\\% & {low} & {high}\\\\")
    return "\n".join(lines + [r"\bottomrule\end{tabular}", r"\end{table}", ""])


def render_cost_table(report: dict) -> str:
    lines = [r"% Generated by artifact/budget_analysis.py. Do not edit.",
             r"\begin{table}[ht]\centering\small",
             r"\caption{Analytical qualification probability and expected pairs at $B=146$.",
             r"Admission stops when qualification is impossible. Diagnostic collection",
             r"preserves all three full-budget classifications.}", r"\label{tab:expected-cost}",
             r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrr@{}}",
             r"\toprule Rate $q$ & Qualify & Admission pairs & Diagnostic pairs\\\midrule"]
    for row in report["operating_characteristics"]:
        if row["budget"] != 146 or row["q"] == .005:
            continue
        p = 100 * row["full_budget_probabilities"]["qualify"]
        prob = f"{p:.4f}" if 0 < p < .01 else f"{p:.1f}"
        a, d = (row["modes"][mode]["expected_pairs"] for mode in ("admission", "diagnostic"))
        lines.append(f"{100*row['q']:.0f}\\% & {prob}\\% & {a:.1f} & {d:.1f}\\\\")
    return "\n".join(lines + [r"\bottomrule\end{tabular*}\end{table}", ""])


def render_figure(report: dict) -> str:
    lines = [r"% Generated by artifact/budget_analysis.py. Do not edit.",
             r"\begin{figure}[ht]\centering"]
    for quantity, ylabel in (("probability", "qualification probability"),
                             ("cost", "expected pairs collected")):
        lines += [r"\begin{tikzpicture}[baseline=(current bounding box.north)]",
                  r"\begin{axis}[width=0.47\linewidth,height=5.2cm,xmin=0,xmax=0.1,",
                  r"xlabel={disagreement probability $q$},",
                  f"ylabel={{{ylabel}}},",
                  r"xtick={0,0.02,0.04,0.06,0.08,0.10},",
                  r"xticklabels={0,0.02,0.04,0.06,0.08,0.10},",
                  r"tick label style={font=\scriptsize},label style={font=\scriptsize},",
                  (r"legend style={font=\scriptsize,draw=none,at={(0.5,-0.35)},anchor=north,legend columns=2}]"
                   if quantity == "cost" else
                   r"legend style={font=\scriptsize,draw=none},legend pos=north east]")]
        for budget, style in ((73, "densely dotted"), (146, "solid"), (292, "dashed")):
            rows = [r for r in report["curves"] if r["budget"] == budget]
            modes = ("admission",) if quantity == "probability" else ("admission", "diagnostic")
            for mode in modes:
                points = []
                for row in rows:
                    value = (row["full_budget_probabilities"]["qualify"] if quantity == "probability"
                             else row["modes"][mode]["expected_pairs"])
                    points.append(f"({row['q']:.4f},{value:.6f})")
                colour = "black" if mode == "admission" else "black!55"
                lines.append(f"\\addplot[{style},{colour}] coordinates {{{' '.join(points)}}};")
                label = f"$B={budget}$" + (" A" if mode == "admission" else " D")
                if quantity == "probability":
                    label = f"$B={budget}$"
                lines.append(f"\\addlegendentry{{{label}}}")
        lines += [r"\end{axis}\end{tikzpicture}%"]
    lines += [r"\caption{Budget choice under independent pair indicators. Both collection",
              r"modes have the same qualification probability (left). Expected collection",
              r"length (right) can be lower when only qualification matters (A, black) than",
              r"when the three-way result must be preserved (D, grey). These are model",
              r"calculations at $\epsilon=0.05$ and 95\% confidence, not observed savings.}",
              r"\label{fig:budget-cost}\end{figure}", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    outputs = {"budget_results.json": json.dumps(report, indent=2, allow_nan=False) + "\n",
               "budget_table.tex": render_table(report),
               "budget_cost_table.tex": render_cost_table(report),
               "budget_figure.tex": render_figure(report)}
    for name, content in outputs.items():
        path = HERE / name
        if args.check:
            if not path.exists() or path.read_text() != content:
                raise SystemExit(f"stale generated output: {name}")
        else:
            path.write_text(content)
    print("PASS budget results, tables and figure" if args.check else "Generated budget results, tables and figure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
