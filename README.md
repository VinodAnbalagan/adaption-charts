# adaption-charts

Synthetic, **verified** marketing-analytics QA generator — built for the
**[Adaption](https://adaptionlabs.ai) AutoScientist Challenge**.

It generates marketing reports (channel/segment spend, revenue, conversions, funnels), derives
question–answer pairs from them, and attaches a reasoning trace that is **correct by
construction**. The result is table-QA training data where the answers — and the reasoning —
can be trusted.

**Published artifacts:**
- 📊 Dataset: [vinod-anbalagan/adaption-marketing-spend-revenue-qa](https://huggingface.co/datasets/vinod-anbalagan/adaption-marketing-spend-revenue-qa)
- 🤖 Model (LoRA): [vinod-anbalagan/Llama-3.2-3B-marketing-spend-revenue-qa](https://huggingface.co/vinod-anbalagan/Llama-3.2-3B-marketing-spend-revenue-qa)

---

## The idea

Most public chart/table-QA datasets give you *answers*. The hard part — a **correct reasoning
trace** — is usually missing or model-generated (and therefore sometimes wrong). This pipeline
inverts the usual order:

1. **Generate the data table first** (a marketing report with known numbers).
2. **Derive the question and answer from that table** — so the answer is exact, with no
   perception step that could misread a value.
3. **Attach a deterministic reasoning trace** — computed from the numbers, not from re-reading
   a chart.
4. **Gate every row through a validator** before it's ever used.

That's the moat: public chart datasets have answers, not correct reasoning.

---

## Pipeline

```bash
# 1. generate figures (--no-render skips PNGs; text track needs no images and runs in seconds)
python scripts/build_pilot.py --no-render \
  --bar 280 --line 280 --grouped 480 --stacked 600 --dashboard 480 --funnel 360 \
  --out data_run

# 2. hold out whole figures (never adapted/trained on) before serializing to text
python scripts/split_holdout.py --pool data_run/canonical/train.jsonl \
  --holdout-frac 0.15 --out data_run/split

# 3. serialize each figure to text in multiple forms -> the Part 1 parquet
python scripts/build_part1_text.py --pool data_run/split/train_pool.jsonl --out data_run/part1
# -> data_run/part1/part1_text.parquet   (upload this to Adaptive Data)
```

After adapting on the Adaption platform, gate the downloaded file:

```bash
python scripts/verify_adapted.py  --adapted <downloaded.json>   # numeric-preservation gate
python scripts/diagnose_adapted.py --adapted <downloaded.json>  # artifact-vs-real failure triage
python scripts/dissect_adapted.py  --adapted <downloaded.json>  # composition / target-quality forensics
```

Drop `--no-render` to also produce PNG charts (for the image/Part 2 track) plus an
`inspect.html` sheet that shows image + ground-truth table + QA + reasoning side by side —
eyeball ~20 before scaling.

---

## QA taxonomy (13 reasoning types)

Each task carries a `qa_type`, spanning simple lookups through multi-step and adversarial
reasoning:

| Type | Asks |
|---|---|
| `retrieve_value` | A single value from the report |
| `find_extremum` | The single highest/lowest cell (not a row total) |
| `compute_sum` | A total across a series |
| `compute_difference` | The change between two values |
| `compute_ratio_percent` | Share-of-total as a percentage (additive metrics only) |
| `multi_series_lookup` | A value at a specific (category, series) grid cell |
| `compare_values` | Which of two values is higher (or equal) |
| `trend_direction` | Whether a metric rose, fell, or held |
| `funnel_conversion` | A stage-to-stage conversion rate |
| `diagnostic` | The funnel bottleneck (lowest-conversion transition) |
| `multi_panel_linked_reasoning` | Cross-panel reasoning over a dashboard |
| `table_extraction` | Normalize the whole report into structured JSON |
| `unanswerable` | The figure is genuinely absent — the model must **abstain**, not guess |

The `unanswerable` class is deliberate: it trains abstention, where capable models most often
fail (they hallucinate a plausible number instead of declining).

**Figure families:** single-series `bar` and `line`, `grouped_bar` and `stacked_bar` grids,
multi-panel `dashboard` (KPI card + channel comparison + spend breakdown), and `funnel`.
Tabular reports are serialized into several **text forms** (analyst prose, bullet summary,
pivoted table, markdown table, compact block, and intentionally "noisy" layouts) so the same
facts appear in multiple shapes — teaching robustness to layout, not to a single template.

---

## The quality gate

`build_pilot.py` runs `validate_dataset` automatically, catching row/column length mismatches,
empty prompts/answers, evidence keys that don't exist in the table, non-parsing numeric
answers, and `unanswerable` rows that secretly assert a value. **Fix DIRTY rows before
scaling.**

After adaptation, three tools read the result at increasing depth:
- **`verify_adapted.py`** — the numeric-preservation gate. Did the platform keep your exact
  answers? Refusal-aware, compound-label aware, with rounding tolerance for percentages.
- **`diagnose_adapted.py`** — buckets failures into *verifier artifact* vs *genuine miss*, so a
  low headline rate isn't mistaken for corruption.
- **`dissect_adapted.py`** — forensics on a full adapted file: on-topic vs off-topic
  composition, self-correcting/contradicting targets, bloat, and near-duplicates.

---

## Repo layout

```
src/chartgen/
  schema.py       data model + task construction (answers exact, evidence linked)
  generator.py    figure builders (bar/line/grouped/stacked/dashboard/funnel) + QA derivation
  serialize.py    figure -> text forms (Part 1 text track)
  validator.py    the DIRTY/clean gate
  curation.py     difficulty/diversity helpers
scripts/
  build_pilot.py        generate + validate + export (+ optional --no-render)
  split_holdout.py      hold out whole figures before text serialization
  build_part1_text.py   serialize figures -> part1_text.parquet
  verify_adapted.py / diagnose_adapted.py / dissect_adapted.py   post-adaptation gates
  push_to_hf.py / upload_to_adaption.py                          publishing helpers
BLUEPRINTS.md     the Adaptive Data steering text ("explain the verified answer; never re-derive")
```

### Two JSONL formats
- **canonical** (`canonical/train.jsonl`) — one row per *figure*, the full nested object; the
  source of truth for regeneration.
- **flat** (`flat/train.jsonl`) — one row per *task*, the shape Adaption ingests. Rows carry a
  type so slices can be adapted with different configs (e.g. `table_extraction` with reasoning
  off to protect exact numbers; QA with reasoning on).

---

## Adaptive Data blueprint

The platform, by default, re-derives numeric answers and can reject exact ground truth as a
"hallucination." [`BLUEPRINTS.md`](BLUEPRINTS.md) reverses that: **the completion is
authoritative — explain it, never re-derive it.** Paste the canonical blueprint into the
platform's Blueprint field and run with rephrase/hallucination off, concise on.

---

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Roadmap

- **Part 2 (data-visualization track):** image-based QA — feed the rendered PNG charts
  (already produced when `--no-render` is omitted) through the multimodal pipeline.
- HTML/CSS dashboard renderer for more realistic (Tableau/GA4-style) figures.
- Additional chart families (area, combo, scatter) and a held-out eval harness for
  independent scoring of exported weights against the holdout split.

## License

Code: MIT. Dataset: CC-BY-4.0. Model adapter: Llama 3.2 Community License (inherited from the
base model).
