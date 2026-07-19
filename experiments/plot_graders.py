"""Render the grader-comparison figure for the pitch (no dependencies).

    python -m experiments.plot_graders
"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent / "grader_swap_results.json"
SVG_PATH = Path(__file__).resolve().parent / "grader_compare.svg"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BAR = "#2a78d6"
SHIPPED = "#008300"
FONT = 'system-ui, -apple-system, &quot;Segoe UI&quot;, sans-serif'

GRADERS = (
    ("mistral-small-2506", "Mistral Small", "$0.60 / M out", False),
    ("mistral-medium-3.5", "Mistral Medium 3.5", "$7.50 / M out", True),
    ("mistral-large-2512", "Mistral Large 3", "$1.50 / M out", False),
)

WIDTH, HEIGHT = 880, 330
LEFT, RIGHT, TOP = 250, 90, 96
ROW_H, BAR_H = 62, 22
MAX_MAE = 120.0


def main() -> None:
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    plot_w = WIDTH - LEFT - RIGHT

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="{FONT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>',
        f'<text x="{LEFT}" y="34" fill="{INK}" font-size="18" font-weight="600">'
        "Any Mistral works as the grader</text>",
        f'<text x="{LEFT}" y="56" fill="{INK_SECONDARY}" font-size="13">'
        "Same 18 transcripts re-read by each grader, per-grader calibration, "
        "leave-one-out MAE — lower is better</text>",
    ]
    for tick in (0, 40, 80, 120):
        x = LEFT + plot_w * tick / MAX_MAE
        parts.append(
            f'<line x1="{x:.1f}" y1="{TOP - 8}" x2="{x:.1f}" '
            f'y2="{TOP + ROW_H * len(GRADERS) - 20}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{TOP + ROW_H * len(GRADERS)}" fill="{INK_MUTED}" '
            f'font-size="11.5" text-anchor="middle" '
            f'style="font-variant-numeric: tabular-nums">{tick}</text>'
        )
    parts.append(
        f'<text x="{LEFT + plot_w / 2}" y="{TOP + ROW_H * len(GRADERS) + 22}" '
        f'fill="{INK_MUTED}" font-size="11.5" text-anchor="middle">'
        "mean absolute Elo error</text>"
    )

    for index, (key, label, price, shipped) in enumerate(GRADERS):
        mae = results[key]["loo_mae"]
        y = TOP + index * ROW_H
        color = SHIPPED if shipped else BAR
        bar_w = plot_w * mae / MAX_MAE
        parts.append(
            f'<text x="{LEFT - 14}" y="{y + BAR_H / 2 + 1}" fill="{INK}" font-size="14" '
            f'text-anchor="end" font-weight="600">{label}</text>'
        )
        parts.append(
            f'<text x="{LEFT - 14}" y="{y + BAR_H / 2 + 17}" fill="{INK_MUTED}" '
            f'font-size="11.5" text-anchor="end">{price}'
            f'{" · shipped" if shipped else ""}</text>'
        )
        parts.append(
            f'<rect x="{LEFT}" y="{y}" width="{bar_w:.1f}" height="{BAR_H}" rx="4" '
            f'fill="{color}"><title>{label}: LOO MAE {mae:.0f} Elo</title></rect>'
        )
        parts.append(
            f'<text x="{LEFT + bar_w + 10:.1f}" y="{y + BAR_H / 2 + 5}" fill="{INK}" '
            f'font-size="14" font-weight="600" '
            f'style="font-variant-numeric: tabular-nums">{mae:.0f}</text>'
        )
    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {SVG_PATH}")


if __name__ == "__main__":
    main()
