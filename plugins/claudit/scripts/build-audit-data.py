#!/usr/bin/env python3
"""Build the audit_data dict consumed by render-report.py.

Usage:
    build-audit-data.py <signals.json> <audit-judgment.json> <output.json>

Inputs:
    signals.json       — output of aggregate-transcripts.py (mechanical numbers)
    audit-judgment.json — the agent's audit decisions (band placement,
                          fired findings, quest selections, takeaway prose,
                          inventory facts gathered from settings/skills/agents)

The audit-judgment.json schema is documented in audit-harness/SKILL.md.

Output: audit_data.json suitable to pipe straight into render-report.py.
"""
from __future__ import annotations

import json
import math
import sys
import html
import datetime
from pathlib import Path


# ---- Catalog-derived constants (used in the rendered report) ----------------

BAND_DESC = {
    "Explorer":  "Just starting. Mostly prompting. Limited or no use of skills, agents, hooks.",
    "Builder":   "Using skills, agents, or hooks intentionally. Has a working harness shape. Verifies their own work.",
    "Operator":  "Manages context, caching, model routing, and compaction deliberately. Treats tokens as a budget. Uses plan mode and subagents as default reflexes.",
    "Architect": "The harness is a designed system. Just-in-time context discipline, verified work, lean stable instructions, custom skills that compound, model routing as default.",
}
GRADE_SORT = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}


# ---- Helpers ---------------------------------------------------------------

def fmt_cost(n):
    n = float(n)
    if n >= 100:
        return f"${n:,.0f}"
    return f"${n:,.2f}"


def fmt_tokens(n):
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.1f}M"
    if n >= 1_000:         return f"{n/1_000:.1f}K"
    return str(int(n))


def fmt_msgs(n):
    return f"{n:,}" if n >= 1000 else str(n)


def project_display(encoded):
    """encoded path-name like '-Users-foo-dev-bar' → 'bar'"""
    parts = encoded.lstrip("-").split("-")
    return parts[-1] if parts else encoded


def project_path(encoded):
    return "/" + encoded.lstrip("-").replace("-", "/")


def grade_for_session(s):
    """Composite score → letter grade. Penalize high cost, error cascades,
    retry churn, compaction. Reward strong cache hit."""
    score = 50.0
    cache = s.get("cache_hit", 0)
    if cache >= 0.95: score += 25
    elif cache >= 0.80: score += 15
    elif cache < 0.50: score -= 10
    cost = s.get("cost", 0)
    if cost > 500: score -= 30
    elif cost > 100: score -= 10
    elif cost > 25: score -= 5
    flags = s.get("flags", [])
    if "compact" in flags: score -= 5
    if "err·casc" in flags: score -= 15
    if any("retry" in f for f in flags): score -= 10
    score = max(0, min(100, score))
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    return "D"


