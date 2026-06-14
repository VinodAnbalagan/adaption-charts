"""serialize.py — render a canonical figure's ground truth as TEXT, in form families.

Part 1 (marketing) pivot: AutoScientist can't train multimodal yet, so Part 1
is text. The canonical table is the invariant; these serializers are different
"renders" of it. Each form is a FAMILY with per-sample variation, so repeated
structure doesn't become a machine-generated tell.

Key correctness rules (learned from review):
  - currency/number formatting is chosen ONCE per sample and applied uniformly
    (mixed $7,043.87 / 9422.93 USD in one sample is a realism killer)
  - the pivot header is the real axis name (Quarter/Period), never "Metric"
  - no ===/--- section-marker artifacts in core forms (model would key on them)
  - some forms add light interpretation (rose/fell/led), not just restatement

Forms / tiers:
  Tier 1 (minimal)  : markdown_table, compact_block
  Tier 2 (core)     : pivoted, bullet_summary, analyst_prose
  Tier 3 (pepper)   : noisy
"""

from __future__ import annotations

import random
from typing import Dict, Any, List, Tuple

# Tier-2-centered. analyst_prose/bullet replace the old repetitive prose;
# multi_section markers removed from core (demoted out entirely per review).
FORM_WEIGHTS = {
    "analyst_prose": 0.22,
    "bullet_summary": 0.20,
    "pivoted": 0.20,
    "noisy": 0.16,
    "compact_block": 0.12,
    "markdown_table": 0.10,
}

EXTRACTION_FORMS = {"analyst_prose", "bullet_summary", "pivoted", "noisy"}

PROMPT_REWRITES = [
    ("shown in the channel chart", "shown in the channel breakdown"),
    ("the channel chart", "the channel breakdown"),
    ("KPI card total", "headline total"),
    ("the KPI card", "the headline figure"),
    ("this figure", "this report"),
    ("this chart", "this report"),
    ("this dashboard", "this report"),
]

DISTRACTOR_NOTES = [
    "Figures exclude internal test traffic.",
    "Attribution window: 7-day click, 1-day view.",
    "Data refreshed nightly; minor restatements possible.",
    "Excludes refunded transactions.",
]

# title phrasings -> variation so the same template doesn't lead every sample
_LEADS = [
    "{title}",
    "{title} — performance snapshot",
    "{title} ({period} summary)",
    "Campaign summary: {title}",
]
_PERIODS = ["weekly", "monthly", "quarterly", "this period"]


def pick_form(rng: random.Random) -> str:
    forms, weights = zip(*FORM_WEIGHTS.items())
    return rng.choices(forms, weights=weights, k=1)[0]


def rewrite_prompt(prompt: str) -> str:
    for a, b in PROMPT_REWRITES:
        prompt = prompt.replace(a, b)
    return prompt


# -------------------------
# per-sample formatting policy (chosen ONCE, applied uniformly)
# -------------------------

class FmtPolicy:
    def __init__(self, rng: random.Random):
        self.currency = rng.choice(["dollar_comma", "usd_suffix"])
        self.thousands = rng.random() < 0.7  # comma grouping for counts

    def num(self, v: Any, unit: str) -> str:
        if not isinstance(v, (int, float)):
            return str(v)
        if unit == "percent":
            return f"{v}%"
        if unit == "currency":
            body = f"{v:,.2f}" if (isinstance(v, float) and v != int(v)) else f"{int(v):,}"
            return f"${body}" if self.currency == "dollar_comma" else f"{body} USD"
        if unit == "count":
            return f"{int(v):,}" if self.thousands else str(int(v))
        return str(v)


def _table_parts(fig: Dict[str, Any]) -> Tuple[List[str], List[List[Any]], Dict[str, str], str]:
    t = fig["data"]["table"]
    return t["columns"], t["rows"], t.get("units", {}), fig["render"]["title"]


def _lead(rng: random.Random, title: str) -> str:
    return rng.choice(_LEADS).format(title=title, period=rng.choice(_PERIODS))


def _row_label(cols: List[str]) -> str:
    """The real name of the first column / pivot rows — never 'Metric'."""
    c0 = cols[0]
    return c0 if c0 not in ("Category",) else "Channel"


# -------------------------
# Tier 1
# -------------------------

