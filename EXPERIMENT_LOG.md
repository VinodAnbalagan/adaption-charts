# Part 2 Experiment Log — Data Visualization Track

Chronological record of every experiment, config, and finding. Source of truth
for the submission write-up and any later blog post.

## Dataset lineage

| Version | Figures | Rows | Notes |
|---|---|---|---|
| Pilot (v2 generator) | 73 | 378 | First multimodal export; scored B (8/10), percentile 11.8 |
| v2 + phrasing variants | 310 | 1,620 | 3–5 phrasings per QA site + varied table prompts; unique prompts 29%→48%; built to clear AutoScientist's 1,000-row minimum |

Generator v2 features (2026-07-07): annotated/unannotated split (ChartMuseum-motivated;
unannotated values snapped to nice tick-aligned grid), truncated_axis nuisance,
font_scale / jpeg_artifact / partial_overlap actually applied, unique-max guards
(pre-existing tie bug fixed), walk-span line snapping (degenerate flat-line fix),
crowded legend over plot area. Prompt phrasing variants added 2026-07-16.

## Platform findings (chronological)

**2026-07-10 — ingestion.** Image URLs (HF-hosted) map to the `context` column;
platform renders them as "context images". Dataset eval: B, 8/10.

**2026-07-16 — AutoScientist minimum.** Finetuning requires ≥1,000 rows;
augmentation unavailable for image datasets, so the minimum must be met natively.
(378-row pilot blocked; rebuilt at 310 figures / 1,620 rows.)

**2026-07-16 — dedup semantics.** Text-style prompt deduplication would treat
same-prompt/different-image rows as duplicates (measured: 1,634 rows → 478 unique
prompts pre-variants). Prompt Deduplication turned OFF for image datasets.

## Training runs

### Run 1 — "Baseline" (2026-07-16)
- Adaptive Data: ALL recipes off (incl. dedup), no blueprint, length minimal
- AutoScientist: auto recipe — google/gemma-3-27b-it-VLM ("large" chosen deliberately
  as the control arm of the headroom experiment), LoRA r=32, α=64, 4 epochs,
  lr 5e-5 cosine, warmup 0.05, train_on_inputs=false
- **Result: base 30 → adapted 70 (win rate on own dataset)**

### Run 2 — "All-features" (2026-07-17)
- Adaptive Data: everything ON (House Special, reasoning traces, hallucination
  mitigation, rephrase+metadata) + strict numeric-fidelity blueprint
- Trained on enhanced_prompt/enhanced_completion
- **Result: base 69 → adapted 31 — INVERSION; adapted loses to base by 38 pts**

### CSV forensics — Run 1 vs Run 2 datasets (1,620 rows each, 2026-07-17)

| Metric | Baseline | All-features |
|---|---|---|
| Completions rewritten by enhancement | 100% | 100% |
| True semantic corruption of QA answers (wrong number / type flip / label change) | 12.7% | 4.7% |
| Benign formatting drift ($18000.0→18000, Mar→March) | ~82% of changes | — |
| Approximation language in completions | 15% | 7% |
| `Answer:` line intact | 99% | 39% |
| Table rows still pure JSON | 78% | 34% |
| Platform judge/compare commentary leaked into completions | 18 rows | **161 rows (~10%)** |

**Key conclusions:**
1. Enhancement rewrites every completion in every config; toggles change *how*, not *whether*.
2. Blueprint + hallucination mitigation genuinely work: 2.7× less semantic corruption.
3. Reasoning traces / checklist machinery destroy exact output format AND leak
   internal judge commentary ("Step 1 — Compare: Response 0 & 2…") into training
   targets — the proximate cause of Run 2's inversion.
4. Run 1's 70% was achieved on 12.7%-corrupted answers → 70 is a floor.

### Run 3 — "Grounded" (2026-07-18) — RESULT: hypothesis FALSIFIED
- Adaptive Data: blueprint ON (strict label-only numeric fidelity + abstain rule)
  + hallucination mitigation ON; traces/House Special/rephrase/dedup OFF; length minimal
