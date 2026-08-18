---
license: apache-2.0
base_model: Qwen/Qwen3.5-9B
library_name: peft
pipeline_tag: image-text-to-text
tags:
  - chart-qa
  - visual-question-answering
  - multimodal
  - lora
  - qwen
  - data-visualization
  - robustness
datasets:
  - vinod-anbalagan/gridline-chartqa
language:
  - en
  - es
  - fr
  - ar
  - zh
---

# Prism — chart QA across ten visual styles

A LoRA adapter for `Qwen/Qwen3.5-9B`, trained on chart question answering
across **ten distinct visual styles** and four additional languages.

Companion to [Gridline](https://huggingface.co/vinod-anbalagan/gridline),
which scored higher on the platform's own metric while being trained on a
single visual style. This card explains why those two facts are not in
tension, and why the lower number here is the more interesting result.

## Result

| | win rate vs base |
|---|---:|
| Prism (Qwen3.5-9B, 10 styles) | **53% / 47%** |
| Gridline (Gemma-3-27B-VLM, 1 style) | 62% / 38% |

Win rate is a **pairwise preference rate**, not two independent scores.
For each held-out question a judge sees the base model's answer and the
adapted model's answer and picks one. The two figures always sum to 100.

Critically, **each dataset is evaluated on its own held-out slice.** A
model trained on a harder, more varied dataset is graded on a harder,
more varied exam. The numbers above are not directly comparable — they
measure different tests.

## The finding

Fifteen training runs across four datasets. Win rate falls as the
evaluation set gets harder:

| dataset | rows | hard rows | visual styles | Gemma-3-27B-VLM | smaller base |
|---|---:|---:|---:|---:|---:|
| v1 | 1,091 | 3.9% | 1 | **62%** | 51% ᵃ |
| v1 + hard rows | 1,415 | 25% | 1 | 55% | — |
| v2 | 3,803 | 21% | 10 | 42% | 49% ᵇ |
| v2 + all features | 5,951 | 21% | 10 | 24% | **53%** ᵃ |

ᵃ Qwen3.5-9B  ᵇ Gemma-3-4B-VLM

**Caveat on this table.** The 27B column holds the base model fixed and is
the cleaner comparison. The "smaller base" column mixes two different
models, and column mapping was not recorded per run (see Configuration),
so cross-column comparisons are suggestive rather than controlled. The
monotonic trend down the 27B column is the claim this card actually
makes.

Two effects are visible.

**1. Difficulty is penalised twice.** A fine-tune that teaches short exact
answers (`$8600`) beats a verbose base model on charts it can read. On
charts it cannot read reliably — unlabeled axes, dark backgrounds, 8pt
type — it produces short *wrong* answers, and a judge comparing a
confident wrong number against a hedged, reasoned wrong answer will often
prefer the hedge. So perceptual difficulty lowers accuracy and lowers the
judge's preference at the same time.

**2. Smaller bases compress the range.** Moving from a 27B to a 9B lifted
the hardest dataset from 24% to 53% and lowered the easiest from 62% to
51%. Both sides of a pairwise comparison degrade together, so the result
drifts toward coin-flip.

Taken together: **on this metric, an easier dataset scores better.** Win
rate partly measures how easy you made your own exam. That is worth
knowing before treating it as a dataset-quality signal.

## Why this model exists

Gridline (62%) was trained on 1,002 synthetic rows rendered in a single
matplotlib theme — same fonts, same palette, same proportions throughout.
A model trained that way can learn superficial cues rather than reading
charts, and has no reason to generalise to a chart that looks different.

Prism was built to remove that crutch:

- **10 visual styles** varying colour, typography, figure geometry,
  title placement and grid treatment — newspaper graphics, spreadsheet
  defaults, journal figures, dark dashboards, dense analyst charts
- **806 perceptually hard rows (21%)** across eight mechanics: truncated
  axes, unlabeled gridline-only values, near-ties within 1–2%,
  near-identical series colours, 12–16 rotated categories, occluded
  legends, log scales, dual axes
- **Four additional languages.** 39% of rows are non-English — Arabic
  10.0%, Chinese 10.0%, Spanish 9.6%, French 9.3%. The platform
  translated answers as well as questions, so a chart labelled
  "Services" in English may carry the answer `服务`. Correct as a
  translation, but no longer matching the text in the image.

None of that helps the in-distribution win rate. All of it should help on
charts the model has not seen before.

## Training data

Source dataset:
[vinod-anbalagan/gridline-chartqa](https://huggingface.co/datasets/vinod-anbalagan/gridline-chartqa)
— 3,803 rows, 3,705 synthetic (correct-by-construction) + 98
hand-authored from real public dashboards (StatCan, US BLS, WHO, ECB,
Bank of Canada).

Synthetic charts are rendered *from* seeded values, with answers computed
before the image is drawn, so labels never depend on reading the image.
Every row carries a provenance JSON with its seed and underlying values.

**Adapted training set.** The platform's Adaptive Data step expanded this
to 5,951 rows — adding Spanish, French, Arabic and Mandarin questions —
and wrote enhanced variants of every prompt and completion alongside the
originals. Training drew 2,601 rows from it, holding the rest out for
evaluation.

That adapted CSV carries both the original `question`/`answer` columns
and the platform's `enhanced_prompt`/`enhanced_completion` rewrites. The
rewrites should not be treated as ground truth: 93% diverge from the
source answers, and a small number contain the platform's own
preference-judging scaffolding leaked into the completion field. The
original columns remain correct-by-construction.

Which pair this particular run trained on is not recoverable — see the
note under Configuration.

## Configuration

```
base_model             Qwen/Qwen3.5-9B
training_type          lora
training_method        sft
n_epochs               1
learning_rate          1e-5
lora_r                 16
lora_alpha             32
lora_trainable_modules q_proj, k_proj, v_proj, o_proj
lr_scheduler_type      cosine
warmup_ratio           0.1
max_grad_norm          2
train_on_inputs        false

adaptive data          all recipes on (rephrase, metadata injection,
                       deduplication, reasoning traces, hallucination
                       mitigation, House Special) + translation
training columns       not recoverable — see note below
```

**Column provenance is uncertain for this run.** The Adaption API does not
record `column_mapping` on a run object, and the UI does not display it
after the fact, so which of `question`/`answer` or
`enhanced_prompt`/`enhanced_completion` this run trained on cannot be
reconstructed. Runs on the same dataset were launched with both settings.
Recorded here as unknown rather than guessed.

This is reported to Adaption as an API gap. It is also the single biggest
methodological weakness of this whole ablation: without per-run column
provenance, several comparisons below are suggestive rather than
controlled.

Worth noting how light this recipe is — one epoch at 1e-5 with rank 16.
The same dataset trained hard on a 27B (four epochs, rank 64, 5e-5)
scored 24%. A gentler touch on a smaller base scored 53%. On a pairwise
metric, moving the model less can help: it keeps the fine-tune's answer
format without degrading accuracy on charts the model finds difficult.

## Limitations

- **Lower in-distribution win rate than Gridline** (53% vs 62%), for the
  reasons above. If your selection criterion is that number, use
  Gridline. If it is behaviour on unfamiliar charts, use this.
- **No external benchmark was run.** The generalisation claim is
  motivated by construction — ten styles, adversarial mechanics — not
  demonstrated on ChartQA or ChartQAPro. Stated plainly because it is the
  main thing this card cannot prove.
- **Answer/image language mismatch on translated rows.** Chart images
  are rendered in English; 1,143 answers were translated. Exact matching
  against visible chart text fails on those rows.
- **Synthetic rows still come from one generator.** Ten rendering styles,
  but a bounded set of domains, value distributions and question
  templates.
- **Column provenance was lost across the sweep.** The platform records
  no per-run `column_mapping`, so it cannot be established after the fact
  whether a given run trained on original or platform-rewritten
  completions. The clean claim in this card is the 27B column of the
  table; the rest is weaker evidence and is labelled as such.

## Reproduction

[github.com/VinodAnbalagan/adaption-charts](https://github.com/VinodAnbalagan/adaption-charts)

```bash
python pipeline/01_synthesize.py      # 3,006 rows, styles round-robined
python pipeline/07_hardgen.py --n-charts 300   # 699 perceptually hard rows
python pipeline/03_hardset_append.py  # 98 real-world hand-authored rows
python pipeline/04_verify.py
```

Style definitions are in `pipeline/lib/styles.py`; adversarial renderers
in `pipeline/lib/hard_render.py`.

## Citation

```bibtex
@misc{anbalagan2026prism,
  title        = {Prism: Chart QA Across Ten Visual Styles},
  author       = {Anbalagan, Vinod},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/vinod-anbalagan/prism}},
  note         = {Adaption Labs AutoScientist Challenge, Part 2}
}
```

## Acknowledgements

Built with the Adaption Labs platform (Adaptive Data + AutoScientist).
Hardset charts are screenshots of publicly available figures from
Statistics Canada, the US Bureau of Labor Statistics, the World Health
Organization, the European Central Bank, the Bank of Canada and the
Climate Policy Database; each row carries its source in the dataset's
`notes` column.
