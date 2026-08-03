"""Generate perceptually-hard synthetic rows and append to the manifest.

Rationale: win rate is won where the BASE model fails and the adapted model
succeeds. Rows both models answer correctly contribute nothing. The existing
'hard' rows were arithmetic over labeled values — easy for a capable VLM.
These rows are hard to PERCEIVE, not hard to compute.

Eight mechanics (see lib/hard_render.py):
  truncated_axis   bar heights misrepresent value ratios
  unlabeled_bar    no labels; values snapped exactly to gridlines
  unlabeled_line   same, for line charts
  near_tie         top two values within ~1-2%
  similar_colors   near-identical series hues; legend must be read
  many_categories  12-16 rotated labels, small annotation font
  crowded_legend   legend occludes the plot area
  log_scale        equal pixels != equal deltas
  dual_axis        two y-axes; question targets one specifically

All answers are correct-by-construction from seeded values.

Usage:
    python pipeline/07_hardgen.py                 # default 200 rows
    python pipeline/07_hardgen.py --n-charts 120
"""

from __future__ import annotations
import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.hard_render import (  # noqa: E402
    render_truncated_bar,
    render_unlabeled_bar,
    render_unlabeled_line,
    render_near_tie_bar,
    render_similar_colors_grouped,
    render_many_categories_bar,
    render_crowded_legend_line,
    render_log_scale_bar,
    render_dual_axis,
)

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
IMAGES = GOLD / "images"
RAW = GOLD / "raw"
MANIFEST = GOLD / "manifest.csv"

MANIFEST_COLS = [
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]

# --- vocabulary -------------------------------------------------------------

SEGMENTS = ["Consumer", "Enterprise", "SMB", "Government", "Education",
            "Nonprofit", "Startup", "Mid-Market"]
REGIONS = ["NA", "EMEA", "APAC", "LATAM", "MEA", "ANZ"]
VERTICALS = ["Healthcare", "Retail", "Finance", "Manufacturing", "Tech",
             "Energy", "Media", "Automotive", "Logistics", "Telecom",
             "Insurance", "Hospitality", "Agriculture", "Construction",
             "Education", "Utilities"]
PRODUCTS = ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E",
            "Widget F", "Gizmo X", "Gizmo Y"]
MONTHS_H1 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
MONTHS_H2 = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
WEEKS = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]


def _row(rid, image_rel, q, a, chart_type, task_type, notes):
    return {
        "id": rid, "source": "synthetic", "image_path": image_rel,
        "question": q, "answer": a, "chart_type": chart_type,
        "task_type": task_type, "difficulty": "hard",
        "verified": "true", "split": "train", "notes": notes,
    }


def _note(mechanic: str, seed: int, idx: int) -> str:
    return f"hard/{mechanic}; procedural gen (seed={seed}, idx={idx}); correct-by-construction"


# --- generators -------------------------------------------------------------

def gen_truncated(rng, i, seed):
    """Truncated axis: heights lie, labels tell truth."""
    cats = rng.sample(SEGMENTS, k=5)
    base = rng.randrange(8000, 12000, 500)
    # tight spread so truncation exaggerates differences dramatically
    vals = [base + rng.randrange(0, 2000, 100) for _ in cats]
    while len(set(vals)) < len(vals):
        vals = [base + rng.randrange(0, 2000, 100) for _ in cats]
    y_floor = min(vals) - 200

    cid = f"hard_trunc_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_truncated_bar(
        cats, vals, f"Q{rng.randint(1,4)} Revenue by Segment", "Revenue ($)",
        REPO / rel, y_floor=y_floor,
    )
    hi = cats[vals.index(max(vals))]
    lo = cats[vals.index(min(vals))]
    delta = max(vals) - min(vals)
    note = _note("truncated_axis", seed, i)
    rows = [
        _row(f"{cid}__q1", rel,
             f"Which segment had the highest revenue?", hi,
             "bar", "max_min", note),
        _row(f"{cid}__q2", rel,
             f"How much more revenue did {hi} generate than {lo}?",
             f"${delta}", "bar", "delta_absolute", note),
    ]
    return rows, prov, cid


