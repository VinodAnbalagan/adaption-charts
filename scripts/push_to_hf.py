#!/usr/bin/env python3
"""push_to_hf.py — convert flat JSONL (from curate.py / build_pilot.py) into a
Hugging Face dataset with a proper Image feature, for the UI-first Adaption flow:

    HF dataset  ->  Adaption UI "import from Hugging Face"  ->  Adaptive Data wizard
                ->  AutoScientist

Creates TWO splits per part so the UI can adapt them with different settings:
    table   (table_extraction rows -> reasoning_traces OFF in the wizard)
    qa      (qa rows               -> reasoning_traces ON is fine)

Usage:
  # dry run: build dataset locally, print schema + sample, save to disk
  python scripts/push_to_hf.py --flat data/curated/part2_flat.jsonl --local-dir data/hf_part2

  # push to the Hub (needs `huggingface-cli login` or HF_TOKEN env var)
  python scripts/push_to_hf.py --flat data/curated/part2_flat.jsonl \
      --repo vinod-anbalagan/adaption-charts-part2 --private

Wizard column mapping (per the MathVision pattern):
    prompt     -> prompt column
    image      -> context column (image)
    completion -> completion column
    reasoning  -> leave unmapped (ours; for later A/B + audit)
    meta_*     -> leave unmapped (slicing / error analysis)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:  # load .env from repo root (HF_TOKEN, ADAPTION_API_KEY)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass


def load_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def to_records(flat_rows):
    """Split rows by task type; keep image as a PATH (datasets lazily loads it)."""
    splits = {"table": [], "qa": []}
    missing = 0
    for r in flat_rows:
        img = r.get("image_path")
        if not img or not os.path.exists(img):
            missing += 1
            continue
        target = dict(r["target_json"])
        reasoning = target.pop("reasoning", None)
        rec = {
            "id": r["id"],
            "prompt": r["prompt"],
            "image": img,  # cast to Image() below
            "completion": json.dumps(target, ensure_ascii=False),
            "reasoning": reasoning or "",
            "meta_part": r.get("part") or "",
            "meta_chart_type": (r.get("metadata") or {}).get("chart_type") or "",
            "meta_difficulty": (r.get("metadata") or {}).get("difficulty") or "",
            "meta_qa_type": (r.get("metadata") or {}).get("qa_type") or "",
        }
        splits["table" if r["task_type"] == "table_extraction" else "qa"].append(rec)
    if missing:
        print(f"WARNING: {missing} rows skipped (image file not found)")
    return splits


def build_dataset_dict(splits):
    from datasets import Dataset, DatasetDict, Features, Value, Image

    features = Features({
        "id": Value("string"),
        "prompt": Value("string"),
        "image": Image(),                 # -> hf_struct on Adaption's side
        "completion": Value("string"),
        "reasoning": Value("string"),
        "meta_part": Value("string"),
        "meta_chart_type": Value("string"),
        "meta_difficulty": Value("string"),
        "meta_qa_type": Value("string"),
    })

    dd = {}
    for name, recs in splits.items():
        if recs:
            dd[name] = Dataset.from_list(recs, features=features)
    return DatasetDict(dd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", required=True)
    ap.add_argument("--repo", default=None, help="e.g. vinod-anbalagan/adaption-charts-part2; omit for local-only")
    ap.add_argument("--local-dir", default=None, help="also save to disk (load_from_disk-compatible)")
    ap.add_argument("--private", action="store_true", help="create the Hub repo as private")
    args = ap.parse_args()

    rows = load_jsonl(args.flat)
    print(f"Loaded {len(rows)} flat rows")
    splits = to_records(rows)
    dd = build_dataset_dict(splits)

    for name, ds in dd.items():
        print(f"  split '{name}': {len(ds)} rows")
    if not dd:
        print("Nothing to push — no valid rows.")
        return

    first = dd[list(dd.keys())[0]][0]
    print("Sample row (image omitted):",
          {k: (v if k != "image" else "<PIL.Image>") for k, v in first.items()})

    if args.local_dir:
        dd.save_to_disk(args.local_dir)
        print(f"Saved locally: {args.local_dir}")

    if args.repo:
        token = os.environ.get("HF_TOKEN")  # from .env; falls back to cached login
        dd.push_to_hub(args.repo, private=args.private, token=token)
        print(f"Pushed: https://huggingface.co/datasets/{args.repo}")
        print("Next: Adaption UI -> import from Hugging Face -> map prompt/image/completion per the docstring.")


if __name__ == "__main__":
    main()
