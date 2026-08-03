"""Append hand-authored hardset rows to gold/manifest.csv.

Copies raw chart images from gold/hardset_raw/ to gold/images/hs_NNNN.png
and appends corresponding QA rows to the manifest. Each row was reviewed
and approved row-by-row in chat.

'hardset' is added as a new allowed source value alongside {synthetic,
chartqa, chartx}. Existing source=hardset rows are removed before
appending, so the script is idempotent — re-runs produce the same output.

verified=false on every hardset row; task 8 (verification pass) will flip
to true after external second-eye check.

Attribution: every row's `notes` field carries `hardset; <src>; <original>`
where <src> is the source institution (StatCan, ECB, WHO, BoC, BLS, ...)
and <original> is the raw filename in gold/hardset_raw/.

Usage:
    python pipeline/03_hardset_append.py
"""

from __future__ import annotations
import csv
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GOLD = REPO / "gold"
IMAGES = GOLD / "images"
RAW = GOLD / "hardset_raw"
MANIFEST = GOLD / "manifest.csv"

MANIFEST_COLS = [
    "id", "source", "image_path", "question", "answer",
    "chart_type", "task_type", "difficulty", "verified", "split", "notes",
]

# Ordered list of hardset specs. Order determines hs_NNNN.png id assignment
# (first entry -> hs_0001, second -> hs_0002, etc.).
# Each entry: (raw_filename, chart_type, source_label, list of QAs).
HARDSET: list[tuple[str, str, str, list[dict]]] = [
    # ---- Batch 1 ----
    ("charts1.png", "mixed", "StatCan", [
        {"q": "Was the largest mode of transportation Land?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
        {"q": "Combining Air and Water shares of transportation, was that greater than Land alone?",
         "a": "No", "t": "hard_multi_step", "d": "hard"},
        {"q": "Which country was the largest source of overseas visitors?",
         "a": "United Kingdom", "t": "max_min", "d": "medium"},
    ]),
    ("charts2.png", "mixed", "StatCan", [
        {"q": "What was the month-over-month change in land arrivals?",
         "a": "10.1%", "t": "lookup_value", "d": "easy"},
        {"q": "Was the share of same-day trips greater than overnight?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
        {"q": "Which province was the top port of entry for arrivals?",
         "a": "Ontario", "t": "max_min", "d": "medium"},
    ]),
    ("charts15.png", "mixed", "ECB", [
        {"q": "In panel (a), did Inflation-protected fund flows increase or decrease after the start of the Middle East war?",
         "a": "Increased", "t": "trend_direction", "d": "medium"},
        {"q": "In panel (b), in which quarter were Redemption requests highest?",
         "a": "Q1 2026", "t": "max_min", "d": "hard"},
        {"q": "In panel (c), did Investment fund cash holdings trend upward or downward from 2015 to 2025?",
         "a": "Downward", "t": "trend_direction", "d": "hard"},
    ]),
    ("charts30.png", "bar", "BLS", [
        {"q": "Which industry had the largest positive productivity change in 2024?",
         "a": "Travel arrangement and reservation services", "t": "max_min", "d": "medium"},
        {"q": "Which industry had the largest negative productivity change in 2024?",
         "a": "Amusement parks and arcades", "t": "max_min", "d": "medium"},
        {"q": "Did Publishing have a positive productivity change in 2024?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),

    # ---- Batch 2 ----
    ("charts3.png", "mixed", "StatCan", [
        {"q": "What was the total number of air arrivals?",
         "a": "2,508,098", "t": "lookup_value", "d": "easy"},
        {"q": "Which airport had the highest number of arrivals?",
         "a": "Toronto Pearson", "t": "max_min", "d": "medium"},
        {"q": "Was the year-over-year change in air arrivals positive?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts4.png", "grouped_bar", "StatCan", [
        {"q": "What was the fasting glucose for Ages 60 to 79 in 2024?",
         "a": "6.0", "t": "lookup_value", "d": "medium"},
        {"q": "From 2009 to 2024, did fasting glucose for Ages 60 to 79 increase or decrease?",
         "a": "Increased", "t": "trend_direction", "d": "medium"},
        {"q": "In 2024, which age group had the highest fasting glucose?",
         "a": "Ages 60 to 79", "t": "max_min", "d": "easy"},
    ]),
    ("charts5.png", "mixed", "StatCan", [
        {"q": "What percentage of Japanese new entrants were women?",
         "a": "73%", "t": "lookup_value", "d": "medium"},
        {"q": "Among racialized groups, which had the highest STEM percentage in field of study?",
         "a": "Chinese", "t": "max_min", "d": "medium"},
        {"q": "Was the count of Not-a-visible-minority new entrants in 2020/2021 greater than in 2016/2017?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts6.png", "mixed", "StatCan", [
        {"q": "What was the count of Not-a-visible-minority graduates in 2023?",
         "a": "272K", "t": "lookup_value", "d": "medium"},
        {"q": "Did the count of Visible minority graduates increase or decrease from 2016 to 2023?",
         "a": "Increased", "t": "trend_direction", "d": "medium"},
        {"q": "Which racialized group had the highest STEM percentage in field of study?",
         "a": "Chinese", "t": "max_min", "d": "medium"},
    ]),
    ("charts7.png", "mixed", "StatCan", [
        {"q": "Which city had the largest year-over-year decline in condo prices in 2026 Q2?",
         "a": "Toronto", "t": "max_min", "d": "medium"},
        {"q": "Which city had the largest positive year-over-year change in condo prices?",
         "a": "Québec", "t": "max_min", "d": "medium"},
        {"q": "Was Vancouver's year-over-year change greater than Ottawa's?",
         "a": "No", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts8.png", "mixed", "StatCan", [
        {"q": "Which city had the largest quarter-over-quarter decline in condo prices in 2026 Q2?",
         "a": "Vancouver", "t": "max_min", "d": "medium"},
        {"q": "Did Québec have a positive quarter-over-quarter change in 2026 Q2?",
         "a": "No", "t": "compare_categories", "d": "medium"},
        {"q": "What was Vancouver's quarter-over-quarter percent change?",
         "a": "-2.6%", "t": "lookup_value", "d": "medium"},
    ]),

    # ---- Batch 3 ----
    ("charts9.png", "mixed", "BoC", [
        {"q": "For US jet fuel, was the color intensity above or below average during May 2026?",
         "a": "Above average", "t": "trend_direction", "d": "medium"},
        {"q": "Which commodity in the non-energy commodity section showed the most intense above-average pricing by May 2026?",
         "a": "UK primary aluminum", "t": "max_min", "d": "hard"},
    ]),
    ("charts10.png", "mixed", "ECB", [
        {"q": "In panel (b), what is the highest crisis frequency shown in the grid?",
         "a": "15%", "t": "max_min", "d": "medium"},
        {"q": "In panel (a), did EA HY Tech spreads rise around the start of the Middle East war?",
         "a": "Yes", "t": "trend_direction", "d": "hard"},
    ]),
    ("charts11.png", "mixed", "ECB", [
        {"q": "In panel (a), from 2022 to 2026 did the 30-year yield trend upward or downward?",
         "a": "Upward", "t": "trend_direction", "d": "medium"},
        {"q": "In panel (b), was Greece's (GR) change in debt-to-GDP negative?",
         "a": "Yes", "t": "compare_categories", "d": "hard"},
    ]),
    ("charts12.png", "mixed", "ECB", [
        {"q": "In panel (b), which country had the highest peak in net sovereign debt issuance during 2020–2021?",
         "a": "Germany", "t": "max_min", "d": "medium"},
        {"q": "In panel (a), was Belgium's (BE) planned 2026 government balance negative?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts13.png", "mixed", "ECB", [
        {"q": "In panel (b), which year is represented by the blue solid line?",
         "a": "2024", "t": "lookup_value", "d": "easy"},
        {"q": "In panel (c), from Q1 2023 to Q1 2026, did headline inflation increase or decrease?",
         "a": "Decreased", "t": "trend_direction", "d": "hard"},
    ]),
    ("charts14.png", "mixed", "ECB", [
        {"q": "In panel (b), what percentage of euro area banks' assets is Non-EU exposure?",
         "a": "25%", "t": "lookup_value", "d": "medium"},
        {"q": "In panel (b), which non-EU region had the largest exposure?",
         "a": "United States", "t": "max_min", "d": "medium"},
        {"q": "In panel (b), was Middle East exposure the smallest of the non-EU regions shown?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),

    # ---- Batch 4 ----
    ("charts16.png", "mixed", "ECB", [
        {"q": "In panel (a), which index reached the highest value by May 2026?",
         "a": "MSCI World Energy Sector Index", "t": "max_min", "d": "medium"},
        {"q": "In panel (a), did the MSCI World Software Index rise or fall between December 2025 and February 2026?",
         "a": "Fell", "t": "trend_direction", "d": "medium"},
    ]),
    ("charts17.png", "mixed", "ECB", [
        {"q": "In panel (c), did Financial Times cyberattack mentions increase or decrease from 2006 to 2026?",
         "a": "Increased", "t": "trend_direction", "d": "medium"},
        {"q": "In panel (b), which distribution has the highest peak density?",
         "a": "HICP inflation Feb. forecast", "t": "max_min", "d": "hard"},
    ]),
    ("charts18.png", "bar", "WHO", [
        {"q": "For the Education dimension in Low-income countries, what was the median difference in DTP zero-dose prevalence?",
         "a": "16.2", "t": "lookup_value", "d": "medium"},
        {"q": "In the Education dimension, which income group had the largest median difference?",
         "a": "Low-income", "t": "max_min", "d": "medium"},
        {"q": "Was the Place-of-residence median difference for All countries less than the Economic-status median difference for All countries?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts19.png", "mixed", "WHO", [
        {"q": "In the Health emergencies protection panel, which region requires the most progress in 2030?",
         "a": "Region of the Americas", "t": "max_min", "d": "medium"},
        {"q": "In the Healthier populations panel, which region requires the most progress in 2030?",
         "a": "African Region", "t": "max_min", "d": "medium"},
    ]),
    ("charts20.png", "stacked_bar", "WHO", [
        {"q": "Which pillar requires the most overall progress?",
         "a": "Healthier populations", "t": "max_min", "d": "medium"},
        {"q": "How many billion additional persons are needed for Healthier populations to meet 2030 expectations?",
         "a": "1.5B", "t": "lookup_value", "d": "medium"},
    ]),
    ("charts21.png", "mixed", "WHO", [
        {"q": "In the WHO region panel, which region had the highest risk of premature mortality from NCDs in 2000?",
         "a": "Eastern Mediterranean Region", "t": "max_min", "d": "medium"},
        {"q": "In the World Bank income groups panel, did the High-income group's risk trend upward or downward from 2000 to 2020?",
         "a": "Downward", "t": "trend_direction", "d": "medium"},
        {"q": "In the WHO region panel, was the Region of the Americas line consistently lower than the Global line?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),

    # ---- Batch 5 ----
    ("charts22.png", "mixed", "WHO", [
        {"q": "What was the neonatal mortality rate in the South-East Asia Region in 1990?",
         "a": "53", "t": "lookup_value", "d": "medium"},
        {"q": "In 1990, which WHO region had the highest under-5 mortality rate?",
         "a": "African Region", "t": "max_min", "d": "medium"},
        {"q": "From 1990 to 2023, did the African Region's under-5 mortality rate decrease?",
         "a": "Yes", "t": "trend_direction", "d": "medium"},
    ]),
    ("charts23.png", "mixed", "WHO", [
        {"q": "In the WHO region panel, what is the approximate value of the rightmost data point on the x-axis?",
         "a": "4.5", "t": "max_min", "d": "hard"},
    ]),
    ("charts24.png", "stacked_bar", "WHO", [
        {"q": "In the African Region panel, did Noncommunicable diseases become a larger share of causes from 2000 to 2021?",
         "a": "Yes", "t": "trend_direction", "d": "medium"},
        {"q": "In the European Region in 2000, which cause group had the largest share?",
         "a": "Noncommunicable diseases", "t": "max_min", "d": "medium"},
    ]),
    ("charts26.png", "mixed", "WHO", [
        {"q": "In the Mortality panel, what was the All Causes value for the All ages column?",
         "a": "5.17", "t": "lookup_value", "d": "medium"},
        {"q": "Among noncommunicable diseases in the Mortality panel All ages column, which cause has the highest value?",
         "a": "Stroke", "t": "max_min", "d": "hard"},
    ]),
    ("charts27.png", "stacked_bar", "WHO", [
        {"q": "In the Female Region of the Americas panel, what was the HALE value in 2019?",
         "a": "67", "t": "lookup_value", "d": "medium"},
        {"q": "In 2000 across all WHO regions for Both sexes, which region had the lowest HALE?",
         "a": "African Region", "t": "max_min", "d": "medium"},
        {"q": "In the African Region Male panel, did HALE increase from 2000 to 2021?",
         "a": "Yes", "t": "trend_direction", "d": "medium"},
    ]),

    # ---- Batch 6 ----
    ("charts28.png", "mixed", "ClimatePolicyDB", [
        {"q": "Which policy instrument covers the most sectors?",
         "a": "Tax", "t": "max_min", "d": "medium"},
        {"q": "Does Comparative energy efficiency label cover the Waste sector?",
         "a": "No", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts29.png", "bar", "ClimatePolicyDB", [
        {"q": "Which emission sector has the largest number of policy approaches?",
         "a": "Buildings", "t": "max_min", "d": "easy"},
        {"q": "Does Cross-sectoral have more policy approaches than Energy industries?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts31.png", "mixed", "BLS", [
        {"q": "What is the highest productivity growth category shown in the legend?",
         "a": "3.4% and above", "t": "lookup_value", "d": "easy"},
    ]),
    ("charts32.png", "stacked_bar", "BLS", [
        {"q": "In which year was the total number of fatal work injuries highest?",
         "a": "2022", "t": "max_min", "d": "medium"},
        {"q": "Did total fatal work injuries increase or decrease from 2023 to 2024?",
         "a": "Decreased", "t": "trend_direction", "d": "medium"},
    ]),
    ("charts33.png", "stacked_bar", "BLS", [
        {"q": "Did the total recordable cases rate decrease from 2022 to 2024?",
         "a": "Yes", "t": "trend_direction", "d": "medium"},
        {"q": "Were the total recordable rates in 2020 and 2021 the same?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts34.png", "bar", "BLS", [
        {"q": "Which activity did people spend the most hours per day on?",
         "a": "Personal care, including sleep", "t": "max_min", "d": "easy"},
        {"q": "Which activity was the second-longest average time per day?",
         "a": "Leisure and sports", "t": "max_min", "d": "medium"},
        {"q": "Do people spend more time on Household activities than on Working and work-related activities?",
         "a": "No", "t": "compare_categories", "d": "medium"},
    ]),

    # ---- Batch 7 ----
    ("charts35.png", "grouped_bar", "BLS", [
        {"q": "For Part-time workers, which benefit has the highest access rate?",
         "a": "Sick leave", "t": "max_min", "d": "medium"},
        {"q": "Is childcare access higher for Full-time workers than Part-time workers?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts36.png", "line", "BLS", [
        {"q": "What was the approximate peak percent change of All imports around 2008?",
         "a": "22", "t": "max_min", "d": "medium"},
        {"q": "During which year did All imports show the deepest negative percent change?",
         "a": "2009", "t": "max_min", "d": "medium"},
    ]),
    ("charts37.png", "line", "BLS", [
        {"q": "What was the largest positive spike in the Total PPI 1-month change during 2020–2022?",
         "a": "1.7", "t": "max_min", "d": "hard"},
        {"q": "What was the largest negative dip in the Total PPI during 2020?",
         "a": "-1.2", "t": "max_min", "d": "medium"},
    ]),
    ("charts38.png", "bar", "BLS", [
        {"q": "Which CPI category had the highest 12-month percentage change in June 2026?",
         "a": "Energy", "t": "max_min", "d": "easy"},
        {"q": "Was the All items CPI change greater than the Food CPI change?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
    ]),
    ("charts39.png", "mixed", "BLS", [
        {"q": "What is the highest metropolitan area unemployment rate category shown in the legend?",
         "a": "5.3% and above", "t": "lookup_value", "d": "medium"},
        {"q": "What is the lowest metropolitan area unemployment rate category shown?",
         "a": "3.5% and below", "t": "lookup_value", "d": "medium"},
    ]),
    ("charts40.png", "line", "BLS", [
        {"q": "In what approximate year did the civilian unemployment rate peak?",
         "a": "2020", "t": "max_min", "d": "medium"},
        {"q": "What was the approximate peak civilian unemployment rate during 2020?",
         "a": "14.8", "t": "lookup_value", "d": "medium"},
        {"q": "From 2010 to 2019, did the civilian unemployment rate generally trend downward?",
         "a": "Yes", "t": "trend_direction", "d": "medium"},
    ]),

    # ---- Batch 8 ----
    ("charts41.png", "mixed", "BLS", [
        {"q": "What is the highest wage-change category shown in the legend?",
         "a": "5.0% and above", "t": "lookup_value", "d": "medium"},
        {"q": "What is the lowest wage-change category shown in the legend?",
         "a": "3.2% and below", "t": "lookup_value", "d": "medium"},
    ]),
    ("charts42.png", "bar", "BLS", [
        {"q": "Which category had the largest number of jobs in Q4 2025?",
         "a": "Gross job gains", "t": "max_min", "d": "easy"},
        {"q": "Were gross job gains greater than gross job losses in Q4 2025?",
         "a": "Yes", "t": "compare_categories", "d": "medium"},
        {"q": "Which category had the smallest number of jobs in Q4 2025?",
         "a": "Losses at closing establishments", "t": "max_min", "d": "medium"},
    ]),
]


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    with MANIFEST.open() as f:
        return list(csv.DictReader(f))


def write_manifest(rows: list[dict]) -> None:
    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    if not RAW.is_dir():
        sys.exit(f"raw hardset dir not found: {RAW}")
    IMAGES.mkdir(parents=True, exist_ok=True)

    # Build all new rows first (fail-fast if any raw image missing)
    new_rows: list[dict] = []
    for idx, (raw_name, chart_type, src, qas) in enumerate(HARDSET, start=1):
        src_path = RAW / raw_name
        if not src_path.is_file():
            sys.exit(f"missing raw image: {src_path}")
        chart_id_base = f"hs_{idx:04d}"
        dst_rel = f"gold/images/{chart_id_base}.png"
        dst_abs = REPO / dst_rel
        shutil.copyfile(src_path, dst_abs)

        for q_idx, qa in enumerate(qas, start=1):
            new_rows.append({
                "id": f"{chart_id_base}__q{q_idx}",
                "source": "hardset",
                "image_path": dst_rel,
                "question": qa["q"],
                "answer": qa["a"],
                "chart_type": chart_type,
                "task_type": qa["t"],
                "difficulty": qa["d"],
                "verified": "false",   # task 8 will confirm
                "split": "train",
                "notes": f"hardset; {src}; {raw_name}",
            })

    # Load existing manifest, drop any old hardset rows, append new hardset rows
    existing = load_manifest()
    kept = [r for r in existing if r.get("source") != "hardset"]
    combined = kept + new_rows
    write_manifest(combined)

    # ---- Summary ----
    print(f"copied {len(HARDSET)} images to gold/images/hs_0001.png … hs_{len(HARDSET):04d}.png")
    print(f"appended {len(new_rows)} hardset rows")
    print(f"manifest total: {len(combined)} rows  "
          f"(kept {len(kept)} non-hardset, added {len(new_rows)} hardset)")

    tt = Counter(r["task_type"] for r in new_rows)
    ct = Counter(r["chart_type"] for r in new_rows)
    df = Counter(r["difficulty"] for r in new_rows)
    print("\nhardset task_type:", dict(tt))
    print("hardset chart_type:", dict(ct))
    print("hardset difficulty:", dict(df))


if __name__ == "__main__":
    main()