def gen_unlabeled_bar(rng, i, seed):
    """No labels — values snapped exactly onto gridlines."""
    cats = rng.sample(VERTICALS, k=5)
    step = rng.choice([500, 1000, 2000])
    vals = [step * rng.randint(2, 9) for _ in cats]
    while len(set(vals)) < len(vals):
        vals = [step * rng.randint(2, 9) for _ in cats]

    cid = f"hard_unlab_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_unlabeled_bar(
        cats, vals, "Revenue by Vertical", "Revenue ($)",
        REPO / rel, tick_step=step,
    )
    target = rng.choice(cats)
    tv = vals[cats.index(target)]
    hi = cats[vals.index(max(vals))]
    note = _note("unlabeled", seed, i)
    rows = [
        _row(f"{cid}__q1", rel, f"What was {target}'s revenue?",
             f"${tv}", "bar", "lookup_value", note),
        _row(f"{cid}__q2", rel, "Which vertical had the highest revenue?",
             hi, "bar", "max_min", note),
    ]
    return rows, prov, cid


def gen_unlabeled_line(rng, i, seed):
    xs = rng.choice([MONTHS_H1, MONTHS_H2, WEEKS[:6]])
    step = rng.choice([100, 200, 500])
    vals = [step * rng.randint(3, 12) for _ in xs]
    while len(set(vals)) < len(vals):
        vals = [step * rng.randint(3, 12) for _ in xs]

    cid = f"hard_unline_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_unlabeled_line(
        xs, vals, "Monthly Signups", "Signups", REPO / rel, tick_step=step,
    )
    target = rng.choice(xs)
    tv = vals[xs.index(target)]
    lo = xs[vals.index(min(vals))]
    note = _note("unlabeled", seed, i)
    rows = [
        _row(f"{cid}__q1", rel, f"How many signups were there in {target}?",
             f"{tv}", "line", "lookup_value", note),
        _row(f"{cid}__q2", rel, "In which period were signups lowest?",
             lo, "line", "max_min", note),
    ]
    return rows, prov, cid


def gen_near_tie(rng, i, seed):
    """Top two within ~1-2% — eyeballing fails."""
    cats = rng.sample(PRODUCTS, k=5)
    top = rng.randrange(6000, 12000, 100)
    second = top - rng.choice([50, 100, 150])
    rest = sorted(
        {rng.randrange(2000, second - 500, 100) for _ in range(12)},
        reverse=True,
    )[:3]
    while len(rest) < 3:
        rest.append(rng.randrange(2000, second - 500, 100))
    vals = [top, second] + rest
    rng.shuffle(vals)

    cid = f"hard_tie_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_near_tie_bar(
        cats, vals, "Units Sold by Product", "Units sold",
        REPO / rel, value_fmt="{:.0f}",
    )
    hi = cats[vals.index(max(vals))]
    srt = sorted(range(len(vals)), key=lambda k: vals[k], reverse=True)
    second_cat = cats[srt[1]]
    note = _note("near_tie", seed, i)
    rows = [
        _row(f"{cid}__q1", rel, "Which product sold the most units?",
             hi, "bar", "max_min", note),
        _row(f"{cid}__q2", rel, "Rank the top 3 products by units sold.",
             ", ".join(cats[k] for k in srt[:3]),
             "bar", "rank_order", note),
        _row(f"{cid}__q3", rel,
             f"How many more units did {hi} sell than {second_cat}?",
             f"{max(vals) - vals[srt[1]]}", "bar", "delta_absolute", note),
    ]
    return rows, prov, cid


