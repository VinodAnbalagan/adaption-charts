"""Inspect compute_ratio_percent failures in full — is the platform's recomputed
percentage actually WRONG, or just formatted differently (20.1 vs 20.13 vs '20.1%')?"""
import json, re

rows = json.load(open("data/adapted/marketing_funnel_qa.json"))
if isinstance(rows, dict):
    for k in ("rows","data","records"):
        if k in rows: rows = rows[k]; break

def norm(s): return str(s).replace(",","").replace("$","").replace("%","").strip()
def hit(ans, txt):
    a,t = norm(ans), norm(txt or "")
    if a in t: return True
    try:
        f=float(a); return any(v in t for v in {a,f"{f:g}",f"{f:.1f}",f"{f:.2f}"})
    except: return False

shown=0
for r in rows:
    if r.get("meta_qa_type")!="compute_ratio_percent": continue
    try: tgt=json.loads(r["completion"])
    except: continue
    ans=str(tgt.get("answer"))
    enh=r.get("enhanced_completion","")
    if hit(ans, enh): continue   # only failures
    shown+=1
    print("="*70)
    print(f"EXPECTED: {ans}")
    print(f"PROMPT: {r.get('prompt')}")
    print(f"CONTEXT (text):\n{r.get('context','')[:400]}")
    print(f"\nFULL ENHANCED_COMPLETION:\n{enh}")
    print()
    if shown>=3: break
