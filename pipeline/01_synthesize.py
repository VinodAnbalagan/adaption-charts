"""Synthesize gold synthetic-core rows (bar, line, grouped_bar, stacked_bar).

Bit-by-bit expansion of the synthetic core.
  slice 1: 1 chart, 3 rows                                     DONE
  slice 2: 2 charts, 6 rows (rotated flat phrasings)           DONE
  slice 3: 6 charts, 18 rows (2 bar domains)                   DONE
  slice 4: 9 charts, 30 rows (+ line + trend + pct_change)     DONE
  slice 5: 13 charts, 42 rows (+ grouped_bar + stacked_bar)    THIS
  slice N: scale to full synthetic-core budget (~250 rows)

Regenerates manifest.csv from scratch on each run.
"""

from __future__ import annotations
from pathlib import Path
import csv
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.render import (  # noqa: E402
    render_bar,
    render_line,
    render_grouped_bar,
    render_stacked_bar,
    render_pie,
    render_donut,
)
from lib.phrasings import (  # noqa: E402
    REVENUE_BAR,
    UNITS_BAR,
    MONTHLY_REVENUE_LINE,
    MONTHLY_USERS_LINE,
    REVENUE_GROUPED,
    REVENUE_STACKED,
    SHARE_CIRCLE,
    pick,
)


REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
IMAGES = GOLD / "images"
RAW = GOLD / "raw"
MANIFEST = GOLD / "manifest.csv"

MANIFEST_COLS = [
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]


# Domain keys now encode chart_type where useful, so we can have separate
# phrasing banks for the same subject matter on different chart types.
DOMAIN_META: dict[str, dict] = {
    "revenue_bar": {
        "phrasings": REVENUE_BAR,
        "value_fmt": "${:.0f}",
        "answer_fmt": "${:.0f}",
    },
    "units_sold_bar": {
        "phrasings": UNITS_BAR,
        "value_fmt": "{:.0f}",
        "answer_fmt": "{:.0f}",
    },
    "monthly_revenue": {
        "phrasings": MONTHLY_REVENUE_LINE,
        "value_fmt": "${:.0f}",
        "answer_fmt": "${:.0f}",
    },
    "monthly_users": {
        "phrasings": MONTHLY_USERS_LINE,
        "value_fmt": "{:.0f}",
        "answer_fmt": "{:.0f}",
    },
    "revenue_grouped": {
        "phrasings": REVENUE_GROUPED,
        "value_fmt": "${:.0f}",
        "answer_fmt": "${:.0f}",
    },
    "revenue_stacked": {
        "phrasings": REVENUE_STACKED,
        "value_fmt": "${:.0f}",
        "answer_fmt": "${:.0f}",
    },
    "share_circle": {
        "phrasings": SHARE_CIRCLE,
        # pie/donut answers are percentages, not raw values —
        # value_fmt / answer_fmt intentionally unused for this domain
        "value_fmt": None,
        "answer_fmt": None,
    },
}


