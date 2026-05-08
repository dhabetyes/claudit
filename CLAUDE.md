# claudit — Project Context

This is the public plugin monorepo for **claudit** — a free, telemetry-funded Claude Code audit product.

## Layout

```
.claude-plugin/marketplace.json     — third-party marketplace manifest
plugins/claudit/                    — the claudit plugin
  .claude-plugin/plugin.json        — plugin manifest (name, version)
  skills/audit-harness/SKILL.md     — v1 skill: harness audit
  assets/catalog/v1.0.0.yaml        — bundled fallback finding catalog
docs/private/                       — gitignored design docs (briefs, TODOs)
  briefs/                           — full product/strategy specs
  TODOS.md                          — open items, decisions, codex findings
```

## Conventions

- **Plugin version** lives in `plugins/claudit/.claude-plugin/plugin.json` and **must always be set explicitly**. Claude Code does not expose `CLAUDE_PLUGIN_VERSION` as an env var — the telemetry client reads version from this file at runtime via `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`. Bumping `version` here is the canonical release step (see V14 in `docs/private/TODOS.md`).
- **Public-facing copy** (README, marketplace listing, blog posts) uses the slash-command install syntax: `/plugin marketplace add` and `/plugin install`. Never the older `claude marketplace add` shell-style syntax (that was an early-research placeholder; verified-correct syntax was locked 2026-05-07).
- **Skills are namespaced.** The `audit-harness` skill is invoked as `/claudit:audit-harness`. The future repo audit skill will be `/claudit:audit-repo`.
- **Briefs and strategy live in `docs/private/`** (gitignored). They are not part of the public plugin distribution. Anything moved out of `docs/private/` becomes public — be deliberate.
- **Catalog source-of-truth** is currently the bundled copy at `plugins/claudit/assets/catalog/v1.0.0.yaml`. From v1.1+ the source-of-truth moves to a separate `claudit-catalog` repo with the synthesis pipeline (see `docs/private/briefs/synthesis-pipeline-spec.md`); the plugin keeps a bundled fallback and fetches latest from CDN at runtime.

## Telemetry

Every audit run posts to a separate collector service (its own repo, deployed to Fly.io with managed Postgres). The plugin reads `~/.claude/claudit/id.txt` for the user UUID; bearer-token auth uses a per-plugin-version shared token shipped with the plugin release. Form-POST email capture from the HTML report goes directly to the collector's `/lead` endpoint (browsers send `Origin: null` from `file://`; that's expected, not abuse).

## Out of scope (do NOT add without discussion)

- Authentication systems beyond UUID + per-version bearer token
- A web dashboard, hosted UI, or cloud-side rendering
- Live audits during an active Claude Code session
- Multi-user / team accounts
- Paid tiers
- The cross-product link between harness and repo audits
