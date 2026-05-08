# claudit

A senior-engineer-grade audit for your Claude Code setup. Free.

`/claudit:audit-harness` reads your harness — settings, skills, agents, hooks, plugins, and recent session transcripts — and writes you an HTML report telling you exactly what to change to get more out of Claude Code.

## Why run it

Most Claude Code users are leaving 30–80% of the product on the floor. Not because they're doing anything wrong — because the failure modes are invisible. Your prompt cache is quietly missing. Your CLAUDE.md is quietly bloated. You're quietly running Opus on tasks Sonnet would crush at 1/5 the cost. You'd never know unless someone pulled the receipts.

claudit pulls the receipts.

### What you actually get

**A capability score that ranks you against what good looks like.** You're placed on a four-band curve — **Explorer → Builder → Operator → Architect** — grounded in published Anthropic guidance, the engineers who built Claude Code (Boris Cherny), and people who use it at scale (Karpathy). It's an absolute standard, not a curve graded against other users. You see your band, your progression % to the next one, and exactly which capabilities are blocking you.

**3–5 personalized quests, ranked by leverage.** Not a 50-item checklist. The smallest set of changes that will move you the furthest, with copy-pasteable fixes. Each quest tells you the why, the fix, and the projected progression impact.

**A full deterministic findings list.** Every detector run, every measurement taken, grouped by category. Tier-aware language — no jargon for beginners, no condescension for power users.

### The wins compound on every session

Every finding maps to a specific lever you can pull. A few of the big ones:

- **Cache hit rate.** Cache reads cost 1/10 what fresh tokens cost. We measure your actual hit rate from your transcripts and tell you what's killing it (usually: a CLAUDE.md that keeps changing). Get from 25% to 70% and ~63% of your input bill disappears.
- **Model routing.** Sonnet trails Opus by ~1.2 points on SWE-bench Verified for one-fifth the cost. If you're 100% Opus, you're paying 5× for ~1.5 points. We catch it.
- **CLAUDE.md size and stability.** Karpathy's CLAUDE.md is ~65 lines. If yours is 400, the model is ignoring half of it AND you're paying tokens on every session AND you're invalidating your own cache every time you edit it. We measure all three.
- **Plan mode adoption.** Per the engineer who built Claude Code, plan mode produces 2–3× success rates on complex tasks. We check whether you're using it and on what.
- **Subagent dispatch as a reflex.** Anthropic's own docs call subagents "one of the most powerful tools available" for keeping main context clean. We count yours and tell you what you're missing.
- **Verification scaffolding.** The single highest-leverage practice in Anthropic's own best-practices guide: run tests/lint/typecheck after Claude makes changes. We detect whether you actually do — via hook or by hand.
- **Tool result bloat, retry churn, error cascades, wasteful thinking.** Every primary failure mode in the published context-engineering literature, measured against your real sessions.

### What it costs you

A few minutes of your Claude session, and the price of those tokens. That's it. The audit runs locally inside Claude Code; the report is a single HTML file written to your current directory. No account, no signup, no install of anything outside the plugin itself.

## Install

claudit is a third-party Claude Code plugin shipped from this repo's marketplace manifest. Install is two slash commands run inside an active Claude Code session (not shell commands):

```
/plugin marketplace add dhabetyes/claudit
/plugin install claudit@claudit
```

Then run:

```
/claudit:audit-harness
```

The report opens automatically when it's done.

## What's coming

A second skill, `/claudit:audit-repo`, will audit your codebase the same way the harness audit audits your Claude Code setup — same opinionated, citation-grounded approach, applied to the project you're working on.

## Why third-party?

claudit ships outside the official Anthropic marketplace by choice. We retain full control over distribution and release cadence; the trade-off is one extra slash command at install time. The plugin runs on your existing Node (Claude Code itself is Node) — no separate runtime, package manager, or daemon.

## Layout

```
.claude-plugin/marketplace.json     — third-party marketplace manifest
plugins/claudit/                    — the claudit plugin
  .claude-plugin/plugin.json        — plugin manifest (name, version)
  skills/audit-harness/SKILL.md     — v1 skill: harness audit
  assets/catalog/v1.0.0.yaml        — bundled finding catalog
```

## License

MIT. See [LICENSE](./LICENSE).