CHART_SPECS: list[dict] = [
    # --- BAR: revenue -------------------------------------------------------
    {
        "chart_id": "syn_bar_0001", "chart_type": "bar",
        "domain": "revenue_bar", "entity": "segment",
        "title": "Q4 Revenue by Segment", "y_label": "Revenue ($)",
        "categories": ["Consumer", "Enterprise", "SMB", "Government", "Education"],
        "values": [4200, 8600, 3100, 2400, 1800],
        "lookup_target": "Enterprise", "extreme": "max",
        "delta_pair": ("Consumer", "Education"),
        "rank_direction": "top",
        "hard_triple": ("Consumer", "SMB", "Enterprise"),
        "notes": "annotated bars; correct-by-construction",
    },
    {
        "chart_id": "syn_bar_0002", "chart_type": "bar",
        "domain": "revenue_bar", "entity": "product line",
        "title": "FY25 Revenue by Product Line", "y_label": "Revenue ($)",
        "categories": ["Basic", "Standard", "Pro", "Premium", "Ultimate"],
        "values": [1500, 3800, 6200, 9400, 5100],
        "lookup_target": "Standard", "extreme": "min",
        "delta_pair": ("Ultimate", "Standard"),
        "hard_triple": ("Standard", "Pro", "Premium"),
        "notes": "annotated bars; correct-by-construction",
    },
    {
        "chart_id": "syn_bar_0003", "chart_type": "bar",
        "domain": "revenue_bar", "entity": "region",
        "title": "H1 Revenue by Region", "y_label": "Revenue ($)",
        "categories": ["NA", "EMEA", "APAC", "LATAM", "MEA"],
        "values": [5200, 6800, 4400, 2900, 1600],
        "lookup_target": "APAC", "extreme": "max",
        "delta_pair": ("NA", "APAC"),
        "rank_direction": "bottom",
        "notes": "annotated bars; correct-by-construction",
    },
    {
        "chart_id": "syn_bar_0004", "chart_type": "bar",
        "domain": "revenue_bar", "entity": "vertical",
        "title": "Q3 Revenue by Vertical", "y_label": "Revenue ($)",
        "categories": ["Healthcare", "Retail", "Finance", "Manufacturing", "Tech"],
        "values": [3300, 5100, 7200, 4800, 6500],
        "lookup_target": "Retail", "extreme": "min",
        "delta_pair": ("Finance", "Manufacturing"),
        "notes": "annotated bars; correct-by-construction",
    },

    # --- BAR: units_sold ----------------------------------------------------
    {
        "chart_id": "syn_bar_0005", "chart_type": "bar",
        "domain": "units_sold_bar", "entity": "product",
        "title": "Q2 Units Sold by Product", "y_label": "Units sold",
        "categories": ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"],
        "values": [1200, 3400, 2100, 4700, 890],
        "lookup_target": "Widget C", "extreme": "max",
        "delta_pair": ("Widget B", "Widget A"),
        "rank_direction": "top",
        "notes": "annotated bars; correct-by-construction",
    },
    {
        "chart_id": "syn_bar_0006", "chart_type": "bar",
        "domain": "units_sold_bar", "entity": "SKU",
        "title": "Weekly Units Sold by SKU", "y_label": "Units sold",
        "categories": ["SKU-101", "SKU-102", "SKU-103", "SKU-104", "SKU-105"],
        "values": [560, 720, 340, 890, 1250],
        "lookup_target": "SKU-102", "extreme": "min",
        "delta_pair": ("SKU-105", "SKU-102"),
        "notes": "annotated bars; correct-by-construction",
    },

    # --- LINE: monthly_revenue ---------------------------------------------
    {
        "chart_id": "syn_line_0001", "chart_type": "line",
        "domain": "monthly_revenue", "entity": "month",
        "title": "Monthly Revenue — H1 2025", "y_label": "Revenue ($)",
        "x_labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "values": [5860, 6415, 6963, 6633, 6705, 7280],
        "lookup_target": "Mar", "extreme": "max",
        "trend_pair": ("Feb", "Mar"),
        "pct_pair": ("Jan", "Jun"),
        "hard_delta_pairs": (("Jan", "Mar"), ("Apr", "Jun")),
        "notes": "annotated line; correct-by-construction",
    },
    {
        "chart_id": "syn_line_0002", "chart_type": "line",
        "domain": "monthly_revenue", "entity": "month",
        "title": "Monthly Revenue — H2 2025", "y_label": "Revenue ($)",
        "x_labels": ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "values": [7150, 7890, 7420, 6980, 7260, 8100],
        "lookup_target": "Sep", "extreme": "min",
        "trend_pair": ("Sep", "Oct"),
        "pct_pair": ("Jul", "Dec"),
        "notes": "annotated line; correct-by-construction",
    },

    # --- LINE: monthly_users ------------------------------------------------
    {
        "chart_id": "syn_line_0003", "chart_type": "line",
        "domain": "monthly_users", "entity": "month",
        "title": "Monthly Active Users — H1 2025", "y_label": "Active users",
        "x_labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "values": [12000, 13500, 14200, 15800, 16400, 17900],
        "lookup_target": "Apr", "extreme": "max",
        "trend_pair": ("Mar", "Apr"),
        "pct_pair": ("Jan", "Jun"),
        "hard_delta_pairs": (("Jan", "Mar"), ("Apr", "Jun")),
        "notes": "annotated line; correct-by-construction",
    },

    # --- GROUPED_BAR: revenue ----------------------------------------------
    {
        "chart_id": "syn_grouped_0001", "chart_type": "grouped_bar",
        "domain": "revenue_grouped", "entity": "segment",
        "series_axis": "year",
        "title": "Revenue by Segment: 2024 vs 2025", "y_label": "Revenue ($)",
        "categories": ["Consumer", "Enterprise", "SMB", "Government", "Education"],
        "series_labels": ["2024", "2025"],
        "series_values": [
            [3800, 8100, 2900, 2200, 1600],   # 2024
            [4200, 7200, 4300, 2400, 1900],   # 2025
        ],
        "lookup_target": ("Enterprise", "2024"),
        "extreme_series": "2025", "extreme": "max",
        "compare_category": "SMB",
        "hard_compare_pair": (("Enterprise", "2024"), ("SMB", "2025")),
        "notes": "annotated grouped bars; correct-by-construction",
    },
    {
        "chart_id": "syn_grouped_0002", "chart_type": "grouped_bar",
        "domain": "revenue_grouped", "entity": "region",
        "series_axis": "half",
        "title": "Revenue by Region: H1 vs H2", "y_label": "Revenue ($)",
        "categories": ["NA", "EMEA", "APAC", "LATAM"],
        "series_labels": ["H1", "H2"],
        "series_values": [
            [5200, 6800, 4400, 2900],   # H1
            [5900, 7100, 4700, 3200],   # H2
        ],
        "lookup_target": ("APAC", "H2"),
        "extreme_series": "H1", "extreme": "max",
        "compare_category": "NA",
        "notes": "annotated grouped bars; correct-by-construction",
    },

    # --- STACKED_BAR: revenue ----------------------------------------------
    {
        "chart_id": "syn_stacked_0001", "chart_type": "stacked_bar",
        "domain": "revenue_stacked", "entity": "segment",
        "title": "Revenue by Segment: Product Tier Breakdown",
        "y_label": "Revenue ($)",
        "categories": ["Consumer", "Enterprise", "SMB", "Government"],
        "series_labels": ["Basic", "Pro", "Premium"],
        "series_values": [
            [1200, 3400, 800, 500],   # Basic
            [1800, 2900, 1400, 900],  # Pro
            [1100, 2200, 900, 1000],  # Premium
        ],
        "lookup_target": ("Enterprise", "Pro"),
        "extreme": "max",
        "sum_target": "Consumer",
        "rank_direction": "top",
        "notes": "annotated stacked bars; segments >8% of max total labeled",
    },
    {
        "chart_id": "syn_stacked_0002", "chart_type": "stacked_bar",
        "domain": "revenue_stacked", "entity": "quarter",
        "title": "Quarterly Revenue by Channel",
        "y_label": "Revenue ($)",
        "categories": ["Q1", "Q2", "Q3", "Q4"],
        "series_labels": ["Organic", "Paid", "Referral"],
        "series_values": [
            [3200, 3800, 4100, 4500],  # Organic
            [1800, 2100, 2400, 2700],  # Paid
            [900, 1100, 1300, 1500],   # Referral
        ],
        "lookup_target": ("Q3", "Paid"),
        "extreme": "min",
        "sum_target": "Q2",
        "notes": "annotated stacked bars; segments >8% of max total labeled",
    },

    # --- PIE: share of spend / budget --------------------------------------
    {
        "chart_id": "syn_pie_0001", "chart_type": "pie",
        "domain": "share_circle", "entity": "channel",
        "noun": "spend",
        "title": "Marketing Spend by Channel",
        "categories": ["Paid Search", "Social", "Email", "SEO", "Display"],
        "values": [4500, 3200, 1800, 2100, 1400],
        "lookup_target": "Social",
        "extreme": "max",
        "compare_pair": ("Email", "SEO"),
        "rank_direction": "top",
        "notes": "annotated pie; slice labels show category + percentage",
    },
    {
        "chart_id": "syn_pie_0002", "chart_type": "pie",
        "domain": "share_circle", "entity": "department",
        "noun": "budget",
        "title": "FY25 Budget Allocation by Department",
        "categories": ["Engineering", "Sales", "Marketing", "Operations", "Support"],
        "values": [4500000, 2800000, 1500000, 900000, 800000],
        "lookup_target": "Marketing",
        "extreme": "min",
        "compare_pair": ("Operations", "Support"),
        "notes": "annotated pie; slice labels show category + percentage",
    },

    # --- DONUT: sales mix --------------------------------------------------
    {
        "chart_id": "syn_donut_0001", "chart_type": "donut",
        "domain": "share_circle", "entity": "category",
        "noun": "sales",
        "title": "Q4 Sales Mix by Product Category",
        "categories": ["Software", "Services", "Hardware", "Subscriptions"],
        "values": [5200, 3800, 1500, 2500],
        "lookup_target": "Services",
        "extreme": "min",
        "compare_pair": ("Subscriptions", "Services"),
        "notes": "annotated donut; slice labels show category + percentage",
    },
]


