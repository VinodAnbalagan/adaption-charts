#!/usr/bin/env python3
"""diagnose_adapted.py — go BEYOND the pass/fail gate: categorize every failure
so a low preservation rate can be read as "verifier artifact" vs "real bug".

The plain gate (verify_adapted.py) gives a number. When that number is low, the
question is always: is the platform actually corrupting answers, or is the
verifier just too strict (compound labels, reworded refusals, rounding)? This
script answers that by bucketing each failure:

  FORMAT_compound_all_parts_present : answer is 'Category, Series' and BOTH parts
                                      appear -> platform correct, format differs
  REFUSAL_OK_reworded               : unanswerable row; platform refused, just
                                      not with the canonical phrase
  REFUSAL_FAIL_invented_answer      : unanswerable row; platform invented a value
                                      (this is a REAL problem)
  NUMERIC_near_value_present        : numeric answer; a value within tolerance is
                                      present (rounding/format artifact)
  GENUINE_MISS                      : none of the above -> investigate

It also reports preservation PER text_form, which localizes serializer bugs
(e.g. analyst_prose/noisy dropping cells for multi-series tables).

Usage:
    python scripts/diagnose_adapted.py --adapted data/adapted/<file>.json [--dump GENUINE_MISS]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict


def load_rows(path: str):
    if path.endswith(".parquet"):
        import pandas as pd
        return pd.read_parquet(path).to_dict(orient="records")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for k in ("rows", "data", "records", "items"):
            if k in data and isinstance(data[k], list):
                return data[k]
    return data


def norm(s):
    return str(s).replace(",", " ").replace("$", "").replace("%", "").lower().strip()


def num_norm(s):
    return str(s).replace(",", "").replace("$", "").replace("%", "").strip()


def strict_hit(ans, txt):
    a, t = num_norm(str(ans)), num_norm(str(txt))
    if a.lower() in t.lower():
        return True
    if re.fullmatch(r"-?\d+(\.\d+)?%?", a):
        core = a.rstrip("%")
        try:
            f = float(core)
            return any(v in t for v in {core, f"{f:g}", f"{f:.1f}", f"{f:.2f}"})
        except ValueError:
            return False
    return False


def all_parts_present(ans, txt):
    parts = [p.strip() for p in str(ans).split(",") if p.strip()]
    if len(parts) < 2:
        return False
    tl = norm(txt)
    return all(norm(p) in tl for p in parts)


def near_number(ans, txt):
    a = num_norm(str(ans)).rstrip("%")
    try:
        f = float(a)
    except ValueError:
        return False
    for num in re.findall(r"-?\d+(?:\.\d+)?", num_norm(txt)):
        try:
            if abs(float(num) - f) <= max(0.15, abs(f) * 0.005):
                return True
        except ValueError:
            pass
    return False


REFUSAL_CUES = ("not stated", "not in the report", "not available", "cannot be",
                "not shown", "not provided", "does not", "no data", "not mention",
                "not include", "not listed", "not present", "unable to", "n/a",
                "no information", "not specify", "not contain", "not appear",
                "is not", "are not reported", "doesn't", "don't", "omitting", "omits")


def has_refusal(txt):
    tl = txt.lower()
    return any(c in tl for c in REFUSAL_CUES)


EQUAL_CUES = ("equal", "the same", "identical", "no difference", "neither",
              "a tie", "both are", "are the same", "are identical", "same value",
              "same rate", "tied")


def is_equal_statement(txt):
    tl = (txt or "").lower()
    return any(c in tl for c in EQUAL_CUES)


def transition_present(ans, txt):
    """For 'X to Y' answers: both endpoints present (arrow/'to'/spacing agnostic)."""
    parts = [p.strip() for p in re.split(r"\s*(?:->|\u2192|\bto\b)\s*", str(ans)) if p.strip()]
    if len(parts) < 2:
        return False
    tl = norm(txt)
    return all(norm(p) in tl for p in parts)


def states_number(txt):
    return bool(re.search(r"\d{2,}", txt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapted", required=True)
    ap.add_argument("--dump", default=None,
                    help="bucket name to print in full (e.g. GENUINE_MISS)")
    args = ap.parse_args()

    rows = load_rows(args.adapted)
    by_type = defaultdict(lambda: {"n": 0, "pass": 0})
    by_form = defaultdict(lambda: {"n": 0, "pass": 0})
    cats = defaultdict(int)
    buckets = defaultdict(list)

    for r in rows:
        try:
            tgt = json.loads(r["completion"]) if isinstance(r["completion"], str) else r["completion"]
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
        ans = tgt.get("answer")
        if ans is None:
            continue
        atype = tgt.get("answer_type", "?")
        qatype = r.get("meta_qa_type", "?")
        form = r.get("meta_text_form", "?")
        enh = str(r.get("enhanced_completion") or "")

        hit = strict_hit(ans, enh)
        by_type[qatype]["n"] += 1
        by_type[qatype]["pass"] += int(hit)
        by_form[form]["n"] += 1
        by_form[form]["pass"] += int(hit)
        if hit:
            continue

        ans_l = str(ans).strip().lower()
        if atype == "unanswerable" or qatype == "unanswerable":
            if has_refusal(enh) and not states_number(enh.split(".")[0]):
                cat = "REFUSAL_OK_reworded"
            elif has_refusal(enh):
                cat = "REFUSAL_hedged_has_number"
            else:
                cat = "REFUSAL_FAIL_invented_answer"
        elif ans_l in ("equal", "the same", "same", "identical", "tie") and is_equal_statement(enh):
            cat = "FORMAT_equal_stated"
        elif ((" to " in str(ans)) or ("->" in str(ans)) or ("\u2192" in str(ans))) and transition_present(ans, enh):
            cat = "FORMAT_transition_both_parts"
        elif "," in str(ans) and all_parts_present(ans, enh):
            cat = "FORMAT_compound_all_parts_present"
        elif atype in ("numeric", "numeric_with_unit") and near_number(ans, enh):
            cat = "NUMERIC_near_value_present"
        elif atype == "label" and norm(str(ans)) in norm(enh):
            cat = "LABEL_present_verifier_missed"
        else:
            cat = "GENUINE_MISS"
        cats[cat] += 1
        buckets[cat].append((qatype, form, ans, r.get("prompt", ""), enh, r.get("context", "")))

    print("=" * 68)
    print("PER QA_TYPE (strict):")
    for t in sorted(by_type):
        d = by_type[t]
        print(f"  {t:28s} {d['pass']:3d}/{d['n']:<3d}")
    print("\nPER TEXT_FORM (strict)  <- localizes serializer bugs:")
    for t in sorted(by_form):
        d = by_form[t]
        print(f"  {t:18s} {d['pass']:3d}/{d['n']:<3d}")
    print("\n" + "=" * 68)
    print("FAILURE CATEGORIZATION:")
    artifact = ("FORMAT_compound_all_parts_present", "REFUSAL_OK_reworded",
                "NUMERIC_near_value_present", "LABEL_present_verifier_missed",
                "FORMAT_equal_stated", "FORMAT_transition_both_parts")
    real = ("GENUINE_MISS", "REFUSAL_FAIL_invented_answer", "REFUSAL_hedged_has_number")
    for c in sorted(cats, key=lambda k: -cats[k]):
        tag = "(verifier artifact)" if c in artifact else "(REAL — investigate)" if c in real else ""
        print(f"  {c:38s} {cats[c]:3d}  {tag}")
    print(f"  {'TOTAL FAILURES':38s} {sum(cats.values()):3d}")
    n_art = sum(cats[c] for c in artifact)
    n_real = sum(cats[c] for c in real)
    print(f"\n  -> {n_art} artifact (correct, verifier-fixable) | {n_real} real (need a fix)")

    if args.dump and args.dump in buckets:
        print("\n" + "#" * 68)
        print(f"# FULL DUMP: {args.dump}")
        print("#" * 68)
        for qatype, form, ans, prompt, enh, ctx in buckets[args.dump]:
            print("=" * 64)
            print(f"qa_type={qatype}  form={form}")
            print(f"EXPECTED: {ans}")
            print(f"PROMPT: {prompt}")
            print(f"CONTEXT:\n{ctx[:500]}")
            print(f"ENHANCED:\n{enh[:650]}\n")


if __name__ == "__main__":
    main()
