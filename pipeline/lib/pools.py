"""Vocabulary + value pools for programmatic chart generation.

Each pool is a dict with:
  domain           : DOMAIN_META key (routes phrasing bank + answer_fmt)
  entity           : natural term for the categorization axis
  y_label          : chart y-axis label
  value_range      : (low, high) inclusive; values rounded to nearest 100
  cat_pool         : source list to sample categories from (>= n_cats needed)
  title_templates  : list of templates; placeholders {q}, {h}, {y} filled with
                     seeded random period markers

Pools are grouped by chart_type. A generator picks a pool round-robin, samples
categories, seeds values, and returns a chart spec compatible with the
existing build_*_rows dispatch.
"""

BAR_POOLS = [
    {
        "domain": "revenue_bar", "entity": "vertical",
        "y_label": "Revenue ($)", "value_range": (1500, 12000),
        "cat_pool": [
            "Healthcare", "Retail", "Finance", "Manufacturing",
            "Tech", "Energy", "Media", "Automotive",
        ],
        "title_templates": [
            "Q{q} Revenue by Vertical",
            "FY20{y} Revenue by Vertical",
            "H{h} Revenue by Vertical",
        ],
    },
    {
        "domain": "revenue_bar", "entity": "channel",
        "y_label": "Revenue ($)", "value_range": (2000, 15000),
        "cat_pool": [
            "Direct", "Partner", "Reseller", "Online",
            "Retail", "Wholesale", "Marketplace",
        ],
        "title_templates": [
            "Q{q} Revenue by Channel",
            "H{h} Revenue by Channel",
        ],
    },
    {
        "domain": "revenue_bar", "entity": "segment",
        "y_label": "Revenue ($)", "value_range": (1500, 12000),
        "cat_pool": [
            "Consumer", "Enterprise", "SMB", "Government",
            "Education", "Nonprofit", "Startup", "Mid-Market",
        ],
        "title_templates": [
            "Q{q} Revenue by Segment",
            "H{h} Revenue by Segment",
            "FY20{y} Revenue by Segment",
        ],
    },
    {
        "domain": "revenue_bar", "entity": "team",
        "y_label": "Revenue ($)", "value_range": (1500, 10000),
        "cat_pool": [
            "Alpha", "Beta", "Gamma", "Delta",
            "Epsilon", "Zeta", "Theta", "Omega",
        ],
        "title_templates": [
            "Q{q} Revenue by Team",
            "Monthly Revenue by Team",
        ],
    },
    {
        "domain": "units_sold_bar", "entity": "product",
        "y_label": "Units sold", "value_range": (500, 8000),
        "cat_pool": [
            "Widget A", "Widget B", "Widget C", "Widget D",
            "Widget E", "Widget F", "Gizmo X", "Gizmo Y",
        ],
        "title_templates": [
            "Q{q} Units Sold by Product",
            "Weekly Units Sold by Product",
        ],
    },
    {
        "domain": "units_sold_bar", "entity": "SKU",
        "y_label": "Units sold", "value_range": (200, 3000),
        "cat_pool": [
            "SKU-201", "SKU-202", "SKU-203", "SKU-204",
            "SKU-205", "SKU-206", "SKU-207", "SKU-208",
        ],
        "title_templates": [
            "Weekly Units Sold by SKU",
            "Monthly Units Sold by SKU",
        ],
    },
]


# Line pools use a walk-with-drift value generator. Fields:
#   trend           : "up" / "down" / "flat" bias for the seeded walk
#   x_pool          : list of x-label options (each option is a full x-axis)
#   period_pool     : optional {period} fill for title templates
LINE_POOLS = [
    {
        "domain": "revenue_line", "entity": "month",
        "y_label": "Revenue ($)", "value_range": (4000, 10000),
        "x_pool": [
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        ],
        "title_templates": [
            "Monthly Revenue — {period}",
            "Revenue by Month — {period}",
        ],
        "period_pool": ["H1 2024", "H2 2024", "H1 2025", "H2 2025"],
    },
    {
        "domain": "revenue_line", "entity": "quarter",
        "y_label": "Revenue ($)", "value_range": (15000, 45000),
        "x_pool": [["Q1", "Q2", "Q3", "Q4"]],
        "title_templates": [
            "Quarterly Revenue — FY{y}",
            "FY{y} Quarterly Revenue",
        ],
        "period_pool": None,
    },
    {
        "domain": "users_line", "entity": "month",
        "y_label": "Active users", "value_range": (5000, 30000),
        "x_pool": [
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        ],
        "title_templates": [
            "Monthly Active Users — {period}",
            "Active Users by Month — {period}",
        ],
        "period_pool": ["H1 2024", "H2 2024", "H1 2025", "H2 2025"],
    },
    {
        "domain": "signups_line", "entity": "week",
        "y_label": "Signups", "value_range": (200, 1500),
        "x_pool": [
            ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"],
        ],
        "title_templates": [
            "Weekly Signups — {period}",
            "Signups by Week — {period}",
        ],
        "period_pool": ["Q1", "Q2", "Q3", "Q4"],
    },
]