def ensure_dirs() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)


def _pluralize(word: str) -> str:
    """Small pluralizer for our entity vocabulary. Overridable via spec."""
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def _normalize_text(s: str) -> str:
    """Post-format normalization for question/answer text.

    Rules:
      - "Services's" -> "Services'"  (possessive of plural-ish nouns ending in s)
    """
    return s.replace("s's", "s'")


def _row(rid, image_rel, q, a, chart_type, task_type, difficulty, notes):
    return {
        "id": rid,
        "source": "synthetic",
        "image_path": image_rel,
        "question": _normalize_text(q),
        "answer": _normalize_text(a),
        "chart_type": chart_type,
        "task_type": task_type,
        "difficulty": difficulty,
        "verified": "true",
        "split": "train",
        "notes": notes,
    }


def _rank_top_n(labels, scores, direction, n=3):
    """Return top-n or bottom-n labels by score, ordered."""
    if direction == "top":
        idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
    else:
        idx = sorted(range(len(scores)), key=lambda i: scores[i])[:n]
    return [labels[i] for i in idx]


def _emit_rank_row(
    spec, phrasings, domain_index, image_rel,
    labels, scores, chart_type, q_index, notes,
    noun=None,
):
    """Emit one rank_order row given labels ranked by scores.
    Returns row dict or None if spec doesn't request rank_order."""
    if "rank_direction" not in spec:
        return None
    direction = spec["rank_direction"]
    ranked = _rank_top_n(labels, scores, direction, n=3)
    ans = ", ".join(ranked)
    key = "rank_order_top" if direction == "top" else "rank_order_bottom"
    entity_plural = spec.get("entity_plural", _pluralize(spec["entity"]))
    fmt_args = {"entities": entity_plural}
    if noun is not None:
        fmt_args["noun"] = noun
    q = pick(phrasings[key], domain_index).format(**fmt_args)
    return _row(
        f"{spec['chart_id']}__{q_index}", image_rel, q, ans,
        chart_type, "rank_order", "medium", notes,
    )


