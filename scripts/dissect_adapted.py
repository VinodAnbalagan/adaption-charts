#!/usr/bin/env python3
"""dissect_adapted.py — full forensic read of a (possibly huge) adapted file, to
explain a WEAK win-rate rather than just numeric preservation.

verify/diagnose answer "did the platform keep my numbers?". This answers the
different question "is the TRAINING TARGET (enhanced_completion) actually good
supervision?" — because a low win-rate usually means the targets are noisy:
off-topic rows, self-correcting/contradicting reasoning, wrong final answers,
or bloat. Streams the file so 138 MB is fine.

Usage:
    python scripts/dissect_adapted.py --adapted data/adapted/marketing_metrics_qa.json
    python scripts/dissect_adapted.py --adapted data/adapted/marketing_metrics_qa.json --dump CONTRADICTION --n 8
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict


# ---------------------------------------------------------------- load (stream)
def load_rows(path):
    """Load a JSON array OR JSONL. For the big array case, json.load is fine on a
    modern machine (138 MB -> a few GB RAM); fall back to JSONL line parsing."""
    with open(path, "r", encoding="utf-8") as f:
        first = f.read(1)
        f.seek(0)
        if first == "[":
            return json.load(f)
        rows = []
        for line in f:
            line = line.strip().rstrip(",")
            if line and line[0] == "{":
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows


# ---------------------------------------------------------------- helpers
MARKETING_TERMS = (
    "channel", "campaign", "spend", "revenue", "conversion", "ctr", "cpc", "cpa",
    "roas", "funnel", "impression", "clicks", "leads", "mql", "sql", "quarter",
    "dashboard", "segment", "kpi", "paid search", "organic", "affiliate",
    "pipeline", "marketing", "email", "social", "display",
)

CONTRADICTION_CUES = (
    "is incorrect", "re-evaluating", "re-evaluate", "correction", "wait,",
    "actually,", "let me reconsider", "on second thought", "i made an error",
    "that's wrong", "scratch that", "apologies", "my mistake", "revising",
    "upon further", "strict data review", "recalculating", "i need to correct",
)

REFUSAL_CUES = (
    "not stated", "cannot be determined", "does not provide", "not available",
    "no data", "not contain", "unable to",
)


def get(row, *keys):
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def text_of(row, *keys):
    v = get(row, *keys)
    return str(v) if v is not None else ""


def parse_completion(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def is_marketing(text):
    tl = text.lower()
    return any(t in tl for t in MARKETING_TERMS)


def has_contradiction(text):
    tl = text.lower()
    return any(c in tl for c in CONTRADICTION_CUES)


def final_answer_correct(answer, enh):
    """Heuristic: does the EXACT ground-truth answer appear in the enhanced text,
    ideally near the end (a clean final answer) rather than only mid-reasoning?"""
    if answer is None:
        return None
    a = str(answer).replace(",", "").replace("$", "").strip().lower()
    if not a:
        return None
    t = enh.replace(",", "").replace("$", "").lower()
    # compound 'X, Y'
    parts = [p.strip() for p in str(answer).split(",")]
    if len(parts) >= 2:
        return all(p.strip().lower() in enh.lower() for p in parts if p.strip())
    return a in t


def tail_has_answer(answer, enh, tail_chars=200):
    if answer is None:
        return None
    parts = [p.strip().lower() for p in str(answer).split(",") if p.strip()]
    tail = enh[-tail_chars:].lower()
    return all(p in tail for p in parts) if parts else None


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapted", required=True)
    ap.add_argument("--dump", default=None,
                    help="bucket to print examples from: CONTRADICTION | OFFTOPIC | "
                         "WRONG_FINAL | BLOATED | ANSWER_NOT_IN_TAIL")
    ap.add_argument("--n", type=int, default=6)
    args = ap.parse_args()

    rows = load_rows(args.adapted)
    n = len(rows)
    print(f"Loaded {n:,} rows from {args.adapted}")
    if not n:
        return
    print(f"Row keys: {list(rows[0].keys())}\n")

    # detect column names once
    r0 = rows[0]
    def findkey(*needles):
        for k in r0.keys():
            kn = k.lower().replace(" ", "_")
            if all(nd in kn for nd in needles):
                return k
        return None
    k_prompt = findkey("prompt") if "enhanced" not in str(findkey("prompt")) else None
    k_orig = findkey("original", "completion") or "completion"
    k_enh = None
    for k in r0.keys():
        kn = k.lower().replace(" ", "_")
        if "enhanced" in kn and "completion" in kn and "reasoning" not in kn:
            k_enh = k
    k_enh = k_enh or "enhanced_completion"
    k_ctx = findkey("context")
    k_qa = findkey("qa_type") or findkey("meta", "qa")
    print(f"Using original='{k_orig}'  enhanced='{k_enh}'  qa_type='{k_qa}'\n")

    # accumulators
    stats = Counter()
    by_qa = defaultdict(Counter)
    enh_lengths = []
    orig_lengths = []
    qa_dist = Counter()
    form_dist = Counter()
    buckets = defaultdict(list)
    dup_enh = Counter()

    for row in rows:
        enh = text_of(row, k_enh)
        orig_raw = get(row, k_orig)
        tgt = parse_completion(orig_raw)
        answer = tgt.get("answer") if isinstance(tgt, dict) else None
        qa_type = text_of(row, k_qa) or "unknown"
        ctx = text_of(row, k_ctx)
        prompt = text_of(row, "prompt", "enhanced_prompt")

        qa_dist[qa_type] += 1
        form_dist[text_of(row, "meta_text_form") or "n/a"] += 1
        enh_lengths.append(len(enh))
        orig_lengths.append(len(str(orig_raw)))
        dup_enh[enh.strip()[:400]] += 1

        # 1) on-topic vs off-topic (diversity/general data dilution)
        blob = (prompt + " " + ctx + " " + enh)
        offtopic = not is_marketing(blob)
        if offtopic:
            stats["OFFTOPIC"] += 1
            if len(buckets["OFFTOPIC"]) < 40:
                buckets["OFFTOPIC"].append((qa_type, answer, prompt[:160], enh[:240]))

        # 2) contradiction / self-correction in the target
        if has_contradiction(enh):
            stats["CONTRADICTION"] += 1
            by_qa[qa_type]["CONTRADICTION"] += 1
            if len(buckets["CONTRADICTION"]) < 40:
                buckets["CONTRADICTION"].append((qa_type, answer, prompt[:160], enh[:500]))

        # 3) correctness of the final target (only where we have a GT answer)
        if answer is not None and not offtopic:
            fa = final_answer_correct(answer, enh)
            th = tail_has_answer(answer, enh)
            is_refusal_ans = str(answer).strip().lower().startswith("not stated")
            if fa is False and not is_refusal_ans:
                stats["WRONG_FINAL"] += 1
                by_qa[qa_type]["WRONG_FINAL"] += 1
                if len(buckets["WRONG_FINAL"]) < 40:
                    buckets["WRONG_FINAL"].append((qa_type, answer, prompt[:160], enh[:400]))
            elif fa is True:
                stats["answer_present"] += 1
                if th is False:
                    stats["ANSWER_NOT_IN_TAIL"] += 1   # answer buried mid-reasoning, not concluded
                    if len(buckets["ANSWER_NOT_IN_TAIL"]) < 40:
                        buckets["ANSWER_NOT_IN_TAIL"].append((qa_type, answer, prompt[:160], enh[:400]))

        # 4) bloat: very long target for a one-number answer
        if answer is not None and len(enh) > 1200:
            stats["BLOATED"] += 1
            if len(buckets["BLOATED"]) < 40:
                buckets["BLOATED"].append((qa_type, answer, prompt[:160], enh[:300]))

    # ----------------------------------------------------------- report
    def pct(x):
        return f"{100.0*x/n:5.1f}%"

    print("=" * 70)
    print("ROW COMPOSITION")
    print(f"  total rows                : {n:,}")
    print(f"  OFF-TOPIC (non-marketing) : {stats['OFFTOPIC']:,}  ({pct(stats['OFFTOPIC'])})  <- diversity/general dilution")
    on = n - stats["OFFTOPIC"]
    print(f"  on-topic marketing        : {on:,}  ({pct(on)})")

    print("\nQA_TYPE DISTRIBUTION (top 15):")
    for t, c in qa_dist.most_common(15):
        print(f"  {t:32s} {c:6,}  ({pct(c)})")

    print("\n" + "=" * 70)
    print("TRAINING-TARGET QUALITY  (enhanced_completion = what the model learns)")
    gt = stats["answer_present"] + stats["WRONG_FINAL"]
    print(f"  rows with a checkable answer        : {gt:,}")
    if gt:
        print(f"  final answer CORRECT (GT present)   : {stats['answer_present']:,}  ({100.0*stats['answer_present']/gt:4.1f}% of checkable)")
        print(f"  final answer WRONG / missing        : {stats['WRONG_FINAL']:,}  ({100.0*stats['WRONG_FINAL']/gt:4.1f}% of checkable)  <- BAD supervision")
    print(f"  self-correcting / CONTRADICTION text: {stats['CONTRADICTION']:,}  ({pct(stats['CONTRADICTION'])})  <- noisy reasoning target")
    print(f"  answer buried (not in conclusion)   : {stats['ANSWER_NOT_IN_TAIL']:,}  ({pct(stats['ANSWER_NOT_IN_TAIL'])})")
    print(f"  BLOATED targets (>1200 chars)       : {stats['BLOATED']:,}  ({pct(stats['BLOATED'])})")

    if enh_lengths:
        enh_lengths.sort()
        orig_lengths.sort()
        mid = enh_lengths[len(enh_lengths) // 2]
        p90 = enh_lengths[int(len(enh_lengths) * 0.9)]
        omid = orig_lengths[len(orig_lengths) // 2]
        print(f"\n  enhanced_completion length: median {mid:,}  p90 {p90:,}  max {enh_lengths[-1]:,} chars")
        print(f"  original  completion length: median {omid:,} chars   (enhanced is ~{mid/max(1,omid):.1f}x longer)")

    # near-duplicate targets (augmentation repeating itself)
    dups = [(k, c) for k, c in dup_enh.items() if c > 1]
    dup_rows = sum(c for _, c in dups)
    print(f"\n  near-duplicate targets (same first 400 chars): {dup_rows:,} rows across {len(dups):,} clusters")
    if dups:
        top = sorted(dups, key=lambda x: -x[1])[:3]
        for k, c in top:
            print(f"     x{c:4d}: {k[:90]!r}...")

    print("\nCONTRADICTION rate by qa_type (where >0):")
    for t in sorted(by_qa, key=lambda t: -by_qa[t]["CONTRADICTION"]):
        cc = by_qa[t]["CONTRADICTION"]
        wf = by_qa[t]["WRONG_FINAL"]
        if cc or wf:
            tot = qa_dist[t]
            print(f"  {t:32s} contradiction {cc:5,}/{tot:<6,} ({100.0*cc/max(1,tot):4.1f}%)   wrong_final {wf:,}")

    print("\n" + "=" * 70)
    print("READOUT")
    contr = 100.0 * stats["CONTRADICTION"] / n
    off = 100.0 * stats["OFFTOPIC"] / n
    wrong = 100.0 * stats["WRONG_FINAL"] / max(1, gt)
    flags = []
    if off >= 15:   flags.append(f"- {off:.0f}% off-topic rows are diluting the marketing signal.")
    if contr >= 8:  flags.append(f"- {contr:.0f}% of targets self-correct/contradict — noisy supervision that caps win-rate.")
    if wrong >= 5:  flags.append(f"- {wrong:.0f}% of checkable targets end on the WRONG answer — actively harmful rows.")
    if stats["BLOATED"] > 0.15 * n: flags.append("- many targets are bloated; the model learns to ramble, not answer.")
    if not flags:
        flags.append("- no single dominant defect; weak win-rate is likely a strong base model (low headroom) rather than bad data.")
    print("\n".join(flags))
    print("\nUse --dump CONTRADICTION (or OFFTOPIC / WRONG_FINAL / BLOATED) --n 8 to see examples.")

    if args.dump and args.dump in buckets:
        print("\n" + "#" * 70)
        print(f"# EXAMPLES: {args.dump}")
        print("#" * 70)
        for qa_type, answer, prompt, enh in buckets[args.dump][:args.n]:
            print("=" * 64)
            print(f"qa_type={qa_type}   GT answer={answer!r}")
            print(f"PROMPT : {prompt}")
            print(f"TARGET : {enh}")
            print()


if __name__ == "__main__":
    main()
