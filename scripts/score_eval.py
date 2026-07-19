#!/usr/bin/env python3
"""score_eval.py — score model predictions against the eval holdout manifest.

Input:
  --manifest  path to eval_manifest.jsonl (from build_eval_holdout.py)
  --preds     path to predictions JSONL, one row per task:
                  {"id": "<matches manifest>", "pred": "<raw model output text>"}
              Extra fields are ignored. Missing ids count as skipped, not wrong.

Output:
  Prints overall accuracy plus a per-bucket table (task_type, qa_type,
  chart_type, difficulty, annotated). Writes a JSON summary next to --preds
  named <preds>.report.json for the write-up.

Scoring policy:
  QA — extract the "Answer:" line if present, otherwise the last non-empty line.
       Normalize both sides (case, punctuation, month names, currency/percent,
       thousands separators, trailing zeros), then compare.
       Numeric answers accept a small relative tolerance (default 0.5%).
  table_extraction — parse pred as JSON (strip common code fences).
       Score chart_type match, and per-cell match on the rows table.
       A row is "correct" only if every cell matches after normalization.

Self-test:
  python scripts/score_eval.py --self-test
  Feeds the gold answers back in as predictions; expects 100% on every bucket.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from typing import Any, Optional


MONTH_MAP = {
    "jan": "january", "feb": "february", "mar": "march", "apr": "april",
    "may": "may", "jun": "june", "jul": "july", "aug": "august",
    "sep": "september", "sept": "september", "oct": "october",
    "nov": "november", "dec": "december",
}

_INCREASE_MAP = {"increased": "increase", "decreased": "decrease",
                 "stayed the same": "stay the same", "same": "stay the same"}


def _strip_common(s: str) -> str:
    s = s.strip().lower()
    # collapse whitespace
    s = re.sub(r"\s+", " ", s)
    # strip trailing punctuation
    s = s.rstrip(".!?,;: ")
    return s


def norm_answer(x: Any) -> str:
    """Normalize a QA answer for comparison. Preserves numeric identity."""
    s = _strip_common(str(x))
    s = s.replace("$", "").replace("£", "").replace("€", "").replace(",", "")
    s = MONTH_MAP.get(s, s)
    s = _INCREASE_MAP.get(s, s)
    return s


def as_num(x: str) -> Optional[float]:
    """Extract a float from a normalized answer if it looks numeric."""
    s = norm_answer(x)
    s = s.replace("%", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def qa_match(gold: dict, pred_text: str, tol: float = 0.005) -> bool:
    """True if pred matches gold answer or any listed alias."""
    pred_answer = extract_answer_line(pred_text)
    if pred_answer is None:
        return False
    candidates = [gold["answer"]] + list(gold.get("aliases") or [])
    for cand in candidates:
        if norm_answer(cand) == norm_answer(pred_answer):
            return True
        cn, pn = as_num(cand), as_num(pred_answer)
        if cn is not None and pn is not None:
            if cn == 0:
                if pn == 0:
                    return True
            elif abs(cn - pn) / abs(cn) <= tol:
                return True
    return False


def extract_answer_line(text: str) -> Optional[str]:
    """Get the value after 'Answer:', else the last non-empty stripped line."""
    if not text:
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        low = ln.lower()
        if low.startswith("answer:") or low.startswith("**answer:**"):
            return re.sub(r"^\**answer:\**\s*", "", ln, flags=re.IGNORECASE).strip()
    return lines[-1] if lines else None


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_table_pred(text: str) -> Optional[dict]:
    """Best-effort JSON parse of a table_extraction completion."""
    if not text:
        return None
    stripped = _FENCE.sub("", text.strip())
    # some models wrap with prose before/after — grab the outermost {...}
    m = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _cell_match(gold_cell: Any, pred_cell: Any) -> bool:
    g_num, p_num = as_num(str(gold_cell)), as_num(str(pred_cell))
    if g_num is not None and p_num is not None:
        if g_num == 0:
            return p_num == 0
        return abs(g_num - p_num) / abs(g_num) <= 0.005
    return norm_answer(gold_cell) == norm_answer(pred_cell)


def table_match(gold: dict, pred_text: str) -> tuple[bool, dict]:
    """Score a table extraction. Returns (row_exact, details)."""
    details = {"json_parsed": False, "chart_type_ok": False,
               "rows_gold": 0, "rows_matched": 0, "rows_correct": False}
    parsed = parse_table_pred(pred_text)
    if not isinstance(parsed, dict):
        return False, details
    details["json_parsed"] = True
    details["chart_type_ok"] = (
        norm_answer(parsed.get("chart_type", "")) == norm_answer(gold.get("chart_type", ""))
    )
    gold_rows = gold["table"]["rows"]
    details["rows_gold"] = len(gold_rows)
    pred_table = parsed.get("table") or {}
    pred_rows = pred_table.get("rows") if isinstance(pred_table, dict) else None
    if not isinstance(pred_rows, list) or len(pred_rows) != len(gold_rows):
        return False, details
    matched = 0
    for gr, pr in zip(gold_rows, pred_rows):
        if len(gr) != len(pr):
            break
        if all(_cell_match(g, p) for g, p in zip(gr, pr)):
            matched += 1
    details["rows_matched"] = matched
    details["rows_correct"] = matched == len(gold_rows) and matched > 0
    return details["rows_correct"], details


def bucket_report(rows: list[dict]) -> dict:
    """Compute accuracy overall and by every meaningful bucket."""
    def _acc(items):
        n = len(items)
        c = sum(1 for x in items if x["correct"])
        return {"n": n, "correct": c, "acc": (c / n if n else 0.0)}

    def _by(key):
        d = defaultdict(list)
        for r in rows:
            d[str(r.get(key))].append(r)
        return {k: _acc(v) for k, v in sorted(d.items())}

    return {
        "overall": _acc(rows),
        "by_task_type": _by("task_type"),
        "by_qa_type": _by("qa_type"),
        "by_chart_type": _by("chart_type"),
        "by_difficulty": _by("difficulty"),
        "by_annotated": _by("annotated"),
    }


def score(manifest_path: str, preds_path: str, tol: float = 0.005) -> dict:
    manifest = {}
    with open(manifest_path) as f:
        for line in f:
            row = json.loads(line)
            manifest[row["id"]] = row

    preds = {}
    with open(preds_path) as f:
        for line in f:
            row = json.loads(line)
            if "id" in row and "pred" in row:
                preds[row["id"]] = row["pred"]

    scored = []
    missing = 0
    table_details_agg = {"json_parsed": 0, "chart_type_ok": 0, "rows_correct": 0, "n": 0}

    for eid, task in manifest.items():
        if eid not in preds:
            missing += 1
            continue
        pred = preds[eid]
        if task["task_type"] == "qa":
            ok = qa_match(task["gold"], pred, tol=tol)
        else:
            ok, det = table_match(task["gold"], pred)
            table_details_agg["n"] += 1
            for k in ("json_parsed", "chart_type_ok", "rows_correct"):
                table_details_agg[k] += int(det[k])
        scored.append({
            "id": eid, "correct": ok,
            "task_type": task["task_type"],
            "qa_type": task.get("qa_type", ""),
            "chart_type": task.get("chart_type"),
            "difficulty": task.get("difficulty"),
            "annotated": task.get("annotated"),
        })

    report = bucket_report(scored)
    report["missing_predictions"] = missing
    report["table_diagnostics"] = table_details_agg
    return report


def _print_report(report: dict) -> None:
    o = report["overall"]
    print(f"\nOverall: {o['correct']}/{o['n']} = {100*o['acc']:.1f}%")
    if report.get("missing_predictions"):
        print(f"(missing predictions: {report['missing_predictions']})")

    def _table(title, d):
        if not d:
            return
        print(f"\n{title}")
        for k, v in d.items():
            print(f"  {k:<24s} {v['correct']:>4d}/{v['n']:<4d}  {100*v['acc']:>5.1f}%")

    _table("By task type:", report["by_task_type"])
    _table("By QA type:", report["by_qa_type"])
    _table("By chart type:", report["by_chart_type"])
    _table("By difficulty:", report["by_difficulty"])
    _table("By annotated:", report["by_annotated"])

    td = report.get("table_diagnostics", {})
    if td.get("n"):
        n = td["n"]
        print(f"\nTable diagnostics (n={n}):")
        print(f"  json parsed          {td['json_parsed']:>4d}/{n} = {100*td['json_parsed']/n:.1f}%")
        print(f"  chart_type correct   {td['chart_type_ok']:>4d}/{n} = {100*td['chart_type_ok']/n:.1f}%")
        print(f"  rows all correct     {td['rows_correct']:>4d}/{n} = {100*td['rows_correct']/n:.1f}%")


def _self_test() -> int:
    """Feed gold answers back as predictions; must score 100%."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as pf:
        # build tiny manifest + gold-as-pred inline
        import subprocess
        subprocess.check_call([
            sys.executable,
            "scripts/build_eval_holdout.py",
            "--out", "/tmp/eval_selftest", "--seed", "12345",
            "--bar", "3", "--line", "3", "--grouped", "2",
            "--stacked", "2", "--dashboard", "1", "--funnel", "1",
        ])
        preds_path = pf.name

    with open("/tmp/eval_selftest/eval_manifest.jsonl") as mf, open(preds_path, "w") as pf:
        for line in mf:
            r = json.loads(line)
            g = r["gold"]
            if r["task_type"] == "qa":
                pred = f"Reasoning stub.\nAnswer: {g['answer']}"
            else:
                pred = json.dumps({"title": g["title"], "chart_type": g["chart_type"],
                                   "table": g["table"]})
            pf.write(json.dumps({"id": r["id"], "pred": pred}) + "\n")

    report = score("/tmp/eval_selftest/eval_manifest.jsonl", preds_path)
    _print_report(report)
    acc = report["overall"]["acc"]
    if acc < 0.999:
        print(f"\nSELF-TEST FAILED: {acc:.3f} — scorer has a bug", file=sys.stderr)
        return 1
    print("\nself-test OK (100% on gold-as-pred).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--preds")
    ap.add_argument("--tol", type=float, default=0.005,
                    help="relative tolerance for numeric answers (default 0.5%)")
    ap.add_argument("--self-test", action="store_true",
                    help="verify scorer against gold-as-pred")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not (args.manifest and args.preds):
        ap.error("--manifest and --preds are required (or use --self-test)")

    report = score(args.manifest, args.preds, tol=args.tol)
    _print_report(report)

    out = args.preds + ".report.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nfull report -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
