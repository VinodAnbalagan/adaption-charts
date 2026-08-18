"""Visual style registry — the same chart data rendered in different dialects.

The single biggest gap in the v1 dataset: 1,002 synthetic rows all used one
matplotlib theme. Same fonts, same palette, same proportions, same grid.
A model trained on that learns one visual dialect, and any real chart that
looks different is out of distribution.

Ten styles imitating conventions you actually see in the wild — newspaper
graphics, spreadsheet defaults, journal figures, dark dashboards. Each
varies on five independent axes:

  colour      bar / line / multi-series palette, background, grid colour
  typography  font family stack, base size, title weight
  geometry    figure aspect ratio and DPI
  placement   title alignment, tick direction, which spines are drawn
  chrome      grid style and density, tick mark length

Font stacks name real system faces first and fall back to matplotlib's
bundled DejaVu, so generation never fails on a machine missing a font — it
just produces slightly less variety.

Usage — the renderers read their style globals at call time, so no change
to render.py or hard_render.py signatures is needed:

    from lib.styles import use_style, STYLE_NAMES

    with use_style("editorial"):
        render_bar(cats, vals, title, ylabel, path)

These are visual variations, not degradations: every style keeps
annotations legible. Perceptual difficulty is handled separately in
hard_render.py, and the two compose — a truncated-axis chart can be
rendered in any style.
"""

from __future__ import annotations
import contextlib
import importlib

_SANS = ["DejaVu Sans"]
_SERIF = ["DejaVu Serif"]

