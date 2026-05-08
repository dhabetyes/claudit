# claudit

Senior-engineer-grade audits for Claude Code users. Free; telemetry-funded.

## Status

**v0.1.0 — Scaffold.** Plugin monorepo and marketplace manifest are in place. The audit pipeline, finding catalog detectors, report renderer, and telemetry client are not yet implemented. See [CHANGELOG.md](./CHANGELOG.md).

## What it is

claudit reads your Claude Code setup — settings, skills, agents, plugins, hooks, MCP servers, and recent session transcripts (with your consent) — and produces an HTML report with:

- A capability band placement: **Explorer / Builder / Operator / Architect**
- 3–5 personalized "quests" — the highest-leverage changes to make next
- A full deterministic findings list, grouped and collapsible
- Tier-aware language (no jargon for beginners; no condescension for power users)

A second skill, `audit-repo`, will audit your codebase in a future release.

## Install

claudit is a third-party Claude Code plugin shipped from this repo's marketplace manifest. **Install is two slash commands run inside an active Claude Code session** (not shell commands):

```
/plugin marketplace add dhabetyes/claudit
/plugin install claudit@claudit
```

Then run:

```
/claudit:audit-harness
```

## Why third-party?

claudit ships outside the official Anthropic marketplace by choice. We retain full control over distribution and release cadence; the trade-off is one extra slash command at install time. The plugin runs on your existing Node (Claude Code itself is Node) — no separate runtime, package manager, or daemon.

## Telemetry

claudit is free. Telemetry is the business model.

Every audit run posts a UUID-tagged event to a collector we operate, containing:

- Finding types, severity, scores
- Capability band, progression %, quest selections
- Catalog version, audit metadata, approximate token cost

What is **never sent**: raw transcripts, source files, prompts, code, `.env` contents, or anything matching common secret patterns. Email is sent only if you submit the report's contact form (and is sent directly from your browser to the collector — the plugin never sees it as part of the audit pipeline).

The full telemetry contract is shown on first run, before the first audit, alongside an estimated token cost. Opt-out is one flag, persistent across runs.

## Layout

```
.claude-plugin/marketplace.json     — third-party marketplace manifest
plugins/claudit/                    — the claudit plugin
  .claude-plugin/plugin.json        — plugin manifest (name, version)
  skills/audit-harness/SKILL.md     — v1 skill: harness audit
  assets/catalog/v1.0.0.yaml        — bundled fallback finding catalog
```

## License

MIT. See [LICENSE](./LICENSE).
