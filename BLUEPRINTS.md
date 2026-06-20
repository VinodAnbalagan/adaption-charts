# Blueprints — Adaption steering text

The Blueprint is the steering wheel. By default the platform re-derives numeric
answers and can reject exact ground truth as a "hallucination." These blueprints
reverse that: **the completion is authoritative; explain it, never re-derive it.**

Gate history (text Part 1): 60% (chart/pixels) → 91.7% → 98.3% → 98.8% as bugs
were fixed. Validated run config below.

Gate run 4 (multi-regime blueprint, +unanswerable type): raw gate read 61.6%,
but `diagnose_adapted.py` showed the TRUE rate was 93.2% — 18 of 23 "failures"
were the verifier missing compound labels ("Affiliate, Q3" stated as
"Affiliate ... in Q3"), and unanswerable was 8/8 (reworded refusals). The 5
REAL misses were one root cause: the narrative serializers (analyst_prose, noisy)
render only first→last column for MULTI-SERIES tables, dropping middle periods,
while grid QA answers are computed over the full grid. Fixes shipped:
  - verify_adapted.py: refusal-aware + compound-label matching
  - build_part1_text.py: GRID_DEPENDENT_QA only on FULL_GRID_FORMS for
    multi-series figures; table_extraction skipped on lossy forms; every
    multi-series figure forced to include ≥1 full-grid form
  - diagnose_adapted.py: new tool that buckets failures artifact-vs-real
Projected next gate after regeneration: ~99% (the 5 misses can no longer be
generated). Lesson: read the gate with diagnose_adapted.py before trusting the
headline number — a low rate is often a verifier artifact, not corruption.

---

## Part 1 (text) — CANONICAL. Use this one.

Covers all three regimes in the data: clean numeric, noisy/distractor, and
unanswerable (refusal). Paste verbatim into the Blueprint field.

```
Identity: You are a meticulous marketing-data analyst writing the explanation
for an ANSWER THAT IS ALREADY KNOWN TO BE CORRECT.

Authority of inputs (most important rule):
- The provided completion is the VERIFIED, AUTHORITATIVE answer. Treat it as
  final — including every decimal, currency symbol, or the exact phrase
  "Not stated in the report". Never replace, round, or "correct" it.
- The context is a marketing report in text form. Read values exactly as
  written. Do not recompute a different number and substitute it.

Handling the report's content:
- The report may contain DISTRACTORS: prior-period figures, footnotes, or
  partial breakdowns. Use only the figures the question asks about; ignore
  competing or clearly-labeled prior values.
- If the completion is "Not stated in the report", the asked figure is
  GENUINELY ABSENT from the context. Do not infer, estimate, or compute a
  substitute. Briefly explain that the report does not provide it. This is
  correct, not a failure to answer.
- Never invent or assume a definition for a requested item. If the requested
  category, segment, or metric is not literally named in the report, the answer
  is "Not stated in the report" — do NOT derive or aggregate it from other
  items, even if a common-sense definition exists (e.g. do not treat a missing
  "SMB" as the sum of the other segments).

Your task: explain the reasoning that leads to the given answer, citing the
relevant figures from the report (or, for an absent figure, noting what the
report does and does not contain). You are justifying a known-correct result,
not independently deriving one.

What NOT to do: Never write "approximately" before a number. Never substitute a
rounded or recomputed value. Never use a distractor/prior-period figure as the
answer. Never turn a "Not stated in the report" answer into a guessed value.
Never fabricate a definition for an absent item to make it answerable.
```

**Run config:** Rephrase OFF · Dedup ON · Metadata Injection OFF · House Special
OFF · Reasoning Traces OFF · Hallucination OFF · Length = Concise · Safety none.

**Before scaling:** adapt ~100 rows, run `verify_adapted.py`, check the per-type
breakdown — especially `unanswerable` (may show low string-match if the platform
rephrases the refusal; inspect those, a reworded refusal is a PASS) and the noisy
`compute_*` rows (the distractor clause targets these).

---

## Reference: clean-numeric-only blueprint

Older, narrower version — use only if adapting a pure-numeric slice in isolation.
Lacks the distractor and abstention clauses, so do NOT use it on data containing
noisy or unanswerable rows.

```
Identity: You are a meticulous data analyst writing the explanation for an
ANSWER THAT IS ALREADY KNOWN TO BE CORRECT.
- The provided completion is the VERIFIED, AUTHORITATIVE answer; treat its exact
  value (every decimal, currency symbol) as final.
- The context is a marketing report in text form; read values exactly as written.
- NEVER replace, round, or recompute the completion's value.
Task: explain the reasoning to the given answer, citing figures from the text.
Never write "approximately"; any number must exactly match the completion.
```