STYLES: dict[str, dict] = {

    # Baseline — what the v1 dataset used throughout.
    "neutral": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "--", "grid.alpha": 0.35,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Arial"] + _SANS,
            "font.size": 10, "axes.titlesize": 13, "axes.labelsize": 11,
            "xtick.labelsize": 10, "ytick.labelsize": 9,
            "figure.facecolor": "white", "axes.facecolor": "white",
        },
        "bar": "#4C72B0", "line": "#DD8452",
        "palette": ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"],
        "scale": (1.0, 1.0), "dpi": 110,
    },

    # Newspaper business graphic: red accent, left-aligned bold title,
    # horizontal rules only, no tick marks.
    "editorial": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "-", "grid.alpha": 0.25, "grid.color": "#888888",
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial Narrow", "Helvetica Neue", "Arial"] + _SANS,
            "font.size": 10.5, "axes.titlesize": 15, "axes.labelsize": 10,
            "axes.titleweight": "bold", "axes.titlelocation": "left",
            "xtick.labelsize": 10, "ytick.labelsize": 9,
            "figure.facecolor": "#FCFCFA", "axes.facecolor": "#FCFCFA",
            "xtick.major.size": 0, "ytick.major.size": 0,
        },
        "bar": "#C7112D", "line": "#1F5C7A",
        "palette": ["#C7112D", "#1F5C7A", "#E8A33D", "#4B8F6E", "#7A5C8F"],
        "scale": (1.18, 0.90), "dpi": 120,
    },

    # Salmon-paper financial press: serif type, warm ground.
    "salmon": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "-", "grid.alpha": 0.30, "grid.color": "#B8A99A",
            "font.family": "serif",
            "font.serif": ["Georgia", "Times New Roman"] + _SERIF,
            "font.size": 10, "axes.titlesize": 14, "axes.labelsize": 10,
            "axes.titlelocation": "left",
            "xtick.labelsize": 9.5, "ytick.labelsize": 9,
            "figure.facecolor": "#FFF1E5", "axes.facecolor": "#FFF1E5",
        },
        "bar": "#0F5499", "line": "#990F3D",
        "palette": ["#0F5499", "#990F3D", "#0D7680", "#96CC28", "#593380"],
        "scale": (1.05, 0.95), "dpi": 115,
    },

    # Spreadsheet default: boxed axes, heavy grid, classic office blue.
    "spreadsheet": {
        "rc": {
            "axes.spines.top": True, "axes.spines.right": True,
            "axes.spines.left": True, "axes.spines.bottom": True,
            "axes.edgecolor": "#808080", "axes.linewidth": 0.9,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "-", "grid.alpha": 0.55, "grid.color": "#D0D0D0",
            "font.family": "sans-serif",
            "font.sans-serif": ["Calibri", "Verdana", "Tahoma"] + _SANS,
            "font.size": 9.5, "axes.titlesize": 12, "axes.labelsize": 9.5,
            "axes.titlelocation": "center",
            "xtick.labelsize": 9, "ytick.labelsize": 9,
            "figure.facecolor": "white", "axes.facecolor": "white",
        },
        "bar": "#4472C4", "line": "#ED7D31",
        "palette": ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"],
        "scale": (0.95, 1.05), "dpi": 105,
    },

    # Stripped back: geometric sans, no grid, no side spines, large type.
    "minimal": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.spines.left": False, "axes.spines.bottom": True,
            "axes.grid": False,
            "font.family": "sans-serif",
            "font.sans-serif": ["Futura", "Avenir Next", "Century Gothic"] + _SANS,
            "font.size": 12, "axes.titlesize": 17, "axes.labelsize": 12,
            "axes.titlelocation": "left",
            "xtick.labelsize": 11.5, "ytick.labelsize": 10.5,
            "figure.facecolor": "white", "axes.facecolor": "white",
            "ytick.major.size": 0,
        },
        "bar": "#2B2B2B", "line": "#E4572E",
        "palette": ["#2B2B2B", "#E4572E", "#17BEBB", "#FFC914", "#76B041"],
        "scale": (1.12, 1.00), "dpi": 125,
    },

    # Dense analyst chart: small high-x-height type, fine dotted grid.
    "dense": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": ":", "grid.alpha": 0.45,
            "font.family": "sans-serif",
            "font.sans-serif": ["Tahoma", "Verdana", "Geneva"] + _SANS,
            "font.size": 8, "axes.titlesize": 10.5, "axes.labelsize": 8.5,
            "xtick.labelsize": 7.5, "ytick.labelsize": 7,
            "xtick.direction": "in", "ytick.direction": "in",
            "xtick.major.size": 2.5, "ytick.major.size": 2.5,
            "figure.facecolor": "white", "axes.facecolor": "#FAFAFA",
        },
        "bar": "#33658A", "line": "#F26419",
        "palette": ["#33658A", "#F26419", "#55DDE0", "#2F4858", "#F6AE2D"],
        "scale": (0.85, 0.82), "dpi": 135,
    },

    # Dark dashboard: wide aspect, humanist sans, faint grid.
    "dark": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.spines.left": False, "axes.spines.bottom": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "-", "grid.alpha": 0.20, "grid.color": "#AAAAAA",
            "font.family": "sans-serif",
            "font.sans-serif": ["Trebuchet MS", "Verdana", "Lucida Grande"] + _SANS,
            "font.size": 10, "axes.titlesize": 14, "axes.labelsize": 10,
            "axes.titlelocation": "left",
            "xtick.labelsize": 9.5, "ytick.labelsize": 9,
            "figure.facecolor": "#1E1E24", "axes.facecolor": "#1E1E24",
            "text.color": "#EDEDED", "axes.labelcolor": "#EDEDED",
            "xtick.color": "#CFCFCF", "ytick.color": "#CFCFCF",
            "axes.titlecolor": "#FFFFFF", "savefig.facecolor": "#1E1E24",
        },
        "bar": "#5EC5E8", "line": "#FF9F1C",
        "palette": ["#5EC5E8", "#FF9F1C", "#8AE68A", "#FF6B6B", "#C39BD3"],
        "scale": (1.22, 0.95), "dpi": 115,
    },

    # Journal figure: serif, thin full box, inward ticks, compact.
    "academic": {
        "rc": {
            "axes.spines.top": True, "axes.spines.right": True,
            "axes.spines.left": True, "axes.spines.bottom": True,
            "axes.edgecolor": "#222222", "axes.linewidth": 0.7,
            "axes.grid": False,
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Palatino"] + _SERIF,
            "font.size": 9.5, "axes.titlesize": 11.5, "axes.labelsize": 10,
            "axes.titlelocation": "center",
            "xtick.labelsize": 9, "ytick.labelsize": 9,
            "xtick.direction": "in", "ytick.direction": "in",
            "figure.facecolor": "white", "axes.facecolor": "white",
        },
        "bar": "#555555", "line": "#222222",
        "palette": ["#555555", "#222222", "#888888", "#AAAAAA", "#333333"],
        "scale": (0.80, 0.85), "dpi": 140,
    },

    # Soft pastel deck: rounded geometric sans, tinted ground.
    "pastel": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "-", "grid.alpha": 0.30, "grid.color": "#D8D8E0",
            "font.family": "sans-serif",
            "font.sans-serif": ["Avenir", "Nunito", "Century Gothic"] + _SANS,
            "font.size": 10.5, "axes.titlesize": 14.5, "axes.labelsize": 10.5,
            "axes.titlelocation": "center",
            "xtick.labelsize": 10, "ytick.labelsize": 9.5,
            "figure.facecolor": "#FBFAFF", "axes.facecolor": "#FBFAFF",
            "xtick.major.size": 0, "ytick.major.size": 0,
        },
        "bar": "#8FB8DE", "line": "#F4A6A0",
        "palette": ["#8FB8DE", "#F4A6A0", "#A8D5BA", "#F6D186", "#C9AEDB"],
        "scale": (1.08, 1.05), "dpi": 110,
    },

    # Presentation scale: heavy strokes, high contrast, big bold type.
    "bold": {
        "rc": {
            "axes.spines.top": False, "axes.spines.right": False,
            "axes.spines.left": True, "axes.spines.bottom": True,
            "axes.edgecolor": "#111111", "axes.linewidth": 1.6,
            "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
            "grid.linestyle": "-", "grid.alpha": 0.22, "grid.color": "#333333",
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial Black", "Helvetica Neue", "Impact"] + _SANS,
            "font.size": 12, "axes.titlesize": 17, "axes.labelsize": 12,
            "axes.titleweight": "bold", "axes.titlelocation": "left",
            "xtick.labelsize": 11.5, "ytick.labelsize": 11,
            "lines.linewidth": 3.0, "lines.markersize": 8,
            "figure.facecolor": "white", "axes.facecolor": "white",
        },
        "bar": "#111111", "line": "#D62828",
        "palette": ["#111111", "#D62828", "#003049", "#F77F00", "#4C956C"],
        "scale": (1.15, 1.10), "dpi": 120,
    },
}

