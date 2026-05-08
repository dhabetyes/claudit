#!/usr/bin/env python3
"""Aggregate Claude Code session transcripts into a signals JSON.

Usage:
    aggregate-transcripts.py [output_path]

Default output: /tmp/claudit-signals.json

Emits per-session rows (session_id, project_dir, primary_model, msg_count,
token totals, cache hit rate, cost from per-model pricing, flags like
compact/plan/retry/err·casc) plus global aggregates (msgs_per_day,
spend_per_day, sessions_per_day, tokens_per_day, models, tool uses,
custom skill uses, total tokens/cost, cache hit rate, agent dispatches,
plan-mode signals, stop reasons, tool-result percentiles, retry-churn,
error-cascade, big-thinking, project rollups).

Reads from `~/.claude/projects/**/*.jsonl` filtered to last 30 days
by mtime. Local-only; no credentials are read.
"""
import json, os, sys, time, re
from collections import Counter, defaultdict
from pathlib import Path

OUTPUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claudit-signals.json"
PROJECTS = Path.home() / ".claude" / "projects"
NOW = time.time()
CUTOFF = NOW - 30 * 86400

# ---- Per-model token pricing (USD per 1M tokens) ---------------------------
# Source: Anthropic published rates as of 2026 model lineup.
# cache_read at 10% of input; cache_creation at 1.25× input.
PRICING = {
    "opus":   {"in": 15.00, "out": 75.00, "cache_r": 1.50,  "cache_c": 18.75},
    "sonnet": {"in":  3.00, "out": 15.00, "cache_r": 0.30,  "cache_c":  3.75},
    "haiku":  {"in":  1.00, "out":  5.00, "cache_r": 0.10,  "cache_c":  1.25},
}

def model_tier(model_name: str | None) -> str:
    if not model_name:
        return "sonnet"
    m = model_name.lower()
    if "opus" in m:    return "opus"
    if "haiku" in m:   return "haiku"
    return "sonnet"

def cost_for_tokens(model: str, *, inp: int, out: int, cache_r: int, cache_c: int) -> float:
    p = PRICING[model_tier(model)]
    return (inp * p["in"] + out * p["out"] + cache_r * p["cache_r"] + cache_c * p["cache_c"]) / 1_000_000

verifier_patterns = re.compile(
    r"\b(npm test|npm run test|bun test|pytest|ruff|eslint|tsc|cargo test|rspec|bin/test|jest|vitest|mix test|go test|rails test)\b",
    re.IGNORECASE,
)

# Global aggregates
all_msgs_per_day = defaultdict(int)
all_sessions_per_day = defaultdict(int)
all_spend_per_day = defaultdict(float)
all_tokens_per_day = defaultdict(lambda: {"in": 0, "out": 0, "cache_r": 0, "cache_c": 0})
all_models_seen = Counter()
all_tool_uses = Counter()
all_custom_skill_uses = Counter()
total_msgs_by_role = Counter()
total_tokens = {"in": 0, "out": 0, "cache_r": 0, "cache_c": 0}
total_cost = 0.0
big_thinking_events = 0
sessions_with_4plus_consec_errors = 0
retry_churn_events = 0
verified_sessions = set()
plan_mode_signals = 0
agent_task_dispatches = 0
sessions_with_compact = 0
session_lengths = []
read_grep_glob = 0
total_assistant_msgs = 0
stop_reasons = Counter()
stop_hook_summary_count = 0
tool_result_sizes = []
files_processed = 0
files_skipped = 0

# Per-session list
sessions_out = []

# Per-project rollup
project_cost = defaultdict(float)
project_session_count = defaultdict(int)

