"""Build the LinkedIn promo image.

Left  — a mosaic mixing chart types, visual styles and hard mechanics, so
        the panel actually looks like the dataset rather than ten copies
        of the same bar chart.
Right — the eight perceptual mechanics that make a row hard.

Run this locally (not in a container) so the real system fonts resolve —
the style variation is much weaker when matplotlib falls back to DejaVu.

Usage:
    python pipeline/10_promo_image.py
    python pipeline/10_promo_image.py --out promo/custom.png
"""

from __future__ import annotations
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import matplotlib.image as mpimg         # noqa: E402

from lib.styles import use_style, STYLE_NAMES   # noqa: E402
from lib.render import (                        # noqa: E402
    render_bar, render_line, render_grouped_bar,
    render_stacked_bar, render_pie, render_donut,
)
from lib.hard_render import (                   # noqa: E402
    render_truncated_bar, render_unlabeled_bar, render_near_tie_bar,
    render_crowded_legend_line, render_log_scale_bar, render_dual_axis,
    render_many_categories_bar,
)

REPO = Path(__file__).resolve().parents[1]

SEG = ["Consumer", "Enterprise", "SMB", "Gov", "Edu"]
REG = ["NA", "EMEA", "APAC", "LATAM"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
PRD = ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"]
VERT = ["Health", "Retail", "Finance", "Mfg", "Tech", "Energy",
        "Media", "Auto", "Logistics", "Telecom", "Insurance", "Hosp"]


def build_cells(tmp: Path) -> list[Path]:
    """One chart per (style, type) pair — 20 cells, all ten styles twice."""
    jobs = [
        # standard families
        ("bar",      lambda p: render_bar(SEG, [4200, 8600, 3100, 2400, 1800],
                                          "Q4 Revenue by Segment", "Revenue", p)),
        ("line",     lambda p: render_line(MON, [5860, 6415, 6963, 6633, 6705, 7280],
                                           "Monthly Revenue", "Revenue", p)),
        ("pie",      lambda p: render_pie(["Software", "Services", "Hardware", "Subs"],
                                          [38, 27, 21, 14], "Sales Mix", p)),
        ("grouped",  lambda p: render_grouped_bar(
            REG, [[6200, 7100, 4800, 3200], [7000, 6400, 5300, 3900]],
            ["2024", "2025"], "Revenue by Region", "Revenue", p)),
        ("donut",    lambda p: render_donut(["Paid", "Organic", "Email", "Social"],
                                            [41, 29, 18, 12], "Traffic Share", p)),
        ("stacked",  lambda p: render_stacked_bar(
            REG, [[2800, 3300, 2100, 1600], [1200, 2900, 1700, 1100],
                  [900, 2300, 1400, 800]],
            ["Software", "Services", "Hardware"],
            "Regional Revenue by Product", "Revenue", p)),
        # hard mechanics
        ("truncated", lambda p: render_truncated_bar(
            SEG, [12400, 12300, 12600, 12200, 12500],
            "Revenue by Segment", "Revenue", p, y_floor=12100)),
        ("unlabeled", lambda p: render_unlabeled_bar(
            ["Health", "Retail", "Finance", "Mfg", "Tech"],
            [4000, 7000, 3000, 6000, 2000],
            "Revenue by Vertical", "Revenue", p, tick_step=1000)),
        ("near_tie",  lambda p: render_near_tie_bar(
            PRD, [8200, 8150, 5400, 3900, 2600],
            "Units Sold by Product", "Units", p, value_fmt="{:.0f}")),
        ("crowded",   lambda p: render_crowded_legend_line(
            MON, [[4200, 4600, 5100, 4900, 5400, 5800],
                  [3100, 3400, 3200, 3900, 4100, 4400],
                  [2200, 2600, 2900, 2700, 3100, 3300],
                  [1400, 1600, 1900, 2100, 2000, 2400]],
            SEG[:4], "Revenue Trend by Segment", "Revenue", p)),
        ("log",       lambda p: render_log_scale_bar(
            PRD, [45, 380, 2400, 47000, 610],
            "Units Sold by Product", "Units", p)),
        ("dual",      lambda p: render_dual_axis(
            ["Q1", "Q2", "Q3", "Q4"], [6200, 7400, 6900, 8100],
            [3.2, 5.7, 4.1, 8.3], "Revenue", "Conversion Rate (%)",
            "Revenue and Conversion", p)),
        ("many",      lambda p: render_many_categories_bar(
            VERT, [9200, 7400, 12100, 5600, 10800, 4300,
                   8900, 6700, 3900, 11200, 5100, 7800],
            "Annual Revenue by Vertical", "Revenue", p)),
    ]

    paths: list[Path] = []
    n_cells = 20
    for i in range(n_cells):
        style = STYLE_NAMES[i % len(STYLE_NAMES)]
        name, fn = jobs[i % len(jobs)]
        out = tmp / f"cell_{i:02d}_{style}_{name}.png"
        with use_style(style):
            fn(out)
        paths.append(out)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="promo/prism_linkedin.png")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cells = build_cells(tmp)

        fig = plt.figure(figsize=(17, 9.2), dpi=140)
        # Reserve bands: title strip on top, caption strip at the bottom.
        gs = fig.add_gridspec(
            1, 2, width_ratios=[1.5, 1], wspace=0.06,
            left=0.035, right=0.975, top=0.865, bottom=0.085,
        )

        TITLE_Y = 0.945

        # ---- left: 4x5 mosaic -------------------------------------------
        left = gs[0].subgridspec(4, 5, hspace=0.06, wspace=0.04)
        for i, p in enumerate(cells):
            ax = fig.add_subplot(left[i // 5, i % 5])
            ax.imshow(mpimg.imread(p))
            ax.axis("off")

        fig.text(0.035, TITLE_Y, "One dataset, ten visual dialects",
                 ha="left", va="center", fontsize=21, fontweight="bold")
        fig.text(0.035, 0.038,
                 "3,803 rows   ·   7 chart families   ·   "
                 "21% perceptually hard   ·   5 languages",
                 ha="left", va="center", fontsize=13, color="#555")

        # ---- right: the eight mechanics ---------------------------------
        ax = fig.add_subplot(gs[1])
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        x0 = fig.subplotpars.left + (fig.subplotpars.right
                                     - fig.subplotpars.left) * 0.615
        fig.text(x0, TITLE_Y, "Hard to see, not hard to compute",
                 ha="left", va="center", fontsize=21, fontweight="bold")

        items = [
            ("truncated axes",   "bar heights misrepresent the ratios"),
            ("no value labels",  "numbers sit exactly on gridlines"),
            ("near ties",        "top two within 1–2%"),
            ("similar colours",  "the legend has to be read"),
            ("occluded legends", "drawn over the data"),
            ("log scales",       "equal pixels, unequal values"),
            ("dual axes",        "read the wrong one, get a plausible answer"),
            ("12–16 categories", "rotated labels, dense scanning"),
        ]

        # Even vertical distribution across the axes, with headroom top
        # and bottom so nothing can collide with the caption strip.
        top, bottom = 0.965, 0.085
        step = (top - bottom) / len(items)
        for i, (name, why) in enumerate(items):
            y = top - i * step
            ax.text(0.015, y, "\u25CF", fontsize=9, color="#C7112D",
                    va="top", ha="left")
            ax.text(0.065, y + 0.004, name, fontsize=15,
                    fontweight="bold", va="top", ha="left")
            ax.text(0.065, y - 0.048, why, fontsize=12.5, color="#555",
                    va="top", ha="left")

        fig.text(x0, 0.038,
                 "Every answer is computed from seeded values before the "
                 "image is drawn.",
                 ha="left", va="center", fontsize=13, color="#555")

        out = REPO / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=140, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
