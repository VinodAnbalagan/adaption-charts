---
license: gemma
base_model: google/gemma-3-27b-it-VLM
library_name: peft
pipeline_tag: image-text-to-text
tags:
  - chart-qa
  - visual-question-answering
  - multimodal
  - lora
  - gemma
  - data-visualization
datasets:
  - vinod-anbalagan/adaption-charts-p2-gold
language:
  - en
---

# Gridline — a LoRA for short-answer chart question answering

**Gridline** is a LoRA adapter for `google/gemma-3-27b-it-VLM`, trained to
answer questions about charts with short, exact answers — `$8600`,
`Enterprise`, `11.3%`, `Yes` — rather than paragraphs of explanation.

Built for the [Adaption Labs AutoScientist Challenge](https://adaptionlabs.ai/blog/autoscientist-challenge)
(Part 2, Data Visualization track). Trained on
[adaption-charts-p2-gold](https://huggingface.co/datasets/vinod-anbalagan/adaption-charts-p2-gold),
a 1,415-row chart-QA dataset where every answer is either
correct-by-construction or hand-verified.

## Result

| Evaluation | Setting | Result |
|---|---|---|
| AutoScientist held-out pairwise judge | Gridline vs. base Gemma-3-27B-VLM, ~200 held-out rows | **62% / 38%** |

The platform's metric is a **pairwise win rate**, not two independent
scores. For each held-out question the judge sees the base model's answer
and the adapted model's answer and picks the better one. The two figures
always sum to 100. So 62/38 means Gridline was preferred in roughly five
of every eight comparisons; 50/50 would mean indistinguishable from base.

This distinction matters for reading the ablation table below — several
configurations scored *below* 50, meaning they made the model measurably
worse than the base it started from.

## Ablation

Eleven training runs across four adapted datasets. Adapted win rate is the
number that matters; base is always its complement.

The Adaption API does not record `column_mapping` on a run object, and
several runs shared a dataset name, so column provenance for part of the
sweep could not be recovered after the fact. Runs are reported below only
at the confidence level they can actually be asserted — configurations
that could not be reconstructed are marked rather than guessed.

### Confirmed configurations

| dataset | recipes | prompt | completion | model | epochs | steps | adapted |
|---|---|---|---|---|---:|---:|---:|
| 1,091 | rephrase + metadata | enhanced | enhanced | 4B VLM | 1 | 23 | 53% |
| 1,091 | rephrase + metadata | **original** | **original** | 27B VLM | 4 | 92 | **62%** |
| 1,415 | **all on** | enhanced | enhanced | 27B VLM | 4 | 84 | 31% |
| 1,415 | **all on** | original | original | 27B VLM | 4 | 84 | 35% |

### Partially reconstructed

Four runs on the 1,091-row dataset at 4 and 8 epochs, mixing original and
enhanced completion columns, produced **58%, 54%, 54%, and 39%**. The
mapping from each score to its exact column configuration was lost. They
are reported as a range rather than assigned to cells.

### What the sweep shows

**Short exact completions beat rewritten ones.** The best run (62%) is
the only confirmed configuration training on both original prompt and
original completion. Every run known to involve rewritten completions
landed at 58% or below.

**Undertraining is real but bounded.** The 4B run completed only 23
optimizer steps and landed at 53% — barely distinguishable from base.
Four epochs (~92 steps) is where signal appears. Eight epochs did not
improve on four in any run.

**Maximal enhancement inverts the model, regardless of column choice.**
The all-on configuration was run twice, once training on enhanced
columns and once on original columns. Both inverted: 31% and 35%. Column
selection does not rescue it — the recipes themselves are the cause.

**The 1,415-row dataset did not beat the 1,091-row dataset.** Raising
perceptual difficulty from 3.9% to 25.3% of rows produced 55% against
62%. See limitations.

## The inversion replicates

This is the finding worth carrying forward.

In Part 1 of the same challenge, on an entirely different dataset in a
different domain, a maximal-recipe configuration produced **69/31**.

In Part 2, on this dataset, with a blueprint written specifically to
prevent the failure mode, the same configuration produced **69/31** and
**66/35** — once training on the platform's rewritten columns, once
training on the original columns.

Same platform, different data, different domain, explicit
countermeasures, both column choices — same magnitude of inversion. This
is reproducible behaviour, not variance, and it is not an artifact of
which columns the run trains on.

The mechanism is measurable. Diffing the platform's `enhanced_completion`
column against the source `answer` column:

| adaptation config | completions diverging from source |
|---|---:|
| rephrase + metadata + blueprint | **31.6%** (345 / 1,091) |
| all recipes off, no blueprint | **100%** (1,091 / 1,091) |

With recipes on and a blueprint, 345 completions diverged. Breakdown:

| kind | count |
|---|---:|
| extra content appended | 134 |
| rewritten | 87 |
| reasoning trace leaked into the answer | 41 |
| **number changed (factually wrong)** | **41** |
| truncated | 40 |

Representative corruptions:

| source answer | platform rewrite |
|---|---|
| `No` | `Yes` |
| `1.5B` | `1.38` |
| `$6500` | `$5700` |
| `Government, Education, Enterprise` | `Government, Education, SMB` |
| `Tech` | `Tech, $5900` |
| `19.0%` | `September: $5800, November: $6900 \nPercentage Change = ((6900 - 5800)...` |

Divergence concentrates in task types whose answers must be *computed*
rather than read off a label:

| task type | diverged |
|---|---|
| percent_change_ratio | 83.9% |
| rank_order | 72.7% |
| hard_multi_step | 42.4% |
| aggregation_sum_avg | 38.6% |
| lookup_value | 7.1% |

The blueprint explicitly forbade all of this — *"Do not change the numeric
precision of an answer"*, *"Never append values the question did not ask
for"*, *"Do NOT add 'Reasoning:' prefixes"*. It reduced damage from 100%
to 31.6% but did not prevent it.

**Practical conclusion: train on your original columns.** Adaptation is
useful as an ingestion and quality-scoring step. Its rewritten completions
are not a safe training target for exact-answer tasks.

## Training data

[adaption-charts-p2-gold](https://huggingface.co/datasets/vinod-anbalagan/adaption-charts-p2-gold)
— 1,415 rows, 1,317 synthetic + 98 hand-authored.

- **Synthetic rows** are correct-by-construction: each chart is rendered
  from seeded values, and the answer is computed from those values
  *before* the image is drawn. No visual estimation in the label.
- **Hardset rows** are hand-authored from real public dashboards
  (Statistics Canada, US BLS, WHO, ECB, Bank of Canada), each reviewed
  against its source image.
- **358 rows (25.3%) are perceptually hard** by construction — see the
  dataset card for the eight-mechanic taxonomy.

Coverage: 7 chart types (bar, line, grouped_bar, stacked_bar, pie, donut,
mixed) × 10 task types (lookup, max/min, delta, trend, percent change,
rank order, category compare, aggregation, multi-series compare,
multi-step).

## Training configuration

```
base_model             google/gemma-3-27b-it-VLM
training_type          lora
training_method        sft
lora_r                 64
lora_alpha             128
lora_dropout           0
lora_trainable_modules q_proj, k_proj, v_proj, o_proj
n_epochs               4
steps                  92
learning_rate          5e-5
lr_scheduler_type      cosine
warmup_ratio           0.05
weight_decay           0.02
max_grad_norm          1
train_on_inputs        false
```

Prompt column: `question` (original). Completion column: `answer`
(original). Image column: chart PNG as multimodal context.

## Usage

```python
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel
from PIL import Image

base_id = "google/gemma-3-27b-it-VLM"
adapter_id = "vinod-anbalagan/gridline"

processor = AutoProcessor.from_pretrained(base_id)
base = AutoModelForImageTextToText.from_pretrained(base_id, device_map="auto")
model = PeftModel.from_pretrained(base, adapter_id)

image = Image.open("chart.png")
messages = [{
    "role": "user",
    "content": [
        {"type": "image"},
        {"type": "text", "text": "Which segment had the highest revenue?"},
    ],
}]
prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
inputs = processor(images=image, text=prompt, return_tensors="pt").to(model.device)
out = model.generate(**inputs, max_new_tokens=32)
print(processor.decode(out[0], skip_special_tokens=True))
```

Expect short answers. Gridline is trained to reply `Enterprise`, not
"Based on the chart, the Enterprise segment appears to have the highest
revenue at approximately $8,600."

## Intended use and limitations

**Intended for** short-answer chart question answering: value lookup,
extremes, differences, trends, percent change, ranking, category
comparison, aggregation over stacked series.

**Not intended for** chart summarization or analytical narrative — it is
trained specifically against verbose output. Also not intended for
gold-standard OCR of dense financial tables; the target is reasoning about
charts, not exact digit extraction from text-heavy images.

**Known limitations:**

- **English only.**
- **Synthetic rows share one rendering style.** 1,317 of 1,415 rows come
  from a single matplotlib theme. Visual robustness comes from the 98
  real-world hardset rows and is correspondingly thin.
- **`mixed` (multi-panel dashboard) charts are underrepresented** — 104
  rows, mostly hardset.
- **Evaluated only on the platform's own held-out slice** (~200 rows from
  the same distribution). No independent external benchmark was run; the
  62% figure is in-distribution.
- **Column provenance was lost for part of the ablation sweep.** The
  platform API does not record `column_mapping` per run, and several runs
  reused a dataset name. Four of eleven runs are reported as an
  unattributed range rather than assigned configurations. Future sweeps
  should log the mapping at launch time; a run tracker is included in the
  companion repo for this purpose.
- **The 1,415-row dataset did not beat the 1,091-row dataset.** Raising
  perceptual difficulty from 3.9% to 25.3% of rows produced 55% vs. 62%.
  Either the harder rows made training harder without making the judged
  comparison easier, or the held-out slice does not over-sample them.
  Reported here rather than omitted.

## Reproduction

Full pipeline, generators, verification scripts and run log:
[github.com/VinodAnbalagan/adaption-charts](https://github.com/VinodAnbalagan/adaption-charts)

```bash
python pipeline/01_synthesize.py       # synthetic core, seeded
python pipeline/07_hardgen.py          # perceptually-hard rows
python pipeline/03_hardset_append.py   # hand-authored real-world rows
python pipeline/04_verify.py           # schema + provenance checks
python pipeline/05_publish.py --public # push to HF
```

Every synthetic row carries a provenance JSON in `gold/raw/` with the
seed and underlying values, so any answer can be recomputed from source.

## Citation

```bibtex
@misc{anbalagan2026gridline,
  title        = {Gridline: A LoRA for Short-Answer Chart Question Answering},
  author       = {Anbalagan, Vinod},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/vinod-anbalagan/gridline}},
  note         = {Adaption Labs AutoScientist Challenge, Part 2}
}
```

## Acknowledgements

Built with the Adaption Labs platform (Adaptive Data + AutoScientist).
Hardset charts are screenshots of publicly available figures from
Statistics Canada, the US Bureau of Labor Statistics, the World Health
Organization, the European Central Bank, and the Bank of Canada; each row
carries its source in the dataset's `notes` column.
