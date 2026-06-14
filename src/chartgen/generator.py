"""generator.py — first-pass synthetic figure generator.

Covers Part 2 charts (bar, grouped_bar, stacked_bar, line) and Part 1 marketing
dashboards (KPI card + channel comparison). The table is generated FIRST; QA is
derived from it, so answers are always exact. Deterministic reasoning traces are
attached to every QA target (the moat — never produced by re-reading the image).

Notable fixes vs the skeleton:
  * KPI-vs-sum question is only emitted when the gap is LEGIBLE (>= a visible
    threshold) or is otherwise labelled 'unanswerable' — no impossible rows.
  * stacked/grouped bars added (the documented frontier-weak chart types).
  * nuisance/realism knobs (rotation, grid, abbrev, palette, similar colors).
  * CSV tables are actually written.
"""

from __future__ import annotations

import os
import csv
import random
from typing import List, Dict, Any, Tuple, Optional

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from .schema import (
    make_id,
    SourceInfo,
    DataTable,
    SeriesData,
    FigureData,
    RenderInfo,
    StyleInfo,
    NuisanceInfo,
    Artifacts,
    DashboardPanel,
    FigureExample,
    make_table_extraction_task,
    make_qa_task,
    KPIItem,
    PanelTable,
    SCHEMA_VERSION,
)

# -------------------------
# Vocab / constants
# -------------------------

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]
CHANNELS = ["Email", "Paid Search", "Organic", "Social", "Affiliate", "Display"]
SEGMENTS = ["Enterprise", "SMB", "Consumer", "Gov", "Education"]
PRODUCTS = ["Basic", "Pro", "Team", "Enterprise"]

MARKETING_METRICS = [
    ("CTR", "percent"),
    ("Conversion Rate", "percent"),
    ("CPC", "currency"),
    ("CPA", "currency"),
    ("CPM", "currency"),
    ("CPL", "currency"),
    ("CAC", "currency"),
    ("ROAS", "ratio"),
    ("ROMI", "percent"),
    ("Conversions", "count"),
    ("Spend", "currency"),
    ("Revenue", "currency"),
    ("Pipeline Value", "currency"),
]

# Marketing funnel: ordered stages, monotonically decreasing counts.
FUNNEL_STAGES = ["Impressions", "Clicks", "Leads", "MQLs", "SQLs", "Opportunities", "Closed-Won"]

PALETTES = ["tab10", "Set2", "Dark2", "Paired", "viridis"]
SIMILAR_PALETTES = ["Blues", "Greens", "Purples"]  # low-contrast on purpose

# Qualitative palettes ONLY — guaranteed categorically distinct. Charts that
# carry a legend (grouped, stacked, funnel) MUST use these, never a continuous
# map (viridis/Blues), where adjacent series collapse to near-identical shades.
DISTINCT_PALETTES = ["tab10", "Set1", "Set2", "Dark2"]
# A hand-ordered high-contrast sequence, used when we need guaranteed maximal
# separation between the FIRST few series (the common 2-4 series case).
DISTINCT_SEQUENCE = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#17becf",  # cyan
]

# Named-color mode: only charts rendered with THESE exact colors get
# color-referenced QA ("the red bar"). Naming colors out of arbitrary palettes
# is unreliable, and a mislabeled color is a poisoned row.
NAMED_COLORS = {
    "red": "#d62728",
    "blue": "#1f77b4",
    "green": "#2ca02c",
    "orange": "#ff7f0e",
    "purple": "#9467bd",
    "brown": "#8c564b",
    "pink": "#e377c2",
    "gray": "#7f7f7f",
}
NAMED_COLOR_PROB = 0.5  # fraction of bar/stacked charts using named colors

