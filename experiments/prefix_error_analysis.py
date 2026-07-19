"""Mean absolute error vs number of questions, on the full 25-model set.

Three systems, one population:
  - fixed questions + calibrated medium transcript read (the shipped system);
  - Terra-authored adaptive ladder, scored by ladder position;
  - medium-authored adaptive ladder, same scoring (author-quality control).

Every estimate is leave-one-out. Writes prefix_error_results.json and
prefix_error.svg.

    python -m experiments.prefix_error_analysis
"""
from __future__ import annotations

import json
import math
from pathlib import Path

EXP = Path(__file__).resolve().parent
FRONTIER_FLOOR = 1740.0
QUESTIONS = 5

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
FONT = 'system-ui, -apple-system, &quot;Segoe UI&quot;, sans-serif'
SERIES = {
    "fixed_calibrated": ("#008300", "Fixed Qs + calibrated read (shipped)", ""),
    "terra_ladder": ("#2a78d6", "Terra-authored adaptive ladder", ""),
    "medium_ladder": ("#eda100", "Medium-authored ladder (control)", ' stroke-dasharray="7 5"'),
}


def load_fixed() -> dict:
    bank = json.loads((EXP / "method_battle_data.json").read_text(encoding="utf-8"))["models"]
    frontier = json.loads((EXP / "frontier_test_data.json").read_text(encoding="utf-8"))["models"]
    out = {}
    for source in (bank, frontier):
        for name, record in source.items():
            out[name] = {
                "true": record["public_elo"],
                "reads": [r["mean_elo"] for r in record["holistic_prefixes"]],
            }
    return out


def load_ladder(path: str) -> dict:
    data = json.loads((EXP / path).read_text(encoding="utf-8"))["models"]
    return {
        name: {
            "true": record["public_elo"],
            "traces": [
                (t["question_difficulty_target"], t["grade_expected_score"])
                for t in record["traces"]
            ],
        }
        for name, record in data.items()
    }


def ladder_score(traces) -> float:
    passed = [d for d, s in traces if s >= 2.5]
    failed = [d for d, s in traces if s < 2.5]
    top_pass = max(passed) if passed else min(d for d, _ in traces) - 300.0
    low_fail = min(failed) if failed else max(d for d, _ in traces) + 300.0
    return (top_pass + low_fail) / 2.0


def loo_mae(scores: dict[str, float], truths: dict[str, float], subset) -> float:
    names = list(scores)
    estimates = {}
    for held in names:
        pairs = [(truths[n], scores[n]) for n in names if n != held]
        k = len(pairs)
        tm = sum(t for t, _ in pairs) / k
        sm = sum(s for _, s in pairs) / k
        tv = sum((t - tm) ** 2 for t, _ in pairs)
        cov = sum((t - tm) * (s - sm) for t, s in pairs)
        slope = cov / tv if tv else 0.0
        if slope <= 0.05:
            estimates[held] = scores[held]
        else:
            estimates[held] = (scores[held] - (sm - slope * tm)) / slope
    members = [n for n in names if subset(truths[n])]
    return sum(abs(estimates[n] - truths[n]) for n in members) / len(members)


def curves() -> dict:
    fixed = load_fixed()
    terra = load_ladder("terra_author_data.json")
    medium = load_ladder("adaptive_battle_data.json")
    everyone = lambda t: True
    frontier = lambda t: t >= FRONTIER_FLOOR

    out: dict[str, dict[str, list[float]]] = {"all": {}, "frontier": {}}
    for label, subset in (("all", everyone), ("frontier", frontier)):
        fixed_curve = []
        terra_curve = []
        medium_curve = []
        for k in range(1, QUESTIONS + 1):
            fixed_curve.append(
                loo_mae(
                    {n: e["reads"][k - 1] for n, e in fixed.items()},
                    {n: e["true"] for n, e in fixed.items()},
                    subset,
                )
            )
            terra_curve.append(
                loo_mae(
                    {n: ladder_score(e["traces"][:k]) for n, e in terra.items()},
                    {n: e["true"] for n, e in terra.items()},
                    subset,
                )
            )
            medium_curve.append(
                loo_mae(
                    {n: ladder_score(e["traces"][:k]) for n, e in medium.items()},
                    {n: e["true"] for n, e in medium.items()},
                    subset,
                )
            )
        out[label] = {
            "fixed_calibrated": fixed_curve,
            "terra_ladder": terra_curve,
            "medium_ladder": medium_curve,
        }
    return out