- Base: gemma_4_31b_it_vlm (NOTE: base changed vs runs 1-2's gemma_3_27b — confound)
- **Result: base 88 → adapted 12 — worst of all runs.** Platform's own quality
  panel agreed: adaptive text 7.7 vs original 8.0 (−3.7%), percentile 25.6→11.8.

**Forensics (vs prior runs):** format survived (98% Answer-lines, 66% JSON) but
true corruption DOUBLED to 20.2%; 8.6% of QA answers rewritten to "It is not
stated in the report" (abstention); 40 extraction tables contain abstain text.
**Mechanism (confirmed by annotated/unannotated split):** corruption 24.7%
unannotated vs 15.8% annotated; abstentions 88 vs 25 (3.5×). Run 1 shows no such
asymmetry (16.7% vs 17.1%). The blueprint's "visible labels are the only source /
never infer from gridlines / else abstain" clause contradicted the dataset's
core design (52% of figures are unannotated with gridline-exact values);
hallucination mitigation enforced the clause onto exactly those rows.
**Lessons:** (1) grounding + instruction must agree with the data's theory of
where truth lives — any future blueprint must explicitly permit gridline-derived
exact values and DROP the abstain rule (unanswerable rows already teach refusal);
(2) abstention-trained models are uniquely toxic in pairwise judging;
(3) keep the base model fixed across ablations.

**Three-run conclusion:** every Adaptive Data config rewrites 100% of
completions; each breaks something different (numbers / format+leakage /
abstention). Least intervention → best model (70%).

### Run 4 — NEXT, highest priority
- Train directly on the ORIGINAL dataset via AutoScientist's fine-tune path,
  bypassing Adaptive Data entirely (zero-corruption arm)
- Base: gemma_3_27b_it_vlm to match Run 1 for a clean original-vs-enhanced comparison
- If original ≥ 70: best model AND centerpiece finding in one run

### Deferred matrix runs
- Small/tiny base on same data (headroom experiment; Run 1 = large-base control)
- Full fine-tune vs LoRA (single-variable, after Run 3; prefer small base)
- Epochs 4 vs 1 (mirrors Sue's Mixtral v3 controlled finding)
- Mixed text+chart training (pending Invent working + empty-context probe)

## Invent-a-Dataset attempts (2026-07-17/18)
- Config: instruction / text / 3 domains (Data analysis & viz, Marketing, Market
  analysis), 14 metric-dense subdomains, 500 rows (~400 credits), custom details
  text steering toward numerically-consistent analytical Q&A
- **Failed to generate 3× — set aside; no credits were deducted; reportable
  to Adaption.** Retry variable if revisited: shorter/no details text.
- Purpose when it works: vocabulary mining for generator v3 pools (fix 52%
  duplicate prompts; break marketing-only lexicon), not training data.

## Challenge intel
- FAQ (2026-07-16): scoring = improvement vs the base you train on + dataset
  quality + hidden held-out eval ("optimize broadly"); multiple submissions per
  track evaluated independently; extra self-reported metrics viewed favorably;
  CC-BY-4.0 compliant.
- Implicit rubric (inferred from Part 1 winners): hidden eval + staff vote +
  write-ups on Kaggle & HF + working HF demo.
- Competitive reference: Sue Huynh's winning Part 1 marketing entry — iterative
  public dataset/model series, ablation narrative, full evidence package
  (results table, demo video, 2 HF Spaces), platform tools credited.

## v3 roadmap (score-relevant per FAQ "optimize broadly")
1. Matplotlib style/theme/aspect diversity (CharXiv fragility counter)
2. New families: pie/donut, horizontal bar, area, scatter
3. Domain vocabulary pools beyond marketing (Invent-mined or hand-written)
4. Local generalization probe: hold out unseen styles/families; report
   train-dialect vs held-out-dialect accuracy as an extra metric
