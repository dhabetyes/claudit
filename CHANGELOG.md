# Changelog

All notable changes to claudit will be documented here. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-05-08

### Changed
- Report is now a 7-tab analytics dashboard (Overview, Quick wins, Medium, Deep work, Sessions, Trends, Setup) instead of a single page. CSS-only tab navigation via `:target`; one inline script for sortable session columns. The visual design is locked in `${CLAUDE_PLUGIN_ROOT}/assets/templates/report.html` so every audit produces an identical-looking report — no more run-to-run design variance.
- Step 5 of `audit-harness` SKILL.md is now a five-substep flow that calls bundled scripts: `aggregate-transcripts.py` → write small `judgment.json` → `build-audit-data.py` → `render-report.py` → open. The agent's contract shrinks from a 60-key data dict to a small judgment file (band placement, fired findings with effort tiers, takeaway prose, inventory facts).
- Telemetry token is shared across v0.2.0 and v0.3.0 so `/events` posts keep validating across the upgrade. Per-version tokens return when the design stabilizes.

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