def build_bar_rows(spec, domain_index, overall_index):
    chart_id = spec["chart_id"]
    meta = DOMAIN_META[spec["domain"]]
    phrasings = meta["phrasings"]
    value_fmt = meta["value_fmt"]
    answer_fmt = meta["answer_fmt"]
    cats = spec["categories"]
    vals = spec["values"]
    entity = spec["entity"]

    image_rel = f"gold/images/{chart_id}.png"
    provenance = render_bar(
        cats, vals,
        title=spec["title"], y_label=spec["y_label"],
        out_path=REPO / image_rel,
        annotate=True, value_fmt=value_fmt,
    )
    provenance.update({
        "chart_id": chart_id, "domain": spec["domain"], "entity": entity,
        "overall_index": overall_index, "domain_index": domain_index,
    })

    lookup_cat = spec["lookup_target"]
    lookup_v = vals[cats.index(lookup_cat)]
    lookup_q = pick(phrasings["lookup_value"], domain_index).format(category=lookup_cat)
    lookup_a = answer_fmt.format(lookup_v)

    if spec["extreme"] == "max":
        extr_a = cats[vals.index(max(vals))]
        extr_q = pick(phrasings["max_min_highest"], domain_index).format(entity=entity)
    else:
        extr_a = cats[vals.index(min(vals))]
        extr_q = pick(phrasings["max_min_lowest"], domain_index).format(entity=entity)

    a_cat, b_cat = spec["delta_pair"]
    delta_v = vals[cats.index(a_cat)] - vals[cats.index(b_cat)]
    delta_q = pick(phrasings["delta_absolute"], domain_index).format(a=a_cat, b=b_cat)
    delta_a = answer_fmt.format(delta_v)

    notes = spec["notes"]
    rows = [
        _row(f"{chart_id}__q1", image_rel, lookup_q, lookup_a, "bar", "lookup_value", "easy", notes),
        _row(f"{chart_id}__q2", image_rel, extr_q, extr_a, "bar", "max_min", "easy", notes),
        _row(f"{chart_id}__q3", image_rel, delta_q, delta_a, "bar", "delta_absolute", "medium", notes),
    ]

    # optional rank_order
    r = _emit_rank_row(spec, phrasings, domain_index, image_rel,
                      cats, vals, "bar", "q4", notes)
    if r:
        rows.append(r)

    # optional hard_multi_step (combined-exceeds)
    if "hard_triple" in spec:
        a_cat, b_cat, c_cat = spec["hard_triple"]
        combined = vals[cats.index(a_cat)] + vals[cats.index(b_cat)]
        target = vals[cats.index(c_cat)]
        hard_a = "Yes" if combined > target else "No"
        hard_q = pick(phrasings["hard_multi_step"], domain_index).format(
            a=a_cat, b=b_cat, c=c_cat,
        )
        rows.append(_row(f"{chart_id}__q5", image_rel, hard_q, hard_a,
                         "bar", "hard_multi_step", "hard", notes))

    return rows, provenance