def gen_similar_colors(rng, i, seed):
    cats = rng.sample(REGIONS, k=4)
    labels = rng.choice([["2023", "2024", "2025"], ["Q1", "Q2", "Q3"],
                         ["Plan", "Forecast", "Actual"]])
    series = [[rng.randrange(2000, 11000, 100) for _ in cats] for _ in labels]

    cid = f"hard_simcol_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_similar_colors_grouped(
        cats, series, list(labels), "Revenue by Region", "Revenue ($)",
        REPO / rel,
    )
    ci = rng.randrange(len(cats))
    si = rng.randrange(len(labels))
    note = _note("similar_colors", seed, i)
    # max within one specific series — requires resolving the legend
    smax = labels[si]
    svals = series[si]
    rows = [
        _row(f"{cid}__q1", rel,
             f"What was {cats[ci]}'s revenue in {labels[si]}?",
             f"${series[si][ci]}", "grouped_bar", "lookup_value", note),
        _row(f"{cid}__q2", rel,
             f"In {smax}, which region had the highest revenue?",
             cats[svals.index(max(svals))],
             "grouped_bar", "max_min", note),
    ]
    return rows, prov, cid


def gen_many_categories(rng, i, seed):
    n = rng.randint(12, 16)
    cats = rng.sample(VERTICALS, k=min(n, len(VERTICALS)))
    vals = [rng.randrange(1000, 15000, 100) for _ in cats]
    while len(set(vals)) < len(vals):
        vals = [rng.randrange(1000, 15000, 100) for _ in cats]

    cid = f"hard_many_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_many_categories_bar(
        cats, vals, "Annual Revenue by Vertical", "Revenue ($)", REPO / rel,
    )
    srt = sorted(range(len(vals)), key=lambda k: vals[k], reverse=True)
    note = _note("many_categories", seed, i)
    rows = [
        _row(f"{cid}__q1", rel, "Which vertical had the highest revenue?",
             cats[srt[0]], "bar", "max_min", note),
        _row(f"{cid}__q2", rel, "Rank the top 3 verticals by revenue.",
             ", ".join(cats[k] for k in srt[:3]), "bar", "rank_order", note),
        _row(f"{cid}__q3", rel, "Which vertical had the lowest revenue?",
             cats[srt[-1]], "bar", "max_min", note),
    ]
    return rows, prov, cid


def gen_crowded_legend(rng, i, seed):
    xs = rng.choice([MONTHS_H1, MONTHS_H2, QUARTERS])
    labels = rng.sample(SEGMENTS, k=4)
    series = [[rng.randrange(2000, 12000, 100) for _ in xs] for _ in labels]

    cid = f"hard_crowd_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_crowded_legend_line(
        xs, series, labels, "Revenue Trend by Segment", "Revenue ($)",
        REPO / rel,
    )
    si = rng.randrange(len(labels))
    svals = series[si]
    a_i = rng.randrange(len(xs) - 1)
    direction = "Increased" if svals[a_i + 1] > svals[a_i] else "Decreased"
    note = _note("crowded_legend", seed, i)
    rows = [
        _row(f"{cid}__q1", rel,
             f"For {labels[si]}, in which period was revenue highest?",
             xs[svals.index(max(svals))], "line", "max_min", note),
        _row(f"{cid}__q2", rel,
             f"For {labels[si]}, did revenue increase or decrease "
             f"from {xs[a_i]} to {xs[a_i + 1]}?",
             direction, "line", "trend_direction", note),
    ]
    return rows, prov, cid


def gen_log_scale(rng, i, seed):
    cats = rng.sample(PRODUCTS, k=5)
    # spread across orders of magnitude so log scale genuinely compresses
    vals = sorted(
        [rng.randrange(10, 100, 5), rng.randrange(100, 1000, 50),
         rng.randrange(1000, 10000, 500), rng.randrange(10000, 100000, 5000),
         rng.randrange(100, 1000, 50)],
    )
    rng.shuffle(vals)

    cid = f"hard_log_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_log_scale_bar(
        cats, vals, "Units Sold by Product", "Units sold", REPO / rel,
    )
    hi = cats[vals.index(max(vals))]
    lo = cats[vals.index(min(vals))]
    note = _note("log_scale", seed, i)
    rows = [
        _row(f"{cid}__q1", rel, "Which product sold the most units?",
             hi, "bar", "max_min", note),
        _row(f"{cid}__q2", rel,
             f"How many more units did {hi} sell than {lo}?",
             f"{max(vals) - min(vals)}", "bar", "delta_absolute", note),
    ]
    return rows, prov, cid


