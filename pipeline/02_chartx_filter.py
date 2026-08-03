"""Filter ChartX rows into gold/manifest.csv.

ChartX (Apache-2.0) is substituted for ChartQA (GPL-3.0) in the external-
benchmark slot. Adds 'chartx' as an allowed source value.

Prereqs (run once on your Mac):
    hf download InternScience/ChartX --repo-type dataset --local-dir ~/chartx
    cd ~/chartx && unzip -q ChartX_png.zip

Then from the repo:
    python pipeline/02_chartx_filter.py --source ~/chartx --n 150

The script:
  1. Loads ChartX_annotation_val.json (4.8K rows).
  2. Filters by chart_type, question quality, answer format.
  3. Infers task_type from question text (heuristic).
  4. Samples n rows with a rough per-chart-type balance.
  5. Copies each row's PNG to gold/images/cx_<chart_type>_<idx>.png.
  6. Appends normalized rows to gold/manifest.csv.
     Existing chartx rows (source == 'chartx') are removed first if
     --reset-chartx is set (default: True to keep runs reproducible).

verified=false is set on every chartx row; task 8 will verify with an
external LLM pass and flip to true where confirmed.
"""

from __future__ import annotations
import argparse
import csv
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
IMAGES = GOLD / "images"
MANIFEST = GOLD / "manifest.csv"

MANIFEST_COLS = [
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]

# Map ChartX chart_type strings -> our schema chart_type values.
# NOTE: actual JSON uses underscored names (bar_chart), not the spaced names
# shown in the HF dataset-viewer schema preview.
# Anything not listed is skipped.
CHARTX_TO_OURS = {
    "bar_chart": "bar",
    "bar_chart_num": "bar",
    "line_chart": "line",
    "line_chart_num": "line",
    "pie_chart": "pie",
    "rings": "donut",
}


# ---- Filters ---------------------------------------------------------------

_UNIT_TAIL_RE = re.compile(
    r"\d+\s*(million|billion|thousand|tonnes?|liters?|kg|km|units|pcs|"
    r"kwh|mwh|hectares?|acres?|barrels?)\b",
    re.IGNORECASE,
)


def is_answer_ok(answer: str) -> tuple[bool, str]:
    """Reject overly long, unit-suffixed, or sentence-style answers."""
    a = (answer or "").strip()
    if not a:
        return False, "empty"
    if len(a) > 30:
        return False, "too_long"
    # Any word-count > 2 is likely a sentence, not a short answer
    if a.count(" ") > 2:
        return False, "multiword"
    # Numbers with trailing units break our short-answer style
    if _UNIT_TAIL_RE.search(a):
        return False, "unit_suffix"
    return True, "ok"


def is_question_ok(question: str) -> tuple[bool, str]:
    q = (question or "").strip()
    if not q:
        return False, "empty"
    if len(q) > 220:
        return False, "too_long"
    return True, "ok"