def build_line_rows(spec, domain_index, overall_index):
    chart_id = spec["chart_id"]
    meta = DOMAIN_META[spec["domain"]]
    phrasings = meta["phrasings"]
    value_fmt = meta["value_fmt"]
    answer_fmt = meta["answer_fmt"]
    xs = spec["x_labels"]
    vals = spec["values"]
    entity = spec["entity"]

    image_rel = f"gold/images/{chart_id}.png"
    provenance = render_line(
        xs, vals,
        title=spec["title"], y_label=spec["y_label"],
        out_path=REPO / image_rel,
        annotate=True, value_fmt=value_fmt,
    )
    provenance.update({
        "chart_id": chart_id, "domain": spec["domain"], "entity": entity,
        "overall_index": overall_index, "domain_index": domain_index,
    })

    lookup_x = spec["lookup_target"]
    lookup_v = vals[xs.index(lookup_x)]
    lookup_q = pick(phrasings["lookup_value"], domain_index).format(category=lookup_x)
    lookup_a = answer_fmt.format(lookup_v)

    if spec["extreme"] == "max":
        extr_a = xs[vals.index(max(vals))]
        extr_q = pick(phrasings["max_min_highest"], domain_index).format(entity=entity)
    else:
        extr_a = xs[vals.index(min(vals))]
        extr_q = pick(phrasings["max_min_lowest"], domain_index).format(entity=entity)

    ta, tb = spec["trend_pair"]
    va, vb = vals[xs.index(ta)], vals[xs.index(tb)]
    trend_a = "Increased" if vb > va else ("Decreased" if vb < va else "Unchanged")
    trend_q = pick(phrasings["trend_direction"], domain_index).format(a=ta, b=tb)

    pa, pb = spec["pct_pair"]
    va2, vb2 = vals[xs.index(pa)], vals[xs.index(pb)]
    pct = (vb2 - va2) / va2 * 100.0
    pct_a = f"{pct:.1f}%"
    pct_q = pick(phrasings["percent_change_ratio"], domain_index).format(a=pa, b=pb)

    notes = spec["notes"]
    rows = [
        _row(f"{chart_id}__q1", image_rel, lookup_q, lookup_a, "line", "lookup_value", "easy", notes),
        _row(f"{chart_id}__q2", image_rel, extr_q, extr_a, "line", "max_min", "easy", notes),
        _row(f"{chart_id}__q3", image_rel, trend_q, trend_a, "line", "trend_direction", "easy", notes),
        _row(f"{chart_id}__q4", image_rel, pct_q, pct_a, "line", "percent_change_ratio", "medium", notes),
    ]

    # optional hard_multi_step: compare two deltas
    if "hard_delta_pairs" in spec:
        (a1, b1), (a2, b2) = spec["hard_delta_pairs"]
        d1 = vals[xs.index(b1)] - vals[xs.index(a1)]
        d2 = vals[xs.index(b2)] - vals[xs.index(a2)]
        hard_a = "Yes" if d1 > d2 else "No"
        hard_q = pick(phrasings["hard_multi_step"], domain_index).format(
            a1=a1, b1=b1, a2=a2, b2=b2,
        )
        rows.append(_row(f"{chart_id}__q5", image_rel, hard_q, hard_a,
                         "line", "hard_multi_step", "hard", notes))
    return rows, provenance


