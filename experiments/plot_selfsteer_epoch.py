"""Scatter: self-steered ladder estimate vs Epoch Capabilities Index.

    python -m experiments.plot_selfsteer_epoch
"""
from __future__ import annotations

import json
import math
from pathlib import Path

EXP = Path(__file__).resolve().parent
ECI_PATH = Path(r"C:\Projects\llm-leaderboard\data\nodes\benchmarks\epoch-ai-eci.json")
SVG_PATH = EXP / "selfsteer_epoch_scatter.svg"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
POINT = "#2a78d6"
FIT = "#eda100"
FONT = 'system-ui, -apple-system, &quot;Segoe UI&quot;, sans-serif'

WIDTH, HEIGHT = 760, 560
LEFT, RIGHT, TOP, BOTTOM = 84, 200, 110, 70
# Outliers worth naming on the plot; everything else stays hover-only.
CALLOUTS = {
    "moonshotai/kimi-k2.6": "kimi-k2.6",
    "moonshotai/kimi-k2-0905": "kimi-k2-0905",
    "openai/gpt-oss-120b": "gpt-oss-120b",
    "anthropic/claude-opus-4.8": "opus-4.8",
    "openai/gpt-5.5": "gpt-5.5",
}


def main() -> None:
    results = json.loads((EXP / "self_steered_results.json").read_text(encoding="utf-8"))
    ladders = results["ladders"]
    rows = {}
    for filename in ("method_battle_data.json", "frontier_test_data.json"):
        for name, record in json.loads((EXP / filename).read_text(encoding="utf-8"))["models"].items():
            rows[name] = record["leaderboard_row"]
    eci = {
        entry["model"]: float(entry["score"])
        for entry in json.loads(ECI_PATH.read_text(encoding="utf-8"))["scores"]["unified"]
    }
    points = [
        (name, eci[rows[name]], ladders[name])
        for name in ladders
        if rows.get(name) in eci
    ]

    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    x_min, x_max = min(xs) - 4, max(xs) + 4
    y_min, y_max = min(ys) - 150, max(ys) + 150
    plot_w = WIDTH - LEFT - RIGHT
    plot_h = HEIGHT - TOP - BOTTOM

    def px(v):
        return LEFT + plot_w * (v - x_min) / (x_max - x_min)

    def py(v):
        return TOP + plot_h * (1.0 - (v - y_min) / (y_max - y_min))

    n = len(points)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = cov / var
    intercept = my - slope * mx

    def pearson(a, b):
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
        den = math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))
        return num / den

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{FONT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>',
        f'<text x="{LEFT}" y="36" fill="{INK}" font-size="18" font-weight="600">'
        "Self-steered interview vs Epoch Capabilities Index</text>",
        f'<text x="{LEFT}" y="58" fill="{INK_SECONDARY}" font-size="13">'
        f"n = {n} models · Spearman ρ = 0.76, Pearson r = {pearson(xs, ys):.2f} · "
        "ladder scale is Terra's own labels, uncalibrated</text>",
        f'<text x="{LEFT}" y="78" fill="{INK_MUTED}" font-size="12">'
        "y: ladder estimate (hardest-passed / easiest-failed midpoint) · x: Epoch ECI score</text>",
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = TOP + plot_h * frac
        value = y_max - (y_max - y_min) * frac
        parts.append(
            f'<line x1="{LEFT}" y1="{gy:.1f}" x2="{LEFT + plot_w}" y2="{gy:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{LEFT - 10}" y="{gy + 4:.1f}" fill="{INK_MUTED}" font-size="11.5" '
            f'text-anchor="end" style="font-variant-numeric: tabular-nums">{value:.0f}</text>'
        )
    parts.append(
        f'<line x1="{LEFT}" y1="{TOP + plot_h}" x2="{LEFT + plot_w}" y2="{TOP + plot_h}" '
        f'stroke="{BASELINE}" stroke-width="1"/>'
    )
    for frac in (0.0, 0.5, 1.0):
        value = x_min + (x_max - x_min) * frac
        parts.append(
            f'<text x="{px(value):.1f}" y="{TOP + plot_h + 22}" fill="{INK_MUTED}" '
            f'font-size="11.5" text-anchor="middle" '
            f'style="font-variant-numeric: tabular-nums">{value:.0f}</text>'
        )
    parts.append(
        f'<line x1="{px(x_min):.1f}" y1="{py(intercept + slope * x_min):.1f}" '
        f'x2="{px(x_max):.1f}" y2="{py(intercept + slope * x_max):.1f}" '
        f'stroke="{FIT}" stroke-width="2" stroke-dasharray="6 5"/>'
    )
    for name, x, y in points:
        parts.append(
            f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="5.5" fill="{POINT}" '
            f'stroke="{SURFACE}" stroke-width="2"><title>{name}: ladder {y:.0f}, '
            f"ECI {x:.1f}</title></circle>"
        )
        label = CALLOUTS.get(name)
        if label:
            parts.append(
                f'<text x="{px(x) + 10:.1f}" y="{py(y) + 4:.1f}" fill="{INK_SECONDARY}" '
                f'font-size="11.5">{label}</text>'
            )
    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {SVG_PATH}")


if __name__ == "__main__":
    main()
