#!/usr/bin/env python3
"""verify_adapted.py — the numeric-preservation gate, run programmatically.

Compares each row's ORIGINAL ground-truth answer against the ENHANCED completion
returned by Adaptive Data. Reports, per answer_type and qa_type:
  - preserved : the exact answer value appears in the enhanced completion
  - missing   : it does not (numeric rows: likely replaced by the platform's
                own visual estimate -> CORRUPTION for training purposes)

Usage:
    python scripts/verify_adapted.py --adapted data/adapted/chart_qa_numeric_label.json
    (also accepts .parquet)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict


def load_rows(path: str):
    if path.endswith(".parquet"):
        import pandas as pd
        df = pd.read_parquet(path)
        return df.to_dict(orient="records")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # common wrappers: {"rows": [...]} / {"data": [...]}
        for key in ("rows", "data", "records", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
        raise SystemExit(f"Unrecognized JSON structure; top-level keys: {list(data.keys())}")
    return data


def find_key(row: dict, *needles: str):
    """Find the first key containing ALL needles (case/format-insensitive)."""
    for k in row.keys():
        norm = k.lower().replace(" ", "_")
        if all(n in norm for n in needles):
            return k
    return None


def norm_num(s: str) -> str:
    return s.replace(",", "").replace("$", "").strip()


# --- refusal / compound matching --------------------------------------------
REFUSAL_CUES = (
    "not stated", "not in the report", "not available", "cannot be determined",
    "not shown", "not provided", "does not", "no data", "not mention",
    "not include", "not listed", "not present", "unable to", "n/a",
    "no information", "not specify", "not contain", "not appear",
    "is not", "are not reported", "cannot be", "doesn't", "don't",
)


def is_refusal(text: str) -> bool:
    """True if the enhanced completion expresses 'this isn't in the report'.
    Used for unanswerable rows, where the platform legitimately rewords the
    canonical refusal (e.g. 'the report does not provide this figure')."""
    tl = (text or "").lower()
    return any(c in tl for c in REFUSAL_CUES)


def compound_label_match(answer: str, text: str) -> bool:
    """For compound LABEL answers like 'Affiliate, Q3' (a grid cell = category +
    series). The platform routinely states both parts correctly but not as a
    comma-joined string ('Affiliate ... in Q3'), so require every comma-part to
    appear, rather than the exact joined form."""
    parts = [p.strip() for p in str(answer).split(",") if p.strip()]
    if len(parts) < 2:
        return False
    tl = text.lower()
    return all(p.lower() in tl for p in parts)


EQUAL_CUES = (
    "equal", "the same", "identical", "no difference", "neither", "a tie",
    "both are", "are the same", "are identical", "same value", "same conversion",
    "same rate", "tied",
)


def is_equal_statement(text: str) -> bool:
    """For compare_values answers whose ground truth is 'equal'. The platform is
    usually correct but phrases it as 'identical' / 'neither was higher', which a
    substring match on 'equal' would miss."""
    tl = (text or "").lower()
    return any(c in tl for c in EQUAL_CUES)


def is_transition_answer(answer: str) -> bool:
    a = str(answer)
    return (" to " in a) or ("->" in a) or ("\u2192" in a)


def transition_match(answer: str, text: str) -> bool:
    """For 'X to Y' transition answers (diagnostic bottleneck). The platform
    writes 'X \u2192 Y' or 'X to Y' with varied spacing; accept if BOTH endpoints
    appear in the text."""
    parts = [p.strip() for p in re.split(r"\s*(?:->|\u2192|\bto\b)\s*", str(answer)) if p.strip()]
    if len(parts) < 2:
        return False
    tl = text.lower()
    return all(p.lower() in tl for p in parts)


def answer_in_text(answer: str, text: str, tol: float = 0.0) -> bool:
    """Exact-value containment, tolerant of commas/$ and trailing .0.
    If tol>0 and both answer and a number in text are numeric, accept a match
    within +/- tol (used for percentages, where 20.07% rounds to 20.1%)."""
    if not text:
        return False
    a, t = norm_num(str(answer)), norm_num(str(text))
    if a in t:
        return True
    # numeric: try float-equivalent forms (570 vs 570.0)
    m = re.fullmatch(r"-?\d+(\.\d+)?%?", a)
    if m:
        core = a.rstrip("%")
        try:
            f = float(core)
            variants = {core, f"{f:g}", f"{f:.1f}", f"{f:.2f}", str(int(f)) if f == int(f) else None}
            if any(v is not None and v in t for v in variants):
                return True
            # rounding tolerance: scan numbers in the text for a near-match
            if tol > 0:
                for num in re.findall(r"-?\d+(?:\.\d+)?", t):
                    try:
                        if abs(float(num) - f) <= tol:
                            return True
                    except ValueError:
                        pass
        except ValueError:
            pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapted", required=True)
    ap.add_argument("--show-failures", type=int, default=5)
    args = ap.parse_args()

    rows = load_rows(args.adapted)
    print(f"Loaded {len(rows)} rows from {args.adapted}")
    if not rows:
        sys.exit("Empty file.")

    print(f"Row keys: {list(rows[0].keys())}\n")

    r0 = rows[0]
    k_orig = find_key(r0, "original", "completion") or find_key(r0, "completion")
    k_enh = None
    for k in r0.keys():
        norm = k.lower().replace(" ", "_")
        if "enhanced" in norm and "completion" in norm and "reasoning" not in norm:
            k_enh = k
            break
    k_reason = find_key(r0, "enhanced", "reasoning")
    k_qa_type = find_key(r0, "qa_type") or find_key(r0, "meta_qa_type")

    if not k_orig or not k_enh:
        sys.exit(f"Could not locate columns. orig={k_orig} enh={k_enh}. Inspect keys above.")
    print(f"Using: original='{k_orig}'  enhanced='{k_enh}'  reasoning='{k_reason}'  qa_type='{k_qa_type}'\n")

    stats = Counter()
    by_type = defaultdict(Counter)
    failures = []

    for i, row in enumerate(rows):
        raw = row.get(k_orig)
        try:
            tgt = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            stats["unparseable_original"] += 1
            continue
        answer = tgt.get("answer")
        if answer is None:
            # table-extraction style target: check a sample of cell values instead
            stats["no_answer_field"] += 1
            continue
        answer_type = tgt.get("answer_type", "unknown")
        qa_type = (row.get(k_qa_type) or "unknown") if k_qa_type else "unknown"

        enh = str(row.get(k_enh) or "")
        # Matching strategy depends on the answer's nature:
        #  - unanswerable: accept any reworded refusal;
        #  - 'equal' answers: accept any equality phrasing ('identical'/'neither');
        #  - transition 'X to Y': accept if both endpoints appear (arrow/spacing);
        #  - compound label 'Category, Series': accept if BOTH parts appear;
        #  - percentages: +/-0.1 rounding tolerance;
        #  - everything else: exact-value containment.
        ans_l = str(answer).strip().lower()
        if answer_type == "unanswerable" or qa_type == "unanswerable":
            ok = is_refusal(enh)
        elif ans_l in ("equal", "the same", "same", "identical", "tie"):
            ok = is_equal_statement(enh)
        elif is_transition_answer(answer):
            ok = transition_match(str(answer), enh) or answer_in_text(str(answer), enh)
        elif answer_type == "label" and "," in str(answer):
            ok = compound_label_match(str(answer), enh) or answer_in_text(str(answer), enh)
        else:
            # percentages get a rounding tolerance: the platform re-derives from the
            # exact (preserved) counts and reports MORE precision than our 1-dp
            # canonical (54.59% vs 54.6%), which is correct, not a miss. Applies to
            # compute_ratio_percent, funnel_conversion, and any 'NN.N%' answer.
            is_pct = (qa_type in ("compute_ratio_percent", "funnel_conversion")
                      or str(answer).strip().endswith("%"))
            tol = 0.1 if is_pct else 0.0
            ok = answer_in_text(str(answer), enh, tol=tol)
        stats["preserved" if ok else "MISSING"] += 1
        by_type[answer_type]["preserved" if ok else "MISSING"] += 1
        by_type[f"qa:{qa_type}"]["preserved" if ok else "MISSING"] += 1
        if not ok and len(failures) < args.show_failures:
            failures.append((i, answer, enh[:300]))

    total = stats["preserved"] + stats["MISSING"]
    print("=== NUMERIC-PRESERVATION GATE ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if total:
        rate = 100.0 * stats["preserved"] / total
        print(f"\n  PRESERVATION RATE: {rate:.1f}%  ({stats['preserved']}/{total})")
        print("  Verdict: " + ("PASS — proceed to full run" if rate >= 95 else
                               "MARGINAL — inspect failures before scaling" if rate >= 85 else
                               "FAIL — do NOT scale; reconfigure first"))
    print("\nPer type:")
    for t, c in sorted(by_type.items()):
        tt = c["preserved"] + c["MISSING"]
        print(f"  {t}: {c['preserved']}/{tt} preserved")
    if failures:
        print(f"\nFirst {len(failures)} failures (row_idx, expected_answer, enhanced_excerpt):")
        for i, a, e in failures:
            print(f"  [{i}] expected '{a}' NOT found in: {e!r}")


if __name__ == "__main__":
    main()
