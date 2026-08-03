# adaption-charts

Chart question-answering dataset and LoRA adapter, built for the
[Adaption Labs AutoScientist Challenge](https://adaptionlabs.ai/blog/autoscientist-challenge)
(Part 2, Data Visualization track).

| artifact | link |
|---|---|
| model | [vinod-anbalagan/gridline](https://huggingface.co/vinod-anbalagan/gridline) |
| dataset | [vinod-anbalagan/adaption-charts-p2-gold](https://huggingface.co/datasets/vinod-anbalagan/adaption-charts-p2-gold) |
| model card | [`MODEL_CARD.md`](MODEL_CARD.md) |
| dataset card | [`gold/README.md`](gold/README.md) |
| experiment log | [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) |
| run tracker | [`RUNS.md`](RUNS.md) |

**Result:** 62/38 pairwise win rate against base `gemma-3-27b-it-VLM`.

## What's here

A 1,415-row chart-QA dataset where every answer is either
correct-by-construction or hand-verified, plus the generators that produce
it and the findings from eleven training runs.

Two things distinguish it from other chart-QA sets:

**Correct-by-construction labels.** Synthetic charts are rendered *from*
seeded values, and answers are computed from those values before the image
is drawn. The label never depends on reading the image, so there is no
annotation error to propagate.

**Perceptual difficulty, not arithmetic difficulty.** 25% of rows are hard
because they are hard to *see* — truncated axes where bar heights
misrepresent ratios, unlabeled charts where values sit exactly on
gridlines, near-ties within 1–2%, near-identical series colours, occluded
legends, log scales, dual axes. Most chart-QA datasets scale difficulty by
adding calculation steps, which a capable VLM handles once it has read the
values. Reading them is the hard part.

## Pipeline

```bash
python pipeline/01_synthesize.py       # synthetic core (seeded, reproducible)
python pipeline/07_hardgen.py          # perceptually-hard rows
python pipeline/03_hardset_append.py   # hand-authored real-world rows
python pipeline/04_verify.py           # schema + provenance checks
python pipeline/05_publish.py --public # push dataset to HuggingFace
python pipeline/08_push_cards.py --model-repo <id>   # push cards
```

`pipeline/06_train.py` drives the Adaption API — dataset upload, adaptation,
hyperparameter recommendation, AutoScientist training, checkpoint download.

Every synthetic row has a provenance JSON in `gold/raw/` recording the seed
and underlying values, so any answer can be recomputed from source.

### Layout

```
gold/
  manifest.csv        the dataset (schema in gold/README.md)
  images/             chart PNGs
  raw/                per-chart provenance (seed + underlying values)
  hardset_raw/        original screenshots for hand-authored rows
pipeline/
  lib/render.py       standard chart renderers
  lib/hard_render.py  adversarial renderers (8 perceptual mechanics)
  lib/pools.py        vocabulary and value pools
  lib/phrasings.py    question templates, flat register
adapted_data/         platform-adapted CSVs (evidence for the drift analysis)
```

## Findings

Documented in full in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) and
[`MODEL_CARD.md`](MODEL_CARD.md).

**Adaptation rewrites completions, always.** With a blueprint explicitly
forbidding it, 31.6% of completions diverged from source answers — 41 of
them numerically wrong, including a `No` flipped to `Yes`. With all recipes
off and no blueprint, 100% were rewritten into long explanations. The
blueprint reduced damage substantially but did not prevent it. Verifiable
against the CSVs in `adapted_data/`.

**Maximal enhancement inverts the model, reproducibly.** Turning every
Adaptive Data recipe on produced 69/31 in Part 1 of the challenge, and
69/31 and 66/35 in Part 2 — different data, different domain, with a
countermeasure blueprint in place, on both column choices. The adapted
model loses to its own base in roughly two of three comparisons.

**Train on your original columns.** The best run is the only confirmed
configuration training on both original prompt and original completion.
Adaptation is useful for ingestion and quality scoring; its rewritten
completions are not a safe training target for exact-answer tasks.

**Negative result, reported.** Raising perceptual difficulty from 3.9% to
25.3% of rows produced 55% against the earlier dataset's 62%. Either the
harder rows made training harder without making the judged comparison
easier, or the held-out slice does not over-sample them.

## Provenance and tooling

Built with the Adaption Labs platform (Adaptive Data + AutoScientist).
Hardset charts are screenshots of publicly available figures from
Statistics Canada, the US Bureau of Labor Statistics, the World Health
Organization, the European Central Bank, the Bank of Canada, and the
Climate Policy Database; each row carries its source in the dataset's
`notes` column.

The generators, verification scripts, and API tooling in `pipeline/` were
written with LLM assistance (Claude). Dataset design, source selection,
the hand-authored hardset, experimental design, and all findings are the
author's. Ablation configurations were run and interpreted manually.

## License

Code: MIT. Dataset: CC-BY-4.0 (see `gold/README.md` for source-specific
attribution notes). Model: inherits the Gemma license.