def _count_numeric_cols(csv_str: str) -> int:
    """ChartX CSVs are tab-separated but use LITERAL '\\t' / '\\n' escape
    strings rather than real tab / newline characters. Un-escape first."""
    if not csv_str:
        return 0
    s = csv_str.replace("\\n", "\n").replace("\\t", "\t")
    lines = [l for l in s.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return 0
    first_row = lines[1].split("\t")
    if len(first_row) < 2:
        return 0
    n = 0
    for cell in first_row[1:]:
        try:
            float(cell.strip())
            n += 1
        except ValueError:
            pass
    return n


def refine_bar_type(csv_str: str, redraw_code: str) -> str:
    """Classify a ChartX 'bar_chart' row as bar / grouped_bar / stacked_bar.

    Signal:
      - 1 numeric series column: single-series -> 'bar'
      - >=2 series + 'bottom=' in the redraw code: 'stacked_bar'
      - >=2 series otherwise: 'grouped_bar'
    """
    n_series = _count_numeric_cols(csv_str)
    if n_series <= 1:
        return "bar"
    if "bottom=" in (redraw_code or ""):
        return "stacked_bar"
    return "grouped_bar"


def normalize_answer(answer: str) -> str:
    a = answer.strip().rstrip(".")
    return a


# ---- task_type inference ---------------------------------------------------
#
# Uses word-boundary regex (not naive substring match) to avoid false hits
# like "sum" matching inside "consumption". Order is deliberate:
#   1. compare_categories only if answer is Yes/No (strong signal)
#   2. rank_order (explicit ranking asks)
#   3. trend_direction (over-time change words)
#   4. delta_absolute (numeric comparison phrasing)
#   5. percent_change_ratio (percent CHANGE specifically, not "what %")
#   6. max_min (BEFORE aggregation — "highest average" is max, not agg)
#   7. aggregation_sum_avg (sum / avg with strong markers)
#   8. lookup_value (default)

_RE_RANK = re.compile(
    r"\b(rank|top\s+\d+|bottom\s+\d+|top\s+three|bottom\s+three)\b", re.I,
)
_RE_TREND = re.compile(
    r"\b(increase or decrease|rise or fall|trend from|grew|fell|declined|"
    r"rose to|dropped to|went up|went down)\b", re.I,
)
_RE_DELTA = re.compile(
    r"\b(how many more|how much more|how many fewer|how much less|"
    r"how much higher|how much lower|how much greater|"
    r"difference between|difference in)\b", re.I,
)
_RE_PCT_CHANGE = re.compile(
    r"\b(percent change|percentage change|by what percent|"
    r"change in .* from|increased by .* percent|decreased by .* percent)\b",
    re.I,
)
_RE_MAX_MIN = re.compile(
    r"\b(highest|lowest|most|least|biggest|smallest|largest|"
    r"greatest|maximum|minimum)\b", re.I,
)
_RE_AGG = re.compile(
    r"\b(average of|mean of|sum of|combined|combined total|"
    r"total .* across|across all|overall total|"
    r"what is the average\b|what is the total\b|what is the sum\b|"
    r"what is the mean\b)\b", re.I,
)


def infer_task_type(question: str, answer: str) -> str:
    ans = (answer or "").strip().lower()
    if ans in ("yes", "no"):
        return "compare_categories"
    q = question or ""
    if _RE_RANK.search(q):
        return "rank_order"
    if _RE_TREND.search(q):
        return "trend_direction"
    if _RE_DELTA.search(q):
        return "delta_absolute"
    if _RE_PCT_CHANGE.search(q):
        return "percent_change_ratio"
    if _RE_MAX_MIN.search(q):
        return "max_min"
    if _RE_AGG.search(q):
        return "aggregation_sum_avg"
    return "lookup_value"


def infer_difficulty(question: str, answer: str, task_type: str) -> str:
    q = (question or "").lower()
    # multi-step / conditional wording -> hard
    if re.search(r"\bbut\b", q) and re.search(r"\b(has|have)\b", q):
        return "hard"
    if re.search(r"\bwhich .* while\b", q):
        return "hard"
    if task_type in ("delta_absolute", "aggregation_sum_avg",
                     "percent_change_ratio", "rank_order"):
        return "medium"
    return "easy"


# ---- Main ------------------------------------------------------------------

def load_manifest_rows() -> list[dict]:
    if not MANIFEST.exists():
        return []
    with MANIFEST.open() as f:
        return list(csv.DictReader(f))


def write_manifest_rows(rows: list[dict]) -> None:
    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    help="path to extracted ChartX dir (contains "
                         "ChartX_annotation_val.json + bar_chart/, line_chart/, ...)")
    ap.add_argument("--n", type=int, default=150,
                    help="target number of rows to sample")
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--reset-chartx", action="store_true", default=True,
                    help="drop existing source=chartx rows before appending")
    ap.add_argument("--split", default="chartx_val",
                    help="use 'chartx_val' or 'chartx_test' annotation JSON")
    args = ap.parse_args()

    source_dir = Path(args.source).expanduser()
    ann_name = "ChartX_annotation_val.json" if args.split == "chartx_val" \
               else "ChartX_annotation_test.json"
    ann_path = source_dir / ann_name
    if not ann_path.exists():
        sys.exit(f"annotation not found: {ann_path}")

    # Auto-detect image root. Zip may extract into ~/chartx/ChartX_png/
    # or ~/chartx/ or elsewhere. Look for the first directory that contains
    # a 'bar_chart' subfolder — that's the ChartX layout root.
    images_root = None
    for candidate in [source_dir, source_dir / "ChartX_png",
                      source_dir / "ChartX", source_dir / "png"]:
        if (candidate / "bar_chart" / "png").is_dir():
            images_root = candidate
            break
    if images_root is None:
        # Last-resort search
        for p in source_dir.rglob("bar_chart"):
            if (p / "png").is_dir():
                images_root = p.parent
                break
    if images_root is None:
        sys.exit(f"could not locate ChartX image root under {source_dir}; "
                 f"expected a 'bar_chart/png/' subdir somewhere below it")
    print(f"images root: {images_root}")

    print(f"loading {ann_name}...")
    with ann_path.open() as f:
        raw = json.load(f)
    print(f"  {len(raw)} rows in annotation")

    # ---- Filter ----
    rng = random.Random(args.seed)
    kept: list[dict] = []
    rejected: Counter = Counter()
    for row in raw:
        chartx_type = row.get("chart_type", "")
        our_ct = CHARTX_TO_OURS.get(chartx_type)
        if not our_ct:
            rejected[f"chart_type:{chartx_type}"] += 1
            continue

        qa = row.get("QA") or {}
        q = qa.get("input", "")
        a = qa.get("output", "")

        ok, why = is_question_ok(q)
        if not ok:
            rejected[f"question:{why}"] += 1
            continue
        ok, why = is_answer_ok(a)
        if not ok:
            rejected[f"answer:{why}"] += 1
            continue

        # Refine bar chart_type using CSV + redraw code to distinguish
        # single-series / grouped_bar / stacked_bar.
        if our_ct == "bar":
            csv_str = row.get("csv", "")
            redraw = (row.get("redrawing") or {}).get("output", "")
            our_ct = refine_bar_type(csv_str, redraw)

        kept.append({
            "our_chart_type": our_ct,
            "chartx_chart_type": chartx_type,
            "imgname": row.get("imgname", ""),
            "img_rel_path": row.get("img", ""),  # e.g. "./bar_chart/png/bar_85.png"
            "topic": row.get("topic", ""),
            "title": (row.get("title") or "").strip(),
            "question": q.strip(),
            "answer": normalize_answer(a),
        })

    print(f"kept {len(kept)}, rejected {sum(rejected.values())}")
    print("  top rejection reasons:")
    for reason, count in rejected.most_common(8):
        print(f"    {count:5d}  {reason}")

    # ---- Balance-sample by our chart_type ----
    by_ct: dict[str, list[dict]] = defaultdict(list)
    for c in kept:
        by_ct[c["our_chart_type"]].append(c)

    print("  available by our chart_type:")
    for ct in sorted(by_ct):
        print(f"    {ct}: {len(by_ct[ct])}")

    # Rough target distribution across n rows. Grouped/stacked now have real
    # supply thanks to CSV+code refinement, so bumped from 5% to 10% each.
    per_type_target = {"bar": 0.25, "line": 0.30, "pie": 0.15,
                       "donut": 0.10, "grouped_bar": 0.10, "stacked_bar": 0.10}
    picked: list[dict] = []
    for ct, frac in per_type_target.items():
        want = int(round(args.n * frac))
        available = by_ct.get(ct, [])
        if not available:
            continue
        take = min(want, len(available))
        picked.extend(rng.sample(available, k=take))

    # If short of n, fill from anything remaining
    remaining_needed = args.n - len(picked)
    if remaining_needed > 0:
        pool = [c for ct_rows in by_ct.values() for c in ct_rows
                if c not in picked]
        pool.sort(key=lambda x: x["imgname"])  # stable
        fill = rng.sample(pool, k=min(remaining_needed, len(pool)))
        picked.extend(fill)

    print(f"picked {len(picked)} rows")

    # ---- Copy images + build manifest rows ----
    IMAGES.mkdir(parents=True, exist_ok=True)
    per_ct_counter: dict[str, int] = defaultdict(int)
    out_rows: list[dict] = []
    missing_images: list[str] = []

    for row in picked:
        our_ct = row["our_chart_type"]
        per_ct_counter[our_ct] += 1
        idx = per_ct_counter[our_ct]
        chart_id = f"cx_{our_ct}_{idx:04d}"

        src_img = images_root / row["img_rel_path"].lstrip("./")
        if not src_img.exists():
            missing_images.append(str(src_img))
            continue

        dst_rel = f"gold/images/{chart_id}.png"
        dst_abs = REPO / dst_rel
        shutil.copyfile(src_img, dst_abs)

        task_type = infer_task_type(row["question"], row["answer"])
        difficulty = infer_difficulty(row["question"], row["answer"], task_type)

        notes = (
            f"chartx {row['chartx_chart_type']}; topic={row['topic']}; "
            f"src_imgname={row['imgname']}"
        )
        out_rows.append({
            "id": chart_id,
            "source": "chartx",
            "image_path": dst_rel,
            "question": row["question"],
            "answer": row["answer"],
            "chart_type": our_ct,
            "task_type": task_type,
            "difficulty": difficulty,
            "verified": "false",  # task 8 will verify
            "split": "train",
            "notes": notes,
        })

    if missing_images:
        print(f"  WARNING: {len(missing_images)} images missing on disk "
              f"(zip not extracted?):")
        for p in missing_images[:5]:
            print(f"    {p}")

    # ---- Merge into manifest ----
    existing = load_manifest_rows()
    if args.reset_chartx:
        existing = [r for r in existing if r.get("source") != "chartx"]
        print(f"reset: kept {len(existing)} non-chartx rows")
    all_rows = existing + out_rows
    write_manifest_rows(all_rows)

    print(f"appended {len(out_rows)} chartx rows; manifest now has "
          f"{len(all_rows)} rows total")
    tt_dist = Counter(r["task_type"] for r in out_rows)
    ct_dist = Counter(r["chart_type"] for r in out_rows)
    diff_dist = Counter(r["difficulty"] for r in out_rows)
    print(f"  new rows task_type: {dict(tt_dist)}")
    print(f"  new rows chart_type: {dict(ct_dist)}")
    print(f"  new rows difficulty: {dict(diff_dist)}")


if __name__ == "__main__":
    main()
