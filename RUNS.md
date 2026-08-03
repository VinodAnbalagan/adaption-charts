# Run tracker — Part 2

The Adaption API does not record `column_mapping` on a run object, so
column provenance must be logged manually at launch time. Fill a row in
before or immediately after starting each run.

Base score varies 38–47 across runs on the same model, so treat
differences under ~7 points as noise (~200 held-out rows, SE ≈ 3.5).

## Datasets

| id | rows | recipes | blueprint | notes |
|---|---:|---|---|---|
| `96042399-fbd0-4d54-a44c-eb8bf76ad75e` | 1091 | rephrase + metadata | yes | 31.6% completion drift |
| *(all-off, 1091)* | 1091 | none | no | 100% completions rewritten to essays |
| *(all-off, 1415)* | 1415 | none | no | first with 358 hard rows |
| *(all-on, 1415)* | 1415 | all incl. traces + halluc. mitigation | yes (`Answer:` line) | |

## Training runs

| # | dataset | model | prompt col | completion col | epochs | steps | base | adapted | Δ |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| 4 | 1091 rephrase+meta | 4B VLM | enhanced | enhanced | 1 | 23 | 47 | 53 | +6 |
| 5 | 1091 rephrase+meta | 27B VLM | original | original | 4 | 92 | 38 | **62** | **+24** |
| 6 | 1091 all-off | 27B VLM | original | enhanced | 4 | 88 | 43 | 58 | +15 |
| 7 | 1091 rephrase+meta | 27B VLM | original | enhanced | 8 | 176 | 46 | 54 | +8 |
| 8 | 1415 all-off | 27B VLM | ? | enhanced | ? | | | | |
| 9 | 1415 all-on | 27B VLM | ? | enhanced | ? | | | | |
| 10 | 1091 rephrase+meta | 27B VLM | original | original | 8 | | | | |

## Clean 2×2: completion column × epochs

Same dataset (1091, rephrase+meta), same model (27B), same original prompt
column. Only completion column and epochs vary.

| | 4 epochs | 8 epochs |
|---|---|---|
| **original completion** | run 5: **62** | run 10: *pending* |
| **enhanced completion** | run 6*: 58 | run 7: 54 |

\* run 6 used the all-off dataset, so it is not a perfect cell — its
enhanced completions were 100% rewritten rather than 31.6% drifted.

Run 10 completes the grid and isolates epochs cleanly at the original
completion column.

## Findings so far

**Epochs.** 1 epoch (23 steps) undertrains: +6. 4 epochs (92 steps): +24.
8 epochs (176 steps): +8. Four is the sweet spot; loss flattens near step
50 and later steps are noise.

**Completion column.** Short exact answers (run 5, +24) beat verbose
rewritten completions (run 6, +15). Direction matches expectation; gap is
near the noise floor so treat as suggestive.

**Adaptation always rewrites completions.** With rephrase + metadata +
blueprint: 31.6% of completions diverged from source answers, 41 of them
numerically wrong (incl. `No` → `Yes`). With all recipes off and no
blueprint: 100% rewritten into long markdown explanations. The blueprint
constrains style, not fidelity — but it does measurably reduce damage
(31.6% vs 100%).

**Base score variance.** 38 / 43 / 46 / 47 across runs on the same 27B
model. Reference completions shape what the pairwise judge calls "better":
verbose references flatter the base model's natural verbosity, short exact
references penalize it.
