---
language:
- en
license: cc-by-4.0
size_categories:
- 1K<n<10K
task_categories:
- question-answering
- table-question-answering
task_ids:
- extractive-qa
- closed-domain-qa
tags:
- adaption
- marketing
- marketing-analytics
- data-analysis-visualization
- corporate-business
- instruction-tuning
- synthetic
- reasoning-traces
- chain-of-thought
- evidence-grounded
- chart-understanding
- table-reasoning
- abstention
pretty_name: Marketing Spend & Revenue QA
---

# Marketing Spend & Revenue QA

A synthetic, **table-grounded** question-answering dataset for marketing analytics. Every
question is answered from an underlying marketing report (channel/segment spend, revenue,
conversions, and funnel metrics), and every answer is **exact and verified by construction**
— not produced by a model reading a chart, but derived directly from the data the report was
built from.

The dataset was generated with a custom pipeline (`adaption-charts`) and then enhanced on the
[Adaption](https://adaptionlabs.ai) Adaptive Data platform, which added explanatory reasoning
traces and deduplicated near-identical prompts while preserving the original verified answers.

- **Rows:** 8,600 (deduplicated from ~14,837 generated rows)
- **Language:** English
- **Domain:** Marketing performance analytics (spend, revenue, conversions, funnels)
- **Format:** Instruction tuning (prompt / completion), chat-ready
- **Answers:** Deterministic and verified — never estimated

---

## Why this dataset is different

Most public chart/table-QA datasets give you *answers*. The hard part — a **correct
reasoning trace** — is usually missing or model-generated (and therefore sometimes wrong).
This dataset inverts the usual pipeline:

1. **The data table is generated first.** A marketing report (e.g. *Spend by Channel per
   Quarter*) is created with known numbers.
2. **The question and answer are derived from that table**, so the answer is exact by
   construction — there is no perception step that could misread a value.
3. **A deterministic reasoning trace is attached** — computed from the numbers, correct by
   construction, never produced by re-reading an image.
4. **A validator gate** rejects any row whose answer, evidence keys, or table shape don't
   line up before the data is ever used.

The result: answers you can trust, and reasoning you can train on.

---

## Task taxonomy (13 reasoning types)

Each row carries a `meta_qa_type`. The mix spans simple lookups through multi-step and
adversarial reasoning:

| `meta_qa_type` | What it asks |
|---|---|
| `retrieve_value` | Look up a single value from the report |
| `find_extremum` | Identify the single highest/lowest cell (not a row total) |
| `compute_sum` | Total a metric across a series |
| `compute_difference` | Change between two values |
| `compute_ratio_percent` | Share-of-total as a percentage (additive metrics only) |
| `multi_series_lookup` | Value at a specific (category, series) cell in a grid |
| `compare_values` | Which of two values is higher (or equal) |
| `trend_direction` | Whether a metric rose, fell, or held over a period |
| `funnel_conversion` | Stage-to-stage conversion rate in a funnel |
| `diagnostic` | The funnel's bottleneck (lowest-conversion transition) |
| `multi_panel_linked_reasoning` | Cross-panel reasoning over a dashboard |
| `table_extraction` | Normalize the whole report into a structured JSON table |
| `unanswerable` | The asked figure is genuinely absent — the model must abstain ("Not stated in the report") rather than guess |

The `unanswerable` class is deliberate: it trains *abstention*, which is where capable models
most often fail (they hallucinate a plausible number instead of declining).

### Source report families
Questions are grounded in six figure families — single-series bar and line reports,
grouped-bar and stacked-bar grids, multi-panel marketing **dashboards** (KPI card + channel
comparison + spend breakdown), and conversion **funnels**. Tabular reports are serialized into
several text presentations (analyst prose, bullet summary, pivoted table, markdown table,
compact block, and intentionally "noisy" formats), so the same facts appear in multiple shapes
— teaching robustness to layout rather than to a single template.

---

## Columns

| Column | Description |
|---|---|
| `prompt` | The original question |
| `completion` | The original verified answer, as JSON: `{answer, answer_type, evidence}` |
| `enhanced_prompt` | Adaptive Data's rephrased/expanded prompt |
| `enhanced_completion` | The reasoning-trace explanation that concludes with the verified answer (the training target) |
| `reasoning_trace` | Adaptive Data's reasoning column |
| `reasoning` | The original deterministic reasoning trace (correct by construction) |
| `context` | The marketing report (text) the question is grounded in |
| `id` | Source figure identifier |
| `meta_qa_type` | Reasoning type (see taxonomy) |
| `meta_figure_kind` / `meta_chart_type` | Source report family |
| `meta_text_form` | Which text serialization the report uses |
| `meta_difficulty` | Difficulty tier |
| `meta_part` | Pipeline part (text track) |

For instruction tuning, the natural mapping is `prompt` → prompt, `enhanced_completion` →
completion, `reasoning_trace` → reasoning.

---

## Adaptive Data quality assessment

After enhancement on the Adaption platform, the dataset's quality (the platform's own grade of
the training text) improved:

