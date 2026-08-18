"""Minimal chart renderers for the gold synthetic core.

One function per chart_type in the target schema. Answers to QA rows are
computed from the underlying values before the figure is drawn, so they are
correct-by-construction.
"""

from __future__ import annotations
from pathlib import Path
from typing import Sequence
import matplotlib.pyplot as plt


# Modest, consistent styling. Not designer-y; readable and neutral.
_STYLE = {
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.35,
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 9,
}

# Distinct colors per chart type + palette for multi-series charts.
_BAR_COLOR = "#4C72B0"   # muted blue
_LINE_COLOR = "#DD8452"  # muted orange
_PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]

# Figure geometry — patched by lib.styles.use_style() so a style can change
# aspect ratio and resolution without touchingeach renderer signature.
_SCALE = (1.0, 1.0)   # (width_mult, height_mult)
_DPI = 110


def _fs(w: float, h: float) -> tuple[float, float]:
    """Apply the active style's figure-size multipliers."""
    return (w * _SCALE[0], h * _SCALE[1])




def render_bar(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    annotate: bool = True,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Single-series vertical bar."""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        bars = ax.bar(list(categories), list(values), color=_BAR_COLOR, width=0.65)
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(values) * 1.15)
        if annotate:
            for bar, v in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    value_fmt.format(v),
                    ha="center", va="bottom", fontsize=9,
                )
        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=_DPI, bbox_inches="tight")
        plt.close(fig)

    return {
        "chart_type": "bar",
        "title": title,
        "y_label": y_label,
        "categories": list(categories),
        "values": list(values),
        "annotated": annotate,
        "value_fmt": value_fmt,
    }


def render_line(
    x_labels: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    annotate: bool = True,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Single-series line chart with markers."""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        x = list(range(len(x_labels)))
        ax.plot(x, list(values), color=_LINE_COLOR, marker="o",
                linewidth=2.2, markersize=6)
        ax.set_xticks(x, labels=list(x_labels))
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.set_axisbelow(True)

        ymin, ymax = min(values), max(values)
        span = (ymax - ymin) if ymax > ymin else max(ymax, 1) * 0.1
        pad = span * 0.15
        ax.set_ylim(ymin - pad, ymax + pad * 1.8)

        if annotate:
            for xi, v in zip(x, values):
                ax.text(xi, v + pad * 0.4, value_fmt.format(v),
                        ha="center", va="bottom", fontsize=8.5)

        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=_DPI, bbox_inches="tight")
        plt.close(fig)

    return {
        "chart_type": "line",
        "title": title,
        "y_label": y_label,
        "x_labels": list(x_labels),
        "values": list(values),
        "annotated": annotate,
        "value_fmt": value_fmt,
    }


def render_grouped_bar(
    categories: Sequence[str],
    series_values: Sequence[Sequence[float]],
    series_labels: Sequence[str],
    title: str,
    y_label: str,
    out_path: Path,
    annotate: bool = True,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Grouped (side-by-side) bar chart across multiple series."""
    n_series = len(series_labels)
    n_cats = len(categories)
    bar_width = 0.8 / n_series
    x = list(range(n_cats))

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(9, 5), dpi=_DPI)
        for i, (label, values) in enumerate(zip(series_labels, series_values)):
            offset = (i - (n_series - 1) / 2) * bar_width
            positions = [xi + offset for xi in x]
            bars = ax.bar(positions, list(values), bar_width, label=label,
                          color=_PALETTE[i % len(_PALETTE)])
            if annotate:
                for bar, v in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height(), value_fmt.format(v),
                            ha="center", va="bottom", fontsize=7.5)
        ax.set_xticks(x, labels=list(categories))
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
        ax.grid(axis="y")
        ax.set_axisbelow(True)

        all_vals = [v for series in series_values for v in series]
        ax.set_ylim(0, max(all_vals) * 1.18)

        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=_DPI, bbox_inches="tight")
        plt.close(fig)

    return {
        "chart_type": "grouped_bar",
        "title": title,
        "y_label": y_label,
        "categories": list(categories),
        "series_labels": list(series_labels),
        "series_values": [list(v) for v in series_values],
        "annotated": annotate,
        "value_fmt": value_fmt,
    }


def _render_pie_like(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    out_path: Path,
    annotate: bool,
    hole: float,
    chart_type: str,
) -> dict:
    """Shared implementation for pie (hole=0) and donut (hole>0)."""
    total = sum(values)
    percents = [v / total * 100 for v in values]

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(7.5, 6), dpi=_DPI)

        wedgeprops = {"edgecolor": "white", "linewidth": 1.5}
        if hole > 0:
            wedgeprops["width"] = 1.0 - hole

        wedges, texts, autotexts = ax.pie(
            list(values),
            labels=list(categories) if annotate else None,
            autopct=((lambda p: f"{p:.1f}%" if p >= 3 else "") if annotate else None),
            colors=_PALETTE[: len(values)],
            startangle=90,
            counterclock=False,
            wedgeprops=wedgeprops,
            pctdistance=0.72 if hole == 0 else 0.78,
            textprops={"fontsize": 10},
        )
        for t in autotexts:
            t.set_fontsize(9)
            t.set_color("white")
            t.set_fontweight("bold")

        ax.set_title(title, pad=12)
        ax.axis("equal")

        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=_DPI, bbox_inches="tight")
        plt.close(fig)

    return {
        "chart_type": chart_type,
        "title": title,
        "categories": list(categories),
        "values": list(values),
        "percents": [round(p, 4) for p in percents],
        "annotated": annotate,
    }


def render_pie(categories, values, title, out_path, annotate=True):
    return _render_pie_like(
        categories, values, title, out_path,
        annotate=annotate, hole=0.0, chart_type="pie",
    )


def render_donut(categories, values, title, out_path, annotate=True):
    return _render_pie_like(
        categories, values, title, out_path,
        annotate=annotate, hole=0.45, chart_type="donut",
    )


def render_stacked_bar(
    categories: Sequence[str],
    series_values: Sequence[Sequence[float]],
    series_labels: Sequence[str],
    title: str,
    y_label: str,
    out_path: Path,
    annotate: bool = True,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Stacked bar chart. Annotates segments above 8% of max total."""
    n_cats = len(categories)
    totals = [sum(sv[i] for sv in series_values) for i in range(n_cats)]
    max_total = max(totals) if totals else 1

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5.5), dpi=_DPI)
        bottoms = [0.0] * n_cats
        for i, (label, values) in enumerate(zip(series_labels, series_values)):
            bars = ax.bar(list(categories), list(values), bottom=bottoms,
                          label=label, color=_PALETTE[i % len(_PALETTE)],
                          width=0.65)
            if annotate:
                for bar, v, b in zip(bars, values, bottoms):
                    if v > max_total * 0.08:
                        ax.text(bar.get_x() + bar.get_width() / 2,
                                b + v / 2, value_fmt.format(v),
                                ha="center", va="center",
                                fontsize=8.5, color="white",
                                fontweight="bold")
            bottoms = [b + v for b, v in zip(bottoms, values)]

        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.set_ylim(0, max_total * 1.15)

        fig.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=_DPI, bbox_inches="tight")
        plt.close(fig)

    return {
        "chart_type": "stacked_bar",
        "title": title,
        "y_label": y_label,
        "categories": list(categories),
        "series_labels": list(series_labels),
        "series_values": [list(v) for v in series_values],
        "annotated": annotate,
        "value_fmt": value_fmt,
    }
