"""Render trajectory_results.json as an SVG line chart (no dependencies).

    python -m experiments.plot_trajectory
"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent / "trajectory_results.json"
SVG_PATH = Path(__file__).resolve().parent / "trajectory_mae.svg"

# Reference dataviz palette, light mode.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = {
    "refit": ("#2a78d6", "Refit ordinal (factorized, items fit LOO)"),
    "holistic": ("#1baf7a", "Holistic raw read"),
    "legacy": ("#eda100", "Legacy ordinal (hand-set difficulties)"),
    "holistic_cal": ("#008300", "Calibrated holistic (shipped)"),
}
FONT = 'system-ui, -apple-system, &quot;Segoe UI&quot;, sans-serif'

WIDTH, HEIGHT = 880, 540
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 64, 250, 92, 56


def nice_ceiling(value: float) -> float:
    step = 50.0
    return step * (int(value / step) + 1)


def main() -> None:
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    curves = results["mae_curves"]
    n_models = len(results["models"])
    truths = [m["true"] for m in results["models"].values()]
    steps = len(curves["refit"])

    top = nice_ceiling(max(max(values) for values in curves.values()))
    plot_w = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_h = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

    def x(question_index: int) -> float:
        return MARGIN_LEFT + plot_w * question_index / (steps - 1)

    def y(error: float) -> float:
        return MARGIN_TOP + plot_h * (1.0 - error / top)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="{FONT}">'
    )
    parts.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>')
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="34" fill="{INK}" font-size="18" font-weight="600">'
        "Mean absolute Elo error after each question</text>"
    )
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="56" fill="{INK_SECONDARY}" font-size="13">'
        f"{n_models} live models, public Elo {min(truths):.0f}–{max(truths):.0f} · "
        "leave-one-out item fits · grader mistral-medium-3.5</text>"
    )

    tick_step = 100.0 if top > 300 else 50.0
    value = 0.0
    while value <= top + 0.1:
        py = y(value)
        if value > 0:
            parts.append(
                f'<line x1="{MARGIN_LEFT}" y1="{py:.1f}" x2="{MARGIN_LEFT + plot_w}" '
                f'y2="{py:.1f}" stroke="{GRID}" stroke-width="1"/>'
            )
        parts.append(
            f'<text x="{MARGIN_LEFT - 10}" y="{py + 4:.1f}" fill="{INK_MUTED}" font-size="12" '
            f'text-anchor="end" style="font-variant-numeric: tabular-nums">{value:.0f}</text>'
        )
        value += tick_step
    parts.append(
        f'<line x1="{MARGIN_LEFT}" y1="{y(0):.1f}" x2="{MARGIN_LEFT + plot_w}" y2="{y(0):.1f}" '
        f'stroke="{BASELINE}" stroke-width="1"/>'
    )
    for index in range(steps):
        parts.append(
            f'<text x="{x(index):.1f}" y="{HEIGHT - 28}" fill="{INK_MUTED}" font-size="12" '
            f'text-anchor="middle">after Q{index + 1}</text>'
        )

    label_slots: list[tuple[float, str]] = []
    for key, (color, label) in SERIES.items():
        values = curves[key]
        dash = ' stroke-dasharray="7 5"' if key == "legacy" else ""
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
        )
        for i, v in enumerate(values):
            parts.append(
                f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="{color}" '
                f'stroke="{SURFACE}" stroke-width="2"><title>{label} — after Q{i + 1}: '
                f"{v:.0f} Elo</title></circle>"
            )
        label_slots.append((y(values[-1]), key))

    # Direct end labels, nudged apart if collided (sub-3:1 slots need them).
    label_slots.sort()
    positions = []
    for base_y, key in label_slots:
        py = base_y
        if positions and py - positions[-1] < 18:
            py = positions[-1] + 18
        positions.append(py)
        color, label = SERIES[key]
        final = curves[key][-1]
        lx = MARGIN_LEFT + plot_w + 14
        parts.append(f'<circle cx="{lx}" cy="{py - 4:.1f}" r="4" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 10}" y="{py:.1f}" fill="{INK}" font-size="12.5">'
            f'{label.split(" (")[0]} '
            f'<tspan fill="{INK_SECONDARY}" style="font-variant-numeric: tabular-nums">'
            f"{final:.0f}</tspan></text>"
        )
        detail = label[label.find("(") :] if "(" in label else ""
        if detail:
            parts.append(
                f'<text x="{lx + 10}" y="{py + 14:.1f}" fill="{INK_MUTED}" font-size="10.5">'
                f"{detail}</text>"
            )
        positions[-1] = py + (16 if detail else 0)

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {SVG_PATH}")


if __name__ == "__main__":
    main()
