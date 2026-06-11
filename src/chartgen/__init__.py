"""chartgen — synthetic chart/dashboard -> structured-data generator for the
Adaption AutoScientist Challenge (Part 1 marketing dashboards, Part 2 charts).

Design: one canonical FigureExample object holds the ground-truth table; QA tasks
are DERIVED from that table so they are always consistent and correct. Every row
can be flattened into one-task-per-row form for training/export.
"""

from .schema import (
    FigureExample,
    DataTable,
    SeriesData,
    FigureData,
    SourceInfo,
    StyleInfo,
    NuisanceInfo,
    RenderInfo,
    Artifacts,
    DashboardPanel,
    TableExtractionTask,
    QATask,
    QATarget,
    Evidence,
    make_id,
    make_table_extraction_task,
    make_qa_task,
    export_canonical_jsonl,
    export_flattened_jsonl,
    write_jsonl,
)
from .validator import validate_example, validate_dataset, ValidationError

__all__ = [
    "FigureExample",
    "DataTable",
    "SeriesData",
    "FigureData",
    "SourceInfo",
    "StyleInfo",
    "NuisanceInfo",
    "RenderInfo",
    "Artifacts",
    "DashboardPanel",
    "TableExtractionTask",
    "QATask",
    "QATarget",
    "Evidence",
    "make_id",
    "make_table_extraction_task",
    "make_qa_task",
    "export_canonical_jsonl",
    "export_flattened_jsonl",
    "write_jsonl",
    "validate_example",
    "validate_dataset",
    "ValidationError",
]
