---
license: cc-by-4.0
task_categories:
- visual-question-answering
- image-to-text
language:
- en
tags:
- charts
- data-visualization
- chart-question-answering
- chart-to-table
- synthetic
- marketing-analytics
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: train
    path: train.jsonl
---

# Adaption Charts — Part 2 (Data Visualization)

A synthetic multimodal dataset of business/marketing charts paired with
question-answering and chart-to-table extraction tasks. Each row references a
rendered chart image and a text prompt/completion pair with exact,
programmatically-verified ground truth.

Built for the **Adaption AutoScientist Challenge (Part 2)**.

## What's in it

Each chart is a synthetically rendered figure (bar, grouped bar, stacked bar,
line, funnel, and multi-panel dashboards) drawn from a marketing-analytics
theme (spend, conversions, CTR, CPA, revenue by channel/campaign/period). Every
figure carries two kinds of task:

- **`table_extraction`** — convert the figure into a normalized table (exact
  JSON ground truth).
- **`qa`** — answer a question about the figure (value lookup, extremum,
  comparison, difference, multi-series lookup, cross-panel reasoning, and
  more). Completions include a short reasoning trace and a canonical answer.

Because the figures are generated from a known underlying table, every answer
is exact by construction rather than hand-labelled.

## Columns

| column | description |
|---|---|
| `id` | unique row id (`<figure>__table` or `<figure>__qa_NN`) |
| `prompt` | the question or instruction |
| `completion` | target text (reasoning + answer for QA; JSON table for extraction) |
| `image` | URL to the chart PNG (in this repo, under `images/`) |
| `task_type` | `qa` or `table_extraction` |
| `qa_type` | question category (empty for extraction rows) |
| `chart_type` | bar / grouped_bar / stacked_bar / line / funnel / multi_panel |
| `difficulty` | easy / medium / hard |
| `parent_id` | the figure this row belongs to |
| `part` | challenge part tag |

Images are referenced by URL and stored in the `images/` folder of this repo.

## Composition

- **Figures:** 73
- **Rows:** 378 (73 `table_extraction` + 305 `qa`)
- **Chart types:** bar (94), line (89), stacked_bar (63), grouped_bar (62),
  multi_panel (40), funnel (30)
- **Difficulty:** easy (183), medium (132), hard (63)

*(Row counts are task rows; one figure yields one extraction row plus several
QA rows. Chart-type and difficulty counts are per task row.)*

## Intended use

Training and evaluating vision-language models on chart understanding: reading
values off axes, comparing series, extracting structured tables from figures,
and reasoning across panels.

## Generation

Charts are rendered with matplotlib from synthetic marketing-analytics tables;
ground truth is derived directly from those tables, so QA answers and extracted
tables are exact. No real company data is used.

## License

Released under CC-BY-4.0. The charts and labels are synthetic and contain no
real or personally identifiable data.

## Citation

If you use this dataset, please credit *Adaption Charts* by
[@vinod-anbalagan](https://huggingface.co/vinod-anbalagan).
