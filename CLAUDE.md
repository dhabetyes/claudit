# claudit — Project Context

This is the public plugin monorepo for **claudit** — a free, telemetry-funded Claude Code audit product.

## Layout

```
.claude-plugin/marketplace.json     — third-party marketplace manifest
plugins/claudit/                    — the claudit plugin
  .claude-plugin/plugin.json        — plugin manifest (name, version)
  skills/audit-harness/SKILL.md     — v1 skill: harness audit
  assets/catalog/v1.0.0.yaml        — bundled fallback finding catalog
                                    — strategy briefs + TODOS live in the
                                      sibling private repo dhabetyes/claudit-catalog,
                                      not here. See sibling-repo note below.
```

## Conventions

- **Plugin version** lives in `plugins/claudit/.claude-plugin/plugin.json` and **must always be set explicitly**. Claude Code does not expose `CLAUDE_PLUGIN_VERSION` as an env var — the telemetry client reads version from this file at runtime via `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`. Bumping `version` here is the canonical release step (see V14 in `docs/private/TODOS.md`).
- **Public-facing copy** (README, marketplace listing, blog posts) uses the slash-command install syntax: `/plugin marketplace add` and `/plugin install`. Never the older `claude marketplace add` shell-style syntax (that was an early-research placeholder; verified-correct syntax was locked 2026-05-07).
- **Upgrading an installed plugin** — `/plugin update claudit` alone does NOT pull a new version. The local marketplace cache must be refreshed first, and the update command needs the fully qualified `<plugin>@<marketplace>` name. Canonical upgrade flow (verified 2026-05-07):
  1. `/plugin marketplace update claudit` (or `claude plugin marketplace update claudit` from shell) — refreshes the cached `marketplace.json` from GitHub
  2. `/plugin update claudit@claudit` (or `claude plugin update claudit@claudit` from shell) — actually pulls the new version
  3. **Restart Claude Code** — `/reload-plugins` is not sufficient for upgrades; the CLI prints "Restart to apply changes" and means it
  
  This is also what the public README install instructions assume for first-time installs (`/plugin marketplace add` is implicitly a fresh fetch). Document the upgrade flow separately when we publish.
- **Skills are namespaced.** The `audit-harness` skill is invoked as `/claudit:audit-harness`. The future repo audit skill will be `/claudit:audit-repo`.
- **Installed plugin lags source.** When running `/claudit:*` from inside this repo, the slash command invokes the installed cache at `~/.claude/plugins/cache/claudit/claudit/<version>/` — which may be older than `plugins/claudit/` in this repo. Before executing, diff the cached SKILL.md against the source SKILL.md. If source is newer, prefer running the source pipeline scripts directly (e.g. `python3 plugins/claudit/scripts/aggregate-transcripts.py`) over the installed skill. This is the canonical pattern for audit runs done from this repo before a plugin version bump.
- **Briefs, TODOS, and the knowledge corpus live in the sibling private repo `dhabetyes/claudit-catalog`** at `~/dev/claudit-catalog/`. That repo is the single source of truth for the harvester pipeline, the harvested corpus, the capability catalog YAMLs (from v1.1+), and the strategic briefs. The previous `docs/private/` location in this repo is retired (2026-05-11). Never recreate `docs/private/` here — the public claudit repo stays focused on plugin distribution only.
- **Catalog source-of-truth** is currently the bundled copy at `plugins/claudit/assets/catalog/v1.0.0.yaml`. From v1.1+ the source-of-truth moves to a separate `claudit-catalog` repo with the synthesis pipeline (see `docs/private/briefs/synthesis-pipeline-spec.md`); the plugin keeps a bundled fallback and fetches latest from CDN at runtime.

## Telemetry

Every audit run posts to the collector service at **`https://claudit.acumen-iq.com`** (separate private repo `dhabetyes/claudit-collector`, deployed to Fly.io + Neon Postgres). The plugin reads `~/.claude/claudit/id.txt` for the user UUID; bearer-token auth uses a per-plugin-version shared token shipped with the plugin release. Form-POST email capture from the HTML report goes directly to the collector's `/lead` endpoint (browsers send `Origin: null` from `file://`; that's expected, not abuse).

**Collector endpoints (live):**
- `POST https://claudit.acumen-iq.com/events` — bearer auth, body's `plugin_version` must match the version associated with the auth token
- `POST https://claudit.acumen-iq.com/lead` — form-POST or JSON, no auth
- `DELETE https://claudit.acumen-iq.com/uuid/<uuid>` — knowledge-of-uuid is the proof
- `GET https://claudit.acumen-iq.com/healthz` — DB ping

## Out of scope (do NOT add without discussion)

- Authentication systems beyond UUID + per-version bearer token
- A web dashboard, hosted UI, or cloud-side rendering
- Live audits during an active Claude Code session
- Multi-user / team accounts
- Paid tiers
- The cross-product link between harness and repo audits
