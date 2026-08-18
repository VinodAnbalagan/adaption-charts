---
license: cc-by-4.0
task_categories:
  - visual-question-answering
  - question-answering
language:
  - en
  - ar
  - zh
  - es
  - fr
size_categories:
  - 1K<n<10K
tags:
  - chart-qa
  - multimodal
  - visualization
  - multilingual
  - adapted
pretty_name: Adaption Prism — adapted multilingual chart QA
---

# Adaption Prism — adapted multilingual chart QA

The training set behind
[Prism](https://huggingface.co/vinod-anbalagan/prism), a LoRA for
chart question answering across ten visual styles.

5,951 rows. Produced by running
[gridline-chartqa](https://huggingface.co/datasets/vinod-anbalagan/gridline-chartqa)
(3,803 hand-verified rows) through Adaption's Adaptive Data step with
every recipe enabled — prompt rephrasing, metadata injection,
deduplication, reasoning traces, hallucination mitigation, House Special
— plus translation into four additional languages.

**This is platform output, not hand-built gold data.** Read the column
notes below before using it. The clean source dataset is
[gridline-chartqa](https://huggingface.co/datasets/vinod-anbalagan/gridline-chartqa).

## Languages

| language | rows | share |
|---|---:|---:|
| English | 3,639 | 61.1% |
| Arabic | 595 | 10.0% |
| Chinese (Simplified) | 593 | 10.0% |
| Spanish | 571 | 9.6% |
| French | 553 | 9.3% |

**Answers were translated as well as questions.** 1,143 rows have
non-ASCII answers — `服务`, `Éducation`, `Augmenté`, `2700 دولار`.

This matters: **the chart images are rendered in English.** A chart whose
bar is labelled "Services" may carry the answer `服务`. The answer is a
correct translation of the correct category, but it no longer matches the
text visible in the image, so exact string matching against chart content
will fail on those rows. Anyone scoring against chart text should either
filter to English or normalise category names back to the image's
language.

## Columns

| column | source | trustworthy as a label? |
|---|---|---|
| `question` | original, or platform translation | yes |
| `answer` | original, or platform translation | yes, with the caveat above |
| `enhanced_prompt` | platform rewrite | rewritten, not ground truth |
| `enhanced_completion` | platform rewrite | **no** — see below |
| `reasoning_trace` | platform-generated | explanatory only |
| `chart_type` | source | yes |
| `task_type` | source | yes |
| `difficulty` | source | yes |
| `notes` | source | yes — includes visual style and mechanic |
| `original_image` | source | URL, see below |
| `source`, `split`, `verified`, `response_constraints` | mixed | metadata |

**On `enhanced_completion`.** 93% of these diverge from the corresponding
`answer`. Mean length goes from 1.4 words to 31.8 — short exact answers
become paragraphs. A small number contain the platform's own
preference-judging scaffolding leaked into the field, e.g. text beginning
`**Step 1 — Compare** | Dimension | Response 0 | Response 1`. Treat this
column as a record of what the platform produced, not as labels.

**On `original_image`.** These are URLs pointing into
[gridline-chartqa](https://huggingface.co/datasets/vinod-anbalagan/gridline-chartqa).
This dataset ships no images of its own and depends on that repo staying
public.

## Underlying data

The source rows are 3,705 synthetic + 98 hand-authored.

Synthetic charts are rendered *from* seeded values, with answers computed
before the image is drawn — labels never depend on reading the image.
They span **ten visual styles** (newspaper graphics, spreadsheet
defaults, journal figures, dark dashboards, dense analyst charts and
others) varying colour, typography, figure geometry, title placement and
grid treatment.

**806 rows (21%) are perceptually hard** by construction, across eight
mechanics: truncated axes where bar heights misrepresent ratios,
unlabeled charts with values snapped exactly onto gridlines, near-ties
within 1–2%, near-identical series colours, 12–16 rotated categories,
legends occluding the plot, log scales, and dual axes.

The 98 hand-authored rows come from real public dashboards — Statistics
Canada, US Bureau of Labor Statistics, WHO, ECB, Bank of Canada, Climate
Policy Database — each reviewed against its source figure.

## Intended use

Training and evaluating short-answer chart QA, including cross-lingual
settings where the question language differs from the chart language.

For clean labels, prefer
[gridline-chartqa](https://huggingface.co/datasets/vinod-anbalagan/gridline-chartqa).
Use this one when you specifically want the multilingual rows or want to
study what Adaptive Data does to a dataset.

## Known limitations

- **Answer/image language mismatch** on translated rows, as above.
- **`enhanced_completion` is not ground truth** — 93% divergence.
- **No images of its own** — depends on the source repo.
- **Synthetic rows come from one generator.** Ten rendering styles, but a
  bounded set of domains, value distributions and question templates.

## Provenance

Generation pipeline, style definitions and adversarial renderers:
[github.com/VinodAnbalagan/adaption-charts](https://github.com/VinodAnbalagan/adaption-charts)

Every synthetic row has a provenance JSON recording its seed and
underlying values, so any answer can be recomputed from source.

## Citation

```bibtex
@misc{anbalagan2026adaptionprism,
  title        = {Adaption Prism: Adapted Multilingual Chart QA},
  author       = {Anbalagan, Vinod},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/datasets/vinod-anbalagan/adaption-prism}}
}
```

Please also credit the upstream chart sources listed above.