def render_drilldown_html(finding, signals):
    """Some findings get a drilldown table or bar list."""
    fid = finding.get("id", "")
    if fid == "f_no_jit_context":
        tools = signals.get("tool_uses", {})
        if not tools:
            return ""
        items = sorted(tools.items(), key=lambda kv: -kv[1])[:8]
        max_v = items[0][1] or 1
        rows = "".join(
            f'<li class="bar-list-row">'
            f'<span class="bar-list-name"><code>{html.escape(name)}</code></span>'
            f'<span class="bar-list-track"><span class="bar-list-fill" style="width: {n/max_v*100:.1f}%;"></span></span>'
            f'<span class="bar-list-value">{n:,}</span>'
            f'</li>'
            for name, n in items
        )
        return (
            '<div class="drilldown">'
            '<p class="drilldown-label">Specifically · tool usage breakdown</p>'
            f'<ul class="bar-list">{rows}</ul>'
            '</div>'
        )
    if fid == "f_hook_matchers_broad":
        broad = finding.get("measured", {}).get("broad_matchers") or []
        if not broad:
            return ""
        rows = "".join(
            f'<tr><td><code>{html.escape(str(b[0]))}</code></td>'
            f'<td><code>{html.escape(repr(b[1]))}</code></td></tr>'
            for b in broad
        )
        return (
            '<div class="drilldown">'
            '<p class="drilldown-label">Specifically · hooks with broad matchers</p>'
            '<table class="drilldown-table">'
            '<thead><tr><th>Event</th><th>Matcher</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )
    return ""


# ---- Main ------------------------------------------------------------------

def main(argv):
    if len(argv) != 4:
        sys.stderr.write(f"usage: {argv[0]} <signals.json> <audit-judgment.json> <output.json>\n")
        return 2
    signals = json.loads(Path(argv[1]).read_text())
    judgment = json.loads(Path(argv[2]).read_text())

    band = judgment["band"]  # {current, next, progression_pct, floor_pct, signal_bonus, must_haves_demonstrated, must_haves_missing}
    cur = band["current"]
    nxt = band.get("next")
    prog_int = int(round(band["progression_pct"]))
    inv = judgment.get("inventory", {})

    # ---- Hero stamp ---------------------------------------------------------
    circumference = 2 * math.pi * 36
    stamp_dashoffset = circumference * (1 - prog_int / 100)

    # ---- Topbar -------------------------------------------------------------
    audit_completed = judgment.get("audit_completed_at", "")
    if audit_completed:
        ac_dt = datetime.datetime.fromisoformat(audit_completed.replace("Z", "+00:00"))
    else:
        ac_dt = datetime.datetime.now(datetime.timezone.utc)
    audit_date_display = ac_dt.strftime("%b %d, %Y")

    # ---- Quests grouped by tier ---------------------------------------------
    fired = judgment.get("fired_findings", [])
    sev_order = {"high": 0, "medium": 1, "low": 2}
    quests_by_tier = {"quick": [], "medium": [], "deep": []}
    for f in fired:
        tier = f.get("tier", "medium")
        if tier not in quests_by_tier:
            tier = "medium"
        quests_by_tier[tier].append(f)
    for tier in quests_by_tier:
        quests_by_tier[tier].sort(key=lambda q: (sev_order.get(q.get("severity", ""), 9), q.get("id", "")))

    def render_impact_tag(q):
        impact = q.get("impact", "")
        return f'<span class="tag tag-impact">{html.escape(impact)}</span>' if impact else ""

    def render_quest_row(q, idx):
        return {
            "OPEN_ATTR": " open" if idx == 0 else "",
            "NUM_PADDED": f"{idx+1:02d}",
            "SEVERITY": q.get("severity", "medium"),
            "TITLE": html.escape(q.get("name", "")),
            "IMPACT_TAG_HTML": render_impact_tag(q),
            "EVIDENCE": html.escape(q.get("evidence", "")),
            "EXPLAIN": html.escape(q.get("explain", "")),
            "FIX": html.escape(q.get("fix", "")),
            "VERIFY": html.escape(q.get("verify", "Next audit will reflect the change.")),
            "DRILLDOWN_HTML": render_drilldown_html(q, signals),
        }

    quest_quick = [render_quest_row(q, i) for i, q in enumerate(quests_by_tier["quick"])]
    quest_medium = [render_quest_row(q, i) for i, q in enumerate(quests_by_tier["medium"])]
    quest_deep = [render_quest_row(q, i) for i, q in enumerate(quests_by_tier["deep"])]

    # Top quests preview (first 3 across all tiers, in tier order)
    all_flat = quests_by_tier["quick"] + quests_by_tier["medium"] + quests_by_tier["deep"]
    top_quests_preview = [
        {
            "SEVERITY": q.get("severity", "medium"),
            "TITLE": html.escape(q.get("name", "")),
            "IMPACT": html.escape(q.get("impact", "")) if q.get("impact") else "",
            "EVIDENCE": html.escape(q.get("evidence", "")),
        }
        for q in all_flat[:3]
    ]

    # ---- Daily aggregations -------------------------------------------------
    spend_per_day = signals.get("spend_per_day", {})
    sessions_per_day = signals.get("sessions_per_day", {})
    tokens_per_day = signals.get("tokens_per_day", {})

    daily_spend = sorted(
        [{"day": d, "cost": c, "sessions": sessions_per_day.get(d, 0)}
         for d, c in spend_per_day.items() if c > 0],
        key=lambda x: x["day"]
    )[-30:]

    daily_days = [d["day"] for d in daily_spend]

    def total_tokens_for_day(day):
        tk = tokens_per_day.get(day, {})
        return tk.get("in", 0) + tk.get("out", 0) + tk.get("cache_r", 0) + tk.get("cache_c", 0)

    def cache_hit_for_day(day):
        tk = tokens_per_day.get(day, {})
        denom = tk.get("in", 0) + tk.get("cache_r", 0) + tk.get("cache_c", 0)
        return (tk.get("cache_r", 0) / denom * 100) if denom > 0 else 0.0

    daily_tokens = [{"day": d, "tokens": total_tokens_for_day(d)} for d in daily_days]
    daily_sessions = [{"day": d, "sessions": sessions_per_day.get(d, 0)} for d in daily_days]
    daily_cache_hit = [{"day": d, "cache_hit_pct": cache_hit_for_day(d)} for d in daily_days]

    if daily_spend:
        spend_max = max(d["cost"] for d in daily_spend)
        spend_max_str = fmt_cost(spend_max)
        start_date = daily_spend[0]["day"][5:]
        end_date = daily_spend[-1]["day"][5:]
    else:
        spend_max_str = "$0"
        start_date = "—"
        end_date = "—"

    token_chart_max = max((d["tokens"] for d in daily_tokens), default=0)
    sessions_chart_max = max((d["sessions"] for d in daily_sessions), default=0)

    # ---- Sessions roster ----------------------------------------------------
    session_rows = []
    sessions_active = 0
    for s in sorted(signals.get("sessions", []), key=lambda x: -x.get("cost", 0)):
        if s.get("msg_count", 0) == 0:
            continue
        sessions_active += 1
        grade = grade_for_session(s)
        cost = s.get("cost", 0)
        primary = (s.get("primary_model") or "—").replace("claude-", "")
        cache_pct = s.get("cache_hit", 0) * 100
        tokens_total = (
            s.get("tokens_in", 0) + s.get("tokens_out", 0)
            + s.get("tokens_cache_r", 0) + s.get("tokens_cache_c", 0)
        )
        tooltip = (
            f"in:{fmt_tokens(s.get('tokens_in', 0))} · "
            f"out:{fmt_tokens(s.get('tokens_out', 0))} · "
            f"cache-r:{fmt_tokens(s.get('tokens_cache_r', 0))} · "
            f"cache-c:{fmt_tokens(s.get('tokens_cache_c', 0))}"
        )
        flags_html = "".join(f'<span class="flag">{html.escape(fl)}</span>' for fl in s.get("flags", []))
        session_rows.append({
            "GRADE": grade,
            "GRADE_NUM": GRADE_SORT[grade],
            "COST_RAW": f"{cost:.2f}",
            "COST_DISPLAY": fmt_cost(cost),
            "PROJECT_PATH": project_path(s.get("project_dir", "")),
            "PROJECT_NAME": html.escape(project_display(s.get("project_dir", ""))),
            "MODEL": html.escape(primary),
            "MSGS": s.get("msg_count", 0),
            "MSGS_DISPLAY": fmt_msgs(s.get("msg_count", 0)),
            "CACHE_RAW": f"{cache_pct:.1f}",
            "CACHE_DISPLAY": f"{cache_pct:.1f}%",
            "TOKENS_RAW": tokens_total,
            "TOKENS_DISPLAY": fmt_tokens(tokens_total),
            "TOKENS_TOOLTIP": tooltip,
            "FLAGS_HTML": flags_html,
        })

    top_sessions_preview = [
        {"GRADE": r["GRADE"], "COST": r["COST_DISPLAY"],
         "PROJECT": r["PROJECT_NAME"], "MSGS": r["MSGS_DISPLAY"]}
        for r in session_rows[:3]
    ]

    # ---- Project rollup -----------------------------------------------------
    pc = signals.get("project_cost", {})
    sorted_projects = sorted(pc.items(), key=lambda kv: -kv[1])[:8]
    max_proj = sorted_projects[0][1] if sorted_projects else 1.0
    project_bars = [
        {"NAME": project_display(p), "PCT": f"{(c/max_proj*100):.1f}", "VALUE": fmt_cost(c)}
        for p, c in sorted_projects
    ]

    # ---- KPI strip ----------------------------------------------------------
    total_cost = signals.get("total_cost", 0)
    cache_savings = signals.get("cache_savings_estimate_usd", 0)
    cache_pct = signals.get("cache_hit_rate", 0) * 100
    err_pct = (signals.get("sessions_with_4plus_consecutive_errors", 0) /
               max(1, signals.get("session_count", 1))) * 100
    primary_model = signals.get("primary_model_window") or "n/a"
    primary_short = primary_model.replace("claude-", "") if isinstance(primary_model, str) else primary_model
    compact_pct = (signals.get("sessions_with_compact", 0) /
                   max(1, signals.get("session_count", 1))) * 100

    # Startup load — agent supplies the breakdown in inventory.startup_load = list of {name, tokens, idx}
    load_items = inv.get("startup_load") or []
    startup_total = sum(it.get("tokens", 0) for it in load_items)
    for it in load_items:
        it["pct"] = (it["tokens"] / startup_total * 100) if startup_total > 0 else 0
        it["title"] = f"{it['name']}: {it['tokens']:,} tk ({it['pct']:.1f}%)"

    kpi_cells = [
        {"KPI_CLASS": " kpi-accent", "KPI_LABEL": "30d spend",
         "KPI_VALUE": fmt_cost(total_cost),
         "KPI_FOOT": f"cache saved {fmt_cost(cache_savings)}"},
        {"KPI_CLASS": "", "KPI_LABEL": "Cache hit",
         "KPI_VALUE": f"{cache_pct:.1f}%",
         "KPI_FOOT": "rare; you amortize context well" if cache_pct >= 80 else "target ≥50%"},
        {"KPI_CLASS": "", "KPI_LABEL": "Tool errors",
         "KPI_VALUE": f"{err_pct:.1f}%",
         "KPI_FOOT": f"{signals.get('session_count', 0)} sessions analyzed"},
        {"KPI_CLASS": "", "KPI_LABEL": "Startup load",
         "KPI_VALUE": f"{startup_total/1000:.0f}K tk" if startup_total else "—",
         "KPI_FOOT": f"{startup_total/200000*100:.1f}% of 200K" if startup_total else ""},
        {"KPI_CLASS": "", "KPI_LABEL": "Until autocompact",
         "KPI_VALUE": "~24 msgs",
         "KPI_FOOT": f"{compact_pct:.1f}% sessions hit it"},
        {"KPI_CLASS": "", "KPI_LABEL": "Primary model",
         "KPI_VALUE": primary_short,
         "KPI_FOOT": "most-used in window"},
    ]

    # ---- Token economics ----------------------------------------------------
    tt = signals.get("total_tokens", {})
    econ_total = tt.get("in", 0) + tt.get("out", 0) + tt.get("cache_r", 0) + tt.get("cache_c", 0)
    if econ_total >= 1_000_000:
        econ_total_str = f"{econ_total/1_000_000:.1f}M"
    else:
        econ_total_str = f"{econ_total:,}"

    econ_items = [
        ("Input tokens",   tt.get("in", 0),      "oxblood"),
        ("Output tokens",  tt.get("out", 0),     "gold"),
        ("Cache read",     tt.get("cache_r", 0), "sage"),
        ("Cache creation", tt.get("cache_c", 0), "amber"),
    ]
    def _pct(n): return (n / econ_total * 100) if econ_total > 0 else 0
    econ_segments = [
        {"PCT": f"{_pct(n):.2f}", "COLOR": color, "TITLE": f"{label}: {n:,} ({_pct(n):.1f}%)"}
        for (label, n, color) in econ_items
    ]
    econ_legend = [
        {"COLOR": color, "NAME": label, "TOKENS": f"{n:,}", "PCT": f"{_pct(n):.1f}"}
        for (label, n, color) in econ_items
    ]

    # ---- Run history --------------------------------------------------------
    today_disp = ac_dt.strftime("%b %d, %Y")
    run_history = judgment.get("run_history") or [
        {"date": today_disp, "band": cur.lower(), "progression_pct": prog_int}
    ]

    # ---- Inventory cells + plugin list -------------------------------------
    enabled_plugins = inv.get("enabled_plugins", [])
    inventory_stats = [
        {"VALUE": str(len(enabled_plugins)), "LABEL": "enabled plugins"},
        {"VALUE": str(inv.get("hooks_count", 0)), "LABEL": "hooks configured"},
        {"VALUE": str(inv.get("allow_count", 0)), "LABEL": "permission allowlist entries"},
    ]

    # ---- Final assembly ----------------------------------------------------
    uuid = judgment["uuid"]

    audit_data = {
        # Topbar
        "RUN_NUMBER": str(judgment.get("run_number", 1)).zfill(3),
        "AUDIT_DATE_DISPLAY": audit_date_display,
        "CATALOG_VERSION": judgment.get("catalog_version", ""),
        "RUN_DURATION": judgment.get("run_duration", "—"),
        # Hero
        "BAND": cur,
        "BAND_LOWER": cur.lower(),
        "NEXT_BAND": nxt or "Architect",
        "PROGRESSION_INT": prog_int,
        "STAMP_DASHOFFSET": f"{stamp_dashoffset:.2f}",
        "BAND_TAGLINE": BAND_DESC.get(cur, ""),
        # KPI strip
        "KPI": kpi_cells,
        # Tab counts
        "COUNT_QUICK_WINS": str(len(quests_by_tier["quick"])),
        "COUNT_MEDIUM": str(len(quests_by_tier["medium"])),
        "COUNT_DEEP": str(len(quests_by_tier["deep"])),
        "COUNT_SESSIONS": str(signals.get("session_count", 0)),
        "SESSIONS_ACTIVE": str(sessions_active),
        "SESSIONS_TOTAL_COST": fmt_cost(total_cost),
        # Spend chart
        "SPEND_CHART_MAX": spend_max_str,
        "SPEND_CHART_START": start_date,
        "SPEND_CHART_END": end_date,
        "DAILY_SPEND": daily_spend,
        # Daily charts
        "DAILY_TOKENS": daily_tokens,
        "DAILY_SESSIONS": daily_sessions,
        "DAILY_CACHE_HIT": daily_cache_hit,
        "TOKEN_CHART_MAX": (lambda n: f"{n/1_000_000_000:.1f}B" if n >= 1_000_000_000 else f"{n/1_000_000:.1f}M" if n >= 1_000_000 else f"{n/1_000:.1f}K" if n >= 1_000 else str(int(n)))(token_chart_max),
        "SESSIONS_CHART_MAX": str(sessions_chart_max),
        # Overview
        "TOP_QUEST": top_quests_preview,
        "TOP_SESSION": top_sessions_preview,
        "PROJECT_BAR": project_bars,
        # Quest tiers
        "QUEST_QUICK": quest_quick,
        "QUEST_MEDIUM": quest_medium,
        "QUEST_DEEP": quest_deep,
        # Sessions
        "SESSION_ROW": session_rows,
        # Trends
        "RUN_HISTORY_COUNT": f"{len(run_history)} run{'s' if len(run_history)!=1 else ''}",
        "RUN_HISTORY": run_history,
        "RUN_HISTORY_LAST_DATE": today_disp,
        "ECON_TOTAL": econ_total_str,
        "ECON_SEGMENT": econ_segments,
        "ECON_LEGEND": econ_legend,
        "HISTORY_DELTA": [],
        # Setup
        "LOAD_SEGMENT": [{"PCT": f"{i['pct']:.1f}", "IDX": i.get("idx", 0), "TITLE": i.get("title", "")} for i in load_items],
        "LOAD_LEGEND":  [{"IDX": i.get("idx", 0), "NAME": i["name"],
                          "TOKENS": f"{i['tokens']:,} tk", "PCT": f"{i['pct']:.1f}"} for i in load_items],
        "INVENTORY_STAT": inventory_stats,
        "COUNT_ENABLED_PLUGINS": str(len(enabled_plugins)),
        "PLUGIN_ITEM": [{"NAME": p} for p in enabled_plugins],
        # Hero takeaway (free-form HTML the agent provides)
        "TAKEAWAY": judgment.get("takeaway_html", ""),
        # Capture form
        "UUID": uuid,
        "UUID_SHORT": uuid[:8],
    }

    out_path = Path(argv[3])
    out_path.write_text(json.dumps(audit_data, indent=2))
    print(f"WROTE {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
