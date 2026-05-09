#!/usr/bin/env python3
"""Scrub PII from a claudit telemetry payload before POST.

Usage:
    scrub-payload.py <input.json> <output.json>

What gets scrubbed:

1. **Project path keys** in `payload.inventory.transcripts_30d_project_cost`
   and `payload.inventory.transcripts_30d_project_session_count` are
   replaced with stable hashes derived from the project's basename.

2. **`project_dir` fields** inside `payload.sessions[]` rows are replaced
   with `project_hash` keys (same hash function).

3. **Absolute path prefixes** (`/Users/...`, `/home/...`, `/root/...`) are
   stripped from any string-valued field in `payload.inventory`,
   replaced with `<scrubbed>`.

4. **`payload.inventory.files_read`** if present — list of paths the agent
   read during inventory — replaced with the count only.

What is NOT scrubbed:

- The user's UUID at top level (it's the user's chosen anonymous identifier).
- Token counts, costs, timestamps, model names, finding IDs, band placement.
- The `display_name` map, IF the agent sends one — but they shouldn't;
  the convention is display names stay local and only hashes cross the wire.

Hash function:
    SHA256(normalized_basename).hexdigest()[:12]
where normalized = lowercase + [a-z0-9-] only.

Same project name across users → same hash. That's intentional — it
unlocks cross-user cohort analysis ("users with a `web-app` project
tend to..."). It does mean common project names are rainbow-table-able,
but that's an acceptable trade for the upside; the absolute path is
what we actually need to keep off the wire.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ABS_PATH_RE = re.compile(r"(/Users/[^/\s]+|/home/[^/\s]+|/root)(/[\w./-]*)?")


def project_hash(encoded_path: str) -> str:
    """Encoded paths look like '-Users-dannyhabetyes-dev-foo' (Claude Code's
    internal encoding) — basename is the last segment after the final dash."""
    if not encoded_path:
        return ""
    parts = encoded_path.lstrip("-").split("-")
    basename = parts[-1] if parts else encoded_path
    normalized = re.sub(r"[^a-z0-9-]", "", basename.lower())
    if not normalized:
        return "_unhashable"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def scrub_string(s: str) -> str:
    """Strip absolute path prefixes from a free-form string."""
    if not isinstance(s, str):
        return s
    return ABS_PATH_RE.sub("<scrubbed>", s)


def scrub_dict_keys_to_hash(d: dict | None) -> dict:
    """Replace project-path keys with their hash; sum collisions."""
    if not d:
        return {}
    out: dict[str, float] = {}
    for k, v in d.items():
        h = project_hash(k)
        out[h] = out.get(h, 0) + (v if isinstance(v, (int, float)) else 0)
    return out


def scrub_payload(payload: dict) -> dict:
    """Top-level scrub. Mutates a deep copy of the payload."""
    p = json.loads(json.dumps(payload))  # deep copy

    # 1. Inventory path-keyed dicts → hash-keyed
    inv = p.get("inventory", {}) or {}
    if "transcripts_30d_project_cost" in inv:
        inv["transcripts_30d_project_cost"] = scrub_dict_keys_to_hash(
            inv["transcripts_30d_project_cost"]
        )
    if "transcripts_30d_project_session_count" in inv:
        inv["transcripts_30d_project_session_count"] = scrub_dict_keys_to_hash(
            inv["transcripts_30d_project_session_count"]
        )

    # 2. inventory.files_read → count only
    if "files_read" in inv:
        files = inv.pop("files_read", [])
        inv["files_read_count"] = len(files) if isinstance(files, list) else 0

    # 3. Free-form strings inside inventory get path-stripped (defensive — catches
    #    things like file_path references the agent may have included).
    for k, v in list(inv.items()):
        if isinstance(v, str):
            inv[k] = scrub_string(v)

    p["inventory"] = inv

    # 4. sessions[] rows: replace project_dir with project_hash
    if "sessions" in p and isinstance(p["sessions"], list):
        scrubbed_sessions = []
        for s in p["sessions"]:
            if not isinstance(s, dict):
                continue
            s_out = dict(s)  # shallow copy
            if "project_dir" in s_out:
                s_out["project_hash"] = project_hash(s_out.pop("project_dir"))
            scrubbed_sessions.append(s_out)
        p["sessions"] = scrubbed_sessions

    return p


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(f"usage: {argv[0]} <input.json> <output.json>\n")
        return 2

    in_path = Path(argv[1])
    out_path = Path(argv[2])

    if not in_path.exists():
        sys.stderr.write(f"input not found: {in_path}\n")
        return 1

    raw = json.loads(in_path.read_text())

    # The wire envelope is `{uuid, event_type, plugin_version, catalog_version, payload}`.
    # We only mutate the inner `payload` dict.
    if "payload" in raw and isinstance(raw["payload"], dict):
        raw["payload"] = scrub_payload(raw["payload"])
    else:
        # Permissive: maybe caller passed the inner payload directly.
        raw = scrub_payload(raw)

    out_path.write_text(json.dumps(raw, indent=2))
    print(f"WROTE {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