def to_markdown_table(fig, rng):
    cols, rows, units, title = _table_parts(fig)
    cols = [_row_label(cols)] + cols[1:]
    lines = [f"## {title}", "", "| " + " | ".join(cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def to_compact_block(fig, rng):
    """Export-style: label then comma-separated values (header implied by order)."""
    cols, rows, units, title = _table_parts(fig)
    lines = [title]
    if len(cols) > 2:
        lines.append("(" + ", ".join(cols[1:]) + ")")
    for r in rows:
        vals = ", ".join(str(r[i]) for i in range(1, len(cols)))
        lines.append(f"{r[0]}: {vals}")
    return "\n".join(lines)


# -------------------------
# Tier 2
# -------------------------

def to_pivoted(fig, rng):
    cols, rows, units, title = _table_parts(fig)
    keys = [str(r[0]) for r in rows]
    # the pivot rows are the metric columns; header is the real axis name
    axis = cols[1] if len(cols) > 2 else "Value"
    header = "Period" if any(q in str(cols[1:]) for q in ("Q1", "Q2", "Jan", "Feb")) else axis
    lines = [f"## {title}", "",
             f"| {header} | " + " | ".join(keys) + " |",
             "|" + "|".join(["---"] * (len(keys) + 1)) + "|"]
    for ci in range(1, len(cols)):
        vals = [str(rows[ri][ci]) for ri in range(len(rows))]
        lines.append(f"| {cols[ci]} | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def to_bullet_summary(fig, rng):
    cols, rows, units, title = _table_parts(fig)
    fmt = FmtPolicy(rng)
    head = rng.choice([
        f"{title}:",
        f"{_lead(rng, title)}:",
        f"{title} — key figures:",
    ])
    lines = [head]
    for r in rows:
        if len(cols) == 2:
            lines.append(f"- {r[0]}: {fmt.num(r[1], units.get(cols[1], ''))}")
        else:
            parts = [f"{cols[i]} {fmt.num(r[i], units.get(cols[i], ''))}" for i in range(1, len(cols))]
            lines.append(f"- {r[0]}: " + "; ".join(parts))
    return "\n".join(lines)


def to_analyst_prose(fig, rng):
    """Interpretive summary: trend verbs for time-series, ranking for single-metric.
    Varied sentence structure; one formatting policy throughout."""
    cols, rows, units, title = _table_parts(fig)
    fmt = FmtPolicy(rng)
    unit1 = units.get(cols[1], "")
    out = [_lead(rng, title) + "."]

    if len(cols) == 2:
        # single metric: lead with ranking, then state EVERY remaining figure.
        # (Must render all rows: percentage-of-total QA is computed over the
        # full table, so dropping any row would make the answer unverifiable.)
        order = sorted(range(len(rows)), key=lambda i: rows[i][1], reverse=True)
        top, bot = rows[order[0]], rows[order[-1]]
        out.append(
            f"{top[0]} led with {fmt.num(top[1], unit1)}, while {bot[0]} was lowest at {fmt.num(bot[1], unit1)}."
        )
        # every middle row, in rank order, with light sentence variation
        for mi in order[1:-1]:
            r = rows[mi]
            out.append(rng.choice([
                f"{r[0]} recorded {fmt.num(r[1], unit1)}.",
                f"{r[0]} came in at {fmt.num(r[1], unit1)}.",
                f"{r[0]} posted {fmt.num(r[1], unit1)}.",
            ]))
    else:
        # multi-period: describe first->last movement per row (trend verbs)
        first_c, last_c = cols[1], cols[-1]
        for r in rows:
            a, b = r[1], r[-1]
            va, vb = fmt.num(a, unit1), fmt.num(b, unit1)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                verb = "rose" if b > a else "fell" if b < a else "held flat"
                out.append(rng.choice([
                    f"{r[0]} {verb} from {va} in {first_c} to {vb} in {last_c}.",
                    f"{r[0]} moved from {va} ({first_c}) to {vb} ({last_c}).",
                ]))
            else:
                out.append(f"{r[0]}: {first_c} {va}, {last_c} {vb}.")
    return "\n".join(out)


# -------------------------
# Tier 3
# -------------------------

def to_noisy(fig, rng):
    """Realistic noise: prior-period distractors (labeled), footnotes, one policy.
    Answer-preserving — distractors are clearly marked prior-period or notes."""
    cols, rows, units, title = _table_parts(fig)
    fmt = FmtPolicy(rng)
    lines = [f"{title} — Performance Update", ""]
    n_prose = max(1, len(rows) // 2)
    unit1 = units.get(cols[1], "")
    for r in rows[:n_prose]:
        v = fmt.num(r[1], unit1) if len(cols) >= 2 else ""
        s = f"{r[0]} reached {v}"
        if isinstance(r[1], (int, float)) and rng.random() < 0.6:
            prior = fmt.num(round(r[1] * rng.uniform(0.7, 1.3), 1), unit1)
            s += f" (prior period: {prior})"
        lines.append(s + ".")
    lines.append("")
    lines.append("Remaining figures:")
    for r in rows[n_prose:]:
        parts = [f"{cols[i]} {fmt.num(r[i], units.get(cols[i], ''))}" for i in range(1, len(cols))]
        lines.append(f"- {r[0]}: " + "; ".join(parts))
    lines.append("")
    for note in rng.sample(DISTRACTOR_NOTES, k=min(2, len(DISTRACTOR_NOTES))):
        lines.append(f"Note: {note}")
    return "\n".join(lines)


SERIALIZERS = {
    "markdown_table": to_markdown_table,
    "compact_block": to_compact_block,
    "pivoted": to_pivoted,
    "bullet_summary": to_bullet_summary,
    "analyst_prose": to_analyst_prose,
    "noisy": to_noisy,
}


def serialize_figure(fig: Dict[str, Any], form: str, rng: random.Random) -> str:
    return SERIALIZERS[form](fig, rng)
