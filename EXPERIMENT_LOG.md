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

---

# Part 2 rebuild — gold dataset (2026-08)

Old v3 pipeline deleted. New dataset built from scratch on branch
`gold-rebuild`: 1100 rows (1002 synthetic correct-by-construction + 98
hand-authored hardset from public dashboards). Published to
`hf://datasets/vinod-anbalagan/adaption-charts-p2-gold`.

## Adaptation runs (Adaptive Data, ~50 credits each)

### Adapt A — 500-row dataset (2026-08-02)
- Recipes: Prompt Rephrase ON, Metadata Injection ON; Dedup / Reasoning
  traces / Hallucination mitigation / House Special all OFF
- Blueprint: short-answer preservation, explicit no-abstain clause
- Length: minimal
- **Result: quality 7.0 → 8.1 (+15.7%), grade B → B, percentile 9.3 → 16.7**

### Adapt B — 1100-row dataset (2026-08-02)
- Same recipe config as Adapt A
- 1100 uploaded → **1091 ingested** (9 dropped silently)
- **Result: quality 6.0 → 7.8 (+30.0%), grade C → B, percentile 7.9 → 16.7**
- Dataset ID `96042399-fbd0-4d54-a44c-eb8bf76ad75e`

## Training runs (AutoScientist — free, no credit cost)

### Run 4 — 4B VLM, enhanced columns, 1 epoch
- Base: `google/gemma-3-4b-it-VLM` (smallest VLM on platform; headroom bet)
- Columns: enhanced_prompt / enhanced_completion (column_mapping omitted,
  platform inferred)
- Recipe: platform default — 1 epoch, lora_r 16, alpha 32,
  q/k/v/o_proj, cosine, lr 5e-5
- **Result: base 47 → adapted 53 (win rate 0.5269)**
- Diagnosis: only ~23 optimizer steps (888 train rows, batch max, 1 epoch).
  Model barely moved; 47/53 is near coin-flip because base and adapted are
  nearly identical.

### Run 5 — 27B VLM, ORIGINAL columns, 4 epochs
- Base: `google/gemma-3-27b-it-VLM` (matches Part 1 Run 1 base)
- Columns: **original** prompt (`question`) / completion (`answer`)
- Recipe: platform-recommended, unedited — 4 epochs, lora_r 64,
  alpha 128, q/k/v/o_proj, cosine, lr 5e-5, warmup 0.05, grad clip 1,
  weight decay 0.02; 92 steps
- **Result: base 38 → adapted 62**
- Note: base score DROPPED 47 → 38 when switching from enhanced to original
  prompts. Enhanced prompts carry persona scaffolding and explicit
  instructions that help the base model; bare questions remove that crutch.
  Lower base → more headroom → larger win-rate gap (+6 → +24).

| run | model | columns | epochs | steps | base → adapted |
|---|---|---|---:|---:|---|
| 4 | 4B VLM | enhanced (31.6% corrupt) | 1 | 23 | 47 → 53 |
| 5 | 27B VLM | original | 4 | 92 | **38 → 62** |

Three variables moved between runs 4 and 5 (model, columns, epochs), so
individual contributions are unresolved. Isolation runs are free.

## Finding: adaptation corrupts 31.6% of answers despite explicit blueprint

Downloaded the adapted CSV for dataset `96042399-...` and diffed
`enhanced_completion` against the source `answer` column across all 1091
rows.

**345 / 1091 (31.6%) differ.** Breakdown:

| kind | count |
|---|---:|
| appended extra content | 134 |
| rewritten | 87 |
| rewritten long (reasoning traces leaked) | 41 |
| **number changed (factually wrong)** | **41** |
| truncated | 40 |
| same number, format changed | 2 |

Concentrated in computed-answer task types:

| task_type | drifted / total |
|---|---|
| percent_change_ratio | 47 / 56 (83.9%) |
| rank_order | 80 / 110 (72.7%) |
| hard_multi_step | 14 / 33 (42.4%) |
| aggregation_sum_avg | 34 / 88 (38.6%) |
| multi_series_compare | 40 / 110 (36.4%) |
| lookup_value | 14 / 196 (7.1%) |

Representative corruptions:

| original | enhanced | problem |
|---|---|---|
| `No` | `Yes` | answer inverted |
| `1.5B` | `1.38` | number replaced |
| `$6500` | `$5700` | number replaced |
| `Government, Education, Enterprise` | `Government, Education, SMB` | wrong category |
| `19.0%` | `September: $5800, November: $6900 \nPercentage Change = ((6900 - 5800)...` | reasoning trace leaked |
| `Tech` | `Tech, $5900` | value appended |

The blueprint explicitly stated: *"Preserve the short, exact answer
format... Do not change the numeric precision of an answer... Do NOT add
'Reasoning:', 'Step 1:', or any step-by-step prefix."* It was not honored.

This mirrors Part 1 Run 2's 12.7% semantic corruption, worse in magnitude.
Consistent with the three-run conclusion: **every Adaptive Data config
rewrites completions; blueprints constrain style, not fidelity.**

Likely mechanism: Prompt Rephrase rewrote prompts to request calculation
steps (*"Show your calculation steps and provide the final percentage
change value"*), and completions were regenerated to match the rewritten
prompt. Prompt and completion drift together — so mixing enhanced prompt
with original completion would be internally inconsistent.

## Platform issues worth reporting to Adaption

1. **Misleading column-validation errors.** Three failed runs reported
   `Selected column 'question' for prompt is not in this dataset` and
   `Selected column 'enhanced_prompt' for prompt is not in this dataset`
   when both columns demonstrably existed in the adapted CSV header. The
   actual problem was the image column. Errors name the prompt column
   regardless of which mapping key is wrong.

2. **Explicit `column_mapping` rejected; omitting it works.** All three
   explicit mappings failed. Omitting the key entirely (letting the
   platform infer) succeeded on the first try. Docs do say "Omit it and
   the platform infers" — but the failure mode gives no hint that's the
   fix.

3. **Private HF repo surfaces as a data error, not an auth error.** Four
   runs failed with `all 888 training rows were skipped — no image could
   be downloaded and validated (PNG/JPEG/WEBP, ≤ 10 MB)`. Root cause: the
   source HF repo had been switched to private. Adapted datasets store
   images as URLs (`image_column_formats: {'file_name': 'url'}`), so the
   repo must stay public for the entire training run, not just ingestion.
   The error suggests malformed images rather than a 401.

4. **Row count silently drops on ingest.** 1100 uploaded → 1091 ingested.
   No warning; the 9 lost rows are unaccounted for.

5. **Run provenance omits `column_mapping`.** Neither
   `autoscientist.get()` nor the AutoScientist Config JSON records which
   columns a run trained on, so runs can't be reproduced or audited from
   the API alone.

6. **`training_jobs` resource in the docs doesn't exist in SDK 0.7.0.**
   `recommend_hyperparams` lives on `client.autoscientist`, not
   `client.training_jobs`.

7. **"Tiny AutoScientist" (<10B) picks a text-only model for multimodal
   datasets.** Selecting it on an image dataset auto-selected
   `Qwen/Qwen3.5-9B`, which cannot process images. The only VLM under 10B
   is `google/gemma-3-4b-it-VLM`, and the model field is not editable
   under that option.

### Deferred matrix runs (all free)
- 4B + original columns + 4 epochs (isolates model size from data cleanliness)
- 27B + enhanced columns + 4 epochs (isolates column choice)
- Full fine-tune vs LoRA
- Mixed text+chart training

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
