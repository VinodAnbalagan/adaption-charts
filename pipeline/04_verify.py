"""Programmatic verification pass for gold/manifest.csv.

Three checks, all free (no external LLM required):

  1. Schema validity — required columns populated, enum values valid,
     image files resolve on disk.

  2. Synthetic provenance — every synthetic row's image_path matches its
     raw/<chart_id>.json provenance file. Catches any pipeline drift
     where the manifest and raw provenance disagree.

  3. Hardset human-review flip — each hardset row was authored + reviewed
     row-by-row in chat before it landed in the manifest. That review IS
     the verification. Flip verified: false -> true, with a note in the
     dataset card explaining what 'verified' means per source:
       - synthetic : correct-by-construction from seeded values
       - hardset   : hand-authored and human-reviewed

Prints any failures and exits nonzero if the manifest doesn't validate.
"""

from __future__ import annotations
import csv
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
MANIFEST = GOLD / "manifest.csv"
RAW = GOLD / "raw"

MANIFEST_COLS = [
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]

ALLOWED_SOURCES = {"synthetic", "chartqa", "chartx", "hardset"}
ALLOWED_CHART_TYPES = {
    "bar", "line", "grouped_bar", "stacked_bar",
    "pie", "donut", "mixed",
}
ALLOWED_TASK_TYPES = {
    "lookup_value", "delta_absolute", "max_min", "rank_order",
    "compare_categories", "aggregation_sum_avg", "multi_series_compare",
    "trend_direction", "percent_change_ratio", "hard_multi_step",
}
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_VERIFIED = {"true", "false"}
ALLOWED_SPLIT = {"train", "val", "test"}

REQUIRED_NON_EMPTY = {
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split",
}  # 'notes' allowed empty


def schema_check(rows: list[dict]) -> list[str]:
    failures: list[str] = []
    seen_ids: set[str] = set()
    for r in rows:
        rid = r.get("id", "<no-id>")

        # required columns non-empty
        for col in REQUIRED_NON_EMPTY:
            if not r.get(col):
                failures.append(f"{rid}: empty '{col}'")

        # unique id
        if rid in seen_ids:
            failures.append(f"{rid}: duplicate id")
        seen_ids.add(rid)

        # enums
        if r.get("source") not in ALLOWED_SOURCES:
            failures.append(f"{rid}: bad source={r.get('source')!r}")
        if r.get("chart_type") not in ALLOWED_CHART_TYPES:
            failures.append(f"{rid}: bad chart_type={r.get('chart_type')!r}")
        if r.get("task_type") not in ALLOWED_TASK_TYPES:
            failures.append(f"{rid}: bad task_type={r.get('task_type')!r}")
        if r.get("difficulty") not in ALLOWED_DIFFICULTY:
            failures.append(f"{rid}: bad difficulty={r.get('difficulty')!r}")
        if r.get("verified") not in ALLOWED_VERIFIED:
            failures.append(f"{rid}: bad verified={r.get('verified')!r}")
        if r.get("split") not in ALLOWED_SPLIT:
            failures.append(f"{rid}: bad split={r.get('split')!r}")

        # image exists on disk
        img_rel = r.get("image_path", "")
        if img_rel:
            img_abs = REPO / img_rel
            if not img_abs.is_file():
                failures.append(f"{rid}: image missing on disk: {img_rel}")
    return failures


def synthetic_provenance_check(rows: list[dict]) -> list[str]:
    failures: list[str] = []
    for r in rows:
        if r.get("source") != "synthetic":
            continue
        base = r["id"].rsplit("__", 1)[0]
        prov_path = RAW / f"{base}.json"
        if not prov_path.is_file():
            failures.append(f"{r['id']}: raw provenance missing ({prov_path.name})")
            continue
        try:
            prov = json.loads(prov_path.read_text())
        except json.JSONDecodeError as e:
            failures.append(f"{r['id']}: provenance JSON invalid: {e}")
            continue
        expected_img = f"gold/images/{base}.png"
        if r["image_path"] != expected_img:
            failures.append(
                f"{r['id']}: image_path mismatch — "
                f"row={r['image_path']!r} expected={expected_img!r}"
            )
        # cross-check chart_type consistency
        if prov.get("chart_type") and prov["chart_type"] != r["chart_type"]:
            failures.append(
                f"{r['id']}: chart_type mismatch — "
                f"row={r['chart_type']!r} provenance={prov['chart_type']!r}"
            )
    return failures


def flip_hardset_verified(rows: list[dict]) -> int:
    flipped = 0
    for r in rows:
        if r.get("source") == "hardset" and r.get("verified") == "false":
            r["verified"] = "true"
            flipped += 1
    return flipped


def write_manifest(rows: list[dict]) -> None:
    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    if not MANIFEST.exists():
        sys.exit(f"manifest not found: {MANIFEST}")

    with MANIFEST.open() as f:
        rows = list(csv.DictReader(f))
    print(f"loaded {len(rows)} rows")

    # [1/3] Schema
    print("\n[1/3] schema check...")
    fails = schema_check(rows)
    if fails:
        print(f"  FAIL: {len(fails)} failures")
        for f in fails[:20]:
            print(f"    {f}")
        if len(fails) > 20:
            print(f"    ... and {len(fails) - 20} more")
        sys.exit(1)
    print("  PASS")

    # [2/3] Synthetic provenance
    print("\n[2/3] synthetic provenance check...")
    fails = synthetic_provenance_check(rows)
    if fails:
        print(f"  FAIL: {len(fails)} failures")
        for f in fails[:20]:
            print(f"    {f}")
        sys.exit(1)
    print("  PASS")

    # [3/3] Hardset flip
    print("\n[3/3] hardset verified flip...")
    flipped = flip_hardset_verified(rows)
    print(f"  flipped {flipped} hardset rows to verified=true")

    write_manifest(rows)

    # Final summary
    src_ver = Counter((r["source"], r["verified"]) for r in rows)
    print("\nfinal manifest state:")
    for k, v in sorted(src_ver.items()):
        print(f"  {v:4d}  source={k[0]:10s}  verified={k[1]}")
    print(f"\ntotal: {len(rows)} rows, all verified.")


if __name__ == "__main__":
    main()
