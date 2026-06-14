#!/usr/bin/env python3
"""curate.py — select the highest-value subset of a generated pool for the
limited Adaption row budget, split by hackathon part.

Usage:
    python scripts/curate.py --pool data/canonical/train.jsonl \
        --part1-rows 8000 --part2-rows 12000 --out data/curated

Outputs (per part):
    data/curated/part1_canonical.jsonl   selected figures (full objects)
    data/curated/part1_flat.jsonl        flattened task rows (Adaption-ready shape)
    data/curated/part2_canonical.jsonl
    data/curated/part2_flat.jsonl
    data/curated/report.json             selection stats per part
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chartgen.curation import select_for_budget, flatten_fig_dict, score_figure


def load_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: str, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, help="canonical JSONL of the full generated pool")
    ap.add_argument("--part1-rows", type=int, default=8000)
    ap.add_argument("--part2-rows", type=int, default=12000)
    ap.add_argument("--out", default="data/curated")
    args = ap.parse_args()

    figs = load_jsonl(args.pool)
    os.makedirs(args.out, exist_ok=True)

    full_report = {}
    for part, budget in (("part1_marketing", args.part1_rows), ("part2_chart", args.part2_rows)):
        part_figs = [f for f in figs if f.get("part") == part]
        selected, report = select_for_budget(part_figs, budget)
        short = "part1" if part.startswith("part1") else "part2"

        write_jsonl(os.path.join(args.out, f"{short}_canonical.jsonl"), selected)
        flat = [row for fig in selected for row in flatten_fig_dict(fig)]
        write_jsonl(os.path.join(args.out, f"{short}_flat.jsonl"), flat)

        report["flat_rows_written"] = len(flat)
        full_report[part] = report
        print(f"[{part}] {report['figures_selected']}/{report['figures_available']} figures "
              f"-> {report['rows_used']} rows (budget {budget}); "
              f"mean score {report['mean_score_selected']} vs pool {report['mean_score_pool']}")
        for bucket, n in sorted(report["per_bucket"].items()):
            print(f"    {bucket}: {n}")

    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"Report: {os.path.join(args.out, 'report.json')}")


if __name__ == "__main__":
    main()