for jsonl_file in PROJECTS.rglob("*.jsonl"):
    try:
        mtime = jsonl_file.stat().st_mtime
        if mtime < CUTOFF:
            files_skipped += 1
            continue
    except OSError:
        continue

    files_processed += 1

    # Per-session accumulators
    s = {
        "session_id": jsonl_file.stem,
        "project_dir": str(jsonl_file.parent.name),  # encoded path like -Users-dannyhabetyes-dev-foo
        "msg_count": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "tokens_cache_r": 0,
        "tokens_cache_c": 0,
        "cost": 0.0,
        "models": Counter(),
        "primary_model": None,
        "flags": [],
        "cache_hit": 0.0,
        "lines": 0,
    }

    session_tool_uses = []
    session_tool_results = []
    session_compact_idx = None
    has_compact = False
    has_plan = False
    output_waste_count = 0
    retry_churn_count = 0
    is_first_assistant_after_user = False
    last_edit_idx = None

    try:
        with jsonl_file.open() as f:
            for idx, raw in enumerate(f):
                s["lines"] += 1
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue

                t = obj.get("type", "")
                msg = obj.get("message", {}) or {}
                ts = obj.get("timestamp", "")
                day = ts[:10] if ts else ""

                if day:
                    all_msgs_per_day[day] += 1

                if t == "system":
                    sub = msg.get("subtype") or obj.get("subtype")
                    if sub == "compact_boundary":
                        has_compact = True
                        session_compact_idx = idx
                    if sub == "stop_hook_summary":
                        stop_hook_summary_count += 1

                if t == "user":
                    total_msgs_by_role["user"] += 1
                    s["msg_count"] += 1
                    content = msg.get("content", []) if isinstance(msg, dict) else []
                    if isinstance(content, list):
                        for blk in content:
                            if not isinstance(blk, dict):
                                continue
                            if blk.get("type") == "tool_result":
                                is_err = bool(blk.get("is_error", False))
                                rcontent = blk.get("content", "")
                                if isinstance(rcontent, list):
                                    bsize = sum(len(json.dumps(x)) for x in rcontent)
                                else:
                                    bsize = len(str(rcontent))
                                tool_result_sizes.append(bsize)
                                session_tool_results.append((idx, is_err, bsize))

                if t == "assistant":
                    total_msgs_by_role["assistant"] += 1
                    s["msg_count"] += 1
                    total_assistant_msgs += 1
                    usage = msg.get("usage", {}) if isinstance(msg, dict) else {}
                    if isinstance(usage, dict):
                        u_in = int(usage.get("input_tokens") or 0)
                        u_out = int(usage.get("output_tokens") or 0)
                        u_cr = int(usage.get("cache_read_input_tokens") or 0)
                        u_cc = int(usage.get("cache_creation_input_tokens") or 0)
                        s["tokens_in"] += u_in
                        s["tokens_out"] += u_out
                        s["tokens_cache_r"] += u_cr
                        s["tokens_cache_c"] += u_cc
                        # Cost based on this turn's model
                        model = msg.get("model")
                        if model:
                            s["models"][model] += 1
                            all_models_seen[model] += 1
                            turn_cost = cost_for_tokens(
                                model, inp=u_in, out=u_out, cache_r=u_cr, cache_c=u_cc
                            )
                            s["cost"] += turn_cost
                            if day:
                                all_spend_per_day[day] += turn_cost
                                d_tk = all_tokens_per_day[day]
                                d_tk["in"] += u_in
                                d_tk["out"] += u_out
                                d_tk["cache_r"] += u_cr
                                d_tk["cache_c"] += u_cc

                    stop_reason = msg.get("stop_reason")
                    if stop_reason:
                        stop_reasons[stop_reason] += 1

                    # Tool uses inside content
                    content = msg.get("content", []) if isinstance(msg, dict) else []
                    if isinstance(content, list):
                        thinking_chars = 0
                        text_chars = 0
                        for blk in content:
                            if not isinstance(blk, dict):
                                continue
                            btype = blk.get("type", "")
                            if btype == "tool_use":
                                name = blk.get("name", "")
                                all_tool_uses[name] += 1
                                if name in ("Read", "Grep", "Glob"):
                                    read_grep_glob += 1
                                if name in ("Agent", "Task"):
                                    agent_task_dispatches += 1
                                if name == "Skill":
                                    inp_dict = blk.get("input", {}) or {}
                                    sk = inp_dict.get("skill") if isinstance(inp_dict, dict) else None
                                    if sk:
                                        all_custom_skill_uses[sk] += 1
                                if name in ("ExitPlanMode", "EnterPlanMode"):
                                    plan_mode_signals += 1
                                    has_plan = True
                                if name == "Bash" and last_edit_idx is not None:
                                    inp_dict = blk.get("input", {}) or {}
                                    cmd = inp_dict.get("command", "") if isinstance(inp_dict, dict) else ""
                                    if idx - last_edit_idx <= 5 and verifier_patterns.search(cmd):
                                        verified_sessions.add(s["session_id"])
                                if name in ("Edit", "Write"):
                                    last_edit_idx = idx
                                inp_str = json.dumps(blk.get("input", {}))
                                session_tool_uses.append((idx, name, inp_str))
                            elif btype == "thinking":
                                thinking_chars += len(blk.get("thinking", "") or "")
                            elif btype == "text":
                                text_chars += len(blk.get("text", "") or "")
                        if thinking_chars > 0:
                            tk_est = thinking_chars / 4
                            tokens_out = int((usage or {}).get("output_tokens") or 0) if isinstance(usage, dict) else 0
                            if tokens_out > 50 and tk_est > 4 * tokens_out:
                                big_thinking_events += 1
                        # output-waste heuristic on simple-tool turns
                        # (skipped for v2 simplicity; can add if needed)

    except Exception as e:
        continue

    # Session post-processing
    session_lengths.append(s["lines"])
    s["primary_model"] = s["models"].most_common(1)[0][0] if s["models"] else None
    s["models"] = dict(s["models"])
    cache_total = s["tokens_in"] + s["tokens_cache_r"] + s["tokens_cache_c"]
    s["cache_hit"] = (s["tokens_cache_r"] / cache_total) if cache_total > 0 else 0.0
    s["tokens_total"] = s["tokens_in"] + s["tokens_out"] + s["tokens_cache_r"] + s["tokens_cache_c"]

    # Flags
    consec_err = max_err_run = 0
    for _, is_err, _ in session_tool_results:
        if is_err:
            consec_err += 1
            max_err_run = max(max_err_run, consec_err)
        else:
            consec_err = 0
    if max_err_run >= 4:
        sessions_with_4plus_consec_errors += 1
        s["flags"].append("err·casc")

    # Retry-churn for this session
    sess_retry = 0
    for i, (idx_e, is_err, _) in enumerate(session_tool_results):
        if not is_err:
            continue
        # check next 6 tool_uses for same name+input
        for ti, (tu_idx, tu_name, tu_input) in enumerate(session_tool_uses):
            if tu_idx <= idx_e and tu_idx > idx_e - 4:
                for nj in range(ti + 1, min(ti + 7, len(session_tool_uses))):
                    nx_idx, nx_name, nx_input = session_tool_uses[nj]
                    if nx_idx - idx_e > 12:
                        break
                    if nx_name == tu_name and nx_input == tu_input:
                        sess_retry += 1
                        break
                break
    if sess_retry > 0:
        s["flags"].append(f"{sess_retry}× retry")
        retry_churn_events += sess_retry

    if has_compact:
        s["flags"].append("compact")
        sessions_with_compact += 1
    if has_plan:
        s["flags"].append("plan")

    if s["session_id"] in verified_sessions:
        # not a flag but record for global aggregate
        pass

    # Aggregates
    project_cost[s["project_dir"]] += s["cost"]
    project_session_count[s["project_dir"]] += 1
    total_tokens["in"] += s["tokens_in"]
    total_tokens["out"] += s["tokens_out"]
    total_tokens["cache_r"] += s["tokens_cache_r"]
    total_tokens["cache_c"] += s["tokens_cache_c"]
    total_cost += s["cost"]

    # Sessions per day (count session by ts of first message — skipping for now, use mtime day)
    session_day = time.strftime("%Y-%m-%d", time.localtime(jsonl_file.stat().st_mtime))
    all_sessions_per_day[session_day] += 1

    sessions_out.append(s)

