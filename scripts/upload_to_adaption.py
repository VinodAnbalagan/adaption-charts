#!/usr/bin/env python3
"""upload_to_adaption.py — package curated flat JSONL into Adaption-ready Parquet
(with embedded image bytes) and run the Adaptive Data pipeline.

SAFE BY DEFAULT: without --live this only uploads and prints a COST ESTIMATE
(estimate=True) — no credits are spent. Add --live to start a real run.

Per-task-type split (deliberate):
  *_table.parquet  -> adapt with reasoning_traces OFF  (protect exact numbers)
  *_qa.parquet     -> adapt with reasoning_traces ON   (platform reasoning OK; A/B vs ours)

Usage:
  # 1. package only (no network)
  python scripts/upload_to_adaption.py --flat data/curated/part2_flat.jsonl --out data/upload --package-only

  # 2. upload + estimate cost (no credits spent)
  ADAPTION_API_KEY=pt_live_... python scripts/upload_to_adaption.py \
      --flat data/curated/part2_flat.jsonl --out data/upload

  # 3. real run, capped
  ADAPTION_API_KEY=pt_live_... python scripts/upload_to_adaption.py \
      --flat data/curated/part2_flat.jsonl --out data/upload --live --max-rows 300
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:  # load .env from repo root (ADAPTION_API_KEY)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

MAX_UPLOAD_BYTES = 2_147_483_648  # Adaption hard cap (2 GB)

BLUEPRINT = (
    "You are a precise chart and dashboard analyst. Answer ONLY from what is "
    "visible in the provided image. Output strictly valid JSON matching the "
    "requested schema. Never invent values that are not shown. If a value "
    "cannot be determined from the image, say so explicitly."
)


def load_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def package(flat_rows, out_dir: str, stem: str, fmt: str = "parquet"):
    """Write per-task-type files with embedded images.

    fmt='parquet' -> image column holds raw PNG bytes.
    fmt='jsonl'   -> image column holds base64-encoded PNG (bytes aren't valid JSON).

    Columns: id, prompt, image, completion (JSON string), reasoning, plus meta_*
    columns (NOT mapped into the run; kept for slicing/error analysis).
    """
    import pandas as pd

    os.makedirs(out_dir, exist_ok=True)
    out_paths = {}
    by_type = {"table_extraction": [], "qa": []}
    missing_images = 0

    for r in flat_rows:
        img_path = r.get("image_path")
        if not img_path or not os.path.exists(img_path):
            missing_images += 1
            continue
        with open(img_path, "rb") as f:
            img_bytes = f.read()

        target = dict(r["target_json"])  # copy
        reasoning = target.pop("reasoning", None)  # keep ours as a separate column

        row = {
            "id": r["id"],
            "prompt": r["prompt"],
            "image": img_bytes if fmt == "parquet" else base64.b64encode(img_bytes).decode("ascii"),
            "completion": json.dumps(target, ensure_ascii=False),
            "reasoning": reasoning or "",
            "meta_part": r.get("part"),
            "meta_chart_type": (r.get("metadata") or {}).get("chart_type"),
            "meta_difficulty": (r.get("metadata") or {}).get("difficulty"),
            "meta_qa_type": (r.get("metadata") or {}).get("qa_type", ""),
        }
        by_type[r["task_type"]].append(row)

    if missing_images:
        print(f"WARNING: {missing_images} rows skipped (image file not found)")

    for task_type, rows in by_type.items():
        if not rows:
            continue
        suffix = "table" if task_type == "table_extraction" else "qa"
        if fmt == "parquet":
            df = pd.DataFrame(rows)
            path = os.path.join(out_dir, f"{stem}_{suffix}.parquet")
            df.to_parquet(path, index=False)
        else:
            path = os.path.join(out_dir, f"{stem}_{suffix}.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        size = os.path.getsize(path)
        print(f"  {path}: {len(rows)} rows, {size/1e6:.1f} MB")
        if size > MAX_UPLOAD_BYTES:
            print(f"  ERROR: exceeds Adaption 2 GB upload cap — switch to URL-based images for this scale.")
        out_paths[task_type] = path
    return out_paths


def run_adaption(parquet_path: str, task_type: str, live: bool, max_rows: int | None):
    """Upload one Parquet and run (or estimate) adaptation with task-appropriate settings."""
    from adaption import Adaption

    api_key = os.environ.get("ADAPTION_API_KEY")
    if not api_key:
        print("ADAPTION_API_KEY not set — skipping upload. Use --package-only to silence this.")
        return

    client = Adaption(api_key=api_key)

    print(f"Uploading {parquet_path} ...")
    result = client.datasets.upload_file(parquet_path)
    dataset_id = result.dataset_id
    print(f"  dataset_id = {dataset_id}")

    # wait for ingestion (row_count populates)
    import time
    while True:
        status = client.datasets.get_status(dataset_id)
        if getattr(status, "row_count", None) is not None:
            break
        time.sleep(2)
    print(f"  ingested: {status.row_count} rows")

    reasoning_on = task_type == "qa"  # OFF for table extraction (protect exact numbers)
    kwargs = dict(
        column_mapping={
            "prompt": "prompt",
            "completion": "completion",
            "context": ["image"],
        },
        recipe_specification={
            "recipes": {
                "deduplication": True,
                "prompt_rephrase": True,
                "reasoning_traces": reasoning_on,
            }
        },
        brand_controls={
            "blueprint": BLUEPRINT,
            "hallucination_mitigation": False,
            "length": "concise",
        },
    )
    if max_rows:
        kwargs["job_specification"] = {"max_rows": max_rows}

    # ALWAYS estimate first
    est = client.datasets.run(dataset_id, estimate=True, **kwargs)
    print(f"  ESTIMATE: ~{est.estimated_credits_consumed} credits, ~{est.estimated_minutes} min "
          f"(reasoning_traces={'ON' if reasoning_on else 'OFF'})")

    if not live:
        print("  (estimate-only; rerun with --live to start the run)")
        return dataset_id

    run = client.datasets.run(dataset_id, **kwargs)
    print(f"  RUN STARTED: {run.run_id}")
    final = client.datasets.wait_for_completion(dataset_id, timeout=3600)
    print(f"  finished: {final.status}")
    url = client.datasets.download(dataset_id)
    print(f"  download: {url}")
    return dataset_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", required=True, help="flat JSONL (from curate.py or build_pilot.py)")
    ap.add_argument("--out", default="data/upload")
    ap.add_argument("--stem", default=None, help="output filename stem (default: flat filename)")
    ap.add_argument("--package-only", action="store_true", help="write files, no network")
    ap.add_argument("--format", choices=["parquet", "jsonl"], default="parquet",
                    help="parquet = raw image bytes; jsonl = base64-encoded images")
    ap.add_argument("--limit", type=int, default=None, help="only package the first N rows (fast debug uploads)")
    ap.add_argument("--live", action="store_true", help="actually start the run (default: estimate only)")
    ap.add_argument("--max-rows", type=int, default=None, help="cap rows processed in the run")
    args = ap.parse_args()

    stem = args.stem or os.path.splitext(os.path.basename(args.flat))[0]
    rows = load_jsonl(args.flat)
    if args.limit:
        rows = rows[: args.limit]
        stem = f"{stem}_n{args.limit}"
    print(f"Loaded {len(rows)} flat rows from {args.flat}")

    paths = package(rows, args.out, stem, fmt=args.format)

    if args.package_only:
        print("Package-only mode; done.")
        return

    for task_type, path in paths.items():
        run_adaption(path, task_type, live=args.live, max_rows=args.max_rows)


if __name__ == "__main__":
    main()
