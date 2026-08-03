---
license: cc-by-4.0
task_categories:
  - visual-question-answering
  - question-answering
language:
  - en
size_categories:
  - 1K<n<10K
tags:
  - chart-qa
  - multimodal
  - visualization
  - reasoning
pretty_name: Adaption Charts P2 — Gold Chart-QA
---

# Adaption Charts P2 — Gold Chart-QA Dataset

A verified, quality-first chart question-answering dataset built for the
Adaption Labs AutoScientist Challenge (Part 2, Data Visualization track).
Two sources: a programmatically generated synthetic core
(correct-by-construction) and a hand-authored hardset built from real
public dashboards and reports.

## At a glance

<!-- AUTOGEN:counts -->
- **1415 rows total** — 1317 synthetic + 98 hardset
<!-- /AUTOGEN:counts -->
- **7 chart types** — bar, line, grouped_bar, stacked_bar, pie, donut, mixed
- **10 task types** — every allowed task_type populated at target
- **English only**, real-world business/finance/health/policy domains
- Every row `verified=true`

## Schema

Each row:

| column | type | description |
|---|---|---|
| `file_name` | string | HF imagefolder path to the chart PNG (`images/...`) |
| `id` | string | unique row id, e.g. `syn_bar_0001__q1` or `hs_0007__q3` |
| `source` | enum | `synthetic` \| `hardset` |
| `question` | string | short flat-register question |
| `answer` | string | short exact answer, e.g. `47`, `Enterprise`, `-$1440.81`, `11.3%`, `Yes` |
| `chart_type` | enum | `bar` \| `line` \| `grouped_bar` \| `stacked_bar` \| `pie` \| `donut` \| `mixed` |
| `task_type` | enum | 10 values: `lookup_value`, `delta_absolute`, `max_min`, `rank_order`, `compare_categories`, `aggregation_sum_avg`, `multi_series_compare`, `trend_direction`, `percent_change_ratio`, `hard_multi_step` |
| `difficulty` | enum | `easy` \| `medium` \| `hard` |
| `verified` | bool | `true` on all rows (see verification protocol below) |
| `split` | enum | `train` on all rows (no held-out val/test in this file) |
| `notes` | string | provenance / attribution / generator notes |

## Composition

<!-- AUTOGEN:composition -->
**By source**

| source | rows | share |
|---|---:|---:|
| synthetic | 1317 | 93.1% |
| hardset | 98 | 6.9% |

**By chart_type**

| chart_type | rows |
|---|---:|
| bar | 417 |
| line | 288 |
| grouped_bar | 201 |
| stacked_bar | 184 |
| pie | 155 |
| mixed | 104 |
| donut | 66 |

**By task_type**

| task_type | rows |
|---|---:|
| max_min | 301 |
| lookup_value | 273 |
| delta_absolute | 156 |
| rank_order | 141 |
| compare_categories | 131 |
| trend_direction | 124 |
| multi_series_compare | 111 |
| aggregation_sum_avg | 89 |
| percent_change_ratio | 56 |
| hard_multi_step | 33 |

**By difficulty**

| difficulty | rows |
|---|---:|
| medium | 726 |
| hard | 358 |
| easy | 331 |
<!-- /AUTOGEN:composition -->

## Perceptual difficulty

Most chart-QA datasets vary difficulty by *arithmetic* — more steps in the
calculation. That is not what challenges a vision-language model. A capable
VLM handles multi-step arithmetic easily once it has read the values; what
it struggles with is reading the values in the first place.

358 rows (25.3%) are hard by **perceptual** construction. Eight mechanics:

| mechanic | what it does | why it's hard |
|---|---|---|
| `truncated_axis` | y-axis starts well above zero | bar height ratios badly misrepresent value ratios; a model comparing pixels is wrong, a model reading labels is right |
| `unlabeled` | no value annotations at all | values are snapped exactly onto gridlines, so the answer stays unambiguous — but only if the axis is actually read |
| `near_tie` | top two values differ by ~1–2% | eyeballing the tallest bar fails |
| `similar_colors` | series palette uses near-identical hues | the legend must be resolved rather than pattern-matched |
| `many_categories` | 12–16 categories, rotated labels, small font | dense visual scanning |
| `crowded_legend` | legend placed over the plot area | partial occlusion of the data |
| `log_scale` | logarithmic y-axis | equal pixel distances are unequal value deltas |
| `dual_axis` | two y-axes at different scales | reading the wrong axis yields a plausible but wrong number |

