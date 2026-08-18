"""Adversarial chart renderers — perceptually hard, answer still exact.

The existing 'hard' rows are arithmetic over labeled values ("Would X and Y
combined exceed Z?"). A capable VLM solves those trivially once it reads the
labels. Win rate is won where the BASE model fails and the adapted model
succeeds — which means perception difficulty, not arithmetic difficulty.

Mechanics implemented here:

  truncated_axis  y-axis starts well above 0, so bar HEIGHT RATIO badly
                  misrepresents value ratio. A model comparing pixels gets
                  it wrong; a model reading labels gets it right.

  unlabeled       no value annotations at all. Values are snapped exactly
                  onto gridlines so the answer remains unambiguous, but the
                  model must actually read the axis.

  near_tie        top two values differ by ~1-2%. Forces precise reading
                  rather than eyeballing the tallest bar.

  similar_colors  multi-series palette with near-identical hues, so the
                  legend must be consulted rather than pattern-matched.

  many_categories 12-16 categories with rotated tick labels — dense visual
                  scanning.

  crowded_legend  legend placed over the plot area, partially occluding
                  data.

  log_scale       log y-axis: equal pixel distances are unequal values.

  dual_axis       two y-axes at different scales; the question targets one
                  of them specifically.

Every renderer returns a provenance dict so answers stay
correct-by-construction.
"""

from __future__ import annotations
from pathlib import Path
from typing import Sequence
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


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

_BAR_COLOR = "#4C72B0"
_LINE_COLOR = "#DD8452"
_PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]

# Figure geometry — patched by lib.styles.use_style() so a style can change
# aspect ratio and resolution without touchingeach renderer signature.
_SCALE = (1.0, 1.0)   # (width_mult, height_mult)
_DPI = 110


def _fs(w: float, h: float) -> tuple[float, float]:
    """Apply the active style's figure-size multipliers."""
    return (w * _SCALE[0], h * _SCALE[1])


# Deliberately hard to tell apart
_SIMILAR = ["#4C72B0", "#5A7EB8", "#6889C0", "#7694C8", "#84A0D0"]


def _save(fig, out_path: Path) -> None:
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)


# --- truncated axis ---------------------------------------------------------

def render_truncated_bar(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    y_floor: float,
    annotate: bool = True,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Bar chart whose y-axis starts at y_floor instead of 0.

    Visual bar heights are proportional to (value - y_floor), which badly
    misrepresents the true ratio. Labels remain on the bars, so a model that
    reads text is correct and a model that compares pixel heights is not.
    """
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        bars = ax.bar(list(categories), list(values), color=_BAR_COLOR, width=0.65)
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.set_ylim(y_floor, max(values) * 1.02)
        if annotate:
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        value_fmt.format(v), ha="center", va="bottom", fontsize=9)
        _save(fig, out_path)
    return {
        "chart_type": "bar", "mechanic": "truncated_axis",
        "title": title, "y_label": y_label, "y_floor": y_floor,
        "categories": list(categories), "values": list(values),
        "annotated": annotate,
    }


# --- unlabeled (read off gridlines) ----------------------------------------

def render_unlabeled_bar(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    tick_step: float,
) -> dict:
    """Bar chart with NO value labels. Values sit exactly on gridlines.

    Caller must pass values that are exact multiples of tick_step so the
    answer is unambiguous when read off the axis.
    """
    for v in values:
        assert abs(v / tick_step - round(v / tick_step)) < 1e-9, \
            f"value {v} is not a multiple of tick_step {tick_step}"

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        ax.bar(list(categories), list(values), color=_BAR_COLOR, width=0.65)
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.yaxis.set_major_locator(mticker.MultipleLocator(tick_step))
        ax.set_ylim(0, max(values) + tick_step)
        _save(fig, out_path)
    return {
        "chart_type": "bar", "mechanic": "unlabeled",
        "title": title, "y_label": y_label, "tick_step": tick_step,
        "categories": list(categories), "values": list(values),
        "annotated": False,
    }


def render_unlabeled_line(
    x_labels: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    tick_step: float,
) -> dict:
    """Line chart with no point labels; values snapped to gridlines."""
    for v in values:
        assert abs(v / tick_step - round(v / tick_step)) < 1e-9, \
            f"value {v} is not a multiple of tick_step {tick_step}"

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        x = list(range(len(x_labels)))
        ax.plot(x, list(values), color=_LINE_COLOR, marker="o",
                linewidth=2.2, markersize=6)
        ax.set_xticks(x, labels=list(x_labels))
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.yaxis.set_major_locator(mticker.MultipleLocator(tick_step))
        lo, hi = min(values), max(values)
        ax.set_ylim(lo - tick_step, hi + tick_step)
        _save(fig, out_path)
    return {
        "chart_type": "line", "mechanic": "unlabeled",
        "title": title, "y_label": y_label, "tick_step": tick_step,
        "x_labels": list(x_labels), "values": list(values),
        "annotated": False,
    }


# --- near tie ---------------------------------------------------------------

def render_near_tie_bar(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    annotate: bool = True,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Bar chart where the top two values differ by ~1-2%.

    Eyeballing the tallest bar is unreliable; the model must read labels.
    """
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        bars = ax.bar(list(categories), list(values), color=_BAR_COLOR, width=0.65)
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.set_ylim(0, max(values) * 1.15)
        if annotate:
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        value_fmt.format(v), ha="center", va="bottom", fontsize=9)
        _save(fig, out_path)
    return {
        "chart_type": "bar", "mechanic": "near_tie",
        "title": title, "y_label": y_label,
        "categories": list(categories), "values": list(values),
        "annotated": annotate,
    }


# --- similar colors ---------------------------------------------------------