# Grouped-bar pools: 2 series side-by-side per category.
GROUPED_POOLS = [
    {
        "domain": "revenue_grouped", "entity": "segment", "series_axis": "year",
        "series_pool": [["2023", "2024"], ["2024", "2025"]],
        "y_label": "Revenue ($)", "value_range": (2000, 10000),
        "cat_pool": [
            "Consumer", "Enterprise", "SMB", "Government",
            "Education", "Nonprofit", "Startup",
        ],
        "title_templates": [
            "Revenue by Segment: {series_a} vs {series_b}",
            "{series_a}-{series_b} Revenue by Segment",
        ],
    },
    {
        "domain": "revenue_grouped", "entity": "region", "series_axis": "half",
        "series_pool": [["H1", "H2"]],
        "y_label": "Revenue ($)", "value_range": (2000, 10000),
        "cat_pool": ["NA", "EMEA", "APAC", "LATAM", "MEA"],
        "title_templates": [
            "Revenue by Region: {series_a} vs {series_b}",
        ],
    },
    {
        "domain": "revenue_grouped", "entity": "vertical", "series_axis": "quarter",
        "series_pool": [["Q1", "Q2"], ["Q3", "Q4"]],
        "y_label": "Revenue ($)", "value_range": (2000, 12000),
        "cat_pool": [
            "Healthcare", "Retail", "Finance", "Manufacturing",
            "Tech", "Energy", "Media",
        ],
        "title_templates": [
            "Revenue by Vertical: {series_a} vs {series_b}",
        ],
    },
    {
        "domain": "revenue_grouped", "entity": "channel", "series_axis": "period",
        "series_pool": [["Plan", "Actual"]],
        "y_label": "Revenue ($)", "value_range": (2000, 12000),
        "cat_pool": [
            "Direct", "Partner", "Reseller", "Online",
            "Retail", "Wholesale", "Marketplace",
        ],
        "title_templates": [
            "Revenue by Channel: {series_a} vs {series_b}",
        ],
    },
]


# Stacked-bar pools: 3 series stacked vertically per category.
STACKED_POOLS = [
    {
        "domain": "revenue_stacked", "entity": "segment",
        "series_pool": [
            ["Basic", "Pro", "Premium"],
            ["Basic", "Standard", "Pro"],
        ],
        "y_label": "Revenue ($)", "value_range": (500, 3500),
        "cat_pool": [
            "Consumer", "Enterprise", "SMB", "Government", "Education",
        ],
        "title_templates": [
            "Revenue by Segment: Product Tier Breakdown",
            "Revenue by Segment and Tier",
        ],
    },
    {
        "domain": "revenue_stacked", "entity": "quarter",
        "series_pool": [
            ["Organic", "Paid", "Referral"],
            ["Direct", "Partner", "Marketplace"],
        ],
        "y_label": "Revenue ($)", "value_range": (500, 4500),
        "cat_pool": ["Q1", "Q2", "Q3", "Q4"],
        "title_templates": [
            "Quarterly Revenue by Channel",
            "Revenue by Quarter and Channel",
        ],
    },
    {
        "domain": "revenue_stacked", "entity": "region",
        "series_pool": [
            ["Basic", "Pro", "Premium"],
            ["Software", "Services", "Hardware"],
        ],
        "y_label": "Revenue ($)", "value_range": (500, 3500),
        "cat_pool": ["NA", "EMEA", "APAC", "LATAM"],
        "title_templates": [
            "Revenue by Region: Product Breakdown",
            "Regional Revenue by Product",
        ],
    },
]


# Circle pools (pie/donut). Same phrasing bank; render differs by chart_type.
CIRCLE_POOLS = [
    {
        "domain": "share_circle", "entity": "channel", "noun": "spend",
        "value_range": (1000, 5000),
        "cat_pool": [
            "Paid Search", "Social", "Email", "SEO",
            "Display", "Direct", "Affiliate",
        ],
        "title_templates": ["Marketing Spend by Channel", "Ad Spend by Channel"],
    },
    {
        "domain": "share_circle", "entity": "category", "noun": "sales",
        "value_range": (1000, 6000),
        "cat_pool": [
            "Software", "Services", "Hardware", "Subscriptions", "Consulting",
        ],
        "title_templates": ["Sales by Product Category", "Sales Mix"],
    },
    {
        "domain": "share_circle", "entity": "region", "noun": "revenue",
        "value_range": (1500, 8000),
        "cat_pool": ["NA", "EMEA", "APAC", "LATAM", "MEA"],
        "title_templates": ["Revenue by Region", "Regional Revenue Share"],
    },
    {
        "domain": "share_circle", "entity": "source", "noun": "traffic",
        "value_range": (2000, 15000),
        "cat_pool": [
            "Organic", "Direct", "Paid", "Referral", "Social", "Email",
        ],
        "title_templates": ["Traffic by Source", "Website Traffic Sources"],
    },
    {
        "domain": "share_circle", "entity": "department", "noun": "budget",
        "value_range": (500, 4500),
        "cat_pool": [
            "Engineering", "Sales", "Marketing", "Operations",
            "Support", "HR", "IT",
        ],
        "title_templates": ["Budget by Department", "FY25 Budget Allocation"],
    },
]