Roughly 90 of these rows carry **no value labels whatsoever** — the answer
must be read off gridlines. Answers remain correct-by-construction because
values are generated as exact multiples of the tick step.

Every hard row's `notes` field names its mechanic, e.g.
`hard/truncated_axis; procedural gen (seed=777, idx=12)`.

## Verification protocol

Every row is `verified=true`, but the mechanism differs by source:

**Synthetic — correct-by-construction.**
Each chart is rendered from a seeded pseudorandom value distribution. The
answer to every question is computed from those underlying values
*before* the chart image is drawn. There is no visual estimation involved.
The full generation pipeline lives in the companion repo alongside this
dataset. Seeds are deterministic.

**Hardset — hand-authored, human-reviewed.**
Every hardset row was authored one at a time from a real chart screenshot.
Each row was reviewed row-by-row against the source image during
authoring, with the answer recorded only after cross-checking what the
chart actually shows. All questions were designed to be answerable from
the image alone without external context.

## Data sources (hardset only)

Hardset uses screenshots of publicly available charts from official
statistical / research bodies. Each row's `notes` column carries the
source institution and original screenshot filename.

| source | rows | note |
|---|---:|---|
| Statistics Canada (StatCan) | 24 | Open Licence Agreement |
| U.S. Bureau of Labor Statistics (BLS) | 29 | U.S. Government works, public domain |
| European Central Bank (ECB) | 18 | Reproduction permitted with attribution |
| World Health Organization (WHO) | 21 | See attribution notes below |
| Bank of Canada (BoC) | 2 | Open license |
| Climate Policy Database | 4 | CC-BY-4.0 |

**Attribution notes.** WHO source materials are typically licensed under
CC-BY-NC-SA-3.0 IGO. This dataset uses WHO chart screenshots for the
transformative purpose of vision-language model training, with full
attribution preserved in each row's `notes`. Downstream users concerned
about commercial use should filter rows where `notes` begin with
`hardset; WHO;` and treat them separately.

## Intended use

Fine-tuning multimodal chart-QA models. Short-answer chart understanding
benchmarks. Ablation studies on chart-type or task-type coverage.

Not intended for downstream tasks that require gold-standard OCR fidelity
or exact numerical extraction from dense financial tables — this dataset
targets *reasoning about charts*, not exact digit extraction.

## Known limitations

- **English only.**
- **Synthetic aesthetic is uniform.** All synthetic rows use the same
  matplotlib renderer with a consistent style. Real-world visual
  diversity comes entirely from the hardset rows.
- **Hardset skews toward `max_min` and `lookup_value`.** Real dashboards
  naturally support these tasks; the balance step trims synthetic
  `max_min` heavily to compensate, but hardset structural bias remains.
- **`chart_type=mixed`** is exclusively hardset — synthetic doesn't
  generate multi-panel dashboards. Mixed charts are visually harder for
  VLMs and represent a natural difficulty axis.
- **No held-out split in this file.** An external evaluation slice
  (ChartQAPro-derived) lives outside this dataset by design.

## Citation

If you use this dataset, please cite:

```
@misc{anbalagan2026adaptioncharts,
  title  = {Adaption Charts P2: A Small Gold Chart-QA Dataset},
  author = {Anbalagan, Vinod},
  year   = {2026},
  howpublished = {\url{https://huggingface.co/datasets/vinod-anbalagan/adaption-charts-p2-gold}}
}
```

Please also credit the upstream chart sources listed in the "Data sources"
section above when relevant.

## License

This dataset is released under **CC-BY-4.0**. See attribution notes above
for source-specific considerations.