def render(results: dict) -> str:
    width, height = 920, 480
    panel_w, panel_h = 360, 300
    panel_top = 100
    panels_x = (70, 520)
    top_value = 50.0 * (int(max(max(c) for panel in results.values() for c in panel.values()) / 50.0) + 1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>',
        f'<text x="{panels_x[0]}" y="34" fill="{INK}" font-size="18" font-weight="600">'
        "Mean absolute Elo error vs number of questions</text>",
        f'<text x="{panels_x[0]}" y="56" fill="{INK_SECONDARY}" font-size="13">'
        "25 live models (1210–1911), leave-one-out · ladder = midpoint of hardest pass / easiest fail</text>",
    ]

    for panel_index, (label, title) in enumerate((("all", "All 25 models"), ("frontier", "Frontier subset (n=8, ≥1740)"))):
        x0 = panels_x[panel_index]
        parts.append(
            f'<text x="{x0}" y="{panel_top - 14}" fill="{INK}" font-size="14.5" font-weight="600">{title}</text>'
        )

        def px(k):
            return x0 + panel_w * (k - 1) / (QUESTIONS - 1)

        def py(v):
            return panel_top + panel_h * (1.0 - v / top_value)

        tick = 100.0 if top_value > 300 else 50.0
        v = 0.0
        while v <= top_value + 0.1:
            parts.append(
                f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x0 + panel_w}" y2="{py(v):.1f}" '
                f'stroke="{GRID if v > 0 else BASELINE}" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{x0 - 8}" y="{py(v) + 4:.1f}" fill="{INK_MUTED}" font-size="11" '
                f'text-anchor="end" style="font-variant-numeric: tabular-nums">{v:.0f}</text>'
            )
            v += tick
        for k in range(1, QUESTIONS + 1):
            parts.append(
                f'<text x="{px(k):.1f}" y="{panel_top + panel_h + 20}" fill="{INK_MUTED}" '
                f'font-size="11.5" text-anchor="middle">Q{k}</text>'
            )
        for key, (color, name, dash) in SERIES.items():
            values = results[label][key]
            points = " ".join(f"{px(k + 1):.1f},{py(v):.1f}" for k, v in enumerate(values))
            parts.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
            )
            for k, v in enumerate(values):
                parts.append(
                    f'<circle cx="{px(k + 1):.1f}" cy="{py(v):.1f}" r="4" fill="{color}" '
                    f'stroke="{SURFACE}" stroke-width="2"><title>{name} after Q{k + 1}: '
                    f"{v:.0f}</title></circle>"
                )

    legend_y = height - 26
    lx = panels_x[0]
    for key, (color, name, dash) in SERIES.items():
        parts.append(
            f'<line x1="{lx}" y1="{legend_y - 4}" x2="{lx + 26}" y2="{legend_y - 4}" '
            f'stroke="{color}" stroke-width="2"{dash}/>'
        )
        parts.append(
            f'<text x="{lx + 32}" y="{legend_y}" fill="{INK}" font-size="12.5">{name}</text>'
        )
        lx += 40 + len(name) * 6.4
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    results = curves()
    (EXP / "prefix_error_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (EXP / "prefix_error.svg").write_text(render(results), encoding="utf-8")
    for label, panel in results.items():
        print(f"[{label}]")
        for key, values in panel.items():
            print(f"  {key:<18} " + " ".join(f"{v:>5.0f}" for v in values))
    print("Saved prefix_error_results.json and prefix_error.svg")


if __name__ == "__main__":
    main()
