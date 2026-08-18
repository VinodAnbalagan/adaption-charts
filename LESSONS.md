# Lessons — Adaption AutoScientist Challenge Part 2

Written after placing 2nd in Data Visualization, and after reading the
1st-place entrant's methods paper (Rodrigues, *Silent Failure in Automated
Model Adaptation*, 176 fine-tunes / 86 launches / 13 datasets).

Kept for the next one.

---

## 1. What the platform numbers actually mean

**The displayed win rate is measured on the training distribution, not
held-out.** The two can move in opposite directions. Rodrigues found a
matched pair where the augmented model was 6.2 points *worse* on the
displayed metric and 11.0 points *better* on the judged one, and across
his paired comparisons the two disagreed in sign 38% of the time — with
the displayed number overstating held-out every single time, by a mean
of 14.1 points.

> Consequence for my Part 2 result: the 62 → 55 → 42 → 24 decline I
> reported probably measures how hard each dataset was to *fit*, not how
> hard the exam was. A ten-style dataset is harder to memorise. Held-out
> performance may well have improved while the number fell.

**The quality grade converges to a fixed attractor near 8.4.** Gain is
almost entirely a function of the starting score:

| starting score | mean gain |
|---:|---|
| 6 | +23.3% |
| 7 | +21.1% |
| 8 | +1.2% (one seed *lost* 12.5%) |

Grade SD falls 0.71 → 0.53 after adaptation. The pipeline normalises
toward a target — it will make an already-good dataset worse and not say
so. My own runs (7.0 → 8.1, and 6.0 → 7.8) are exactly this pattern.
Neither number said anything about my data.

**The base model is auto-selected and dominates the outcome.** Five
near-identical datasets drew five different bases. Interface edits to the
base did not persist across the run. Held-out sits at 76–78 on a capable
base and collapses to 45–54 on sub-10B. Domain classification drives the
routing, so a dataset classified into an unlucky domain gets a worse
model for reasons unrelated to its content.

> Consequence: my "smaller bases compress the range" finding is probably
> confounded. I may have been watching the platform re-roll the base
> rather than comparing bases.

**Sub-10B bases overfit at the default schedule.** Eval-loss minima:
gemma-3-4b at epoch 2, llama-3.2-3b at 2, qwen-0.8b underfits,
llama-4-scout-109B at 6. My 8-epoch runs underperforming 4-epoch runs is
this effect.

**Augmentation helps only where the seed under-covers its category.**
11 of 11 paired seeds improved (mean +14.4, p=0.0010), with the largest
gain on the *weakest* seed and near-zero gain on already-well-covered
ones. My v2 was already broad, so more rows added nothing.

---

## 2. Method

**Script every run through the API.** Nearly every finding above requires
programmatic control the interface does not give: pinning the base,
recording the config, retrieving what actually executed. I lost per-run
column mapping to this and had to publish part of my results table as
"provenance uncertain".

**Pair within seed.** Same data, same base, same recipe, vary exactly one
thing, repeat across many seeds. That converts "62 vs 42" into a sign
test with a p-value. Unpaired single comparisons are how both of us
initially reached wrong conclusions.

**Run enough of them.** 176 runs versus my 15. The gap between second and
first was not rigour of thought — it was infrastructure to exercise that
rigour at scale.

**Build a verifier and run it every time.** Six cheap machine-checkable
audits, each of which would have caught something I hit:

| check | catches |
|---|---|
| adapter no-op — does it change base logits at all? | silently zeroed adapters |
| fact preservation — do seed facts survive adaptation? | my 41 numerically-wrong completions |
| language pinning — does output language match declared? | my `服务` vs English-chart mismatch |
| domain routing — which base did classification select? | silent base substitution |
| metric-task alignment — does the rubric match the task? | the short-answer rubric mismatch |
| expansion provenance — what fraction is generated vs seeded? | undisclosed synthesis |