# Global aggregates
cache_total_g = total_tokens["in"] + total_tokens["cache_r"] + total_tokens["cache_c"]
cache_hit_rate = (total_tokens["cache_r"] / cache_total_g) if cache_total_g > 0 else 0.0

# Tool error rate (across all assistant turns)
tool_error_count = sum(1 for sz in tool_result_sizes if False)  # we only stored is_err in session loop
# Re-walk tool_result_sizes — it doesn't have is_err. Compute differently: count is_err rows
# We need to recompute: tool errors across all sessions.
tool_total_count = len(tool_result_sizes)
# We didn't store is_err globally; estimate from session-level data isn't practical. Skip exact figure.
# Use stop_reasons["tool_use"] vs "end_turn" as a proxy denominator.
tool_use_share = (stop_reasons.get("tool_use", 0) / max(1, stop_reasons.get("tool_use", 0) + stop_reasons.get("end_turn", 0)))

# Tool result percentiles
def pctile(arr, p):
    if not arr: return 0
    arr = sorted(arr)
    return arr[min(int(len(arr)*p), len(arr)-1)]

# Cache savings estimate
# Cache reads cost 10% of input. So savings = cache_r tokens × (input_rate - cache_r_rate)
# Use a blended rate. Approximation: assume Sonnet rate.
cache_savings = total_tokens["cache_r"] * (PRICING["sonnet"]["in"] - PRICING["sonnet"]["cache_r"]) / 1_000_000