STYLE_NAMES: list[str] = list(STYLES)

_TARGETS = ("lib.render", "lib.hard_render")
_GLOBALS = ("_STYLE", "_BAR_COLOR", "_LINE_COLOR", "_PALETTE", "_SCALE", "_DPI")


@contextlib.contextmanager
def use_style(name: str):
    """Temporarily apply a named style to the chart renderers.

    Patches the style globals in render.py and hard_render.py and restores
    them on exit. The renderers resolve these at call time, so signatures
    are untouched.
    """
    if name not in STYLES:
        raise KeyError(f"unknown style {name!r}; have {STYLE_NAMES}")
    spec = STYLES[name]

    mods = []
    for mod_name in _TARGETS:
        try:
            mods.append(importlib.import_module(mod_name))
        except ImportError:
            continue

    new = {
        "_STYLE": dict(spec["rc"]),
        "_BAR_COLOR": spec["bar"],
        "_LINE_COLOR": spec["line"],
        "_PALETTE": list(spec["palette"]),
        "_SCALE": tuple(spec.get("scale", (1.0, 1.0))),
        "_DPI": spec.get("dpi", 110),
    }

    saved = [(m, {g: getattr(m, g, None) for g in _GLOBALS}) for m in mods]
    for m in mods:
        for g, v in new.items():
            setattr(m, g, v)
    try:
        yield name
    finally:
        for m, old in saved:
            for g, v in old.items():
                if v is not None:
                    setattr(m, g, v)


def style_for_index(i: int) -> str:
    """Deterministic round-robin over styles, for reproducible generation."""
    return STYLE_NAMES[i % len(STYLE_NAMES)]