| Metric | Before | After |
|---|---|---|
| Quality score | 6.0 | **8.2** (+36.7% relative) |
| Grade | C | **B** |
| Percentile | 8.2 | **31.5** |

Enhancement was run with a stripped configuration (rephrase off, hallucination off, concise) so
the platform **explained** each verified answer rather than re-deriving it — preserving exact
numbers while adding reasoning. Prompt deduplication reduced ~14.8K generated rows to 8.6K
unique ones.

---

## Downstream use — model result

This dataset was used to fine-tune **Llama-3.2-3B-Instruct** (LoRA, r=32, α=64, 3 epochs, SFT)
via Adaption's AutoScientist. The resulting adapter is published here:

👉 **[vinod-anbalagan/Llama-3.2-3B-marketing-spend-revenue-qa](https://huggingface.co/vinod-anbalagan/Llama-3.2-3B-marketing-spend-revenue-qa)**

In head-to-head evaluation against its base model, the adapted model won **88%** of comparisons
(vs **12%** for the base). As with any such comparison, win rate is measured relative to the
specific base model used.

---

## Intended uses

- Fine-tuning small/mid models for marketing-analytics QA, table reading, and evidence-grounded
  numeric reasoning.
- Training **abstention** (the `unanswerable` class) and resistance to distractors.
- A source of *verified reasoning traces* for table QA, where most datasets provide only answers.

## Limitations

- **Synthetic.** Reports are generated, not scraped from real dashboards; numbers and entities
  are fabricated. Layout realism is text-based, not pixel-perfect screenshots.
- **English, marketing-only.** Metrics, channels, and segments are drawn from a marketing
  vocabulary; it is not a general table-QA benchmark.
- The `enhanced_completion` text is model-written (then quality-checked); the **answers** are
  verified, but the surrounding prose may occasionally be more verbose than necessary.

## Generation method & reproducibility

The data table is generated first and QA is derived from it, with a deterministic reasoning
trace and a validator gate (row/column shape, evidence-key existence, parseable numeric
answers, and genuinely-empty `unanswerable` rows). Answer preservation through the enhancement
step was checked programmatically before release.

## Citation

```bibtex
@misc{anbalagan2026marketingqa,
  title  = {Marketing Spend & Revenue QA: a table-grounded, reasoning-traced QA dataset},
  author = {Anbalagan, Vinod},
  year   = {2026},
  howpublished = {\url{https://huggingface.co/datasets/vinod-anbalagan/adaption-marketing-spend-revenue-qa}},
  note   = {Generated with the adaption-charts pipeline; enhanced via Adaption Adaptive Data}
}
```

## Acknowledgements

Built for the **Adaption AutoScientist Challenge**. Dataset enhancement and model training via
the [Adaption](https://adaptionlabs.ai) platform (Adaptive Data + AutoScientist).
