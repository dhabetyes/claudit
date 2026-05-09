# Changelog

All notable changes to claudit will be documented here. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-05-08

### Added
- **Per-session telemetry** (`payload.sessions[]`): one row per session in the 30-day audit window. Each row carries day, msg count, primary model, cache hit, cost (USD), token breakdown, behavior flags, max consecutive errors, and a project hash. Lands in the new `audit_sessions` collector table.
- **Per-day telemetry** (`payload.daily[]`): rollups of sessions, cost, and tokens per day with activity. Lands in the new `audit_daily` collector table.
- `plugins/claudit/scripts/scrub-payload.py` — bundled scrubber that runs between payload construction and POST. Replaces `project_dir` with `project_hash` (SHA256 of normalized basename, first 12 hex chars) and strips any leaked absolute paths from inventory fields.

### Changed
- `audit-harness` SKILL.md Step 6 grew two new substeps: build the unscrubbed payload (now including `sessions[]` + `daily[]`), then run the bundled scrubber, then post. Added an explicit grep guard that fails the audit if `/Users/`, `/home/`, or `/root` paths leaked through scrubbing.
- Plugin v0.4.0 ships its own bearer token; the collector's `PLUGIN_TOKENS` env var registers it alongside v0.2.0 and v0.3.0 for parallel-rollout compatibility.

### Why
- The previous payload sent only 30-day aggregates. That blocked us from giving the kind of feedback our actual audience needs — non-developer builders using Claude Code as their dev environment, who learn from concrete examples (\"look at this $1,430 session from April 22\") rather than abstract metrics. Per-session and per-day data is the substrate for cohort comparisons (\"users at your spend tier usually X\"), trend findings (\"your retry-churn doubled this week\"), and project-grouped patterns. None of those are possible from aggregates.
- The path-scrubbing rule fixes a real PII leak: pre-v0.4.0 payloads sent absolute filesystem paths like `/Users/<username>/Claude-Projects/<project>` in the project rollups. From v0.4.0 onward only the basename hash crosses the wire; the human-readable name stays in the local-only HTML report.

### Schema (collector)
- New tables `audit_sessions` and `audit_daily`, both keyed by `event_id` with `ON DELETE CASCADE`. UUID denormalized into both tables so cohort queries skip the join. Indexes on `(uuid, day)` for trend queries and `project_hash` for project rollups.

## [0.3.0] — 2026-05-08

### Changed
- Report is now a 7-tab analytics dashboard (Overview, Quick wins, Medium, Deep work, Sessions, Trends, Setup) instead of a single page. CSS-only tab navigation via `:target`; one inline script for sortable session columns. The visual design is locked in `${CLAUDE_PLUGIN_ROOT}/assets/templates/report.html` so every audit produces an identical-looking report — no more run-to-run design variance.
- Step 5 of `audit-harness` SKILL.md is now a five-substep flow that calls bundled scripts: `aggregate-transcripts.py` → write small `judgment.json` → `build-audit-data.py` → `render-report.py` → open. The agent's contract shrinks from a 60-key data dict to a small judgment file (band placement, fired findings with effort tiers, takeaway prose, inventory facts).
- v0.3.0 ships its own bearer token (per-version, as designed). The collector's `PLUGIN_TOKENS` env var has been updated to recognize it — v0.2.0 and v0.3.0 are valid in parallel during the rollout.
- Telemetry failure is now treated as a **fatal audit failure**, not a swallowed warning. A non-2xx response from `/events` causes Step 5 to stop and surface the HTTP code + response body + version/token used. Rationale: telemetry is the value model funding claudit being free, so silent telemetry breaks degrade into "audits stop flowing in" without anyone noticing.

### Added
- `plugins/claudit/scripts/aggregate-transcripts.py` — pure mechanical aggregation of `~/.claude/projects/**/*.jsonl` (last 30 days). Emits per-session rows with computed cost (per-model pricing for Opus / Sonnet / Haiku tiers), flags (`compact`, `plan`, `Nx retry`, `err·casc`), per-day rollups, project rollups, tool-use counts.
- `plugins/claudit/scripts/build-audit-data.py` — combines aggregator output + agent judgment into the full render dict. Owns: per-session grading (A/B/C/D), currency/token formatting, drilldown HTML for select findings, KPI strip composition, daily-chart series alignment.
- `plugins/claudit/scripts/render-report.py` — template engine with paired `<!-- CLAUDIT:NAME -->` markers and procedural generators for the SVG charts (spend bars, run history line, daily token volume, daily sessions, daily cache-hit rate).
- `plugins/claudit/assets/templates/report.html` — 47 KB templatized design (20 marker types). Same CSP as the reference, including Google Fonts (Fraunces / Inter Tight / JetBrains Mono).

## [0.2.0] — 2026-05-07

### Changed
- `audit-harness` SKILL.md is now an executable runbook, not a placeholder. Running `/claudit:audit-harness` now actually performs the audit: reads config + plugins + agents + skills + hooks + recent transcripts, evaluates the bundled finding catalog, places the user on a capability band, picks 3–5 quests, renders an HTML report at `./.claudit-report.html`, opens it, and posts a full data dump to `https://claudit.acumen-iq.com/events`.

## [0.1.0] — 2026-05-07

Pre-release scaffold. No functional audit yet.

### Added
- Monorepo structure: `.claude-plugin/marketplace.json` + `plugins/claudit/.claude-plugin/plugin.json`.
- Placeholder `audit-harness` skill at `plugins/claudit/skills/audit-harness/SKILL.md`. Slash command: `/claudit:audit-harness`.
- Bundled fallback finding catalog at `plugins/claudit/assets/catalog/v1.0.0.yaml`.
- README, LICENSE (MIT), CHANGELOG, project-level CLAUDE.md.
