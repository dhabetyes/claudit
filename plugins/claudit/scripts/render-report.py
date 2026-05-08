#!/usr/bin/env python3
"""Render the claudit harness audit report from a data JSON + bundled template.

Usage:
    render-report.py <audit_data.json> <output.html>

The bundled template lives at <plugin>/assets/templates/report.html and is
located via this script's own path. The data JSON shape is documented in
the audit-harness SKILL.md.

Stdlib only; no external dependencies. Substitution is dumb string
replacement — the data builder is responsible for producing valid HTML
in any field it intends to be rendered as HTML (the convention is that
field names ending in _HTML may contain markup; everything else is
treated as plain text but the renderer does NOT escape — the data
builder hands us final strings).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR.parent / "assets" / "templates" / "report.html"

# Paired marker:  <!-- CLAUDIT:NAME -->  ... <!-- /CLAUDIT:NAME -->
# Backref forces opening and closing names to match, so nested same-named
# markers can't collide. Inner content is non-greedy.
PAIR_RE = re.compile(
    r"<!--\s*CLAUDIT:(?P<name>[A-Z_]+)\s*-->\s*(?P<inner>[\s\S]*?)<!--\s*/CLAUDIT:(?P=name)\s*-->\s*"
)

SCALAR_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


def render(template: str, ctx: dict) -> str:
    """Render template against ctx. Recursive for nested loop markers."""
    # 1. Expand all paired loop markers (top-down — outermost first).
    while True:
        m = PAIR_RE.search(template)
        if not m:
            break
        name = m.group("name")
        inner = m.group("inner")
        items = ctx.get(name, [])
        if not isinstance(items, list):
            # Scalar value where a loop was expected — drop the block.
            items = []
        rendered = "".join(
            render(inner, item if isinstance(item, dict) else {}) for item in items
        )
        template = template[: m.start()] + rendered + template[m.end():]

    # 2. Substitute scalar placeholders {KEY} from ctx.
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in ctx and not isinstance(ctx[key], list):
            return str(ctx[key])
        # Leave unknown placeholders intact — useful for debugging.
        return match.group(0)

    return SCALAR_RE.sub(repl, template)


def render_gauge_dynamic(progression_pct: float) -> str:
    """Generate the gauge ticks + marker SVG for the given progression %.

    Mirrors the geometry baked into the original designed report:
      - 50 ticks evenly spaced along x = 20 .. 608 (588 wide, 12 px step)
      - Major ticks (every 5th) have y1 = 22 (taller); others y1 = 32
      - Marker triangle "▼ {pct}" at x = 20 + (pct/100) * 588, y = 10
      - Marker line at the same x, from y=14 to y=60
      - Filled tick count = round(pct/100 * 50), capped to [0, 50]
    """
    pct = max(0.0, min(100.0, float(progression_pct)))
    filled = max(0, min(50, int(round(pct / 100 * 50))))
    marker_x = 20 + (pct / 100) * 588

    # Marker triangle text + value
    out = []
    out.append(
        f'<text class="current" x="{marker_x:.1f}" y="10" text-anchor="middle">▼ {pct:.1f}</text>'
    )
    # Baseline
    out.append(
        '<line x1="20" y1="56" x2="608" y2="56" stroke="currentColor" stroke-width="0.5" opacity="0.25"/>'
    )
    # Ticks
    out.append('<g stroke-linecap="butt" stroke-width="2">')
    for i in range(50):
        x = 20 + i * 12
        is_major = (i % 5 == 0) or (i == 49)
        y1 = 22 if is_major else 32
        cls = "tick fill" if i < filled else "tick"
        out.append(f'  <line class="{cls}" x1="{x}" x2="{x}" y1="{y1}" y2="{56}"/>')
    out.append('</g>')
    # Pointer line
    out.append(
        f'<line class="marker-line" x1="{marker_x:.1f}" y1="14" x2="{marker_x:.1f}" y2="60"/>'
    )
    return "\n        ".join(out)


def expand_procedural(template: str, ctx: dict) -> str:
    """Replace single-line procedural markers (no closing tag) with computed content."""
    pct = float(ctx.get("PROGRESSION_TOTAL", 0))
    gauge_html = render_gauge_dynamic(pct)
    template = template.replace("<!-- CLAUDIT:GAUGE_DYNAMIC -->", gauge_html)
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

    # Sanity check — surface any unresolved placeholders so the caller can fix data.
    remaining = SCALAR_RE.findall(rendered)
    # Filter out CSS-like false positives (e.g. media queries don't include {KEY} but
    # we also want to ignore the CSS variable references in style — those use var(--name),
    # not {NAME}, so they don't match SCALAR_RE).
    if remaining:
        sys.stderr.write(
            f"WARN: {len(remaining)} unresolved placeholder(s): {sorted(set(remaining))[:10]}\n"
        )

    print(f"WROTE {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