def build_grouped_rows(spec, domain_index, overall_index):
    chart_id = spec["chart_id"]
    meta = DOMAIN_META[spec["domain"]]
    phrasings = meta["phrasings"]
    value_fmt = meta["value_fmt"]
    answer_fmt = meta["answer_fmt"]
    cats = spec["categories"]
    series_labels = spec["series_labels"]
    series_values = spec["series_values"]
    entity = spec["entity"]
    series_axis = spec["series_axis"]

    image_rel = f"gold/images/{chart_id}.png"
    provenance = render_grouped_bar(
        cats, series_values, series_labels,
        title=spec["title"], y_label=spec["y_label"],
        out_path=REPO / image_rel,
        annotate=True, value_fmt=value_fmt,
    )
    provenance.update({
        "chart_id": chart_id, "domain": spec["domain"], "entity": entity,
        "series_axis": series_axis,
        "overall_index": overall_index, "domain_index": domain_index,
    })

    # lookup_value
    lookup_cat, lookup_series = spec["lookup_target"]
    si = series_labels.index(lookup_series)
    ci = cats.index(lookup_cat)
    lookup_v = series_values[si][ci]
    lookup_q = pick(phrasings["lookup_value"], domain_index).format(
        category=lookup_cat, series=lookup_series
    )
    lookup_a = answer_fmt.format(lookup_v)

    # max_min within a specific series
    ex_series = spec["extreme_series"]
    ex_si = series_labels.index(ex_series)
    ex_vals = series_values[ex_si]
    if spec["extreme"] == "max":
        extr_a = cats[ex_vals.index(max(ex_vals))]
        extr_q = pick(phrasings["max_min_highest"], domain_index).format(
            entity=entity, series=ex_series
        )
    else:
        extr_a = cats[ex_vals.index(min(ex_vals))]
        extr_q = pick(phrasings["max_min_lowest"], domain_index).format(
            entity=entity, series=ex_series
        )

    # multi_series_compare: assumes exactly 2 series
    cmp_cat = spec["compare_category"]
    cmp_ci = cats.index(cmp_cat)
    sa, sb = series_labels[0], series_labels[1]
    va, vb = series_values[0][cmp_ci], series_values[1][cmp_ci]
    cmp_a = sa if va > vb else (sb if vb > va else "Same")
    cmp_q = pick(phrasings["multi_series_compare"], domain_index).format(
        category=cmp_cat, series_axis=series_axis,
        series_a=sa, series_b=sb,
    )

    notes = spec["notes"]
    rows = [
        _row(f"{chart_id}__q1", image_rel, lookup_q, lookup_a, "grouped_bar", "lookup_value", "easy", notes),
        _row(f"{chart_id}__q2", image_rel, extr_q, extr_a, "grouped_bar", "max_min", "easy", notes),
        _row(f"{chart_id}__q3", image_rel, cmp_q, cmp_a, "grouped_bar", "multi_series_compare", "medium", notes),
    ]

    # optional hard_multi_step: compare (cat, series) tuples across the grid
    if "hard_compare_pair" in spec:
        (cat1, series1), (cat2, series2) = spec["hard_compare_pair"]
        v1 = series_values[series_labels.index(series1)][cats.index(cat1)]
        v2 = series_values[series_labels.index(series2)][cats.index(cat2)]
        hard_a = "Yes" if v1 > v2 else "No"
        hard_q = pick(phrasings["hard_multi_step"], domain_index).format(
            cat1=cat1, series_a=series1, cat2=cat2, series_b=series2,
        )
        rows.append(_row(f"{chart_id}__q4", image_rel, hard_q, hard_a,
                         "grouped_bar", "hard_multi_step", "hard", notes))
    return rows, provenance