**Never trust the displayed number alone.** Get held-out. If it isn't
exposed, build an independent eval set — the task I kept deferring and
never did.

---

## 3. Dataset design

**Pick a named concept people already care about.** The winner used
Tufte's Lie Factor — citable, formula-backed, recognised since 1983. A
dataset called `misleading_chart_qa` explains itself; "perceptual
difficulty taxonomy" needs a paragraph.

**Ask whether your mechanism is an obstacle or a subject.** We both
implemented truncated axes. I treated it as an obstacle for the model to
overcome; he treated it as the thing to detect and quantify. Same
mechanic, and the second framing is worth more.

**Narrow and deep beats broad.** His winning set: 1,879 rows, mostly line
charts, one distortion family. Mine: 3,803 rows, 7 chart families, 10
styles, 5 languages. Breadth is harder to build and easier to dismiss.

**Real sourced data does double duty.** Our World In Data gives citations,
verifiability, *and* scales like synthetic because every grapher has a CSV
endpoint. I had that property on 98 hand-authored rows out of 3,803.

**Include unanswerable questions.** He labelled `unanswerable` and
`absent_entity` and taught appropriate refusal. My blueprint forbade
abstentions — defensible given Part 1's abstain disaster, but the result
is a model that always answers.

**Explain the label.** His `mechanism` column says *why* a chart misleads.
That makes the dataset useful to humans, not just as training fodder.

---

## 4. Packaging

What he shipped: two Zenodo DOIs, a working demo on a custom subdomain, a
write-up on his own domain, an open-source API client, weights.

What I shipped: model, dataset, cards, repo.

The gap is presentation surface, not substance. All of it is cheap:

- **domain** ~£10/year (Cloudflare Registrar sells at cost)
- **site** free — GitHub Pages / Cloudflare Pages
- **demo** free — HuggingFace Space + CNAME
- **DOI** free — Zenodo

**Validate the platform's own claims.** He reproduced their advertised
"+16 past 20k datapoints" at +17.4. That hands the company independent
confirmation of their own marketing. Costs nothing, and it is the kind of
thing people remember.

**Retract in the artifact, not just in conversation.** He put the
retraction of his own scaling claim in the model card. I corrected the
Qwen modality claim publicly within a day. Same instinct — worth keeping.

---

## 5. The one-line version

Both of us had the right instincts. He built the infrastructure to
exercise them at 176 runs and framed the work around a concept people
already cared about. That is the whole difference, and both halves are
fixable before the next one.

---

# Plan for the next hackathon

Written so a fresh session can pick this up cold. Everything below assumes
no memory of the Part 2 work beyond this file.

## Context you need

- Repo: `github.com/VinodAnbalagan/adaption-charts`
- Part 2 result: 2nd place, Data Visualization. Models
  `vinod-anbalagan/gridline` (62% displayed) and
  `vinod-anbalagan/prism` (53% displayed, 10 visual styles, 5 languages).
- Existing assets worth reusing: `pipeline/lib/render.py` (6 chart
  renderers), `pipeline/lib/hard_render.py` (8 adversarial mechanics),
  `pipeline/lib/styles.py` (10 visual style dialects),
  `pipeline/06_train.py` (Adaption API client, partial).
- Adaption SDK quirks documented in `EXPERIMENT_LOG.md`. Read it before
  writing any API code.

## Phase 0 — build the harness BEFORE the dataset (day 1)

This is the single highest-leverage change. Last time the dataset was
finished before any experiment infrastructure existed, which capped the
run count at ~15 and lost per-run provenance.

**`runner.py`** — one function that takes a config dict and returns a
result row. It must:

- accept `dataset_id`, `base_model`, `seed`, `epochs`, `lora_r`,
  `lora_alpha`, `target_modules`, `lr`, `column_mapping`
- **pin the base model explicitly** — never let the platform auto-select
  (Part 2 finding: auto-selection dominates outcome and interface edits
  do not persist)
- write every field of the launched config to a local JSONL immediately,
  before the run starts — the API does not record `column_mapping`
