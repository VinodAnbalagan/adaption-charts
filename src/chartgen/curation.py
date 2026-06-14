"""curation.py — score and select the highest-value figures for the limited
Adaption budget (~20k adapted ROWS ≈ ~4k figures at current tasks/figure).

Principle: the budget should buy maximum DIFFICULTY + DIVERSITY, not whatever
the RNG happened to produce. Two parts:

  1. score_figure(fig_dict) -> float        (value of one figure)
  2. select_for_budget(figs, row_budget)    (diversity-enforced greedy selection)

Operates on CANONICAL JSONL dicts (the output of export_canonical_jsonl), so it
can run on any previously generated pool without re-instantiating dataclasses.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Any, List, Tuple

# -------------------------
# Scoring weights
# -------------------------

# Documented-weak chart types are worth the most (the wedge).
CHART_TYPE_WEIGHT = {
    "stacked_bar": 3.0,
    "grouped_bar": 2.5,
    "multi_panel": 2.5,
    "combo": 2.0,
    "scatter": 1.8,
    "area": 1.5,
    "multi_line": 1.5,
    "line": 1.2,
    "bar": 1.0,
    "funnel": 1.5,
    "table_only": 1.0,
}

DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}

# QA types that force multi-step visual+numeric reasoning are worth more.
QA_TYPE_BONUS = {
    "multi_panel_linked_reasoning": 0.6,
    "diagnostic": 0.5,
    "compute_sum": 0.4,
    "compute_ratio_percent": 0.4,
    "funnel_conversion": 0.4,
    "visual_reference": 0.35,
    "compute_difference": 0.3,
    "multi_series_lookup": 0.3,
    "rank_order": 0.3,
    "threshold_count": 0.3,
    "hypothetical": 0.3,
    "unanswerable": 0.3,
    "compare_values": 0.2,
    "find_extremum": 0.15,
    "trend_direction": 0.15,
    "identify_category_by_value": 0.2,
    "retrieve_value": 0.1,
    "compute_sum_": 0.0,
}


def n_rows(fig: Dict[str, Any]) -> int:
    """How many flattened task rows this figure becomes."""
    tasks = fig.get("tasks", {})
    n = 1 if tasks.get("table_extraction") else 0
    n += len(tasks.get("qa", []))
    return n


def score_figure(fig: Dict[str, Any]) -> float:
    """Higher = more valuable to spend budget on."""
    base = CHART_TYPE_WEIGHT.get(fig.get("chart_type", "bar"), 1.0)
    base *= DIFFICULTY_WEIGHT.get(fig.get("difficulty", "easy"), 1.0)

    # QA-type variety: sum of distinct-type bonuses (variety > repetition).
    qa_types = {q.get("qa_type") for q in fig.get("tasks", {}).get("qa", [])}
    base += sum(QA_TYPE_BONUS.get(t, 0.1) for t in qa_types)

    # Nuisance factors = realism stress, worth a bit.
    nuis = fig.get("render", {}).get("nuisance", {})
    base += 0.15 * sum(1 for v in nuis.values() if v)

    # Format diversity: percent/currency/ratio units are harder than counts.
    units = set((fig.get("data", {}).get("table", {}).get("units") or {}).values())
    base += 0.2 * len(units & {"percent", "currency", "ratio"})

    # Dashboard richness: KPIs + extra tables in the extraction target.
    te = fig.get("tasks", {}).get("table_extraction") or {}
    tgt = te.get("target", {})
    base += 0.3 * len(tgt.get("kpis", []))
    base += 0.3 * len(tgt.get("extra_tables", []))

    return base


def select_for_budget(
    figs: List[Dict[str, Any]],
    row_budget: int,
    bucket_key=lambda f: (f.get("part"), f.get("chart_type")),
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Diversity-enforced greedy selection.

    Buckets figures by (part, chart_type), sorts each bucket by score desc,
    then round-robins across buckets taking the best remaining figure each
    pass, until adding another would exceed row_budget. Guarantees no single
    chart type floods the quota while still preferring high-value figures.

    Returns (selected_figs, report).
    """
    buckets: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for f in figs:
        buckets[bucket_key(f)].append(f)
    for k in buckets:
        buckets[k].sort(key=score_figure, reverse=True)

    order = sorted(buckets.keys(), key=lambda k: -max(score_figure(f) for f in buckets[k]))
    idx = {k: 0 for k in buckets}
    selected: List[Dict[str, Any]] = []
    used_rows = 0
    progressed = True

    while progressed:
        progressed = False
        for k in order:
            i = idx[k]
            if i >= len(buckets[k]):
                continue
            fig = buckets[k][i]
            cost = n_rows(fig)
            if used_rows + cost > row_budget:
                idx[k] = len(buckets[k])  # bucket can't fit anything cheaper reliably; close it
                continue
            selected.append(fig)
            used_rows += cost
            idx[k] = i + 1
            progressed = True

    report = {
        "row_budget": row_budget,
        "rows_used": used_rows,
        "figures_selected": len(selected),
        "figures_available": len(figs),
        "per_bucket": {
            str(k): sum(1 for f in selected if bucket_key(f) == k) for k in buckets
        },
        "mean_score_selected": (
            round(sum(score_figure(f) for f in selected) / len(selected), 3) if selected else 0.0
        ),
        "mean_score_pool": (
            round(sum(score_figure(f) for f in figs) / len(figs), 3) if figs else 0.0
        ),
    }
    return selected, report


# -------------------------
# Dict-based flatten (mirror of FigureExample.flatten_tasks, for JSONL dicts)
# -------------------------

def flatten_fig_dict(fig: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    tasks = fig.get("tasks", {})
    base_meta = {
        "chart_type": fig.get("chart_type"),
        "figure_kind": fig.get("figure_kind"),
        "difficulty": fig.get("difficulty"),
        **(fig.get("metadata") or {}),
    }
    te = tasks.get("table_extraction")
    if te:
        rows.append({
            "id": f"{fig['id']}__table",
            "parent_id": fig["id"],
            "task_type": "table_extraction",
            "part": fig.get("part"),
            "domain": fig.get("domain"),
            "image_path": fig.get("artifacts", {}).get("image_path"),
            "prompt": te["prompt"],
            "target_json": te["target"],
            "metadata": base_meta,
        })
    for i, qa in enumerate(tasks.get("qa", [])):
        rows.append({
            "id": f"{fig['id']}__qa_{i:02d}",
            "parent_id": fig["id"],
            "task_type": "qa",
            "part": fig.get("part"),
            "domain": fig.get("domain"),
            "image_path": fig.get("artifacts", {}).get("image_path"),
            "prompt": qa["prompt"],
            "target_json": qa["target"],
            "metadata": {**base_meta, "qa_type": qa.get("qa_type")},
        })
    return rows
