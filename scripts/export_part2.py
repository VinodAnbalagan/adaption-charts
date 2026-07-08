#!/usr/bin/env python3
"""export_part2.py — turn a chartgen canonical build into an Adaption-ready
multimodal training file, in EITHER image mode:

  --images bytes   base64-encode each PNG into the row (self-contained file).
                   Use for the pilot (300-500 figures) or if the form accepts
                   inline/base64 image bytes.
  --images urls    emit an image URL column and stage every referenced PNG in
                   <out>/images/ for upload to a HuggingFace dataset repo (or
                   any static host). Use at scale (5K+ figures, HF 2GB limit
                   applies to the JSONL, not the image repo).

Row schema (column names overridable, since the Part 2 form may dictate names):
  prompt      the question / instruction (text)
  completion  the target text. qa rows: deterministic reasoning trace + final
              answer (the moat). table_extraction rows: exact JSON table only
              (reasoning OFF protects exact numbers, same as Part 1).
  image       base64 string, data URI, or URL depending on mode
  + passthrough metadata columns (task_type, chart_type, difficulty, qa_type,
    parent_id) for filtering/config-splitting on the platform.

Usage (from repo root):
  # pilot, self-contained bytes file
  python scripts/export_part2.py --canonical data_p2_pilot/canonical/train.jsonl \
      --out export_pilot --images bytes

  # scale, URL mode against a HF dataset repo
  python scripts/export_part2.py --canonical data_full/canonical/train.jsonl \
      --out export_full --images urls \
      --base-url https://huggingface.co/datasets/<user>/<repo>/resolve/main/images

Then upload export_*/train.jsonl (and train.csv) to Adaption; in URL mode also
upload export_*/images/* to the host referenced by --base-url FIRST.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import sys


def load_canonical(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def resolve_image(ex_image_path: str, canonical_path: str) -> str:
    """Image paths in the JSONL are relative to the build's working dir; try
    as-given, then relative to the canonical file's grandparent (build --out)."""
    if os.path.isfile(ex_image_path):
        return ex_image_path
    root = os.path.dirname(os.path.dirname(os.path.abspath(canonical_path)))
    cand = os.path.join(root, *ex_image_path.split("/")[-2:])
    if os.path.isfile(cand):
        return cand
    raise FileNotFoundError(f"image not found: {ex_image_path} (also tried {cand})")


def qa_completion(target: dict) -> str:
    """Reasoning trace + canonical final answer line (exact-match friendly)."""
    reasoning = (target.get("reasoning") or "").strip()
    answer = str(target.get("answer", "")).strip()
    if reasoning:
        return f"{reasoning}\nAnswer: {answer}"
    return f"Answer: {answer}"


def table_completion(target: dict) -> str:
    """Exact JSON only — no prose, no reasoning (protects exact numbers)."""
    out = {
        "title": target.get("title"),
        "chart_type": target.get("chart_type"),
        "table": target.get("table"),
    }
    if target.get("kpis"):
        out["kpis"] = target["kpis"]
    if target.get("extra_tables"):
        out["extra_tables"] = target["extra_tables"]
    return json.dumps(out, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", required=True,
                    help="canonical train.jsonl from build_pilot.py")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--images", choices=["bytes", "urls"], required=True)
    ap.add_argument("--base-url", default=None,
                    help="URL prefix for --images urls (no trailing slash)")
    ap.add_argument("--data-uri", action="store_true",
                    help="bytes mode: emit data:image/png;base64,... instead of raw base64")
    ap.add_argument("--prompt-col", default="prompt")
    ap.add_argument("--completion-col", default="completion")
    ap.add_argument("--image-col", default="image")
    ap.add_argument("--task-types", default="qa,table_extraction",
                    help="comma list: qa,table_extraction")
    ap.add_argument("--no-csv", action="store_true", help="skip the CSV twin")
    args = ap.parse_args()

    if args.images == "urls" and not args.base_url:
        ap.error("--images urls requires --base-url")

    wanted = {t.strip() for t in args.task_types.split(",") if t.strip()}
    examples = load_canonical(args.canonical)
    os.makedirs(args.out, exist_ok=True)
    img_dir = os.path.join(args.out, "images")
    if args.images == "urls":
        os.makedirs(img_dir, exist_ok=True)

    rows, image_cache, total_img_bytes = [], {}, 0
    for ex in examples:
        img_path = resolve_image(ex["artifacts"]["image_path"], args.canonical)
        fname = os.path.basename(img_path)

        if img_path not in image_cache:
            if args.images == "bytes":
                with open(img_path, "rb") as f:
                    raw = f.read()
                total_img_bytes += len(raw)
                b64 = base64.b64encode(raw).decode("ascii")
                image_cache[img_path] = (
                    f"data:image/png;base64,{b64}" if args.data_uri else b64
                )
            else:
                shutil.copy2(img_path, os.path.join(img_dir, fname))
                image_cache[img_path] = f"{args.base_url.rstrip('/')}/{fname}"
        image_ref = image_cache[img_path]

        tasks = ex.get("tasks", {})
        meta_base = {
            "parent_id": ex["id"],
            "chart_type": ex.get("chart_type"),
            "difficulty": ex.get("difficulty"),
            "part": ex.get("part"),
        }

        te = tasks.get("table_extraction")
        if te and "table_extraction" in wanted:
            rows.append({
                "id": f"{ex['id']}__table",
                args.prompt_col: te["prompt"],
                args.completion_col: table_completion(te["target"]),
                args.image_col: image_ref,
                "task_type": "table_extraction",
                "qa_type": "",
                **meta_base,
            })

        if "qa" in wanted:
            for i, qa in enumerate(tasks.get("qa", [])):
                rows.append({
                    "id": f"{ex['id']}__qa_{i:02d}",
                    args.prompt_col: qa["prompt"],
                    args.completion_col: qa_completion(qa["target"]),
                    args.image_col: image_ref,
                    "task_type": "qa",
                    "qa_type": qa.get("qa_type", ""),
                    **meta_base,
                })

    jsonl_path = os.path.join(args.out, "train.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if not args.no_csv:
        csv_path = os.path.join(args.out, "train.csv")
        cols = list(rows[0].keys()) if rows else []
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    size_mb = os.path.getsize(jsonl_path) / 1e6
    n_imgs = len(image_cache)
    print(f"figures: {len(examples)}  ->  training rows: {len(rows)}  ({n_imgs} unique images)")
    print(f"train.jsonl: {size_mb:.1f} MB" + ("" if args.no_csv else "  (+ train.csv)"))
    if args.images == "bytes":
        print(f"embedded image payload: {total_img_bytes/1e6:.1f} MB raw "
              f"(~{total_img_bytes*1.37/1e6:.1f} MB as base64)")
        if size_mb > 1500:
            print("WARNING: file approaching typical 2GB upload limits — switch to --images urls")
    else:
        print(f"staged {n_imgs} PNGs in {img_dir} — upload these to {args.base_url} BEFORE submitting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
