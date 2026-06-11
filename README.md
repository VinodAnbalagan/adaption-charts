# adaption-charts

Synthetic chart/dashboard → structured-data generator for the **Adaption AutoScientist Challenge**.

- **Part 2** = single charts (`bar`, `grouped_bar`, `stacked_bar`, `line`).
- **Part 1** = marketing dashboards (`multi_panel`: KPI card + channel comparison).

The table is generated **first**; QA is **derived** from it, so every answer is exact.
Each figure carries a **deterministic reasoning trace** (correct by construction — never
produced by re-reading the image). That's the moat: public chart datasets have answers,
not correct reasoning.

## Quickstart

```bash
cd adaption-charts
python -m venv .venv && source .venv/bin/activate
pip install -e .

# generate 50, validate, export JSONL, build inspection sheet
python scripts/build_pilot.py --bar 10 --line 10 --grouped 10 --stacked 10 --dashboard 10 --out data

open data/inspect.html   # eyeball ~20 before scaling
```

## Outputs

```
data/
  renders/        PNG charts + matching .csv ground-truth tables
  canonical/train.jsonl   one row per FIGURE (full nested object)
  flat/train.jsonl        one row per TASK (table_extraction | qa)
  inspect.html            image + ground-truth table + QA + reasoning, side by side
```

## Why two JSONL formats
- **canonical** = the full object; keep as source of truth + for regeneration.
- **flat** = one task per row, the shape Adaption ingests. Rows carry `task_type` so the
  two slices can be adapted with **different** configs:
  - `table_extraction` → `reasoning_traces` **OFF** (protect exact numbers; no re-write).
  - `qa` → `reasoning_traces` **ON** is acceptable (added reasoning helps).

## Budget reality (important)
Adaption account caps at **~20k adapted rows**. `flatten_tasks()` multiplies figures into
~4 rows each, so **20k rows ≈ ~5k figures**. Generate a large raw pool locally, then send
only the **highest-value, most-diverse** ~5k figures through Adaption. (Curation scorer = TODO.)

## Validator
`scripts/build_pilot.py` runs `validate_dataset` automatically. It catches: row/column length
mismatches, empty prompts/answers, evidence keys that don't exist in the table, non-parsing
numeric answers, and `unanswerable` rows that secretly assert a value. Fix DIRTY rows before scaling.

## Known TODOs (next builds)
1. **Curation scorer** — rank figures by difficulty/diversity to protect the 20k budget.
2. **HTML/CSS → screenshot** dashboard renderer for Part 1 (real Tableau/GA4 look, not matplotlib subplots).
3. More QA types: `compute_ratio_percent` on more chart types, `threshold_count`, `unanswerable`, `hypothetical`.
4. Area / combo / scatter chart types.
5. Adaption upload script (Parquet w/ image bytes for pilot; HF-URL images for scale).
6. Held-out eval harness + baseline scoring.

See the master plan in the Obsidian vault (`Adaption_AutoScientist_Challenge.md`).
