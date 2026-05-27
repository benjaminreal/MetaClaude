# nate-update

> Bring the Nate B. Jones knowledge base up to date in a single orchestrated run.

## Why this skill?

The Nate archive pipeline spans 6+ scripts, Chrome MCP browser automation, YouTube transcript downloads, and Open Brain ingest. Without structured orchestration, updates are error-prone and non-resumable — an interrupted run means manual rescue and guessing where things left off.

**nate-update** codifies the full pipeline into 7 resumable stages with a state file. If Chrome disconnects, context exhausts, or you need to stop, the skill picks up exactly where it left off next time.

**Version:** 1.0.0

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/nate-update ~/.claude/skills/nate-update

# Project-scoped (available only in this project)
cp -r skills/nate-update .claude/skills/nate-update
```

**Cowork:** Import the `.skill` file from the [GitHub Releases](https://github.com/benjaminreal/MetaClaude/releases) page.

> If this is the first skill you install and `~/.claude/skills/` didn't exist before, restart Claude Code so it picks up the new directory.

---

## How to Use

Say any of these when you want to update the archive:

> `nate update` · `update nate` · `sync nate` · `nate sync` · `update nate archive` · `sync nate content` · `nate archive update`

The skill runs pre-flight checks, detects new Substack posts, and walks through the pipeline with your confirmation at key points.

### What it does

1. **Detects new posts** since the last update via the Substack API
2. **Downloads articles** via Chrome MCP (Gmail MCP as backup)
3. **Downloads transcripts** — all as backups, founding-tier Executive Briefings for Open Brain ingest
4. **Downloads prompt kits** from `promptkit.natebjones.com`
5. **Ingests + tags** new content into Open Brain (`nate_content` table)
6. **Regenerates indexes** and presents a summary

### Resumability

Every stage writes progress to `nate_update_state.json`. If interrupted:

- Re-invoke the skill
- It finds the state file and offers to resume or start fresh
- Resume skips completed stages and already-processed slugs

### What it won't do

- Backfill historical content outside the detected delta window
- Modify the `nate_content` schema or `.env` configuration
- Rewrite existing scripts — it orchestrates them as-is
- Download templates from Notion, GDocs, GSheets, Drive, or Guides (deferred to v2)

---

## Requirements

- **Chrome MCP** — connected browser with Claude extension (required for article and prompt kit downloads)
- **Environment variables** — `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY` (verified via `scripts/check_env.py`)
- **Gmail MCP** — optional backup source for article downloads
- **`youtube-transcript-api`** — optional, for transcript downloads (`pip install youtube-transcript-api`)

---

## How It Works (Under the Hood)

The skill follows a 10-part internal structure with 7 pipeline stages.

### 1. Purpose & Scope
Defines what the pipeline does and doesn't do. v1 covers articles, transcripts, and prompt kits. Notion/GDocs/Guides deferred to v2.

### 2. Pre-flight Checklist
Verifies workspace, environment, Chrome MCP, baseline counts, date range, and state file. Issues Dropbox sync warning before file writes.

### 3. Core Workflow (7 stages)

| Stage | What happens |
|---|---|
| 1. Pre-flight | Execute checklist, write initial state file |
| 2. Catalog + delta | Paginate Substack API, detect new posts, present delta table |
| 3. Download articles | Chrome MCP primary, Gmail backup, canonical markdown format |
| 4. Download transcripts | YouTube transcripts; founding-tier for ingest, others as backups |
| 5. Download prompt kits | Prompt kit pages via Chrome MCP |
| 6. Ingest + tag | `--changed-only` ingest, Haiku tagging, re-ingest with tags |
| 7. Verify + indexes | Sanity check, regenerate indexes, present summary |

### 4. State Management
JSON state file enables resume after interruption. Handles Dropbox corruption and schema version mismatches.

### 5. Chrome MCP Health Strategy
Check at stage start, re-check on failure, Gmail fallback for Stage 3.

### 6. Decision Rules
Handles skips, empty deltas, unexpected audience values, YouTube failures, cost limits, and mid-session status checks.

### 7. Harness Adaptations
Chrome MCP and Bash required. Gmail MCP, `youtube-transcript-api`, and `build_inventory.py` optional with graceful degradation.

### 8. Script Reference
Documents the 7 existing scripts the skill orchestrates.

### 9. Eval Criteria
Pipeline correctness (every slug processed or logged), safety (file boundaries, Dropbox warning, cost cap), output quality (canonical formats, accurate counts).

### 10. Version & Changelog

**v1.0.0** — 2026-05-25
- Initial release. 7-stage resumable pipeline with state file.
- Chrome MCP primary, Gmail MCP backup for article downloads.
- Prompt kits from `promptkit.natebjones.com` only (v1).
- Founding-tier transcripts ingested; others downloaded as backups.
- Design source: Session #21 audit report.

---

_Part of [MetaClaude](https://github.com/benjaminreal/MetaClaude) — a personal skills workspace._

_Uses [Open Brain](https://github.com/NatheBJ/open-brain) by Nathe B. Jones for knowledge base storage._
