"""schema.py — canonical figure object + task targets + JSONL writers.

This is the contract everything else is measured against. The table is canonical;
QA derives from it. Keep this stable; version bumps go in FigureData.schema_version.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Literal
import json
import uuid

# -------------------------
# Enums / aliases
# -------------------------

PartType = Literal["part1_marketing", "part2_chart"]
DomainType = Literal["marketing", "general"]
FigureKind = Literal["chart", "dashboard", "table_image"]
ChartType = Literal[
    "bar",
    "grouped_bar",
    "stacked_bar",
    "line",
    "multi_line",
    "area",
    "scatter",
    "combo",
    "funnel",
    "table_only",
    "multi_panel",
]
DifficultyType = Literal["easy", "medium", "hard"]
OriginType = Literal["synthetic", "public_seed", "mixed"]
LicenseTag = Literal["safe_synthetic", "verify_required"]

QAType = Literal[
    "retrieve_value",
    "find_extremum",
    "compare_values",
    "compute_difference",
    "compute_sum",
    "compute_ratio_percent",
    "identify_category_by_value",
    "trend_direction",
    "multi_series_lookup",
    "rank_order",
    "threshold_count",
    "multi_panel_linked_reasoning",
    "visual_reference",
    "funnel_conversion",
    "diagnostic",
    "unanswerable",
    "hypothetical",
]

PanelType = Literal[
    "kpi_card",
    "time_series_panel",
    "channel_comparison_bar",
    "campaign_table",
    "funnel_panel",
    "geo_panel",
    "budget_vs_return_combo",
    "small_multiples",
]

TaskType = Literal["table_extraction", "qa"]

SCHEMA_VERSION = "1.0"


def make_id(prefix: str = "fig") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# -------------------------
# Provenance
# -------------------------

@dataclass
class SourceInfo:
    origin: OriginType
    seed_name: str
    license_tag: LicenseTag


# -------------------------
# Tabular data
# -------------------------

@dataclass
class DataTable:
    columns: List[str]
    rows: List[List[Any]]
    units: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SeriesData:
    name: str
    x: List[Any]
    y: List[Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FigureData:
    schema_version: str
    table: DataTable
    series: List[SeriesData] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "table": self.table.to_dict(),
            "series": [s.to_dict() for s in self.series],
        }


# -------------------------
# Render metadata (includes nuisance/realism knobs)
# -------------------------

@dataclass
class StyleInfo:
    theme: str = "tableau_like"
    font_scale: str = "medium"          # small | medium | large
    rotation_x: int = 0
    show_grid: bool = True
    show_values: bool = False
    abbrev_numbers: bool = False         # 12,000 -> 12K
    currency_symbol: Optional[str] = None
    decimal_places: int = 1
    palette: str = "default"
    legend_loc: str = "best"


@dataclass
class NuisanceInfo:
    jpeg_artifact: bool = False
    low_res: bool = False
    partial_overlap: bool = False
    similar_colors: bool = False
    crowded_legend: bool = False


@dataclass
class RenderInfo:
    title: str
    subtitle: Optional[str]
    x_label: Optional[str]
    y_label: Optional[str]
    legend: List[str] = field(default_factory=list)
    style: StyleInfo = field(default_factory=StyleInfo)
    nuisance: NuisanceInfo = field(default_factory=NuisanceInfo)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "legend": self.legend,
            "style": asdict(self.style),
            "nuisance": asdict(self.nuisance),
        }


# -------------------------
# Artifacts
# -------------------------

@dataclass
class Artifacts:
    image_path: str
    thumb_path: Optional[str] = None
    table_csv_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -------------------------
# Dashboard panels
# -------------------------

@dataclass
class DashboardPanel:
    panel_id: str
    panel_type: PanelType
    title: str
    table: Optional[DataTable] = None
    value: Optional[Any] = None
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "panel_id": self.panel_id,
            "panel_type": self.panel_type,
            "title": self.title,
            "value": self.value,
            "unit": self.unit,
        }
        if self.table is not None:
            out["table"] = self.table.to_dict()
        return out


# -------------------------
# Task targets
# -------------------------

@dataclass
class KPIItem:
    name: str
    value: Any
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PanelTable:
    panel_id: str
    title: str
    table: DataTable

    def to_dict(self) -> Dict[str, Any]:
        return {"panel_id": self.panel_id, "title": self.title, "table": self.table.to_dict()}


@dataclass
class TableExtractionTarget:
    figure_kind: FigureKind
    chart_type: ChartType
    title: str
    table: DataTable
    # Dashboard-level extraction: KPI cards and additional panel tables.
    # Empty for single charts; populated for dashboards so the target matches
    # EVERYTHING visible in the image, not just one panel.
    kpis: List[KPIItem] = field(default_factory=list)
    extra_tables: List[PanelTable] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "figure_kind": self.figure_kind,
            "chart_type": self.chart_type,
            "title": self.title,
            "table": self.table.to_dict(),
        }
        if self.kpis:
            out["kpis"] = [k.to_dict() for k in self.kpis]
        if self.extra_tables:
            out["extra_tables"] = [t.to_dict() for t in self.extra_tables]
        return out


@dataclass
class Evidence:
    row_keys: List[str] = field(default_factory=list)
    column_keys: List[str] = field(default_factory=list)
    panel_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QATarget:
    answer: str
    answer_type: str
    evidence: Evidence = field(default_factory=Evidence)
    # reasoning: the DETERMINISTIC, CORRECT chain-of-thought we generate from the
    # source table. This is the moat — never produced by re-reading the image.
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "answer": self.answer,
            "answer_type": self.answer_type,
            "evidence": self.evidence.to_dict(),
        }
        if self.reasoning is not None:
            out["reasoning"] = self.reasoning
        return out


# -------------------------
# Tasks
# -------------------------

@dataclass
class TableExtractionTask:
    prompt: str
    target: TableExtractionTarget
    metric: str = "json_table_exact_or_cell_tolerant"
    numeric_tolerance: float = 0.01

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": "table_extraction",
            "prompt": self.prompt,
            "target": self.target.to_dict(),
            "grading": {
                "metric": self.metric,
                "numeric_tolerance": self.numeric_tolerance,
            },
        }


@dataclass
class QATask:
    qa_type: QAType
    prompt: str
    target: QATarget
    metric: str = "normalized_exact"
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": "qa",
            "qa_type": self.qa_type,
            "prompt": self.prompt,
            "target": self.target.to_dict(),
            "grading": {
                "metric": self.metric,
                "aliases": self.aliases,
            },
        }


# -------------------------
# Canonical figure object
# -------------------------

@dataclass
class FigureExample:
    id: str
    part: PartType
    domain: DomainType
    figure_kind: FigureKind
    chart_type: ChartType
    difficulty: DifficultyType
    source: SourceInfo
    data: FigureData
    render: RenderInfo
    artifacts: Artifacts
    tasks_table_extraction: Optional[TableExtractionTask] = None
    tasks_qa: List[QATask] = field(default_factory=list)
    panels: List[DashboardPanel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "id": self.id,
            "part": self.part,
            "domain": self.domain,
            "figure_kind": self.figure_kind,
            "chart_type": self.chart_type,
            "difficulty": self.difficulty,
            "source": asdict(self.source),
            "data": self.data.to_dict(),
            "render": self.render.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "tasks": {
                "table_extraction": (
                    self.tasks_table_extraction.to_dict()
                    if self.tasks_table_extraction else None
                ),
                "qa": [q.to_dict() for q in self.tasks_qa],
            },
            "metadata": self.metadata,
        }
        if self.panels:
            out["panels"] = [p.to_dict() for p in self.panels]
        return out

    def flatten_tasks(self) -> List[Dict[str, Any]]:
        """One row per task. Rows carry task_type so the two slices can be
        adapted with DIFFERENT Adaption configs (reasoning_traces ON for qa,
        OFF for table_extraction to protect exact numbers)."""
        rows: List[Dict[str, Any]] = []

        if self.tasks_table_extraction is not None:
            rows.append({
                "id": f"{self.id}__table",
                "parent_id": self.id,
                "task_type": "table_extraction",
                "part": self.part,
                "domain": self.domain,
                "image_path": self.artifacts.image_path,
                "prompt": self.tasks_table_extraction.prompt,
                "target_json": self.tasks_table_extraction.target.to_dict(),
                "metadata": {
                    "chart_type": self.chart_type,
                    "figure_kind": self.figure_kind,
                    "difficulty": self.difficulty,
                    **self.metadata,
                },
            })

        for i, qa in enumerate(self.tasks_qa):
            rows.append({
                "id": f"{self.id}__qa_{i:02d}",
                "parent_id": self.id,
                "task_type": "qa",
                "part": self.part,
                "domain": self.domain,
                "image_path": self.artifacts.image_path,
                "prompt": qa.prompt,
                "target_json": qa.target.to_dict(),
                "metadata": {
                    "chart_type": self.chart_type,
                    "figure_kind": self.figure_kind,
                    "difficulty": self.difficulty,
                    "qa_type": qa.qa_type,
                    **self.metadata,
                },
            })

        return rows


# -------------------------
# Helper constructors
# -------------------------

def make_table_extraction_task(
    figure_kind: FigureKind,
    chart_type: ChartType,
    title: str,
    table: DataTable,
    prompt: str = "Convert this figure into a normalized table.",
    kpis: Optional[List[KPIItem]] = None,
    extra_tables: Optional[List[PanelTable]] = None,
) -> TableExtractionTask:
    return TableExtractionTask(
        prompt=prompt,
        target=TableExtractionTarget(
            figure_kind=figure_kind,
            chart_type=chart_type,
            title=title,
            table=table,
            kpis=kpis or [],
            extra_tables=extra_tables or [],
        ),
    )


def make_qa_task(
    qa_type: QAType,
    prompt: str,
    answer: str,
    answer_type: str,
    row_keys: Optional[List[str]] = None,
    column_keys: Optional[List[str]] = None,
    panel_ids: Optional[List[str]] = None,
    aliases: Optional[List[str]] = None,
    reasoning: Optional[str] = None,
) -> QATask:
    return QATask(
        qa_type=qa_type,
        prompt=prompt,
        target=QATarget(
            answer=answer,
            answer_type=answer_type,
            evidence=Evidence(
                row_keys=row_keys or [],
                column_keys=column_keys or [],
                panel_ids=panel_ids or [],
            ),
            reasoning=reasoning,
        ),
        aliases=aliases or [],
    )


# -------------------------
# JSONL writers
# -------------------------

def write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_canonical_jsonl(path: str, examples: List["FigureExample"]) -> None:
    write_jsonl(path, [ex.to_dict() for ex in examples])


def export_flattened_jsonl(path: str, examples: List["FigureExample"]) -> None:
    rows: List[Dict[str, Any]] = []
    for ex in examples:
        rows.extend(ex.flatten_tasks())
    write_jsonl(path, rows)