CAMPAIGNS = ["Spring Sale", "Brand Launch", "Holiday Push", "Retargeting", "Lead Gen", "Black Friday"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# -------------------------
# TEMPLATE FAMILIES
# Title, metric, and category pool are bound TOGETHER so charts are semantically
# coherent (no more 'Revenue by Segment' plotting CPA). Each entry:
#   (title, metric_name, category_pool)
# metric units come from METRIC_UNITS below.
# -------------------------

METRIC_UNITS = dict(MARKETING_METRICS)  # name -> unit

BAR_TEMPLATES = [
    ("Conversions by Channel", "Conversions", CHANNELS),
    ("Spend by Campaign", "Spend", CAMPAIGNS),
    ("CTR by Channel", "CTR", CHANNELS),
    ("Revenue by Segment", "Revenue", SEGMENTS),
    ("ROAS by Channel", "ROAS", CHANNELS),
    ("CPA by Campaign", "CPA", CAMPAIGNS),
    ("CPC by Channel", "CPC", CHANNELS),
    ("Conversion Rate by Segment", "Conversion Rate", SEGMENTS),
]

GROUPED_TEMPLATES = [
    ("Spend by Channel per Quarter", "Spend", CHANNELS, QUARTERS),
    ("Conversions by Channel per Quarter", "Conversions", CHANNELS, QUARTERS),
    ("Revenue by Segment per Quarter", "Revenue", SEGMENTS, QUARTERS),
    ("CTR by Channel per Quarter", "CTR", CHANNELS, QUARTERS),
]

STACKED_TEMPLATES = [
    ("Revenue Composition by Channel", "Revenue", CHANNELS),
    ("Spend Breakdown by Channel", "Spend", CHANNELS),
    ("Conversions by Source over Time", "Conversions", CHANNELS),
]

LINE_TEMPLATES = [
    ("CTR Trend by Month", "CTR"),
    ("Monthly Revenue Trend", "Revenue"),
    ("ROAS Trend", "ROAS"),
    ("Monthly Spend", "Spend"),
    ("Conversion Rate Over Time", "Conversion Rate"),
    ("CPA Trend by Month", "CPA"),
]


# -------------------------
# Utilities
# -------------------------

def ensure_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def fmt_value(val: float, unit: str, decimals: int = 1, currency: str = "$") -> str:
    if unit == "percent":
        return f"{round(val, decimals)}%"
    if unit == "currency":
        return f"{currency}{round(val, 2)}"
    if unit == "ratio":
        return f"{round(val, 2)}"
    if unit == "count":
        return str(int(round(val)))
    return str(round(val, decimals))


def metric_range(name: str) -> Tuple[float, float]:
    return {
        "CTR": (0.5, 8.0),
        "Conversion Rate": (0.5, 20.0),
        "CPC": (0.2, 15.0),
        "CPA": (5.0, 120.0),
        "CPM": (2.0, 40.0),
        "CPL": (8.0, 200.0),
        "CAC": (30.0, 600.0),
        "ROAS": (0.5, 8.0),
        "ROMI": (-20.0, 350.0),
        "Conversions": (50, 2000),
        "Spend": (100, 20000),
        "Revenue": (500, 80000),
        "Pipeline Value": (10000, 500000),
    }.get(name, (1.0, 100.0))


def decimals_for(unit: str) -> int:
    return {"percent": 1, "ratio": 2, "currency": 2, "count": 0}.get(unit, 1)


def rand_vals(n: int, low: float, high: float, decimals: int = 1) -> List[float]:
    if decimals == 0:
        return [float(random.randint(int(low), int(high))) for _ in range(n)]
    return [round(random.uniform(low, high), decimals) for _ in range(n)]


def argmax_idx(v: List[float]) -> int:
    return max(range(len(v)), key=lambda i: v[i])


def argmin_idx(v: List[float]) -> int:
    return min(range(len(v)), key=lambda i: v[i])


def sample_style(difficulty: str) -> Tuple[StyleInfo, NuisanceInfo]:
    """Harder difficulty => more nuisance factors (realism stress)."""
    style = StyleInfo(
        font_scale=random.choice(["small", "medium", "large"]),
        rotation_x=random.choice([0, 0, 20, 45]),
        show_grid=random.random() > 0.3,
        show_values=random.random() > 0.6,
        abbrev_numbers=random.random() > 0.6,
        decimal_places=random.choice([0, 1, 2]),
        palette=random.choice(PALETTES),
        legend_loc=random.choice(["best", "upper right", "upper left"]),
    )
    nuis = NuisanceInfo()
    if difficulty in ("medium", "hard"):
        nuis.crowded_legend = random.random() > 0.6
        nuis.similar_colors = random.random() > 0.7
    if difficulty == "hard":
        nuis.low_res = random.random() > 0.6
        nuis.jpeg_artifact = random.random() > 0.6
        nuis.partial_overlap = random.random() > 0.7
        if nuis.similar_colors:
            style.palette = random.choice(SIMILAR_PALETTES)
    return style, nuis


def distinct_series_colors(n: int) -> list:
    """n guaranteed-distinct colors for legend-bearing charts (grouped/stacked/
    funnel). Uses a hand-ordered high-contrast sequence for the first 8 series,
    then falls back to a qualitative colormap. NEVER returns near-identical
    shades, and is immune to the similar_colors nuisance (which only belongs on
    single-series bars where there is no legend to confuse).
    """
    if n <= len(DISTINCT_SEQUENCE):
        return DISTINCT_SEQUENCE[:n]
    cmap = plt.get_cmap("tab10")
    base = list(getattr(cmap, "colors", []))
    return [base[i % len(base)] for i in range(n)]


def write_csv(path: str, table: DataTable) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(table.columns)
        w.writerows(table.rows)


def series_colors(palette: str, n: int, similar: bool = False) -> list:
    """Return n visually distinct (or deliberately similar) colors.

    Fixes the classic bug: integer-indexing a CONTINUOUS colormap (Blues, viridis)
    returns the first few of 256 entries -> near-white / near-identical bars.
    Qualitative ListedColormaps (tab10, Set2) are indexed directly; continuous maps
    are sampled across a mid-range band so nothing is invisible.
    """
    try:
        cmap = plt.get_cmap(palette)
    except Exception:
        cmap = plt.get_cmap("tab10")
    colors = getattr(cmap, "colors", None)
    if colors is not None:  # qualitative map: index discrete entries
        return [colors[i % len(colors)] for i in range(n)]
    # continuous map: sample floats in a readable band
    lo, hi = (0.45, 0.62) if similar else (0.30, 0.85)
    if n == 1:
        return [cmap(0.6)]
    return [cmap(lo + (hi - lo) * i / (n - 1)) for i in range(n)]


# NOTE: similar_colors is a legitimate difficulty nuisance for SINGLE-series bar
# charts (one fill, no legend) but must never apply to multi-series legend charts
# below — grouped/stacked/funnel call distinct_series_colors() instead.


def _dpi_for(nuis: NuisanceInfo) -> int:
    return 70 if nuis.low_res else 150


def _save(fig, image_path: str, nuis: NuisanceInfo) -> None:
    ensure_dir(os.path.dirname(image_path))
    fig.savefig(image_path, dpi=_dpi_for(nuis))
    plt.close(fig)


# =========================================================
# SINGLE-SERIES BAR  (Part 2)
# =========================================================

def _spec_bar() -> Dict[str, Any]:
    title, name, pool = random.choice(BAR_TEMPLATES)
    unit = METRIC_UNITS[name]
    n = random.randint(3, min(6, len(pool)))
    cats = random.sample(pool, n)
    low, high = metric_range(name)
    dec = decimals_for(unit)
    vals = rand_vals(n, low, high, dec)
    # named-color mode: assign distinct named colors to bars -> enables
    # color-referenced QA with guaranteed-correct ground truth.
    color_names = None
    if random.random() < NAMED_COLOR_PROB:
        color_names = random.sample(list(NAMED_COLORS.keys()), n)
    return {
        "metric": name, "unit": unit, "dec": dec, "cats": cats, "vals": vals,
        "color_names": color_names,
        "columns": ["Category", name],
        "rows": [[cats[i], vals[i]] for i in range(n)],
        "units": {"Category": "label", name: unit},
        "title": title,
    }


def _qa_bar(spec) -> List:
    name, unit, dec = spec["metric"], spec["unit"], spec["dec"]
    cats, vals = spec["cats"], spec["vals"]
    tasks = []

    i = random.randrange(len(cats))
    tasks.append(make_qa_task(
        "retrieve_value",
        f"What is the {name} for {cats[i]}?",
        fmt_value(vals[i], unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[cats[i]], column_keys=[name],
        reasoning=f"Read the bar for {cats[i]}; its height is {fmt_value(vals[i], unit, dec)}.",
    ))

    mx = argmax_idx(vals)
    tasks.append(make_qa_task(
        "find_extremum",
        f"Which category has the highest {name}?",
        cats[mx], "label",
        row_keys=cats, column_keys=[name],
        reasoning=f"Compare all bars; {cats[mx]} is tallest at {fmt_value(vals[mx], unit, dec)}.",
    ))

    a, b = random.sample(range(len(cats)), 2)
    diff = abs(vals[a] - vals[b])
    hi, lo = (cats[a], cats[b]) if vals[a] >= vals[b] else (cats[b], cats[a])
    tasks.append(make_qa_task(
        "compute_difference",
        f"What is the difference in {name} between {cats[a]} and {cats[b]}?",
        fmt_value(diff, unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[cats[a], cats[b]], column_keys=[name],
        aliases=[str(round(diff, 2)), str(round(diff, 1))],
        reasoning=f"{hi}={fmt_value(max(vals[a],vals[b]),unit,dec)}, {lo}={fmt_value(min(vals[a],vals[b]),unit,dec)}; difference {fmt_value(diff,unit,dec)}.",
    ))

    # share-of-total (only when unit is additive)
    if unit in ("count", "currency"):
        total = sum(vals)
        j = random.randrange(len(cats))
        pct = round(100.0 * vals[j] / total, 1) if total else 0.0
        tasks.append(make_qa_task(
            "compute_ratio_percent",
            f"What percent of total {name} came from {cats[j]}?",
            f"{pct}%", "numeric_with_unit",
            row_keys=[cats[j]], column_keys=[name],
            aliases=[str(pct)],
            reasoning=f"{cats[j]}={fmt_value(vals[j],unit,dec)} of total {fmt_value(total,unit,dec)}; {vals[j]}/{total}={pct}%.",
        ))

    # --- visual_reference QA (forces visual grounding; no table shortcut) ---
    # positional reference: always safe (we control bar order, ties broken by construction)
    pos_kind = random.choice(["leftmost", "rightmost"])
    pi = 0 if pos_kind == "leftmost" else len(cats) - 1
    tasks.append(make_qa_task(
        "visual_reference",
        f"What is the value of the {pos_kind} bar?",
        fmt_value(vals[pi], unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[cats[pi]], column_keys=[name],
        reasoning=f"The {pos_kind} bar is {cats[pi]}; its height is {fmt_value(vals[pi], unit, dec)}.",
    ))
    # color reference: only in named-color mode (ground truth guaranteed)
    if spec.get("color_names"):
        ci = random.randrange(len(cats))
        color = spec["color_names"][ci]
        if random.random() < 0.5:
            tasks.append(make_qa_task(
                "visual_reference",
                f"What is the value of the {color} bar?",
                fmt_value(vals[ci], unit, dec),
                "numeric_with_unit" if unit != "count" else "numeric",
                row_keys=[cats[ci]], column_keys=[name],
                reasoning=f"The {color} bar is {cats[ci]}; its height is {fmt_value(vals[ci], unit, dec)}.",
            ))
        else:
            tasks.append(make_qa_task(
                "visual_reference",
                f"Which category is shown by the {color} bar?",
                cats[ci], "label",
                row_keys=[cats[ci]], column_keys=[name],
                reasoning=f"The {color} bar corresponds to {cats[ci]}.",
            ))
    return tasks


def _render_bar(path, spec, style: StyleInfo, nuis: NuisanceInfo):
    fig, ax = plt.subplots(figsize=(7, 4))
    if spec.get("color_names"):
        colors = [NAMED_COLORS[c] for c in spec["color_names"]]
    else:
        colors = series_colors(style.palette, len(spec["cats"]), nuis.similar_colors)
    ax.bar(spec["cats"], spec["vals"], color=colors)
    ax.set_title(spec["title"])
    ax.set_ylabel(spec["metric"])
    ax.tick_params(axis="x", rotation=style.rotation_x)
    ax.grid(style.show_grid, axis="y", alpha=0.3)
    if style.show_values:
        for i, v in enumerate(spec["vals"]):
            ax.text(i, v, fmt_value(v, spec["unit"], spec["dec"]), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    _save(fig, path, nuis)


def build_bar(idx: int, render_dir: str, difficulty: str = "easy") -> FigureExample:
    spec = _spec_bar()
    style, nuis = sample_style(difficulty)
    img = os.path.join(render_dir, f"bar_{idx:05d}.png")
    _render_bar(img, spec, style, nuis)
    table = DataTable(spec["columns"], spec["rows"], spec["units"])
    csv_path = img.replace(".png", ".csv")
    write_csv(csv_path, table)
    return FigureExample(
        id=make_id("chart"), part="part2_chart", domain="general",
        figure_kind="chart", chart_type="bar", difficulty=difficulty,
        source=SourceInfo("synthetic", "generator_bar_v1", "safe_synthetic"),
        data=FigureData(SCHEMA_VERSION, table, []),
        render=RenderInfo(spec["title"], None, "Category", spec["metric"], [], style, nuis),
        artifacts=Artifacts(img, table_csv_path=csv_path),
        tasks_table_extraction=make_table_extraction_task("chart", "bar", spec["title"], table),
        tasks_qa=_qa_bar(spec),
    )


# =========================================================
# GROUPED BAR  (Part 2 — documented-weak)
# =========================================================

def _spec_grouped() -> Dict[str, Any]:
    title, name, pool, series_pool = random.choice(GROUPED_TEMPLATES)
    unit = METRIC_UNITS[name]
    cats = random.sample(pool, random.randint(3, 4))            # x groups
    series = random.sample(series_pool, random.randint(2, 3))   # bars per group
    series.sort()  # Q1 < Q2 < ... reads naturally
    low, high = metric_range(name)
    dec = decimals_for(unit)
    data = {s: rand_vals(len(cats), low, high, dec) for s in series}
    columns = ["Category"] + series
    rows = [[cats[i]] + [data[s][i] for s in series] for i in range(len(cats))]
    units = {"Category": "label", **{s: unit for s in series}}
    return {"metric": name, "unit": unit, "dec": dec, "cats": cats, "series": series,
            "data": data, "columns": columns, "rows": rows, "units": units,
            "title": title}


def _qa_grouped(spec) -> List:
    name, unit, dec = spec["metric"], spec["unit"], spec["dec"]
    cats, series, data = spec["cats"], spec["series"], spec["data"]
    tasks = []

    s = random.choice(series); ci = random.randrange(len(cats))
    tasks.append(make_qa_task(
        "multi_series_lookup",
        f"For {cats[ci]}, what is the {name} in {s}?",
        fmt_value(data[s][ci], unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[cats[ci]], column_keys=[s],
        reasoning=f"Find group {cats[ci]}, then the {s} bar: {fmt_value(data[s][ci], unit, dec)}.",
    ))

    # extremum across everything
    flat = [(c, s2, data[s2][i]) for i, c in enumerate(cats) for s2 in series]
    bc, bs, bv = max(flat, key=lambda t: t[2])
    tasks.append(make_qa_task(
        "find_extremum",
        f"Which category and series has the highest {name}?",
        f"{bc}, {bs}", "label",
        row_keys=cats, column_keys=series,
        reasoning=f"Scan every bar; max is {bc}/{bs} at {fmt_value(bv, unit, dec)}.",
    ))

    # per-group total (stacked-style reasoning over grouped data)
    if unit in ("count", "currency"):
        ci2 = random.randrange(len(cats))
        tot = sum(data[s2][ci2] for s2 in series)
        tasks.append(make_qa_task(
            "compute_sum",
            f"What is the total {name} for {cats[ci2]} across all series?",
            fmt_value(tot, unit, dec),
            "numeric_with_unit" if unit != "count" else "numeric",
            row_keys=[cats[ci2]], column_keys=series,
            reasoning="Sum the group's bars: " + " + ".join(fmt_value(data[s2][ci2], unit, dec) for s2 in series) + f" = {fmt_value(tot, unit, dec)}.",
        ))
    return tasks


def _render_grouped(path, spec, style, nuis):
    import numpy as np
    cats, series, data = spec["cats"], spec["series"], spec["data"]
    x = np.arange(len(cats)); w = 0.8 / len(series)
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = distinct_series_colors(len(series))
    for k, s in enumerate(series):
        ax.bar(x + k * w - 0.4 + w / 2, data[s], width=w, label=s, color=colors[k])
    ax.set_xticks(x); ax.set_xticklabels(cats, rotation=style.rotation_x)
    ax.set_title(spec["title"]); ax.set_ylabel(spec["metric"])
    ax.grid(style.show_grid, axis="y", alpha=0.3)
    ax.legend(loc=style.legend_loc, fontsize=7 if nuis.crowded_legend else 9)
    fig.tight_layout()
    _save(fig, path, nuis)


def build_grouped(idx: int, render_dir: str, difficulty: str = "medium") -> FigureExample:
    spec = _spec_grouped()
    style, nuis = sample_style(difficulty)
    img = os.path.join(render_dir, f"grouped_{idx:05d}.png")
    _render_grouped(img, spec, style, nuis)
    table = DataTable(spec["columns"], spec["rows"], spec["units"])
    csv_path = img.replace(".png", ".csv")
    write_csv(csv_path, table)
    return FigureExample(
        id=make_id("chart"), part="part2_chart", domain="general",
        figure_kind="chart", chart_type="grouped_bar", difficulty=difficulty,
        source=SourceInfo("synthetic", "generator_grouped_v1", "safe_synthetic"),
        data=FigureData(SCHEMA_VERSION, table, []),
        render=RenderInfo(spec["title"], None, "Category", spec["metric"], spec["series"], style, nuis),
        artifacts=Artifacts(img, table_csv_path=csv_path),
        tasks_table_extraction=make_table_extraction_task("chart", "grouped_bar", spec["title"], table),
        tasks_qa=_qa_grouped(spec),
    )


# =========================================================
# STACKED BAR  (Part 2 — the most documented-weak type)
# =========================================================

def _spec_stacked() -> Dict[str, Any]:
    title, name, seg_pool = random.choice(STACKED_TEMPLATES)
    unit = METRIC_UNITS[name]
    cats = sorted(random.sample(range(len(MONTHS)), random.randint(3, 5)))
    cats = [MONTHS[i] for i in cats]                          # x axis, in calendar order
    series = random.sample(seg_pool, random.randint(2, 4))    # stack segments
    series_color_names = None
    if random.random() < NAMED_COLOR_PROB:
        series_color_names = random.sample(list(NAMED_COLORS.keys()), len(series))
    low, high = metric_range(name)
    dec = decimals_for(unit)
    # per-segment values; total = stack height
    data = {s: rand_vals(len(cats), low / max(1, len(series)), high / max(1, len(series)), dec) for s in series}
    totals = [round(sum(data[s][i] for s in series), dec) for i in range(len(cats))]
    columns = ["Period"] + series + ["Total"]
    rows = [[cats[i]] + [data[s][i] for s in series] + [totals[i]] for i in range(len(cats))]
    units = {"Period": "label", **{s: unit for s in series}, "Total": unit}
    return {"metric": name, "unit": unit, "dec": dec, "cats": cats, "series": series,
            "series_color_names": series_color_names,
            "data": data, "totals": totals, "columns": columns, "rows": rows,
            "units": units, "title": title}


def _qa_stacked(spec) -> List:
    name, unit, dec = spec["metric"], spec["unit"], spec["dec"]
    cats, series, data, totals = spec["cats"], spec["series"], spec["data"], spec["totals"]
    tasks = []

    # segment lookup — the thing models fail (reading a stack segment, not the top)
    s = random.choice(series); ci = random.randrange(len(cats))
    tasks.append(make_qa_task(
        "multi_series_lookup",
        f"In {cats[ci]}, what is the {s} portion of {name}?",
        fmt_value(data[s][ci], unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[cats[ci]], column_keys=[s],
        reasoning=f"In the {cats[ci]} stack, the {s} segment spans {fmt_value(data[s][ci], unit, dec)} (segment height, not the cumulative top).",
    ))

    # stack total
    ci2 = random.randrange(len(cats))
    tasks.append(make_qa_task(
        "compute_sum",
        f"What is the total {name} in {cats[ci2]}?",
        fmt_value(totals[ci2], unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[cats[ci2]], column_keys=series,
        reasoning="Total = sum of segments = " + " + ".join(fmt_value(data[s2][ci2], unit, dec) for s2 in series) + f" = {fmt_value(totals[ci2], unit, dec)}.",
    ))

    # which segment dominates a given period
    ci3 = random.randrange(len(cats))
    seg_vals = [(s2, data[s2][ci3]) for s2 in series]
    top_seg = max(seg_vals, key=lambda t: t[1])[0]
    tasks.append(make_qa_task(
        "find_extremum",
        f"Which segment is largest in {cats[ci3]}?",
        top_seg, "label",
        row_keys=[cats[ci3]], column_keys=series,
        reasoning=f"Compare segment heights within {cats[ci3]}; {top_seg} is largest.",
    ))

    # color-referenced segment lookup (named-color mode only)
    if spec.get("series_color_names"):
        si = random.randrange(len(series))
        color = spec["series_color_names"][si]
        ci4 = random.randrange(len(cats))
        tasks.append(make_qa_task(
            "visual_reference",
            f"In {cats[ci4]}, what is the value of the {color} segment?",
            fmt_value(data[series[si]][ci4], unit, dec),
            "numeric_with_unit" if unit != "count" else "numeric",
            row_keys=[cats[ci4]], column_keys=[series[si]],
            reasoning=f"The {color} segments are {series[si]}; in {cats[ci4]} that segment spans {fmt_value(data[series[si]][ci4], unit, dec)}.",
        ))
    return tasks


def _render_stacked(path, spec, style, nuis):
    import numpy as np
    cats, series, data = spec["cats"], spec["series"], spec["data"]
    fig, ax = plt.subplots(figsize=(8, 4))
    if spec.get("series_color_names"):
        colors = [NAMED_COLORS[c] for c in spec["series_color_names"]]
    else:
        colors = distinct_series_colors(len(series))
    bottom = np.zeros(len(cats))
    for k, s in enumerate(series):
        vals = np.array(data[s])
        ax.bar(cats, vals, bottom=bottom, label=s, color=colors[k])
        bottom += vals
    ax.set_title(spec["title"]); ax.set_ylabel(spec["metric"])
    ax.tick_params(axis="x", rotation=style.rotation_x)
    ax.grid(style.show_grid, axis="y", alpha=0.3)
    ax.legend(loc=style.legend_loc, fontsize=7 if nuis.crowded_legend else 9)
    fig.tight_layout()
    _save(fig, path, nuis)


def build_stacked(idx: int, render_dir: str, difficulty: str = "hard") -> FigureExample:
    spec = _spec_stacked()
    style, nuis = sample_style(difficulty)
    img = os.path.join(render_dir, f"stacked_{idx:05d}.png")
    _render_stacked(img, spec, style, nuis)
    table = DataTable(spec["columns"], spec["rows"], spec["units"])
    csv_path = img.replace(".png", ".csv")
    write_csv(csv_path, table)
    return FigureExample(
        id=make_id("chart"), part="part2_chart", domain="general",
        figure_kind="chart", chart_type="stacked_bar", difficulty=difficulty,
        source=SourceInfo("synthetic", "generator_stacked_v1", "safe_synthetic"),
        data=FigureData(SCHEMA_VERSION, table, []),
        render=RenderInfo(spec["title"], None, "Period", spec["metric"], spec["series"], style, nuis),
        artifacts=Artifacts(img, table_csv_path=csv_path),
        tasks_table_extraction=make_table_extraction_task("chart", "stacked_bar", spec["title"], table),
        tasks_qa=_qa_stacked(spec),
    )


# =========================================================
# LINE  (Part 2)
# =========================================================

def _spec_line() -> Dict[str, Any]:
    title, name = random.choice(LINE_TEMPLATES)
    unit = METRIC_UNITS[name]
    months = MONTHS[: random.randint(4, 6)]
    low, high = metric_range(name); dec = decimals_for(unit)
    vals = []; cur = random.uniform(low, high)
    for _ in months:
        cur = max(low, min(high, cur + random.uniform(-(high - low) * 0.08, (high - low) * 0.08)))
        vals.append(round(cur, dec))
    return {"metric": name, "unit": unit, "dec": dec, "x": months, "y": vals,
            "columns": ["Month", name], "rows": [[months[i], vals[i]] for i in range(len(months))],
            "units": {"Month": "label", name: unit}, "title": title}


def _qa_line(spec) -> List:
    name, unit, dec = spec["metric"], spec["unit"], spec["dec"]
    x, y = spec["x"], spec["y"]
    tasks = []
    i = random.randrange(len(x))
    tasks.append(make_qa_task(
        "retrieve_value", f"What was the {name} in {x[i]}?",
        fmt_value(y[i], unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[x[i]], column_keys=[name],
        reasoning=f"Read the point at {x[i]}: {fmt_value(y[i], unit, dec)}.",
    ))
    mx = argmax_idx(y)
    tasks.append(make_qa_task(
        "find_extremum", f"In which month was {name} highest?",
        x[mx], "label", row_keys=x, column_keys=[name],
        reasoning=f"Peak of the line is at {x[mx]} ({fmt_value(y[mx], unit, dec)}).",
    ))
    trend = "increase" if y[-1] > y[0] else "decrease" if y[-1] < y[0] else "stay the same"
    tasks.append(make_qa_task(
        "trend_direction",
        f"Did {name} generally increase, decrease, or stay the same over the period?",
        trend, "label", row_keys=[x[0], x[-1]], column_keys=[name],
        reasoning=f"Start {fmt_value(y[0], unit, dec)} -> end {fmt_value(y[-1], unit, dec)}, so it tends to {trend}.",
    ))

    # month-over-month delta (forces reading TWO adjacent points + arithmetic)
    j = random.randrange(1, len(x))
    delta = round(y[j] - y[j - 1], dec)
    if delta == 0:
        chg_reason = f"{x[j-1]}={fmt_value(y[j-1], unit, dec)}, {x[j]}={fmt_value(y[j], unit, dec)}; no change."
        chg_aliases = ["0", "no change", "unchanged"]
    else:
        direction = "increased" if delta > 0 else "decreased"
        chg_reason = f"{x[j-1]}={fmt_value(y[j-1], unit, dec)}, {x[j]}={fmt_value(y[j], unit, dec)}; it {direction} by {fmt_value(abs(delta), unit, dec)}."
        chg_aliases = [str(abs(delta)), f"{direction} by {fmt_value(abs(delta), unit, dec)}"]
    tasks.append(make_qa_task(
        "compute_difference",
        f"By how much did {name} change from {x[j-1]} to {x[j]}?",
        fmt_value(abs(delta), unit, dec),
        "numeric_with_unit" if unit != "count" else "numeric",
        row_keys=[x[j-1], x[j]], column_keys=[name],
        aliases=chg_aliases,
        reasoning=chg_reason,
    ))

    # compare two specified (non-adjacent when possible) months
    a, b = sorted(random.sample(range(len(x)), 2))
    if y[a] == y[b]:
        cmp_ans = "equal"
        cmp_reason = f"{x[a]} and {x[b]} are both {fmt_value(y[a], unit, dec)}."
    else:
        hi = a if y[a] > y[b] else b
        cmp_ans = x[hi]
        cmp_reason = f"{x[a]}={fmt_value(y[a], unit, dec)} vs {x[b]}={fmt_value(y[b], unit, dec)}; {x[hi]} is higher."
    tasks.append(make_qa_task(
        "compare_values",
        f"Which month had higher {name}: {x[a]} or {x[b]}?",
        cmp_ans, "label",
        row_keys=[x[a], x[b]], column_keys=[name],
        reasoning=cmp_reason,
    ))
    return tasks


def _render_line(path, spec, style, nuis):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(spec["x"], spec["y"], marker="o")
    ax.set_title(spec["title"]); ax.set_ylabel(spec["metric"]); ax.set_xlabel("Time")
    ax.tick_params(axis="x", rotation=style.rotation_x)
    ax.grid(style.show_grid, alpha=0.3)
    fig.tight_layout()
    _save(fig, path, nuis)


def build_line(idx: int, render_dir: str, difficulty: str = "easy") -> FigureExample:
    spec = _spec_line()
    style, nuis = sample_style(difficulty)
    img = os.path.join(render_dir, f"line_{idx:05d}.png")
    _render_line(img, spec, style, nuis)
    table = DataTable(spec["columns"], spec["rows"], spec["units"])
    csv_path = img.replace(".png", ".csv")
    write_csv(csv_path, table)
    series = [SeriesData(spec["metric"], spec["x"], spec["y"])]
    return FigureExample(
        id=make_id("chart"), part="part2_chart", domain="general",
        figure_kind="chart", chart_type="line", difficulty=difficulty,
        source=SourceInfo("synthetic", "generator_line_v1", "safe_synthetic"),
        data=FigureData(SCHEMA_VERSION, table, series),
        render=RenderInfo(spec["title"], None, "Month", spec["metric"], [spec["metric"]], style, nuis),
        artifacts=Artifacts(img, table_csv_path=csv_path),
        tasks_table_extraction=make_table_extraction_task("chart", "line", spec["title"], table),
        tasks_qa=_qa_line(spec),
    )


# =========================================================
# MARKETING DASHBOARD  (Part 1)  — KPI-vs-sum bug FIXED
# =========================================================

# A KPI/sum gap is only askable when it is visually legible. We require the gap
# to be at least this fraction of the shown sum, else we relabel as unanswerable.
_LEGIBLE_GAP_FRAC = 0.10


def _spec_dashboard() -> Dict[str, Any]:
    name, unit = "Conversions", "count"
    n = random.randint(3, 5)
    cats = random.sample(CHANNELS, n)
    vals = [random.randint(100, 900) for _ in range(n)]
    shown_sum = sum(vals)

    # FIX: choose a KPI total whose relationship to the shown sum is *legible*.
    mode = random.choice(["equal", "greater", "less"])
    if mode == "equal":
        kpi_total = shown_sum
    elif mode == "greater":
        kpi_total = shown_sum + random.randint(
            int(_LEGIBLE_GAP_FRAC * shown_sum) + 20, int(0.4 * shown_sum) + 50)
    else:  # less  (e.g. dashboard total excludes a channel)
        kpi_total = shown_sum - random.randint(
            int(_LEGIBLE_GAP_FRAC * shown_sum) + 20, int(0.3 * shown_sum) + 30)
        kpi_total = max(kpi_total, max(vals))  # stay sane

    # THIRD PANEL: monthly Spend trend line, with its own ground-truth table.
    months = MONTHS[: random.randint(4, 6)]
    s_low, s_high = metric_range("Spend")
    spend = []
    cur = random.uniform(s_low, s_high)
    for _ in months:
        cur = max(s_low, min(s_high, cur + random.uniform(-(s_high - s_low) * 0.10, (s_high - s_low) * 0.10)))
        spend.append(round(cur, 0))

    return {"metric": name, "unit": unit, "cats": cats, "vals": vals,
            "shown_sum": shown_sum, "kpi_total": kpi_total, "gap_mode": mode,
            "months": months, "spend": spend,
            "columns": ["Channel", name], "rows": [[cats[i], vals[i]] for i in range(n)],
            "units": {"Channel": "label", name: unit},
            "title": "Campaign Performance Dashboard"}


def _qa_dashboard(spec) -> List:
    name, cats, vals = spec["metric"], spec["cats"], spec["vals"]
    kpi_total, shown_sum, mode = spec["kpi_total"], spec["shown_sum"], spec["gap_mode"]
    tasks = []

    i = random.randrange(len(cats))
    tasks.append(make_qa_task(
        "retrieve_value",
        f"How many {name.lower()} came from {cats[i]}?",
        str(int(vals[i])), "numeric",
        row_keys=[cats[i]], column_keys=[name], panel_ids=["p2"],
        reasoning=f"Read the {cats[i]} bar in the channel panel: {int(vals[i])}.",
    ))

    mx = argmax_idx(vals)
    tasks.append(make_qa_task(
        "find_extremum",
        f"Which channel had the most {name.lower()}?",
        cats[mx], "label",
        row_keys=cats, column_keys=[name], panel_ids=["p2"],
        reasoning=f"{cats[mx]} has the tallest bar ({int(vals[mx])}).",
    ))

    # FIXED multi-panel question: legible by construction; answer derived from mode.
    if mode == "equal":
        ans, alias = "Equal", ["equal", "the same", "same"]
        reason = f"KPI total {kpi_total} equals the sum of channel bars {shown_sum}."
    elif mode == "greater":
        ans, alias = "Yes", ["yes", "true"]
        reason = f"KPI total {kpi_total} exceeds the channel sum {shown_sum} by {kpi_total - shown_sum}."
    else:
        ans, alias = "No", ["no", "false"]
        reason = f"KPI total {kpi_total} is less than the channel sum {shown_sum} by {shown_sum - kpi_total}."
    tasks.append(make_qa_task(
        "multi_panel_linked_reasoning",
        f"Is the KPI card total greater than the sum of {name.lower()} shown in the channel chart?",
        ans, "boolean" if mode != "equal" else "label",
        panel_ids=["p1", "p2"], aliases=alias, reasoning=reason,
    ))

    # trend-panel question (third panel)
    months, spend = spec["months"], spec["spend"]
    mxs = argmax_idx(spend)
    tasks.append(make_qa_task(
        "find_extremum",
        "In which month was Spend highest?",
        months[mxs], "label",
        panel_ids=["p3"],
        reasoning=f"Peak of the spend trend line is at {months[mxs]} (${int(spend[mxs]):,}).",
    ))
    return tasks


def _render_dashboard(path, spec, style, nuis):
    fig = plt.figure(figsize=(11, 6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 2], height_ratios=[1, 1])
    ax_kpi = fig.add_subplot(gs[0, 0])
    ax_bar = fig.add_subplot(gs[:, 1])
    ax_trend = fig.add_subplot(gs[1, 0])

    # KPI card
    ax_kpi.axis("off")
    ax_kpi.text(0.5, 0.72, "Total " + spec["metric"], ha="center", va="center", fontsize=12)
    ax_kpi.text(0.5, 0.40, f"{spec['kpi_total']:,}", ha="center", va="center", fontsize=24, weight="bold")
    ax_kpi.set_facecolor("#f5f5f7")

    # channel bars
    colors = series_colors(style.palette, len(spec["cats"]), nuis.similar_colors)
    ax_bar.bar(spec["cats"], spec["vals"], color=colors)
    ax_bar.set_title("Conversions by Channel", fontsize=11)
    ax_bar.tick_params(axis="x", rotation=style.rotation_x)
    ax_bar.grid(style.show_grid, axis="y", alpha=0.3)

    # spend trend line (third panel)
    ax_trend.plot(spec["months"], spec["spend"], marker="o", linewidth=1.5)
    ax_trend.set_title("Monthly Spend", fontsize=10)
    ax_trend.tick_params(axis="both", labelsize=7)
    ax_trend.grid(style.show_grid, alpha=0.3)

    fig.suptitle(spec["title"], fontsize=13)
    fig.tight_layout()
    _save(fig, path, nuis)


def build_dashboard(idx: int, render_dir: str, difficulty: str = "medium") -> FigureExample:
    spec = _spec_dashboard()
    style, nuis = sample_style(difficulty)
    img = os.path.join(render_dir, f"dashboard_{idx:05d}.png")
    _render_dashboard(img, spec, style, nuis)
    table = DataTable(spec["columns"], spec["rows"], spec["units"])
    spend_table = DataTable(
        ["Month", "Spend"],
        [[spec["months"][i], spec["spend"][i]] for i in range(len(spec["months"]))],
        {"Month": "label", "Spend": "currency"},
    )
    csv_path = img.replace(".png", ".csv")
    write_csv(csv_path, table)
    return FigureExample(
        id=make_id("mkt"), part="part1_marketing", domain="marketing",
        figure_kind="dashboard", chart_type="multi_panel", difficulty=difficulty,
        source=SourceInfo("synthetic", "generator_dashboard_v2", "safe_synthetic"),
        data=FigureData(SCHEMA_VERSION, table, []),
        render=RenderInfo(spec["title"], "Weekly overview", None, None, [], style, nuis),
        artifacts=Artifacts(img, table_csv_path=csv_path),
        panels=[
            DashboardPanel("p1", "kpi_card", "Total Conversions", value=spec["kpi_total"], unit="count"),
            DashboardPanel("p2", "channel_comparison_bar", "Conversions by Channel", table=table),
            DashboardPanel("p3", "time_series_panel", "Monthly Spend", table=spend_table),
        ],
        tasks_table_extraction=make_table_extraction_task(
            "dashboard", "multi_panel", spec["title"], table,
            prompt="Extract ALL quantitative data from this dashboard: every KPI card and every panel's table.",
            kpis=[KPIItem("Total Conversions", spec["kpi_total"], "count")],
            extra_tables=[PanelTable("p3", "Monthly Spend", spend_table)],
        ),
        tasks_qa=_qa_dashboard(spec),
        metadata={"panel_count": 3, "dashboard_theme": "marketing_ops", "gap_mode": spec["gap_mode"]},
    )


# =========================================================
# MARKETING FUNNEL  (Part 1)  — stage-to-stage conversion + diagnostic
# =========================================================

FUNNEL_TITLES = [
    "Lead Funnel Performance",
    "Marketing Funnel Overview",
    "Demand Gen Funnel",
    "Campaign Funnel: Awareness to Close",
]


def _spec_funnel() -> Dict[str, Any]:
    """Ordered funnel stages with monotonically decreasing counts.
    Stage-to-stage conversion rates and drop-offs are the funnel-specific
    reasoning targets; a diagnostic question reads the worst drop-off.
    """
    # take a contiguous slice of the canonical funnel (>=4 stages)
    start = random.randint(0, 2)
    end = random.randint(start + 4, len(FUNNEL_STAGES))
    stages = FUNNEL_STAGES[start:end]
    n = len(stages)

    # top-of-funnel volume, then each stage retains a random fraction of the prior
    top = random.choice([50000, 80000, 100000, 250000, 500000])
    counts = [top]
    for _ in range(1, n):
        retain = random.uniform(0.18, 0.62)  # realistic step conversion
        counts.append(max(1, int(round(counts[-1] * retain))))

    columns = ["Stage", "Count"]
    rows = [[stages[i], counts[i]] for i in range(n)]
    units = {"Stage": "label", "Count": "count"}
    return {"stages": stages, "counts": counts, "columns": columns,
            "rows": rows, "units": units, "title": random.choice(FUNNEL_TITLES)}


def _qa_funnel(spec) -> List:
    stages, counts = spec["stages"], spec["counts"]
    n = len(stages)
    tasks = []

    # 1. raw stage count (retrieve)
    i = random.randrange(n)
    tasks.append(make_qa_task(
        "retrieve_value",
        f"How many {stages[i]} were there?",
        str(counts[i]), "numeric",
        row_keys=[stages[i]], column_keys=["Count"],
        reasoning=f"Read the {stages[i]} stage of the funnel: {counts[i]:,}.",
    ))

    # 2. stage-to-stage conversion rate (the core funnel skill)
    j = random.randrange(1, n)
    conv = round(100.0 * counts[j] / counts[j - 1], 1)
    tasks.append(make_qa_task(
        "funnel_conversion",
        f"What is the conversion rate from {stages[j-1]} to {stages[j]}?",
        f"{conv}%", "numeric_with_unit",
        row_keys=[stages[j - 1], stages[j]], column_keys=["Count"],
        aliases=[str(conv)],
        reasoning=f"{stages[j]} ({counts[j]:,}) / {stages[j-1]} ({counts[j-1]:,}) = {conv}%.",
    ))

    # 3. drop-off between two adjacent stages (absolute)
    k = random.randrange(1, n)
    drop = counts[k - 1] - counts[k]
    tasks.append(make_qa_task(
        "compute_difference",
        f"How many were lost between {stages[k-1]} and {stages[k]}?",
        str(drop), "numeric",
        row_keys=[stages[k - 1], stages[k]], column_keys=["Count"],
        aliases=[f"{drop:,}"],
        reasoning=f"{stages[k-1]} ({counts[k-1]:,}) - {stages[k]} ({counts[k]:,}) = {drop:,} lost.",
    ))

    # 4. end-to-end funnel conversion (multi-hop: first to last)
    e2e = round(100.0 * counts[-1] / counts[0], 2)
    tasks.append(make_qa_task(
        "funnel_conversion",
        f"What is the overall conversion rate from {stages[0]} to {stages[-1]}?",
        f"{e2e}%", "numeric_with_unit",
        row_keys=[stages[0], stages[-1]], column_keys=["Count"],
        aliases=[str(e2e)],
        reasoning=f"{stages[-1]} ({counts[-1]:,}) / {stages[0]} ({counts[0]:,}) = {e2e}%.",
    ))

    # 5. diagnostic (PM-AGI action-based shape, over our exact numbers):
    #    find the WORST stage-to-stage conversion -> the bottleneck.
    step_convs = [(stages[s - 1], stages[s], counts[s] / counts[s - 1]) for s in range(1, n)]
    worst = min(step_convs, key=lambda t: t[2])
    worst_pct = round(100.0 * worst[2], 1)
    tasks.append(make_qa_task(
        "diagnostic",
        "Which funnel stage transition has the largest drop-off (the bottleneck)?",
        f"{worst[0]} to {worst[1]}", "label",
        row_keys=[worst[0], worst[1]], column_keys=["Count"],
        aliases=[f"{worst[0]}->{worst[1]}", f"{worst[0]}\u2192{worst[1]}"],
        reasoning=(f"Compare step conversion rates; {worst[0]}->{worst[1]} is lowest at "
                   f"{worst_pct}%, the biggest leak in the funnel."),
    ))
    return tasks


def _render_funnel(path, spec, style, nuis):
    """Horizontal funnel: centered bars, widest at top, narrowing down.
    Labels use white text with a dark outline so they stay legible on any
    bar color (dark continuous palettes like viridis would hide black text)."""
    import matplotlib.patheffects as pe
    stages, counts = spec["stages"], spec["counts"]
    n = len(stages)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = distinct_series_colors(n)
    maxc = max(counts)
    for i, (st, c) in enumerate(zip(stages, counts)):
        width = c / maxc
        y = n - 1 - i
        ax.barh(y, width, left=(1 - width) / 2, color=colors[i], height=0.7)
        txt = ax.text(0.5, y, f"{st}: {c:,}", ha="center", va="center",
                      fontsize=8 if nuis.crowded_legend else 9,
                      color="white", weight="bold")
        txt.set_path_effects([pe.withStroke(linewidth=2.5, foreground="#222222")])
    ax.set_xlim(0, 1); ax.set_ylim(-0.5, n - 0.5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(spec["title"])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    _save(fig, path, nuis)


def build_funnel(idx: int, render_dir: str, difficulty: str = "medium") -> FigureExample:
    spec = _spec_funnel()
    style, nuis = sample_style(difficulty)
    img = os.path.join(render_dir, f"funnel_{idx:05d}.png")
    _render_funnel(img, spec, style, nuis)
    table = DataTable(spec["columns"], spec["rows"], spec["units"])
    csv_path = img.replace(".png", ".csv")
    write_csv(csv_path, table)
    return FigureExample(
        id=make_id("mkt"), part="part1_marketing", domain="marketing",
        figure_kind="chart", chart_type="funnel", difficulty=difficulty,
        source=SourceInfo("synthetic", "generator_funnel_v1", "safe_synthetic"),
        data=FigureData(SCHEMA_VERSION, table, []),
        render=RenderInfo(spec["title"], None, "Stage", "Count", spec["stages"], style, nuis),
        artifacts=Artifacts(img, table_csv_path=csv_path),
        tasks_table_extraction=make_table_extraction_task("chart", "funnel", spec["title"], table),
        tasks_qa=_qa_funnel(spec),
        metadata={"stage_count": len(spec["stages"])},
    )


# =========================================================
# Dataset builder
# =========================================================

_BUILDERS = {
    "bar": build_bar,
    "grouped_bar": build_grouped,
    "stacked_bar": build_stacked,
    "line": build_line,
    "dashboard": build_dashboard,
    "funnel": build_funnel,
}


def build_mixed_dataset(
    counts: Dict[str, int],
    render_dir: str = "data/renders",
    seed: Optional[int] = None,
) -> List[FigureExample]:
    """counts: e.g. {'bar':20,'grouped_bar':20,'stacked_bar':20,'line':20,'dashboard':20}"""
    if seed is not None:
        random.seed(seed)
    examples: List[FigureExample] = []
    for kind, n in counts.items():
        builder = _BUILDERS[kind]
        for i in range(n):
            examples.append(builder(i, render_dir=render_dir))
    random.shuffle(examples)
    return examples
