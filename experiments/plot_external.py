"""Render external-correlation scatters as SVG (no dependencies).

    python -m experiments.plot_external
"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent / "external_correlation.json"
SVG_PATH = Path(__file__).resolve().parent / "external_scatter.svg"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
POINT = "#2a78d6"
FIT = "#eda100"
FONT = 'system-ui, -apple-system, &quot;Segoe UI&quot;, sans-serif'

WIDTH, HEIGHT = 900, 505
PANEL_W, PANEL_H = 360, 300
PANEL_TOP = 110
PANELS_X = (70, 510)


def nice_range(values: list[float]) -> tuple[float, float]:
    low, high = min(values), max(values)
    pad = (high - low) * 0.12 or 1.0
    return low - pad, high + pad


def panel(
    x0: float,
    results: dict,
    title: str,
    x_label: str,
) -> list[str]:
    pairs = results["pairs"]
    xs = [p["external"] for p in pairs]
    ys = [p["viberank"] for p in pairs]
    x_min, x_max = nice_range(xs)
    y_min, y_max = nice_range(ys)

    def px(value: float) -> float:
        return x0 + PANEL_W * (value - x_min) / (x_max - x_min)

    def py(value: float) -> float:
        return PANEL_TOP + PANEL_H * (1.0 - (value - y_min) / (y_max - y_min))

    parts = []
    parts.append(
        f'<text x="{x0}" y="{PANEL_TOP - 26}" fill="{INK}" font-size="14.5" font-weight="600">{title}</text>'
    )
    parts.append(
        f'<text x="{x0}" y="{PANEL_TOP - 8}" fill="{INK_SECONDARY}" font-size="12">'
        f'n = {results["n"]} · Spearman ρ = {results["viberank_spearman"]:.2f} '
        f'(ground-truth ceiling {results["ground_truth_spearman"]:.2f})</text>'
    )
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = PANEL_TOP + PANEL_H * frac
        parts.append(
            f'<line x1="{x0}" y1="{gy:.1f}" x2="{x0 + PANEL_W}" y2="{gy:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        value = y_max - (y_max - y_min) * frac
        parts.append(
            f'<text x="{x0 - 8}" y="{gy + 4:.1f}" fill="{INK_MUTED}" font-size="11" '
            f'text-anchor="end" style="font-variant-numeric: tabular-nums">{value:.0f}</text>'
        )
    parts.append(
        f'<line x1="{x0}" y1="{PANEL_TOP + PANEL_H}" x2="{x0 + PANEL_W}" '
        f'y2="{PANEL_TOP + PANEL_H}" stroke="{BASELINE}" stroke-width="1"/>'
    )
    for frac in (0.0, 0.5, 1.0):
        value = x_min + (x_max - x_min) * frac
        parts.append(
            f'<text x="{px(value):.1f}" y="{PANEL_TOP + PANEL_H + 20}" fill="{INK_MUTED}" '
            f'font-size="11" text-anchor="middle" '
            f'style="font-variant-numeric: tabular-nums">{value:.0f}</text>'
        )
    parts.append(
        f'<text x="{x0 + PANEL_W / 2}" y="{PANEL_TOP + PANEL_H + 40}" fill="{INK_MUTED}" '
        f'font-size="11.5" text-anchor="middle">{x_label}</text>'
    )

    n = len(xs)
    x_mean, y_mean = sum(xs) / n, sum(ys) / n
    var = sum((v - x_mean) ** 2 for v in xs)
    cov = sum((a - x_mean) * (b - y_mean) for a, b in zip(xs, ys))
    if var > 0:
        slope = cov / var
        intercept = y_mean - slope * x_mean
        y1, y2 = intercept + slope * x_min, intercept + slope * x_max
        parts.append(
            f'<line x1="{px(x_min):.1f}" y1="{py(y1):.1f}" x2="{px(x_max):.1f}" '
            f'y2="{py(y2):.1f}" stroke="{FIT}" stroke-width="2" stroke-dasharray="6 5"/>'
        )
    for p in pairs:
        parts.append(
            f'<circle cx="{px(p["external"]):.1f}" cy="{py(p["viberank"]):.1f}" r="5" '
            f'fill="{POINT}" stroke="{SURFACE}" stroke-width="2">'
            f'<title>{p["leaderboard_row"]}: VibeRank {p["viberank"]:.0f}, '
            f'external {p["external"]:.1f}</title></circle>'
        )
    return parts


def main() -> None:
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="{FONT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>',
        f'<text x="{PANELS_X[0]}" y="34" fill="{INK}" font-size="18" font-weight="600">'
        "A $0.04 vibe check against full benchmark indices</text>",
        f'<text x="{PANELS_X[0]}" y="56" fill="{INK_SECONDARY}" font-size="13">'
        "VibeRank estimate (5 answers, calibrated holistic read, leave-one-out) "
        "vs external capability indices</text>",
    ]
    parts += panel(
        PANELS_X[0], results["epoch_eci"], "Epoch Capabilities Index", "Epoch ECI score"
    )
    parts += panel(
        PANELS_X[1],
        results["aa_index"],
        "Artificial Analysis Intelligence Index",
        "AA Intelligence Index (v4)",
    )
    parts.append(
        f'<text x="{PANELS_X[0]}" y="{HEIGHT - 12}" fill="{INK_MUTED}" font-size="11">'
        "y-axis: VibeRank Elo estimate · dashed line: least-squares fit · "
        "hover points for model names</text>"
    )
    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {SVG_PATH}")


if __name__ == "__main__":
    main()