def build_stacked_rows(spec, domain_index, overall_index):
    chart_id = spec["chart_id"]
    meta = DOMAIN_META[spec["domain"]]
    phrasings = meta["phrasings"]
    value_fmt = meta["value_fmt"]
    answer_fmt = meta["answer_fmt"]
    cats = spec["categories"]
    series_labels = spec["series_labels"]
    series_values = spec["series_values"]
    entity = spec["entity"]

    image_rel = f"gold/images/{chart_id}.png"
    provenance = render_stacked_bar(
        cats, series_values, series_labels,
        title=spec["title"], y_label=spec["y_label"],
        out_path=REPO / image_rel,
        annotate=True, value_fmt=value_fmt,
    )
    provenance.update({
        "chart_id": chart_id, "domain": spec["domain"], "entity": entity,
        "overall_index": overall_index, "domain_index": domain_index,
    })

    # totals per category
    totals = [sum(sv[i] for sv in series_values) for i in range(len(cats))]

    # lookup: (category, series) -> single stack segment value
    lookup_cat, lookup_series = spec["lookup_target"]
    si = series_labels.index(lookup_series)
    ci = cats.index(lookup_cat)
    lookup_v = series_values[si][ci]
    lookup_q = pick(phrasings["lookup_value"], domain_index).format(
        category=lookup_cat, series=lookup_series
    )
    lookup_a = answer_fmt.format(lookup_v)

    # max_min: which category has highest/lowest total stack
    if spec["extreme"] == "max":
        extr_a = cats[totals.index(max(totals))]
        extr_q = pick(phrasings["max_min_highest"], domain_index).format(entity=entity)
    else:
        extr_a = cats[totals.index(min(totals))]
        extr_q = pick(phrasings["max_min_lowest"], domain_index).format(entity=entity)

    # aggregation_sum_avg: total across all series for a category
    sum_cat = spec["sum_target"]
    sci = cats.index(sum_cat)
    sum_v = sum(sv[sci] for sv in series_values)
    sum_q = pick(phrasings["aggregation_sum_avg"], domain_index).format(category=sum_cat)
    sum_a = answer_fmt.format(sum_v)

    notes = spec["notes"]
    # stacked lookup + max_min are visually harder — bump difficulty
    rows = [
        _row(f"{chart_id}__q1", image_rel, lookup_q, lookup_a, "stacked_bar", "lookup_value", "medium", notes),
        _row(f"{chart_id}__q2", image_rel, extr_q, extr_a, "stacked_bar", "max_min", "medium", notes),
        _row(f"{chart_id}__q3", image_rel, sum_q, sum_a, "stacked_bar", "aggregation_sum_avg", "medium", notes),
    ]

    # optional rank_order by total
    r = _emit_rank_row(spec, phrasings, domain_index, image_rel,
                      cats, totals, "stacked_bar", "q4", notes)
    if r:
        rows.append(r)
    return rows, provenance


