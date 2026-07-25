"""Question phrasing templates for the synthetic core.

Register: flat / direct / one clause / ChartQA-human style.
Each task_type has 2-3 flat variants. Rotation picks one deterministically per
chart (per-domain chart_index % n) so no same-template signal concentrates.

Templates use named placeholders. Drivers .format(...) them with actual
category names / entity terms.

Domains covered so far:
  - REVENUE_BAR         : bar charts of $-denominated revenue
  - UNITS_BAR           : bar charts of unit counts
  - MONTHLY_REVENUE_LINE: line charts of monthly $ revenue
  - MONTHLY_USERS_LINE  : line charts of monthly user counts
  - REVENUE_GROUPED     : grouped bars, revenue split across a series axis
  - REVENUE_STACKED     : stacked bars, revenue composed from stack components
  - SHARE_CIRCLE        : pie/donut, generic share-of-{noun} phrasings
"""

from __future__ import annotations
from typing import Sequence


# --- BAR --------------------------------------------------------------------

REVENUE_BAR: dict[str, list[str]] = {
    "lookup_value": [
        "What was {category}'s revenue?",
        "Revenue for {category}?",
        "How much revenue did {category} generate?",
    ],
    "max_min_highest": [
        "Which {entity} had the highest revenue?",
        "Which {entity} made the most revenue?",
        "Which {entity} led in revenue?",
    ],
    "max_min_lowest": [
        "Which {entity} had the lowest revenue?",
        "Which {entity} made the least revenue?",
        "Which {entity} was smallest in revenue?",
    ],
    "delta_absolute": [
        "How much more revenue did {a} generate than {b}?",
        "What was the revenue difference between {a} and {b}?",
        "By how much does {a}'s revenue exceed {b}'s?",
    ],
    "rank_order_top": [
        "Rank the top 3 {entities} by revenue.",
        "List the top 3 {entities} by revenue.",
        "Name the top 3 {entities} in revenue.",
    ],
    "rank_order_bottom": [
        "Rank the bottom 3 {entities} by revenue.",
        "List the bottom 3 {entities} by revenue.",
        "Name the bottom 3 {entities} in revenue.",
    ],
    "hard_multi_step": [
        "Would {a} and {b} combined exceed {c}'s revenue?",
        "Do the combined revenues of {a} and {b} exceed {c}'s?",
        "Together, would {a} and {b} out-earn {c}?",
    ],
}


UNITS_BAR: dict[str, list[str]] = {
    "lookup_value": [
        "How many units did {category} sell?",
        "Units sold by {category}?",
        "What was {category}'s unit total?",
    ],
    "max_min_highest": [
        "Which {entity} sold the most units?",
        "Which {entity} had the highest unit sales?",
        "Which {entity} led in units sold?",
    ],
    "max_min_lowest": [
        "Which {entity} sold the fewest units?",
        "Which {entity} had the lowest unit sales?",
        "Which {entity} was weakest in unit sales?",
    ],
    "delta_absolute": [
        "How many more units did {a} sell than {b}?",
        "What was the unit sales difference between {a} and {b}?",
        "By how many units does {a} exceed {b}?",
    ],
    "rank_order_top": [
        "Rank the top 3 {entities} by units sold.",
        "List the top 3 {entities} by units sold.",
        "Name the top 3 {entities} in units sold.",
    ],
    "rank_order_bottom": [
        "Rank the bottom 3 {entities} by units sold.",
        "List the bottom 3 {entities} by units sold.",
        "Name the bottom 3 {entities} in units sold.",
    ],
    "hard_multi_step": [
        "Would {a} and {b} combined exceed {c}'s unit sales?",
        "Do the combined unit sales of {a} and {b} exceed {c}'s?",
        "Together, would {a} and {b} out-sell {c}?",
    ],
}


# --- LINE -------------------------------------------------------------------

MONTHLY_REVENUE_LINE: dict[str, list[str]] = {
    "lookup_value": [
        "What was the revenue in {category}?",
        "Revenue in {category}?",
        "How much revenue was recorded in {category}?",
    ],
    "max_min_highest": [
        "In which {entity} was revenue highest?",
        "Which {entity} had the highest revenue?",
        "Which {entity} peaked in revenue?",
    ],
    "max_min_lowest": [
        "In which {entity} was revenue lowest?",
        "Which {entity} had the lowest revenue?",
        "Which {entity} recorded the lowest revenue?",
    ],
    "trend_direction": [
        "Did revenue increase or decrease from {a} to {b}?",
        "From {a} to {b}, did revenue increase or decrease?",
        "Between {a} and {b}, did revenue increase or decrease?",
    ],
    "percent_change_ratio": [
        "What was the percent change in revenue from {a} to {b}?",
        "By what percent did revenue change from {a} to {b}?",
        "What was the percentage change in revenue between {a} and {b}?",
    ],
    "hard_multi_step": [
        "Was the increase from {a1} to {b1} larger than the increase from {a2} to {b2}?",
        "Did the {a1}-to-{b1} change exceed the {a2}-to-{b2} change?",
        "Was revenue growth from {a1} to {b1} bigger than from {a2} to {b2}?",
    ],
}