def render_similar_colors_grouped(
    categories: Sequence[str],
    series_values: Sequence[Sequence[float]],
    series_labels: Sequence[str],
    title: str,
    y_label: str,
    out_path: Path,
    value_fmt: str = "${:.0f}",
) -> dict:
    """Grouped bars with near-identical hues — legend must be consulted."""
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
                          color=_SIMILAR[i % len(_SIMILAR)])
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        value_fmt.format(v), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x, labels=list(categories))
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
        ax.grid(axis="y")
        all_vals = [v for s in series_values for v in s]
        ax.set_ylim(0, max(all_vals) * 1.18)
        _save(fig, out_path)
    return {
        "chart_type": "grouped_bar", "mechanic": "similar_colors",
        "title": title, "y_label": y_label,
        "categories": list(categories), "series_labels": list(series_labels),
        "series_values": [list(v) for v in series_values],
        "annotated": True,
    }


# --- many categories --------------------------------------------------------

def render_many_categories_bar(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    value_fmt: str = "${:.0f}",
) -> dict:
    """12-16 categories with rotated labels and small annotation font."""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(11, 5), dpi=_DPI)
        bars = ax.bar(list(categories), list(values), color=_BAR_COLOR, width=0.7)
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        ax.set_ylim(0, max(values) * 1.15)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    value_fmt.format(v), ha="center", va="bottom", fontsize=6.5)
        _save(fig, out_path)
    return {
        "chart_type": "bar", "mechanic": "many_categories",
        "title": title, "y_label": y_label,
        "categories": list(categories), "values": list(values),
        "annotated": True,
    }


# --- crowded legend ---------------------------------------------------------

def render_crowded_legend_line(
    x_labels: Sequence[str],
    series_values: Sequence[Sequence[float]],
    series_labels: Sequence[str],
    title: str,
    y_label: str,
    out_path: Path,
) -> dict:
    """Multi-line chart with the legend sitting over the plot area."""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        x = list(range(len(x_labels)))
        for i, (label, values) in enumerate(zip(series_labels, series_values)):
            ax.plot(x, list(values), label=label,
                    color=_PALETTE[i % len(_PALETTE)],
                    marker="o", linewidth=2, markersize=4)
        ax.set_xticks(x, labels=list(x_labels))
        ax.set_title(title, pad=12)
        ax.set_ylabel(y_label)
        ax.grid(axis="y")
        # legend inside the axes, over the data
        ax.legend(loc="center", fontsize=9, framealpha=0.75, ncol=2)
        _save(fig, out_path)
    return {
        "chart_type": "line", "mechanic": "crowded_legend",
        "title": title, "y_label": y_label,
        "x_labels": list(x_labels), "series_labels": list(series_labels),
        "series_values": [list(v) for v in series_values],
        "annotated": False,
    }


# --- log scale --------------------------------------------------------------

def render_log_scale_bar(
    categories: Sequence[str],
    values: Sequence[float],
    title: str,
    y_label: str,
    out_path: Path,
    value_fmt: str = "{:.0f}",
) -> dict:
    """Log-scale y-axis: equal pixel distances are NOT equal value deltas."""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=_fs(8, 5), dpi=_DPI)
        bars = ax.bar(list(categories), list(values), color=_BAR_COLOR, width=0.65)
        ax.set_yscale("log")
        ax.set_title(title, pad=12)
        ax.set_ylabel(f"{y_label} (log scale)")
        ax.grid(axis="y", which="both")
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    value_fmt.format(v), ha="center", va="bottom", fontsize=9)
        _save(fig, out_path)
    return {
        "chart_type": "bar", "mechanic": "log_scale",
        "title": title, "y_label": y_label,
        "categories": list(categories), "values": list(values),
        "annotated": True,
    }


# --- dual axis --------------------------------------------------------------

def render_dual_axis(
    x_labels: Sequence[str],
    bar_values: Sequence[float],
    line_values: Sequence[float],
    bar_label: str,
    line_label: str,
    title: str,
    out_path: Path,
) -> dict:
    """Bars on the left axis, line on the right axis at a different scale.

    The question must name which series it targets; a model that reads the
    wrong axis produces a plausible-but-wrong number.
    """
    with plt.rc_context(_STYLE):
        fig, ax1 = plt.subplots(figsize=_fs(9, 5), dpi=_DPI)
        x = list(range(len(x_labels)))
        bars = ax1.bar(x, list(bar_values), color=_BAR_COLOR, width=0.6,
                       label=bar_label)
        ax1.set_ylabel(bar_label, color=_BAR_COLOR)
        ax1.tick_params(axis="y", labelcolor=_BAR_COLOR)
        ax1.set_xticks(x, labels=list(x_labels))
        ax1.grid(axis="y", alpha=0.25)
        for bar, v in zip(bars, bar_values):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                     f"{v:.0f}", ha="center", va="bottom", fontsize=8,
                     color=_BAR_COLOR)

        ax2 = ax1.twinx()
        ax2.plot(x, list(line_values), color=_LINE_COLOR, marker="o",
                 linewidth=2.2, markersize=6, label=line_label)
        ax2.set_ylabel(line_label, color=_LINE_COLOR)
        ax2.tick_params(axis="y", labelcolor=_LINE_COLOR)
        ax2.grid(False)
        for xi, v in zip(x, line_values):
            ax2.text(xi, v, f"{v:.1f}", ha="center", va="bottom",
                     fontsize=8, color=_LINE_COLOR)

        ax1.set_title(title, pad=12)
        _save(fig, out_path)
    return {
        "chart_type": "mixed", "mechanic": "dual_axis",
        "title": title,
        "x_labels": list(x_labels),
        "bar_label": bar_label, "bar_values": list(bar_values),
        "line_label": line_label, "line_values": list(line_values),
        "annotated": True,
    }
