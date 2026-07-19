#!/usr/bin/env python3
"""build_eval_holdout.py — build a HELD-OUT eval set the model never trained on.

Uses a fresh seed (different figures, values, phrasings) at the same
distribution as training. This measures whether the model LEARNED the task
rather than memorized rows.

Produces:
  <out>/eval_manifest.jsonl  — one row per task with gold answer and buckets
  <out>/renders/*.png        — the eval images

Usage:
  python scripts/build_eval_holdout.py --out eval_holdout --seed 777 \
      --bar 12 --line 12 --grouped 8 --stacked 8 --dashboard 6 --funnel 6

Then run your model over the manifest's prompts + image_paths and write a
predictions JSONL with the same `id` keys plus a `pred` field. Feed both to
`score_eval.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

# make chartgen importable when script is run from repo root
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "src"))

from chartgen import generator as g  # noqa: E402


BUILDERS = {
    "bar": (g.build_bar, ["easy", "hard"]),   # split across two difficulties
    "line": (g.build_line, ["easy"]),
    "grouped": (g.build_grouped, ["medium"]),
    "stacked": (g.build_stacked, ["hard"]),
    "dashboard": (g.build_dashboard, ["medium"]),
    "funnel": (g.build_funnel, ["medium"]),
}


def _emit_row(ex, base: dict, task_type: str, task) -> dict:
    row = dict(base)
    row["task_type"] = task_type
    row["prompt"] = task.prompt
    if task_type == "qa":
        row["id"] = f"{ex.id}__qa_{task.qa_type}_{base['_seq']:02d}"
        row["qa_type"] = task.qa_type
        row["gold"] = {
            "answer": str(task.target.answer),
            "aliases": [str(a) for a in (task.aliases or [])],
            "answer_type": task.target.answer_type,
        }
    else:
        row["id"] = f"{ex.id}__table"
        row["qa_type"] = ""
        row["gold"] = {
            "title": task.target.title,
            "chart_type": task.target.chart_type,
            "table": task.target.table.to_dict()
                if hasattr(task.target.table, "to_dict")
                else {
                    "columns": task.target.table.columns,
                    "rows": task.target.table.rows,
                    "units": task.target.table.units,
                },
        }
    row.pop("_seq", None)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument(
        "--seed",
        type=int,
        default=777,
        help="random seed — MUST differ from training seed (11) to be a real holdout",
    )
    for fam in BUILDERS:
        ap.add_argument(f"--{fam}", type=int, default=8)
    args = ap.parse_args()

    if args.seed == 11:
        sys.exit("ERROR: seed 11 is the training seed. Pick a different one.")

    render_dir = os.path.join(args.out, "renders")
    os.makedirs(render_dir, exist_ok=True)

    random.seed(args.seed)
    rows = []
    idx = 0
    n_fig = 0

    for fam, (build_fn, diffs) in BUILDERS.items():
        n = getattr(args, fam)
        if n <= 0:
            continue
        # spread requested count across the difficulties for coverage
        per_diff = [n // len(diffs)] * len(diffs)
        for k in range(n - sum(per_diff)):
            per_diff[k] += 1
        for diff, cnt in zip(diffs, per_diff):
            for _ in range(cnt):
                ex = build_fn(idx, render_dir=render_dir, difficulty=diff)
                idx += 1
                n_fig += 1
                base = {
                    "parent_id": ex.id,
                    "chart_type": ex.chart_type,
                    "difficulty": ex.difficulty,
                    "annotated": ex.render.style.show_values,
                    "image_path": ex.artifacts.image_path,
                }
                # table extraction row
                base["_seq"] = 0
                rows.append(_emit_row(ex, base, "table_extraction", ex.tasks_table_extraction))
                # QA rows
                for i, qa in enumerate(ex.tasks_qa):
                    base["_seq"] = i
                    rows.append(_emit_row(ex, base, "qa", qa))

    manifest_path = os.path.join(args.out, "eval_manifest.jsonl")
    with open(manifest_path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_qa = sum(1 for r in rows if r["task_type"] == "qa")
    n_te = sum(1 for r in rows if r["task_type"] == "table_extraction")
    n_ann = sum(1 for r in rows if r["annotated"])
    print(
        f"eval set: {n_fig} figures -> {len(rows)} tasks "
        f"({n_qa} QA + {n_te} table) | annotated {n_ann}, unannotated {len(rows)-n_ann}"
    )
    print(f"manifest -> {manifest_path}")
    print(f"images   -> {render_dir}/")
    print(f"seed {args.seed} != training seed 11: no figure overlap with training data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
