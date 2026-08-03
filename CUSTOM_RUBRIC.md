# Custom Evaluation Rubric — Chart-QA

Paste the following into the "Custom evaluation rubric" section in Adaption's
Adaptive Data configuration. Two parts: (1) System prompt (leave as default
or paste the version below), (2) Scoring criteria (paste ours below).

---

## System prompt (default template — leave as-is or paste)

```
You are an expert evaluator for a chart question-answering (chart-QA)
dataset. Each row contains a chart image, a short question about the chart,
and a short exact answer. Score both the question (message) and the answer
(completion) on a 0-10 scale.

<message>
{message}
</message>

<completion>
{completion}
</completion>

**Output Format:**
Be exact in your score by referencing the schema below. Return your
selection of structured metadata in valid JSON with only the following
schema:

{{
    "message_quality_score": integer,
    "completion_quality_score": integer
}}
```

---

## Scoring criteria (paste this into "Your scoring criteria")

```
### message_quality_score Scale (the QUESTION about the chart)

**0 (Empty message)** — There is no question or null entry.

**1-2 (Broken / Unanswerable)** — Gibberish, missing entities, references
a chart element that doesn't exist, or requires information not visible
in the chart. Examples: "asdf", "Tell me about the chart", "What color
is the background?"

**3-4 (Ambiguous)** — Readable but references multiple possible chart
elements without disambiguation, or requires external domain knowledge
the chart alone doesn't provide. Examples: "What does the chart say?",
"Which one is best?", "Explain the trend."

**5-6 (Basic Clarity)** — Clear question about a specific chart element
but may be verbose, chatty, or require complex parsing. May include
unnecessary framing. Example: "Looking at the chart carefully, could
you tell me which segment had the highest revenue this quarter?"

**7-8 (Well-Formed Chart-QA)** — Flat register, direct, one-clause,
unambiguously answerable from the chart alone. Follows the ChartQA-human
question style. Tests a well-defined chart reasoning task (lookup,
extremes, comparison, difference, trend, aggregation, ranking, percent
change). Examples:
  - "Which segment had the highest revenue?"
  - "What was the value in Q3?"
  - "How much more revenue did Enterprise generate than SMB?"
  - "Did revenue increase or decrease from Feb to Mar?"

**9-10 (Gold-Standard Chart-QA)** — All of 7-8, plus: the correct answer
is deterministic and single-valued from the chart alone. No ambiguity in
which element or metric is being asked about. Multi-step questions are
scored 9-10 if each step is unambiguous.

### completion_quality_score Scale (the ANSWER)

**0 (Empty completion)** — No answer or null entry.

**1-2 (Wrong / Broken)** — Incorrect answer, gibberish, or completely
wrong type (e.g., a category name when a number is expected).

**3-4 (Wrapped or Verbose)** — Answer contains the correct information
but is buried in extra text, reasoning wrappers, or explanations.
Examples: "The answer is Enterprise because...", "Reasoning: Step 1..."

**5-6 (Correct but Suboptimal Format)** — Correct answer with minor
format issues (missing units, extra whitespace, inconsistent
capitalization, wrong decimal precision).

**7-8 (Correct Short Exact-Match)** — Correct answer in expected
short-form format. Valid formats include:
  - Bare number: 47, 8600, 2100
  - Currency: $8600, -$1440.81
  - Percentage: 11.3%, -2.6%, 24.6%
  - Category label: Enterprise, United Kingdom, Widget C, SKU-102
  - Yes / No
  - Direction word: Increased, Decreased, Upward, Downward
  - Comma-separated rank list: Enterprise, Consumer, SMB
  - Number with unit suffix: 272K, 1.5B, 6.7B

**9-10 (Gold-Standard Chart-QA Answer)** — All of 7-8, plus: format is
optimal for the specific task type (exact match to what the chart shows,
correct decimal precision, appropriate sign for signed values), uses the
minimal representation necessary, and matches conventional chart-QA
benchmark answer conventions.

### Special Cases

- **Chart-QA answers are expected to be SHORT.** Typical: 1-3 tokens
  for lookup/max_min, 4-5 for rank_order. Long reasoning responses are
  LOW quality (2-4 range), even when factually correct. Verbose is a
  quality FAILURE for this task.

- **Both annotated labels and gridline-derived values are valid.** Do
  NOT penalize an answer for being read from a gridline instead of an
  explicit label — chart reading includes visual estimation.

- **Yes/No answers are the correct format for compare_categories
  questions.** Score 7-10 based on factual correctness, not length.

- **Domain vocabulary (business, finance, health, policy) is expected.**
  Do NOT penalize for niche terminology when the domain is clear from
  context.

- **Multi-word category labels are single answers.** "United Kingdom",
  "Region of the Americas", "Ages 60 to 79", "Personal care, including
  sleep" are all valid single-answer completions, not lists.

- **Refusals or abstentions are quality failures.** Every question in
  this dataset is answerable from the chart. An "It is not stated"
  answer scores 1-2, even if the model was being cautious.
```

---

## Why this rubric

Adaption's default rubric was written for text-only chat/summarization
datasets. It rewards verbose scaffolded prompts and long analytical
answers. Chart-QA is different by design: short-answer exact-match on
chart reading. Our rubric flips the polarity to match:

- Short answers score HIGH (7-10 for correct short-form)
- Long "reasoning" answers score LOW (1-4)
- Flat one-clause questions score HIGH (7-10)
- Chatty "please tell me" questions score LOWER (5-6)

Expected effect: pushes our dataset from B (7/10) toward A (9+/10) on
the Adaptive Data grade.