- poll to completion, then append the result to the same JSONL
- be safely re-runnable with an incrementing attempt key

**`verify.py`** — the six audits from Section 2, run against every
produced artifact. Non-negotiable: adapter no-op, fact preservation,
language pinning, domain routing, metric-task alignment, expansion
provenance.

**`evalset.py`** — an independent held-out set, built and frozen before
any training. The displayed win rate is on the training distribution.
Without an external eval you cannot tell improvement from memorisation.
This was task 10 last time and never got done. Do it first.

## Phase 1 — pick the frame (day 1, before writing a generator)

Before building anything, answer in one sentence: **what named thing does
this dataset measure?**

Test the frame against these:

- Does an existing named concept apply (Tufte's Lie Factor, Simpson's
  paradox, base rate neglect, anchoring)? Prefer one that predates you.
- Is the mechanism the *subject* or just an obstacle? Prefer subject.
- Would a non-specialist understand the stakes from the title alone?
- Can it be sourced from real data with citations?

If the answer to any of these is no, keep looking. A week of generator
work on the wrong frame is worse than a day of thinking.

## Phase 2 — the experiment grid (this is the deliverable)

Design the grid before generating data, so the dataset serves the
experiment rather than the other way round.

**Core design: paired within seed.** For each seed, run matched pairs
where exactly one factor differs. Aim for n ≥ 11 pairs so a sign test has
power. That is what turns a table into a result.

Factors worth pairing on, given what Part 2 established:

| factor | levels | why it is worth testing |
|---|---|---|
| augmentation on/off | 2 | reproduce the +14.4 result; check whether it holds when the seed already covers its category |
| base model | pinned large vs pinned small | Part 2's base comparison was confounded by auto-selection; do it properly |
| epochs | 2 / 4 / 8 | sub-10B bases overfit at default; find the actual minimum per base |
| column mapping | original vs enhanced | never cleanly resolved in Part 2 |
| difficulty mix | easy-heavy vs hard-heavy | tests whether displayed win rate tracks fit difficulty rather than quality |

**Always record both numbers.** Displayed (on-dataset) and independent
held-out. The gap between them is itself a finding — Part 2's headline
result may have been measuring only the first.

**Budget:** adaptation costs roughly 0.05 credits/row. AutoScientist
training is free. So spend credits on a small number of well-chosen
adaptations and run many training variants against each.

## Phase 3 — dataset (days 2–3)

Only now build data, sized to serve the grid.

- ~1,500–2,500 rows is enough. Part 2's 3,803 did not beat the 1,091.
- Real sourced data where possible. Our World In Data has thousands of
  graphers with CSV endpoints — citations and scale in one.
- Include unanswerable rows and teach appropriate refusal. Part 2
  forbade abstentions entirely and produced a model that always answers.
- Add a `mechanism` column explaining *why* each row is what it is.
- Keep answers correct-by-construction, and keep the provenance JSONs.

## Phase 4 — outputs (final day, budget real time for this)

Ship all of it. Each item is cheap and the gap in Part 2 was presentation,
not substance.

- [ ] model + dataset on HuggingFace, cards written properly
- [ ] Kaggle mirrors
- [ ] **working demo** — HuggingFace Space, free
- [ ] **write-up on own domain** — ~£10/year, GitHub Pages free
- [ ] **Zenodo DOI** — free, makes it citable
- [ ] open-source the runner/client
- [ ] LinkedIn + Discord posts
- [ ] validate one of the platform's own advertised claims and report it

## Standing rules

1. Never click a run you could script.
2. Log the config before launching, not after.
3. Every comparison paired within seed, or it is an anecdote.
4. Get the held-out number. The displayed one is on your training data.
5. Pin the base model explicitly, every time.
6. Run the verifier on every artifact.
7. Report negative results and retract in the artifact, not just in chat.
8. Keep a `RUNS.md` updated as you go — reconstructing it afterwards
   does not work.
