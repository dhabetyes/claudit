---
name: audit-harness
description: Audit the user's Claude Code harness — settings, skills, agents, hooks, MCP servers, plugins, and recent session transcripts. Produces an HTML report with capability band placement (Explorer / Builder / Operator / Architect), personalized quests, and a deterministic findings list. Use when the user asks to "audit my Claude Code setup", "claudit audit", "audit harness", "check my Claude Code", "see what I'm missing", or runs the slash command directly.
---

# Audit Harness — v0.1.0 (scaffold)

This skill is currently a scaffold. The audit pipeline, finding catalog, report renderer, and telemetry client are not yet implemented.

## Intended behavior (v1)

When invoked, the skill should:

1. **Consent UX (first run only).** Show a plain-English summary of what gets read, what gets sent to the collector, and what is never sent. Display an estimated token cost based on transcript size. Persist consent at `~/.claude/claudit/consent.json`. Allow opt-out of the open-ended LLM transcript pass while still running the deterministic-only audit.
2. **Read configuration.** Enumerate `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/skills/`, `~/.claude/agents/`, `~/.claude/plugins/`, and any hooks. Compute the static-detectable surface.
3. **Read transcripts.** With consent, read recent session transcripts from `~/.claude/projects/*/`. Extract behavior signals (cache hit rate, compaction frequency, hook ordering, model routing, agent usage patterns).
4. **Run the deterministic finding catalog.** Load the bundled fallback catalog at `${CLAUDE_PLUGIN_ROOT}/assets/catalog/v1.0.0.yaml` (or fetch the latest from the CDN). Match each finding's detector against the user's data.
5. **Place the user on the capability band** (Explorer / Builder / Operator / Architect) using the deterministic scoring formula. Compute progression to the next band.
6. **Pick 3–5 quests** via the quest selector subagent. Each quest gets an estimated progression-bar impact.
7. **Render the HTML report** at `./.claudit-report.html` with strict CSP, escape-by-default templating, and the email-capture form pointing at the collector's `/lead` endpoint. Open in the user's default browser.
8. **Post telemetry.** Send a UUID-tagged event to the collector (unless opted out). Read the UUID from `~/.claude/claudit/id.txt`, generate it on first run if absent. Read the plugin version from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` for per-version write-auth.

## Out of scope for v1

- The repo audit (`audit-repo`) — ships in v2 as a second skill in this same plugin.
- A web dashboard, hosted UI, or cloud-side rendering.
- Live audits during an active Claude Code session.

## Implementation status

Nothing functional yet. The plugin manifest, marketplace manifest, and bundled catalog are in place; the skill body needs the full audit pipeline.
