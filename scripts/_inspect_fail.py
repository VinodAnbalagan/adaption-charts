"""Dump 2 failed + 2 passed numeric rows in full, to see exactly how the
platform's enhanced_completion + reasoning_trace diverge from ground truth.
Helps decide: is reasoning_traces the contamination vector?"""
import json, re

rows = json.load(open("data/adapted/chart_qa_numeric_label.json"))
if isinstance(rows, dict):
    for k in ("rows", "data", "records"):
        if k in rows: rows = rows[k]; break

def norm(s): return str(s).replace(",", "").replace("$", "").strip()
def hit(ans, txt):
    a, t = norm(ans), norm(txt or "")
    if a in t: return True
    m = re.fullmatch(r"-?\d+(\.\d+)?%?", a)
    if m:
        core = a.rstrip("%")
        try:
            f = float(core)
            return any(v in t for v in {core, f"{f:g}", f"{f:.1f}", f"{f:.2f}"})
        except: pass
    return False

passed, failed = [], []
for r in rows:
    try: tgt = json.loads(r["completion"])
    except: continue
    ans = tgt.get("answer")
    if ans is None or tgt.get("answer_type") == "label": continue
    bucket = passed if hit(str(ans), r.get("enhanced_completion","")) else failed
    if len(bucket) < 2:
        bucket.append((r.get("meta_qa_type"), ans, r.get("prompt"),
                       r.get("enhanced_completion",""), r.get("reasoning_trace","")))

for label, group in (("FAILED", failed), ("PASSED", passed)):
    for qa, ans, prompt, enh, trace in group:
        print("="*70)
        print(f"[{label}] qa_type={qa}  EXPECTED={ans}")
        print(f"PROMPT: {prompt}")
        print(f"\nENHANCED_COMPLETION:\n{enh[:700]}")
        print(f"\nREASONING_TRACE:\n{str(trace)[:700]}")
        print()
