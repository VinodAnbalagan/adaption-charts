"""validator.py — cheap structural checks that catch mislabeled / malformed rows
BEFORE they reach Adaption and cost credits. Run on every batch; fail loud.

Checks:
  - every row has len == len(columns)
  - no empty prompt / no empty answer
  - at least one task exists
  - image_path non-empty
  - evidence row_keys/column_keys actually exist in the table
  - numeric answers parse (when answer_type says numeric)
  - unanswerable tasks have an answer that signals it (not a hallucinated value)
"""

from __future__ import annotations

from typing import List, Tuple, Optional
import re

from .schema import FigureExample, DataTable


class ValidationError(Exception):
    pass


_NUMERIC_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _table_row_keys(table: DataTable) -> List[str]:
    # first column is treated as the row-key column
    return [str(r[0]) for r in table.rows]


def _parse_numeric(s: str) -> Optional[float]:
    m = _NUMERIC_RE.search(s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def validate_example(ex: FigureExample) -> List[str]:
    """Return a list of problem strings. Empty list == clean."""
    problems: List[str] = []

    # --- artifacts ---
    if not ex.artifacts.image_path:
        problems.append("empty image_path")

    # --- at least one task ---
    if ex.tasks_table_extraction is None and not ex.tasks_qa:
        problems.append("no tasks at all")

    # --- table shape ---
    table = ex.data.table
    ncol = len(table.columns)
    if ncol == 0:
        problems.append("table has no columns")
    for ri, row in enumerate(table.rows):
        if len(row) != ncol:
            problems.append(f"row {ri} len {len(row)} != ncol {ncol}")

    row_keys = set(_table_row_keys(table))
    col_keys = set(table.columns)

    # --- table extraction target matches data ---
    if ex.tasks_table_extraction is not None:
        if not ex.tasks_table_extraction.prompt.strip():
            problems.append("table_extraction has empty prompt")
        tgt_rows = ex.tasks_table_extraction.target.table.rows
        if len(tgt_rows) != len(table.rows):
            problems.append(
                f"table_extraction target rows {len(tgt_rows)} != data rows {len(table.rows)}"
            )

    # --- QA checks ---
    for qi, qa in enumerate(ex.tasks_qa):
        tag = f"qa[{qi}]({qa.qa_type})"
        if not qa.prompt.strip():
            problems.append(f"{tag} empty prompt")
        ans = qa.target.answer
        if ans is None or str(ans).strip() == "":
            problems.append(f"{tag} empty answer")

        # evidence keys must exist (panels excepted — they live outside the table)
        for rk in qa.target.evidence.row_keys:
            if str(rk) not in row_keys:
                problems.append(f"{tag} evidence row_key '{rk}' not in table rows")
        for ck in qa.target.evidence.column_keys:
            if str(ck) not in col_keys:
                problems.append(f"{tag} evidence column_key '{ck}' not in table columns")

        # numeric answers must parse
        if qa.target.answer_type in ("numeric", "numeric_with_unit"):
            if qa.qa_type != "unanswerable" and _parse_numeric(str(ans)) is None:
                problems.append(f"{tag} numeric answer '{ans}' does not parse")

        # unanswerable must not assert a concrete numeric value
        if qa.qa_type == "unanswerable":
            low = str(ans).strip().lower()
            ok = any(k in low for k in (
                "not", "cannot", "can't", "insufficient",
                "n/a", "unknown", "unanswerable", "no ",
            ))
            if not ok:
                problems.append(
                    f"{tag} unanswerable answer '{ans}' looks like a concrete value"
                )

    return problems


def validate_dataset(
    examples: List[FigureExample],
    raise_on_error: bool = False,
) -> Tuple[int, List[Tuple[str, List[str]]]]:
    """Validate all examples. Returns (n_clean, [(id, problems), ...] for dirty ones)."""
    dirty: List[Tuple[str, List[str]]] = []
    for ex in examples:
        probs = validate_example(ex)
        if probs:
            dirty.append((ex.id, probs))
    n_clean = len(examples) - len(dirty)
    if dirty and raise_on_error:
        first = dirty[0]
        raise ValidationError(f"{len(dirty)} dirty examples. First: {first[0]} -> {first[1]}")
    return n_clean, dirty
