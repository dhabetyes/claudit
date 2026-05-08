# Changelog

All notable changes to claudit will be documented here. This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
