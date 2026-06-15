#!/usr/bin/env python3
"""build_part1_text.py — build the Part 1 (marketing, TEXT) dataset from a
canonical figure pool. AutoScientist can't train multimodal in Part 1, so the
chart render is replaced by six text serializations of the same ground truth.

Each figure is serialized in 1-2 forms (render twins: same QA, different text),
QA is filtered/rewritten for text mode, and rows are written as:
    prompt   = the question
    context  = the serialized report text
    completion = ground-truth JSON answer
    reasoning  = our deterministic trace
    meta_*     = slicing columns (unmapped in Adaption)

Usage:
    python scripts/build_part1_text.py --pool data_full/split/train_pool.jsonl \
        --out data_full/part1_text --forms-per-fig 2 --seed 11

Outputs:
    part1_text_flat.jsonl   all task rows
    part1_text.parquet      upload-ready (File tab; no images involved)
    sample_preview.txt      first few serializations for eyeballing
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chartgen.serialize import (
    serialize_figure, pick_form, rewrite_prompt, EXTRACTION_FORMS, FORM_WEIGHTS,
)

# QA types that reference visual attributes -> meaningless/unanswerable in text
DROP_QA_TYPES = {"visual_reference"}

# QA whose answer is computed over the WHOLE table (denominator = all rows, or
# sum of all rows). These may ONLY attach to forms that render every row AND do
# not introduce competing/partial figures, or the stated answer won't match what
# is visible in the text.
#
# NOTE: 'noisy' is deliberately EXCLUDED here. By design it renders partial
# breakdowns and can surface a competing per-period total, so a whole-table sum
# or share-of-total becomes genuinely ambiguous against the visible text
# (verified: the only gate failures at 98.3% were compute_sum on noisy, where the
# platform correctly read a stated total instead of re-summing a partial list).
# Noisy KEEPS the QA types where distractors are fair game (retrieve_value,
# find_extremum, compute_difference between two named values, etc.).
WHOLE_TABLE_QA = {"compute_ratio_percent", "compute_sum"}
FULL_TABLE_FORMS = {"markdown_table", "compact_block", "pivoted",
                    "bullet_summary", "analyst_prose"}


def load_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rows_for_figure(fig, form: str, text: str):
    """Flatten one serialized figure into task rows (text mode)."""
    out = []
    base_meta = {
        "chart_type": fig.get("chart_type"),
        "figure_kind": fig.get("figure_kind"),
        "difficulty": fig.get("difficulty"),
        "text_form": form,
    }
    tasks = fig.get("tasks", {})

    te = tasks.get("table_extraction")
    if te and form in EXTRACTION_FORMS:
        target = dict(te["target"])
        out.append({
            "id": f"{fig['id']}__{form}__table",
            "prompt": "Extract all quantitative data from this report into a normalized JSON table.",
            "context": text,
            "completion": json.dumps(target, ensure_ascii=False),
            "reasoning": "",
            "meta_part": "part1_marketing_text",
            "meta_qa_type": "table_extraction",
            **{f"meta_{k}": v for k, v in base_meta.items()},
        })

    for i, qa in enumerate(tasks.get("qa", [])):
        qa_type = qa.get("qa_type", "")
        if qa_type in DROP_QA_TYPES:
            continue
        # whole-table QA only on forms that render every row
        if qa_type in WHOLE_TABLE_QA and form not in FULL_TABLE_FORMS:
            continue
        target = dict(qa["target"])
        reasoning = target.pop("reasoning", "") or ""
        out.append({
            "id": f"{fig['id']}__{form}__qa_{i:02d}",
            "prompt": rewrite_prompt(qa["prompt"]),
            "context": text,
            "completion": json.dumps(target, ensure_ascii=False),
            "reasoning": reasoning,
            "meta_part": "part1_marketing_text",
            "meta_qa_type": qa.get("qa_type", ""),
            **{f"meta_{k}": v for k, v in base_meta.items()},
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, help="canonical JSONL (train_pool, NOT holdout)")
    ap.add_argument("--out", default="data_full/part1_text")
    ap.add_argument("--forms-per-fig", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    figs = load_jsonl(args.pool)
    os.makedirs(args.out, exist_ok=True)

    all_rows = []
    form_counts = {}
    previews = []
    for fig in figs:
        forms = set()
        while len(forms) < args.forms_per_fig:
            forms.add(pick_form(rng))
        for form in forms:
            text = serialize_figure(fig, form, rng)
            form_counts[form] = form_counts.get(form, 0) + 1
            rows = rows_for_figure(fig, form, text)
            all_rows.extend(rows)
            if len(previews) < 6:
                previews.append(f"===== {fig['id']} [{form}] =====\n{text}\n")

    flat_path = os.path.join(args.out, "part1_text_flat.jsonl")
    with open(flat_path, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pq_path = os.path.join(args.out, "part1_text.parquet")
    import pandas as pd
    pd.DataFrame(all_rows).to_parquet(pq_path, index=False)

    prev_path = os.path.join(args.out, "sample_preview.txt")
    with open(prev_path, "w", encoding="utf-8") as f:
        f.write("\n".join(previews))

    print(f"Figures: {len(figs)} -> task rows: {len(all_rows)}")
    print("Form distribution (figure-serializations):")
    for k, v in sorted(form_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}   (target weight {FORM_WEIGHTS[k]:.2f})")
    print(f"  flat:    {flat_path}")
    print(f"  parquet: {pq_path}  <- upload this via File tab")
    print(f"  preview: {prev_path}  <- read this first")


if __name__ == "__main__":
    main()
