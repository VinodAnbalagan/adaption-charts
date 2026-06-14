#!/usr/bin/env python3
"""build_pilot.py — generate a small batch, validate it, export JSONL, and emit
an HTML inspection sheet so you can eyeball each render against its ground truth.

Usage (from repo root):

    python scripts/build_pilot.py --bar 10 --line 10 --grouped 10 --stacked 10 --dashboard 10 --out data

Then open data/inspect.html in a browser. The rule from the plan: generate ~50,
eyeball ~20, fix issues, THEN scale.
"""

from __future__ import annotations

import argparse
import os
import sys

# allow running without install: add src/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chartgen.generator import build_mixed_dataset
from chartgen.schema import export_canonical_jsonl, export_flattened_jsonl
from chartgen.validator import validate_dataset


def make_inspect_html(examples, out_path: str) -> None:
    rows = []
    for ex in examples:
        d = ex.to_dict()
        img_rel = os.path.relpath(ex.artifacts.image_path, os.path.dirname(out_path))
        qa_html = ""
        for q in d["tasks"]["qa"]:
            tgt = q["target"]
            qa_html += (
                f"<div class='qa'><b>[{q['qa_type']}]</b> {q['prompt']}"
                f"<br><span class='ans'>&rarr; {tgt['answer']}</span>"
                f"<br><span class='rsn'>{tgt.get('reasoning','')}</span></div>"
            )
        te = d["tasks"]["table_extraction"]
        table = te["target"]["table"] if te else None
        table_html = ""
        if te:
            tgt = te["target"]
            for k in tgt.get("kpis", []):
                table_html += f"<div class='qa'><b>KPI:</b> {k['name']} = <span class='ans'>{k['value']}</span> ({k.get('unit','')})</div>"
        if table:
            table_html += "<table class='gt'><tr>" + "".join(f"<th>{c}</th>" for c in table["columns"]) + "</tr>"
            for r in table["rows"]:
                table_html += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
            table_html += "</table>"
        if te:
            for et in te["target"].get("extra_tables", []):
                t2 = et["table"]
                table_html += f"<div class='meta'>{et['panel_id']} &middot; {et['title']}</div>"
                table_html += "<table class='gt'><tr>" + "".join(f"<th>{c}</th>" for c in t2["columns"]) + "</tr>"
                for r in t2["rows"]:
                    table_html += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                table_html += "</table>"
        rows.append(f"""
        <div class='card'>
          <div class='meta'>{ex.id} &middot; {ex.chart_type} &middot; {ex.difficulty} &middot; {ex.part}</div>
          <div class='body'>
            <img src='{img_rel}' />
            <div class='right'>{table_html}{qa_html}</div>
          </div>
        </div>""")

    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;background:#fafafa}}
 .card{{background:#fff;border:1px solid #e5e5e5;border-radius:10px;margin-bottom:18px;padding:14px}}
 .meta{{font-size:12px;color:#666;margin-bottom:8px}}
 .body{{display:flex;gap:18px;align-items:flex-start}}
 img{{max-width:520px;border:1px solid #eee;border-radius:6px}}
 .right{{flex:1;font-size:13px}}
 table.gt{{border-collapse:collapse;margin-bottom:10px}}
 table.gt td,table.gt th{{border:1px solid #ddd;padding:3px 7px;font-size:12px}}
 .qa{{margin:6px 0;padding:6px;background:#f7f7f9;border-radius:6px}}
 .ans{{color:#0a7d32;font-weight:600}}
 .rsn{{color:#555;font-style:italic;font-size:12px}}
</style></head><body>
<h2>chartgen inspection &mdash; {len(examples)} figures</h2>
{''.join(rows)}
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bar", type=int, default=10)
    ap.add_argument("--line", type=int, default=10)
    ap.add_argument("--grouped", type=int, default=10)
    ap.add_argument("--stacked", type=int, default=10)
    ap.add_argument("--dashboard", type=int, default=10)
    ap.add_argument("--funnel", type=int, default=0)
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    render_dir = os.path.join(args.out, "renders")
    os.makedirs(os.path.join(args.out, "canonical"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "flat"), exist_ok=True)
    os.makedirs(render_dir, exist_ok=True)

    counts = {
        "bar": args.bar, "line": args.line, "grouped_bar": args.grouped,
        "stacked_bar": args.stacked, "dashboard": args.dashboard,
        "funnel": args.funnel,
    }
    counts = {k: v for k, v in counts.items() if v > 0}
    examples = build_mixed_dataset(counts, render_dir=render_dir, seed=args.seed)

    n_clean, dirty = validate_dataset(examples)
    print(f"Validation: {n_clean}/{len(examples)} clean, {len(dirty)} dirty")
    for eid, probs in dirty[:10]:
        print(f"  DIRTY {eid}: {probs}")

    export_canonical_jsonl(os.path.join(args.out, "canonical", "train.jsonl"), examples)
    export_flattened_jsonl(os.path.join(args.out, "flat", "train.jsonl"), examples)

    n_flat = sum(len(ex.flatten_tasks()) for ex in examples)
    inspect_path = os.path.join(args.out, "inspect.html")
    make_inspect_html(examples, inspect_path)

    print(f"Figures: {len(examples)}  ->  flattened task rows: {n_flat}")
    print(f"  canonical: {os.path.join(args.out, 'canonical', 'train.jsonl')}")
    print(f"  flat:      {os.path.join(args.out, 'flat', 'train.jsonl')}")
    print(f"  inspect:   {inspect_path}  <- OPEN THIS, eyeball ~20 before scaling")


if __name__ == "__main__":
    main()
