#!/usr/bin/env python3
"""Render the claudit harness audit report from a data JSON + bundled template.

Usage:
    render-report.py <audit_data.json> <output.html>

The bundled template lives at <plugin>/assets/templates/report.html and is
located via this script's own path. The data JSON shape is documented in
the audit-harness SKILL.md.

Stdlib only; no external dependencies.

Substitution model
------------------

* Scalar `{KEY}` placeholders are looked up in the JSON dict and substituted
  verbatim. The renderer does NOT HTML-escape — the data builder is
  responsible for producing valid HTML in any field that contains markup.

* Paired loop markers `<!-- CLAUDIT:NAME --> ... <!-- /CLAUDIT:NAME -->`
  define a row template. The renderer iterates `ctx[NAME]` (a list of dicts)
  and renders the row template once per item. Loops are recursive — markers
  inside markers nest correctly thanks to a name-backref'd regex.

* Procedural markers (single-line, no closing tag) trigger renderer-side
  computation. Currently:
  - `<!-- CLAUDIT:SPEND_CHART_BARS -->`  daily-spend SVG bar group
  - `<!-- CLAUDIT:RUN_HISTORY_SVG -->`   band-progression line chart body
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR.parent / "assets" / "templates" / "report.html"

# Paired marker regex — name backref forces opening/closing names to match.
PAIR_RE = re.compile(
    r"<!--\s*CLAUDIT:(?P<name>[A-Z_]+)\s*-->\s*"
    r"(?P<inner>[\s\S]*?)"
    r"<!--\s*/CLAUDIT:(?P=name)\s*-->\s*"
)

SCALAR_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")

# ---------------------------------------------------------------------------
# Procedural generators — chart geometry lives here, coupled to the SVG
# viewBox in the template. Designers can change colors/strokes in the
# template; geometry constants live here.
# ---------------------------------------------------------------------------

# Daily spend chart geometry (matches viewBox="0 0 560 140" in the template)
SPEND_CHART_X_LEFT = 38
SPEND_CHART_X_RIGHT = 552
SPEND_CHART_Y_TOP = 8
SPEND_CHART_Y_BOTTOM = 118
SPEND_CHART_BAR_GAP = 2  # visual gap between bars

# Run history chart geometry (matches viewBox="0 0 720 100" in the template)
HISTORY_X_LEFT = 38
HISTORY_X_RIGHT = 712
HISTORY_Y_BAND_FLOOR = 78  # y coord of explorer floor (top of chart proper)
HISTORY_Y_BAND_STEP = 17.5  # y delta per band
BAND_INDEX = {"explorer": 0, "builder": 1, "operator": 2, "architect": 3}
BAND_LABEL_3 = ["exp", "bui", "ope", "arc"]


def _fmt_cost(cents_or_dollars: float) -> str:
    """Format a cost as the reference does: $1,095 / $52.30 / $3.91."""
    n = float(cents_or_dollars)
    if n >= 100:
        return f"${n:,.0f}"
    return f"${n:,.2f}"


def render_spend_chart_bars(daily_spend: list[dict]) -> str:
    """Generate `<g class="bar-group">...</g>` markup for each daily-spend entry.

    Each item: {"day": "YYYY-MM-DD", "cost": <float dollars>, "sessions": <int>}
    """
    if not daily_spend:
        return ""
    n = len(daily_spend)
    span = SPEND_CHART_X_RIGHT - SPEND_CHART_X_LEFT
    spacing = span / n
    width = spacing - SPEND_CHART_BAR_GAP
    height_span = SPEND_CHART_Y_BOTTOM - SPEND_CHART_Y_TOP
    max_cost = max((d["cost"] for d in daily_spend), default=0) or 1.0

    parts = []
    for idx, d in enumerate(daily_spend):
        x = SPEND_CHART_X_LEFT + idx * spacing
        cost = float(d["cost"])
        h = max(0.1, (cost / max_cost) * height_span)
        y = SPEND_CHART_Y_BOTTOM - h
        cost_str = _fmt_cost(cost)
        sess = int(d.get("sessions", 0))
        plural = "" if sess == 1 else "s"
        parts.append(
            f'<g class="bar-group">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{h:.1f}" '
            f'class="bar-rect" data-day="{d["day"]}" data-cost="{cost_str}">'
            f'<title>{d["day"]}: {cost_str} · {sess} session{plural}</title>'
            f"</rect></g>"
        )
    return "".join(parts)


def render_daily_value_bars(daily: list[dict], *, value_key: str, value_fmt, css_class: str, axis_label_x: int = 38) -> str:
    """Generic daily-value bar chart. Each item has a `day` and a numeric value.

    value_fmt(n) returns the display string (e.g. token count or session count).
    """
    if not daily:
        return ""
    n = len(daily)
    # Use the same x-range as spend chart (38..552) but allow a different left margin
    # for charts whose axis text starts at x=46 (token volume).
    left = axis_label_x
    right = SPEND_CHART_X_RIGHT
    span = right - left
    spacing = span / n
    width = spacing - SPEND_CHART_BAR_GAP
    height_span = SPEND_CHART_Y_BOTTOM - SPEND_CHART_Y_TOP
    max_v = max((d[value_key] for d in daily), default=0) or 1.0

    parts = []
    for idx, d in enumerate(daily):
        x = left + idx * spacing
        v = float(d[value_key])
        h = max(0.1, (v / max_v) * height_span)
        y = SPEND_CHART_Y_BOTTOM - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{h:.1f}" '
            f'class="bar-rect {css_class}">'
            f'<title>{d["day"]}: {value_fmt(v)}</title></rect>'
        )
    return "".join(parts)


def _fmt_tokens(n: float) -> str:
    n = float(n)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B tokens"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M tokens"
    if n >= 1_000:
        return f"{n/1_000:.1f}K tokens"
    return f"{int(n):,} tokens"


def _fmt_sessions(n: float) -> str:
    n = int(n)
    return f"{n} session{'' if n == 1 else 's'}"


def render_cache_hit_line(daily: list[dict]) -> str:
    """Daily cache-hit-rate line chart. Each item has `day` and `cache_hit_pct` (0-100)."""
    if not daily:
        return ""
    n = len(daily)
    left = SPEND_CHART_X_LEFT
    right = SPEND_CHART_X_RIGHT
    span = right - left
    # Y axis: 0% at y=118, 100% at y=8, 50% at y=63 (110 px range over 100 pct)
    y_zero = SPEND_CHART_Y_BOTTOM
    y_full = SPEND_CHART_Y_TOP
    y_span = y_zero - y_full

    points = []
    for idx, d in enumerate(daily):
        if n == 1:
            x = left
        else:
            x = left + idx * (span / (n - 1))
        pct = max(0.0, min(100.0, float(d["cache_hit_pct"])))
        y = y_zero - (pct / 100.0) * y_span
        points.append((x, y, pct, d["day"]))

    parts = []
    coords = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in points)
    if len(points) > 1:
        parts.append(f'<polyline points="{coords}" class="line-stroke" />')
    for x, y, pct, day in points:
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" class="line-dot">'
            f'<title>{day}: {pct:.1f}%</title></circle>'
        )
    return "".join(parts)


def render_run_history_svg(history: list[dict]) -> str:
    """Generate the run-history line chart SVG body.

    Each item: {"date": "YYYY-MM-DD", "band": "<lower>", "progression_pct": <int>}
    Results are placed left-to-right in chronological order (oldest first).
    """
    if not history:
        return ""
    parts = []

    # Band reference lines + labels (4 dashed horizontal rules at band thresholds)
    for i in range(4):
        y = HISTORY_Y_BAND_FLOOR - i * HISTORY_Y_BAND_STEP
        parts.append(
            f'<line x1="{HISTORY_X_LEFT}" y1="{y}" x2="{HISTORY_X_RIGHT}" y2="{y}" '
            f'class="axis-ref" stroke-dasharray="2 4" />'
        )
    for i, label in enumerate(BAND_LABEL_3):
        y = HISTORY_Y_BAND_FLOOR - i * HISTORY_Y_BAND_STEP + 5.75  # vertical-center the label
        parts.append(
            f'<text x="34" y="{y}" class="axis-label" text-anchor="end">{label}</text>'
        )

    # Baseline + start/end date labels
    parts.append(
        f'<line x1="{HISTORY_X_LEFT}" y1="{HISTORY_Y_BAND_FLOOR}" '
        f'x2="{HISTORY_X_RIGHT}" y2="{HISTORY_Y_BAND_FLOOR}" class="axis" />'
    )
    parts.append(
        f'<text x="{HISTORY_X_LEFT}" y="96" class="axis-label">{history[0]["date"]}</text>'
    )
    parts.append(
        f'<text x="{HISTORY_X_RIGHT}" y="96" class="axis-label" text-anchor="end">now</text>'
    )

    # Compute (x, y) per run
    pts = []
    n = len(history)
    span = HISTORY_X_RIGHT - HISTORY_X_LEFT
    for idx, h in enumerate(history):
        if n == 1:
            x = HISTORY_X_LEFT
        else:
            x = HISTORY_X_LEFT + idx * (span / (n - 1))
        bidx = BAND_INDEX.get(h["band"].lower(), 0)
        # Position dot proportionally inside the band-strip (lower in strip = lower band)
        progression_frac = float(h.get("progression_pct", 0)) / 100.0
        y = HISTORY_Y_BAND_FLOOR - (bidx + progression_frac) * HISTORY_Y_BAND_STEP
        pts.append((x, y, h))

    # Polyline through points (only if >1)
    if len(pts) > 1:
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
        parts.append(f'<polyline points="{coords}" class="line-stroke" />')

    # Dots
    for x, y, h in pts:
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" class="line-dot">'
            f'<title>{h["date"]}: {h["band"]} {int(h.get("progression_pct", 0))}%</title>'
            f"</circle>"
        )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Template engine
# ---------------------------------------------------------------------------

def render(template: str, ctx: dict) -> str:
    """Render template against ctx. Recursive for nested loop markers."""
    while True:
        m = PAIR_RE.search(template)
        if not m:
            break
        name = m.group("name")
        inner = m.group("inner")
        items = ctx.get(name, [])
        if not isinstance(items, list):
            items = []
        rendered = "".join(
            render(inner, item if isinstance(item, dict) else {}) for item in items
        )
        template = template[: m.start()] + rendered + template[m.end():]

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in ctx and not isinstance(ctx[key], list):
            return str(ctx[key])
        return match.group(0)

    return SCALAR_RE.sub(repl, template)


def expand_procedural(template: str, ctx: dict) -> str:
    """Replace single-line procedural markers with computed content."""
    if "<!-- CLAUDIT:SPEND_CHART_BARS -->" in template:
        bars = render_spend_chart_bars(ctx.get("DAILY_SPEND", []))
        template = template.replace("<!-- CLAUDIT:SPEND_CHART_BARS -->", bars)
    if "<!-- CLAUDIT:RUN_HISTORY_SVG -->" in template:
        svg_body = render_run_history_svg(ctx.get("RUN_HISTORY", []))
        template = template.replace("<!-- CLAUDIT:RUN_HISTORY_SVG -->", svg_body)
    if "<!-- CLAUDIT:DAILY_TOKEN_BARS -->" in template:
        bars = render_daily_value_bars(
            ctx.get("DAILY_TOKENS", []), value_key="tokens",
            value_fmt=_fmt_tokens, css_class="bar-rect-amber", axis_label_x=50,
        )
        template = template.replace("<!-- CLAUDIT:DAILY_TOKEN_BARS -->", bars)
    if "<!-- CLAUDIT:DAILY_SESSIONS_BARS -->" in template:
        bars = render_daily_value_bars(
            ctx.get("DAILY_SESSIONS", []), value_key="sessions",
            value_fmt=_fmt_sessions, css_class="bar-rect-sage", axis_label_x=38,
        )
        template = template.replace("<!-- CLAUDIT:DAILY_SESSIONS_BARS -->", bars)
    if "<!-- CLAUDIT:DAILY_CACHE_HIT_LINE -->" in template:
        line = render_cache_hit_line(ctx.get("DAILY_CACHE_HIT", []))
        template = template.replace("<!-- CLAUDIT:DAILY_CACHE_HIT_LINE -->", line)
    return template


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(f"usage: {argv[0]} <audit_data.json> <output.html>\n")
        return 2

    data_path = Path(argv[1])
    out_path = Path(argv[2])

    if not TEMPLATE_PATH.exists():
        sys.stderr.write(f"template missing at {TEMPLATE_PATH}\n")
        return 1
    if not data_path.exists():
        sys.stderr.write(f"data file missing at {data_path}\n")
        return 1

    template = TEMPLATE_PATH.read_text()
    data = json.loads(data_path.read_text())

    template = expand_procedural(template, data)
    rendered = render(template, data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered)

    remaining = SCALAR_RE.findall(rendered)
    if remaining:
        # Filter out a few CSS-style false positives that look like {KEY}
        # (none currently expected, but be tolerant)
        sys.stderr.write(
            f"WARN: {len(remaining)} unresolved placeholder(s): "
            f"{sorted(set(remaining))[:15]}\n"
        )

    print(f"WROTE {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