out = {
    "files_processed": files_processed,
    "files_skipped_outside_window": files_skipped,
    "session_count": len(sessions_out),
    "sessions_with_activity": sum(1 for s in sessions_out if s["msg_count"] > 0),
    "msgs_per_day": dict(all_msgs_per_day),
    "spend_per_day": dict(all_spend_per_day),
    "sessions_per_day": dict(all_sessions_per_day),
    "tokens_per_day": {d: dict(v) for d, v in all_tokens_per_day.items()},
    "models_seen": dict(all_models_seen),
    "primary_model_window": all_models_seen.most_common(1)[0][0] if all_models_seen else None,
    "tool_uses": dict(all_tool_uses.most_common(40)),
    "custom_skill_uses": dict(all_custom_skill_uses.most_common(40)),
    "total_assistant_msgs": total_assistant_msgs,
    "total_tokens": total_tokens,
    "total_cost": total_cost,
    "cache_hit_rate": cache_hit_rate,
    "cache_savings_estimate_usd": cache_savings,
    "agent_task_dispatches": agent_task_dispatches,
    "plan_mode_signals": plan_mode_signals,
    "stop_reasons": dict(stop_reasons),
    "stop_hook_summary_count": stop_hook_summary_count,
    "tool_result_median_bytes": pctile(tool_result_sizes, 0.5),
    "tool_result_p95_bytes": pctile(tool_result_sizes, 0.95),
    "median_session_lines": sorted(session_lengths)[len(session_lengths)//2] if session_lengths else 0,
    "max_session_lines": max(session_lengths) if session_lengths else 0,
    "sessions_with_long_lines_gt_1500": sum(1 for n in session_lengths if n > 1500),
    "sessions_with_compact": sessions_with_compact,
    "sessions_with_4plus_consecutive_errors": sessions_with_4plus_consec_errors,
    "retry_churn_events": retry_churn_events,
    "big_thinking_events": big_thinking_events,
    "verified_sessions_count": len(verified_sessions),
    "read_grep_glob": read_grep_glob,
    "jit_context_ratio": (read_grep_glob / total_assistant_msgs) if total_assistant_msgs > 0 else 0,
    "tool_use_share_of_stops": tool_use_share,
    "project_cost": dict(project_cost),
    "project_session_count": dict(project_session_count),
    "sessions": sessions_out,
}

with open(OUTPUT_PATH, "w") as f:
    json.dump(out, f, default=str)
print(f"WROTE {OUTPUT_PATH} (sessions={len(sessions_out)}, total_cost=${total_cost:,.2f}, cache_hit={cache_hit_rate*100:.2f}%)")