def build_pie_like_rows(spec, domain_index, overall_index):
    """Shared row builder for pie and donut charts."""
    chart_id = spec["chart_id"]
    ct = spec["chart_type"]  # "pie" or "donut"
    meta = DOMAIN_META[spec["domain"]]
    phrasings = meta["phrasings"]
    cats = spec["categories"]
    vals = spec["values"]
    entity = spec["entity"]
    noun = spec["noun"]

    total = sum(vals)
    percents = [v / total * 100 for v in vals]

    image_rel = f"gold/images/{chart_id}.png"
    if ct == "pie":
        provenance = render_pie(cats, vals, spec["title"], REPO / image_rel, annotate=True)
    elif ct == "donut":
        provenance = render_donut(cats, vals, spec["title"], REPO / image_rel, annotate=True)
    else:
        raise ValueError(f"unexpected pie-like chart_type: {ct}")
    provenance.update({
        "chart_id": chart_id, "domain": spec["domain"], "entity": entity,
        "noun": noun,
        "overall_index": overall_index, "domain_index": domain_index,
    })

    # lookup_value -> percentage
    lookup_cat = spec["lookup_target"]
    lookup_pct = percents[cats.index(lookup_cat)]
    lookup_q = pick(phrasings["lookup_value"], domain_index).format(
        category=lookup_cat, noun=noun
    )
    lookup_a = f"{lookup_pct:.1f}%"

    # max_min -> category name
    if spec["extreme"] == "max":
        extr_a = cats[vals.index(max(vals))]
        extr_q = pick(phrasings["max_min_highest"], domain_index).format(
            entity=entity, noun=noun
        )
    else:
        extr_a = cats[vals.index(min(vals))]
        extr_q = pick(phrasings["max_min_lowest"], domain_index).format(
            entity=entity, noun=noun
        )

    # compare_categories -> Yes / No
    a_cat, b_cat = spec["compare_pair"]
    cmp_a = "Yes" if vals[cats.index(a_cat)] > vals[cats.index(b_cat)] else "No"
    cmp_q = pick(phrasings["compare_categories"], domain_index).format(
        a=a_cat, b=b_cat, noun=noun
    )

    notes = spec["notes"]
    rows = [
        _row(f"{chart_id}__q1", image_rel, lookup_q, lookup_a, ct, "lookup_value", "easy", notes),
        _row(f"{chart_id}__q2", image_rel, extr_q, extr_a, ct, "max_min", "easy", notes),
        _row(f"{chart_id}__q3", image_rel, cmp_q, cmp_a, ct, "compare_categories", "medium", notes),
    ]

    # optional rank_order by raw values (== rank by share)
    r = _emit_rank_row(spec, phrasings, domain_index, image_rel,
                      cats, vals, ct, "q4", notes, noun=noun)
    if r:
        rows.append(r)
    return rows, provenance


def build_rows_for_chart(spec, domain_index, overall_index):
    ct = spec["chart_type"]
    if ct == "bar":
        return build_bar_rows(spec, domain_index, overall_index)
    if ct == "line":
        return build_line_rows(spec, domain_index, overall_index)
    if ct == "grouped_bar":
        return build_grouped_rows(spec, domain_index, overall_index)
    if ct == "stacked_bar":
        return build_stacked_rows(spec, domain_index, overall_index)
    if ct in ("pie", "donut"):
        return build_pie_like_rows(spec, domain_index, overall_index)
    raise ValueError(f"unknown chart_type: {ct}")


def main() -> None:
    ensure_dirs()
    with MANIFEST.open("w", newline="") as f:
        csv.writer(f).writerow(MANIFEST_COLS)

    domain_counters: dict[str, int] = {d: 0 for d in DOMAIN_META}
    per_chart_type: dict[str, int] = {}
    total_rows = 0
    for overall_index, spec in enumerate(CHART_SPECS):
        dom = spec["domain"]
        domain_index = domain_counters[dom]
        rows, prov = build_rows_for_chart(spec, domain_index, overall_index)
        (RAW / f"{spec['chart_id']}.json").write_text(json.dumps(prov, indent=2))
        with MANIFEST.open("a", newline="") as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow([r.get(c, "") for c in MANIFEST_COLS])
        domain_counters[dom] += 1
        per_chart_type[spec["chart_type"]] = per_chart_type.get(spec["chart_type"], 0) + 1
        total_rows += len(rows)

    print(f"generated {total_rows} rows across {len(CHART_SPECS)} charts")
    print("  by chart_type:")
    for ct, n in per_chart_type.items():
        print(f"    {ct}: {n}")
    print("  by domain:")
    for dom, n in domain_counters.items():
        if n:
            print(f"    {dom}: {n}")


if __name__ == "__main__":
    main()
