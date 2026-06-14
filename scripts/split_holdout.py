#!/usr/bin/env python3
"""split_holdout.py — carve an eval holdout out of a generated pool BEFORE curation.

The holdout is our benchmark for "did the trained model actually improve."
It must be split off before the premium training set is selected, and it must
never be uploaded to Adaption or shown to AutoScientist.

Splits at the FIGURE level (never the task level — tasks from one figure share
an image, so splitting them across train/holdout leaks the image). Stratified
by (part, chart_type, difficulty) so the holdout mirrors the pool.

Usage:
    python scripts/split_holdout.py --pool data_full/canonical/train.jsonl \
        --holdout-frac 0.15 --out data_full/split

Outputs:
    data_full/split/train_pool.jsonl   -> feed THIS to curate.py
    data_full/split/holdout.jsonl      -> NEVER upload; eval only
    data_full/split/holdout_flat.jsonl -> flattened tasks for the eval harness
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chartgen.curation import flatten_fig_dict


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
    ap.add_argument("--holdout-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/split")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    figs = load_jsonl(args.pool)

    strata = defaultdict(list)
    for f in figs:
        strata[(f.get("part"), f.get("chart_type"), f.get("difficulty"))].append(f)

    train, holdout = [], []
    for key, group in strata.items():
        rng.shuffle(group)
        k = max(1, round(len(group) * args.holdout_frac)) if len(group) > 1 else 0
        holdout.extend(group[:k])
        train.extend(group[k:])

    os.makedirs(args.out, exist_ok=True)
    write_jsonl(os.path.join(args.out, "train_pool.jsonl"), train)
    write_jsonl(os.path.join(args.out, "holdout.jsonl"), holdout)
    flat = [row for fig in holdout for row in flatten_fig_dict(fig)]
    write_jsonl(os.path.join(args.out, "holdout_flat.jsonl"), flat)

    print(f"Pool: {len(figs)} figures")
    print(f"  train_pool: {len(train)} figures -> {os.path.join(args.out, 'train_pool.jsonl')}")
    print(f"  holdout:    {len(holdout)} figures ({len(flat)} tasks) -> NEVER upload")
    per = defaultdict(lambda: [0, 0])
    for f in train:
        per[(f.get("part"), f.get("chart_type"))][0] += 1
    for f in holdout:
        per[(f.get("part"), f.get("chart_type"))][1] += 1
    for k in sorted(per, key=str):
        tr, ho = per[k]
        print(f"    {k}: train {tr} / holdout {ho}")


if __name__ == "__main__":
    main()