def gen_dual_axis(rng, i, seed):
    xs = rng.choice([MONTHS_H1, MONTHS_H2, QUARTERS])
    bar_vals = [rng.randrange(2000, 12000, 100) for _ in xs]
    line_vals = [round(rng.uniform(1.5, 9.5), 1) for _ in xs]
    while len(set(line_vals)) < len(line_vals):
        line_vals = [round(rng.uniform(1.5, 9.5), 1) for _ in xs]

    cid = f"hard_dual_{i:04d}"
    rel = f"gold/images/{cid}.png"
    prov = render_dual_axis(
        xs, bar_vals, line_vals, "Revenue ($)", "Conversion Rate (%)",
        "Revenue and Conversion Rate", REPO / rel,
    )
    t = rng.choice(xs)
    ti = xs.index(t)
    note = _note("dual_axis", seed, i)
    rows = [
        _row(f"{cid}__q1", rel, f"What was the conversion rate in {t}?",
             f"{line_vals[ti]}%", "mixed", "lookup_value", note),
        _row(f"{cid}__q2", rel,
             "In which period was the conversion rate highest?",
             xs[line_vals.index(max(line_vals))],
             "mixed", "max_min", note),
        _row(f"{cid}__q3", rel, f"What was the revenue in {t}?",
             f"${bar_vals[ti]}", "mixed", "lookup_value", note),
    ]
    return rows, prov, cid


GENERATORS = [
    gen_truncated, gen_unlabeled_bar, gen_unlabeled_line, gen_near_tie,
    gen_similar_colors, gen_many_categories, gen_crowded_legend,
    gen_log_scale, gen_dual_axis,
]


# --- main -------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-charts", type=int, default=90,
                    help="charts per full rotation cycle (9 generators)")
    ap.add_argument("--seed", type=int, default=777)
    args = ap.parse_args()

    IMAGES.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    all_rows: list[dict] = []
    for i in range(args.n_charts):
        gen = GENERATORS[i % len(GENERATORS)]
        rows, prov, cid = gen(rng, i, args.seed)
        prov.update({"chart_id": cid, "seed": args.seed, "idx": i})
        (RAW / f"{cid}.json").write_text(json.dumps(prov, indent=2))
        all_rows.extend(rows)

    # Merge: drop any previous hard/* rows, then append
    existing = []
    if MANIFEST.exists():
        with MANIFEST.open() as f:
            existing = [r for r in csv.DictReader(f)
                        if not r["id"].startswith("hard_")]
    combined = existing + all_rows
    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
        w.writeheader()
        for r in combined:
            w.writerow(r)

    mech = Counter(r["notes"].split(";")[0].replace("hard/", "")
                   for r in all_rows)
    tt = Counter(r["task_type"] for r in all_rows)
    ct = Counter(r["chart_type"] for r in all_rows)
    print(f"generated {len(all_rows)} hard rows across {args.n_charts} charts")
    print(f"manifest: {len(existing)} existing + {len(all_rows)} hard = {len(combined)}")
    print(f"\nby mechanic: {dict(mech)}")
    print(f"by task_type: {dict(tt)}")
    print(f"by chart_type: {dict(ct)}")

    n_hard = sum(1 for r in combined if r["difficulty"] == "hard")
    print(f"\ntotal hard rows in manifest: {n_hard} / {len(combined)} "
          f"({n_hard / len(combined) * 100:.1f}%)")


if __name__ == "__main__":
    main()
