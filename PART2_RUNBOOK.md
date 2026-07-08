# Part 2 Runbook — Data Visualization Track

Self-contained next steps. Everything here was tested end-to-end on 2026-07-07:
generator v2 validates 100/100 clean, both export modes produce well-formed
files (bytes mode: valid PNG round-trip; urls mode: staged images + 0.3MB JSONL
per 100 figures).

## Pipeline (3 commands)

```bash
# 1. GENERATE — pilot scale first (~100 figures / ~500 task rows)
python scripts/build_pilot.py --bar 20 --line 20 --grouped 20 --stacked 20 \
    --dashboard 10 --funnel 5 --out data_p2_pilot --seed 7
open data_p2_pilot/inspect.html        # eyeball ~20 before anything else

# 2a. EXPORT — if the form takes IMAGE BYTES (pilot default)
python scripts/export_part2.py --canonical data_p2_pilot/canonical/train.jsonl \
    --out export_pilot --images bytes
# add --data-uri if the platform wants data:image/png;base64,... format

# 2b. EXPORT — if the form takes IMAGE URLS (use at scale)
python scripts/export_part2.py --canonical data_p2_pilot/canonical/train.jsonl \
    --out export_pilot --images urls \
    --base-url https://huggingface.co/datasets/VinodAnbalagan/adaption-charts-p2/resolve/main/images
# then: create the HF dataset repo, upload export_pilot/images/* into images/,
# verify ONE url opens in an incognito browser tab (repo must be PUBLIC),
# and only then upload train.jsonl to Adaption.

# 3. UPLOAD train.jsonl (or train.csv) to the Part 2 form.
```

If the form dictates different column names, don't edit code:
`--prompt-col X --completion-col Y --image-col Z`.

## Decision table when the form drops

| Form says              | Do                                                        |
|------------------------|-----------------------------------------------------------|
| accepts base64/bytes   | `--images bytes` (pilot), consider urls beyond ~2K figures |
| accepts URLs           | `--images urls` + HF public dataset repo                  |
| accepts both           | bytes for pilot run, urls for the scaled run              |
| CSV only               | upload train.csv (written automatically)                  |
| separate image upload  | zip export_*/images/, use urls-mode jsonl minus base-url as relative names |

## Adaption run config (proven Part 1 recipe, unchanged)

- Instruction dataset (not preference pairs) for run 1
- Augmentation OFF, Blueprint ON
- Split by task_type if the platform allows two configs:
  - qa rows: reasoning traces ON (completions already carry the trace + "Answer:")
  - table_extraction rows: reasoning OFF (exact JSON, protect numbers)
- Numeric-preservation gate before scaling (same check as Part 1)

## Base model choice

Same headroom logic as Part 1 (keep this out of public materials): pick the
SMALLEST VLM on the platform's catalog. Candidates in ascending capability:
Qwen2.5-VL-3B < Llama-3.2-11B-Vision < Qwen2.5-VL-7B. Verify what Together/
Adaption actually list on the day; take the smallest that supports images.

## After the pilot run: error bucketing

Bucket eval failures into: (1) visual read errors (wrong value off axis),
(2) wrong-series / color-legend confusion, (3) arithmetic slips, (4) format
mismatches, (5) refusal errors on unanswerable. Turn UP the generator knob
matching the biggest bucket (annotation rate down, similar_colors/crowded_legend
up, font small, truncated_axis up) and regenerate. That's the scaling loop.

## Scale run

5K–20K figures: raise counts in build_pilot.py args, new --out, --seed change.
Use --images urls. HF 2GB applies to a single file, not the repo; images live
as individual PNGs so only the JSONL size matters (it stays tiny in urls mode).

## Social (July 7+ window, Invent-a-Dataset is live)

- Invent is TEXT-ONLY for now → the chart generator covers the modality their
  pipeline doesn't have yet. Public framing: "complementary dataset", never
  method details, never the small-model insight, no repo link during the
  competition.
- Combined story if Invent images ship in time: their engine for text-side
  analytical reasoning (Data analysis & viz + Marketing domains), chartgen for
  image-side visual grounding — one model trained on both.
- Post checklist: branded graphic, screenshot + dashboard results, tag
  @adaption_ai (X) / @Adaption (LinkedIn), story-first caption.

## Known-good state (commit this)

- src/chartgen/generator.py — v2 builders (annotated/unannotated split,
  nice-grid values, truncated_axis, font_scale/jpeg_artifact wired, unique-max
  guards, walk-span line snapping)
- src/chartgen/schema.py — NuisanceInfo.truncated_axis
- scripts/export_part2.py — dual-mode exporter (this file's pipeline step 2)