MONTHLY_USERS_LINE: dict[str, list[str]] = {
    "lookup_value": [
        "How many users were there in {category}?",
        "Users in {category}?",
        "What was the user count in {category}?",
    ],
    "max_min_highest": [
        "In which {entity} were users highest?",
        "Which {entity} had the most users?",
        "Which {entity} peaked in users?",
    ],
    "max_min_lowest": [
        "In which {entity} were users lowest?",
        "Which {entity} had the fewest users?",
        "Which {entity} recorded the lowest user count?",
    ],
    "trend_direction": [
        "Did users increase or decrease from {a} to {b}?",
        "From {a} to {b}, did users increase or decrease?",
        "Between {a} and {b}, did users increase or decrease?",
    ],
    "percent_change_ratio": [
        "What was the percent change in users from {a} to {b}?",
        "By what percent did users change from {a} to {b}?",
        "What was the percentage change in users between {a} and {b}?",
    ],
    "hard_multi_step": [
        "Was the increase from {a1} to {b1} larger than the increase from {a2} to {b2}?",
        "Did the {a1}-to-{b1} change exceed the {a2}-to-{b2} change?",
        "Was user growth from {a1} to {b1} bigger than from {a2} to {b2}?",
    ],
}


# --- GROUPED BAR ------------------------------------------------------------
# Multi-series bars side-by-side per category.
# Placeholders: {category}, {series}, {entity}, {series_axis}, {series_a}, {series_b}

REVENUE_GROUPED: dict[str, list[str]] = {
    "lookup_value": [
        "What was {category}'s revenue in {series}?",
        "{category} revenue in {series}?",
        "How much revenue did {category} generate in {series}?",
    ],
    "max_min_highest": [
        "In {series}, which {entity} had the highest revenue?",
        "Which {entity} led in revenue in {series}?",
        "In {series}, which {entity} peaked in revenue?",
    ],
    "max_min_lowest": [
        "In {series}, which {entity} had the lowest revenue?",
        "In {series}, which {entity} recorded the lowest revenue?",
        "Which {entity} made the least revenue in {series}?",
    ],
    "multi_series_compare": [
        "For {category}, which {series_axis} had higher revenue, {series_a} or {series_b}?",
        "Was {category}'s revenue higher in {series_a} or {series_b}?",
        "Between {series_a} and {series_b}, which had higher revenue for {category}?",
    ],
    "hard_multi_step": [
        "Was {cat1}'s revenue in {series_a} higher than {cat2}'s in {series_b}?",
        "Did {cat1} in {series_a} out-earn {cat2} in {series_b}?",
        "Between {cat1} in {series_a} and {cat2} in {series_b}, was the former higher?",
    ],
}


# --- STACKED BAR ------------------------------------------------------------
# Series stacked vertically within each category bar.
# Placeholders: {category}, {series}, {entity}

REVENUE_STACKED: dict[str, list[str]] = {
    "lookup_value": [
        "What was the {series} revenue for {category}?",
        "{series} revenue for {category}?",
        "How much {series} revenue did {category} contribute?",
    ],
    "max_min_highest": [
        "Which {entity} had the highest total revenue?",
        "Which {entity} led in total revenue?",
        "Which {entity} recorded the highest total revenue?",
    ],
    "max_min_lowest": [
        "Which {entity} had the lowest total revenue?",
        "Which {entity} recorded the lowest total revenue?",
        "Which {entity} had the smallest total revenue?",
    ],
    "aggregation_sum_avg": [
        "What was {category}'s total revenue?",
        "How much total revenue did {category} generate?",
        "What was the total revenue for {category}?",
    ],
    "rank_order_top": [
        "Rank the top 3 {entities} by total revenue.",
        "List the top 3 {entities} by total revenue.",
        "Name the top 3 {entities} in total revenue.",
    ],
    "rank_order_bottom": [
        "Rank the bottom 3 {entities} by total revenue.",
        "List the bottom 3 {entities} by total revenue.",
        "Name the bottom 3 {entities} in total revenue.",
    ],
}


# --- PIE / DONUT ------------------------------------------------------------
# Generic share-of-noun phrasings. {noun} varies per chart ("spend", "budget",
# "sales", etc.) so one bank covers many pie/donut topics.
# Placeholders: {category}, {entity}, {noun}, {a}, {b}

SHARE_CIRCLE: dict[str, list[str]] = {
    "lookup_value": [
        "What percentage of {noun} came from {category}?",
        "What share of {noun} did {category} represent?",
        "{category}'s share of total {noun}?",
    ],
    "max_min_highest": [
        "Which {entity} had the largest share of {noun}?",
        "Which {entity} dominated {noun}?",
        "Which {entity} had the biggest slice of {noun}?",
    ],
    "max_min_lowest": [
        "Which {entity} had the smallest share of {noun}?",
        "Which {entity} had the smallest slice of {noun}?",
        "Which {entity} accounted for the least {noun}?",
    ],
    "compare_categories": [
        "Was {a}'s share of {noun} larger than {b}'s?",
        "Did {a} have a bigger share of {noun} than {b}?",
        "Was {a}'s {noun} share greater than {b}'s?",
    ],
    "rank_order_top": [
        "Rank the top 3 {entities} by share of {noun}.",
        "List the top 3 {entities} by share of {noun}.",
        "Name the top 3 {entities} by {noun} share.",
    ],
    "rank_order_bottom": [
        "Rank the bottom 3 {entities} by share of {noun}.",
        "List the bottom 3 {entities} by share of {noun}.",
        "Name the bottom 3 {entities} by {noun} share.",
    ],
}


def pick(templates: Sequence[str], chart_index: int) -> str:
    """Deterministic rotation by chart_index. Same chart -> same template."""
    return templates[chart_index % len(templates)]
