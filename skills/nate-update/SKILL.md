---
name: nate-update
description: "Update the Nate B. Jones knowledge base — download new articles, transcripts, and prompt kits from Substack; ingest into Open Brain. MUST trigger on: 'update nate archive', 'nate update', 'sync nate content', 'update nate', 'nate archive update', 'sync nate', 'nate sync'. Do NOT trigger on general Open Brain, Supabase, or Nate content search questions."
version: 1.0.0
---

# nate-update

Update the Nate B. Jones knowledge base: detect new Substack content, download articles + transcripts + prompt kits, ingest into Open Brain's `nate_content` table, and regenerate indexes.

---

## 1. Purpose & Scope

**Purpose:** Bring the Nate B. Jones archive up to date in a single orchestrated run. The pipeline has 7 resumable stages, each writing progress to a state file so interrupted runs can continue where they left off.

**Why a skill?** The archive update pipeline involves 6+ scripts, Chrome MCP browser automation, YouTube transcript downloads, and Open Brain ingest. Without structured orchestration, updates are error-prone and non-resumable — Session #20 demonstrated this when an autonomous agent terminated mid-pipeline, forcing a manual rescue. This skill codifies the pipeline, adds state management, and handles the failure modes discovered in Sessions #20-21.

**Does:**
- Detect new Substack posts since the last update (forward delta)
- Download articles via Chrome MCP (Gmail MCP as backup)
- Download YouTube transcripts for all articles, but only ingest founding-tier Executive Briefings
- Download prompt kits from `promptkit.natebjones.com`
- Ingest new/changed content into Open Brain (`nate_content` table) using `--changed-only`
- Tag new articles via Haiku
- Regenerate all archive indexes

**Does NOT:**
- Backfill historical content outside the detected delta window
- Modify the `nate_content` schema or `.env` configuration
- Rewrite existing scripts — it orchestrates them as-is
- Download templates from Notion, GDocs, GSheets, Drive, or Guides (deferred to v2)
- Quality-test transcripts vs. articles

---

## 2. Pre-flight Checklist

Before any pipeline work, confirm:

1. **Workspace root.** Project root contains `scripts/ingest_nate_content.py` and `Context/NateBJones/`. If invoked from a subdir, walk up.

2. **Environment.** Run `python3 scripts/check_env.py`. Required keys: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`. If any missing, stop and tell the user.

3. **Chrome MCP.** Call `mcp__Claude_in_Chrome__list_connected_browsers`. If no browser connected, tell the user: *"Chrome MCP is not connected. Please open your browser with the Claude extension and connect."* Do not proceed past Stage 2 without it (Stages 1-2 don't require Chrome).

4. **Gmail MCP availability.** Check tool list for Gmail MCP tools (`search_threads`, `get_thread`). If available, note as backup source for article downloads. If absent, Chrome MCP is the only article source — note in state file.

5. **Baseline counts.** Run `python3 scripts/verify_nate_ingest.py` and count local files:
   ```
   ls Context/NateBJones/articles/*.md | wc -l
   ls Context/NateBJones/templates/promptkit/*.md | wc -l
   ```
   Record in state file.

6. **Date range.** Auto-detect the most recent article date from filesystem:
   ```
   grep -rh "^\*\*Date:\*\*" Context/NateBJones/articles/*.md | sort -t' ' -k2 | tail -1
   ```
   Present to user: *"Last article is from [date]. Scan from [date+1] to today ([today])?"*
   User may override with a different range.

7. **State file check.** If `nate_update_state.json` exists at project root, a prior run was interrupted. Present: *"Found interrupted run from [date]. Resume from Stage [N], or start fresh?"* Resume skips to the incomplete stage. Fresh start deletes the state file.

8. **Dropbox sync warning.** Before Stage 3: *"About to do file writes to the Nate archive. Per CLAUDE.md, you may want to pause Dropbox sync."*

---

## 3. Core Workflow

### Stage 1: Pre-flight

Execute the Pre-flight Checklist (Section 2). Write initial state file:

```json
{
  "schema_version": 1,
  "run_id": "YYYY-MM-DD",
  "started": "ISO-8601",
  "window": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "baseline": {"rows": 0, "articles": 0, "promptkits": 0},
  "delta_slugs": [{"slug": "...", "audience": "..."}],
  "gmail_available": false,
  "completed_stages": [],
  "articles_downloaded": [],
  "transcripts_downloaded": [],
  "promptkits_downloaded": [],
  "errors": []
}
```

Mark `"preflight"` in `completed_stages`.

### Stage 2: Catalog + delta detection

1. Paginate `https://natesnewsletter.substack.com/api/v1/archive?sort=new&limit=12&offset=N` using `curl` (no auth needed for the listing). Sleep 0.25s between pages.
   After fetching the first page, validate that each post object contains the expected fields: `slug`, `post_date`, `audience`, `title`. If any are missing, stop immediately and report the schema mismatch to the user — do not continue pagination or write the catalog.
2. Write the full catalog to `scripts/nate_substack_all.json` (project-local, replaces prior copy).
3. Filter to posts where `post_date >= window.from AND post_date <= window.to`.
4. Cross-check each slug against local filesystem: `articles/<slug>.md` exists?
5. Present forward-delta table to user:

   ```
   | Slug | Date | Audience | Already local? |
   |------|------|----------|---------------|
   ```

6. Record `delta_slugs` as `[{"slug": "...", "audience": "..."}]` in state file.

**If delta is empty:** Tell user *"No new posts in the window. Archive is current."* Delete state file. Stop.

Mark `"catalog"` in `completed_stages`.

### Stage 3: Download articles

**Chrome MCP health check:** Call `list_connected_browsers`. Not connected → save state, yield.

For each entry in `delta_slugs` where `entry.audience` is `everyone` or `only_paid`, and `entry.slug` not in `articles_downloaded`:

**Filesystem cross-check:** If `Context/NateBJones/articles/<slug>.md` already exists on disk but is NOT in `articles_downloaded`, treat it as already downloaded — skip the download step and add the slug to `articles_downloaded`, but still process it in Stages 5-6.

1. Navigate to `https://natesnewsletter.substack.com/p/<slug>` via Chrome MCP.
2. Use `read_page` (NOT `get_page_text` — must preserve link hrefs) to extract the article.
   **Truncation check:** If the extracted body has no `## Links` section and word count < 500, the page may be truncated. Scroll down and call `read_page` again to capture additional content; if still insufficient, fall back to Gmail.
3. Format as canonical markdown:

   ```markdown
   # {title}

   **Date:** YYYY-MM-DD
   **Source:** https://natesnewsletter.substack.com/p/{slug}

   ---

   {body paragraphs}

   ## Links
   - [link text](url)
   ...
   ```

4. Save to `Context/NateBJones/articles/<slug>.md`.
5. Append slug to `articles_downloaded` in state file.

**On Chrome MCP failure mid-stage:**
1. Re-check `list_connected_browsers`.
2. Reconnected → retry failed slug once, then continue.
3. Still disconnected → try Gmail backup (see below). If Gmail unavailable, save state and yield.

**Gmail backup (if available):**
If Chrome fails for a specific article after retry and Gmail MCP is available:
1. Search: `search_threads` with query `from:nate subject:"<first 5 words of title>"`.
2. Extract body from thread via `get_thread`.
3. Convert to canonical markdown format.
4. Note `"source": "gmail"` for this slug in state file.

Mark `"download_articles"` in `completed_stages` when all article slugs are processed.

### Stage 4: Download transcripts

For each entry in `delta_slugs` where `entry.audience` is `founding`:

**Executive briefing transcript (for Open Brain ingest):**
1. Navigate to the Substack article preview via Chrome MCP. Inspect for an embedded YouTube link.
2. If no YouTube link in preview: navigate to `youtube.com/@NateBJones/videos` and match by recency + title keywords.
3. Capture the YouTube video ID and human-readable title.
4. Append entry to the `VIDEOS` dict in `scripts/download_paywalled_transcripts.py`:
   ```python
   "<video_id>": ("<slug>", "<article_title>", "<date>", "<yt_title>"),
   ```
5. Run `python3 scripts/download_paywalled_transcripts.py --run`.
6. Verify transcript at `Context/NateBJones/transcripts/executive-briefings/<slug>-transcript.md` with word count > 1500.

**Community transcript backup (NOT for ingest):**
For any article in the delta (regardless of audience), if a YouTube transcript is available, download to `Context/NateBJones/transcripts/youtube-only/<slug>-transcript.md`. These are backups only and are NOT ingested into Open Brain.

Update `transcripts_downloaded` in state file. Mark `"download_transcripts"` in `completed_stages`.

**If a YouTube video doesn't exist or has no transcript:** Log the error, tell the user, continue. Do not block the pipeline.

### Stage 5: Download prompt kits

**Chrome MCP health check:** Same pattern as Stage 3.

For each article slug from Stage 3 (whether newly downloaded or already local), and slug not in `promptkits_downloaded`:

**Filesystem cross-check:** If `Context/NateBJones/templates/promptkit/` already contains a file derived from this slug but the slug is NOT in `promptkits_downloaded`, treat the prompt kit as already downloaded — add the slug to `promptkits_downloaded` and skip to the next slug (still process the article in Stage 6).

1. Navigate to `https://natesnewsletter.substack.com/p/<slug>` via Chrome MCP.
2. Use `read_page` or `find` to locate links containing `promptkit.natebjones.com`.
3. If no prompt kit link found: record `"no_promptkit"` for this slug in state file, continue.
4. For each prompt kit URL found:
   a. Navigate to the prompt kit page via Chrome MCP.
   b. Extract content via `read_page`.
      **Truncation check:** If the extracted body has no `## Links` section and word count < 500, scroll down and call `read_page` again to capture additional content.
      **Auth-wall check:** If extracted content is fewer than 200 characters, or contains any of the strings "sign in", "subscribe", "log in", "create an account" (case-insensitive), log this slug as a failed download with reason "auth-wall" and continue to the next article — do not save this page.
   c. Format with canonical template header:

      ```markdown
      # {Title}

      **Source:** {promptkit_url}
      **Platform:** promptkit
      **Downloaded:** YYYY-MM-DD

      ## Referenced by

      - [{article_title}](../../articles/{slug}.md) ({date})

      ---

      {body with prompts}
      ```

   d. Save to `Context/NateBJones/templates/promptkit/<Title>.md`.
      Use the existing naming convention in `templates/promptkit/` — match article-derived title casing. Do NOT normalize historical filenames.
5. Append slug to `promptkits_downloaded` in state file.

Mark `"download_promptkits"` in `completed_stages`.

### Stage 6: Ingest + tag

1. **Ingest (changed only):**
   ```
   python3 scripts/ingest_nate_content.py --run --changed-only
   ```
   Embeds and upserts only rows whose content hash has changed since the last run.

2. **Tag new articles:**
   ```
   python3 scripts/tag_nate_articles.py --run
   ```
   Auto-filters to untagged articles. Use `--slugs` for targeted tagging if preferred.

3. **Re-ingest with tags:**
   ```
   python3 scripts/ingest_nate_content.py --run --changed-only
   ```
   Tags now attached to rows via `nate_tags.json`. Only rows where tags changed will be re-embedded.

Mark `"ingest_tag"` in `completed_stages`.

### Stage 7: Verify + indexes

1. **Verify:** `python3 scripts/verify_nate_ingest.py`
   Confirm row count delta makes sense: `new_rows - baseline.rows` should approximately match the number of new articles + new templates. If mismatch > 2, flag to user but don't fail.

2. **Regenerate indexes:**
   ```
   python3 scripts/regenerate_indexes.py
   python3 scripts/build_inventory.py
   ```

3. **Present summary to user:**

   ```
   Archive update complete.
   Window: {from} to {to}
   Articles downloaded: +{N} ({slug list})
   Transcripts: +{N} ({executive briefings list})
   Prompt kits: +{N}
   nate_content rows: {baseline} -> {new} (+{delta})
   Errors: {count} ({details or "none"})
   Estimated cost: ~${amount}
   ```

4. **Cleanup:** Delete `nate_update_state.json`.

---

## 4. State Management

**File:** `nate_update_state.json` at project root.

**Purpose:** Enable resume after interruption (Chrome disconnect, context exhaustion, user halt). Each stage appends its completion marker and per-slug progress.

**Resume logic:**
- On invocation, if state file exists → read it, present status, offer resume or fresh start.
- On resume → skip `completed_stages`; within the current stage, skip already-processed slugs.
- On fresh start → delete state file, begin from Stage 1.

**Corruption handling (Dropbox risk):** Wrap JSON parse of the state file in try/except. On parse failure, warn the user ("State file is unreadable — possibly a truncated Dropbox write") and offer to start fresh. Also check for Dropbox conflict copies matching `nate_update_state (*.json` in the project root; if found, warn the user and ask which file to use before proceeding.

**`schema_version` check:** On resume, if `schema_version` is missing or doesn't match the current version, warn the user that the state file was written by a different skill version and offer to start fresh.

**Cleanup:** Delete state file on successful completion of Stage 7. If the user manually aborts, the file persists for next invocation.

**Do NOT store sensitive data** (API keys, tokens, passwords) in the state file.

---

## 5. Chrome MCP Health Strategy

Check once at stage start, re-check on failure.

1. **Stage-start check:** Before Stages 3, 4, or 5, call `list_connected_browsers`.
   - Connected → proceed.
   - Not connected → save state, yield: *"Chrome MCP disconnected. Please reconnect the browser extension and re-invoke the skill."*

2. **Mid-stage failure:** If any Chrome MCP call returns an error:
   - Re-check `list_connected_browsers`.
   - Reconnected → retry the failed operation once, then continue.
   - Still disconnected → save state (including per-slug progress), yield with message.

3. **Gmail fallback (Stage 3 only):** If Chrome fails for a specific article after retry AND Gmail MCP is available, attempt email extraction before yielding.

---

## 6. Decision Rules

| Situation | Action |
|---|---|
| User says "skip" a stage | Respect it. Mark stage in `completed_stages` with `skipped: true`. |
| Forward delta is empty | Report "archive is current," delete state file, stop. |
| Unexpected audience value (not `everyone` / `only_paid` / `founding`) | Stop and ask the user before proceeding. |
| YouTube video not found for a founding-tier article | Log error, tell user, continue with remaining items. |
| Ingest script fails after 2 retries | Stop and surface the error to user. |
| Cost projection exceeds $1.00 | Stop and ask for explicit user approval. |
| `get_page_text` used instead of `read_page` | Wrong tool. `read_page` preserves links. Fix and retry. |
| User re-invokes mid-session ("what's the status") | Read state file, report progress. |
| Slug exists locally but appears in delta | Skip download. Still ingest/tag if content is new or changed. |
| Article body appears truncated or empty | Log error for that slug, continue. Ask user at end of stage. |

---

## 7. Harness Adaptations

**Required:**
- **Read / Write / Edit files** — articles, templates, state file, script modifications
- **Bash** — Python scripts, curl, filesystem checks
- **Chrome MCP** (`mcp__Claude_in_Chrome__*`) — article and prompt kit download via browser

**Optional (graceful degradation):**

| Capability | Used by | If missing |
|---|---|---|
| Gmail MCP | Stage 3 fallback | Chrome is the only article source |
| `youtube-transcript-api` (pip) | Stage 4 | Tell user to install: `pip install youtube-transcript-api` |
| `build_inventory.py` | Stage 7 xlsx | Skip xlsx regeneration, note in summary |

**Loading deferred tools:** Chrome MCP tools may be deferred at session start. Load via `ToolSearch` with query `Claude_in_Chrome` (single call, returns all). Gmail MCP tools: load via `ToolSearch` with query `search_threads` or similar. Do not load tools individually.

---

## 8. Script Reference

These existing scripts do the heavy lifting. The skill orchestrates them.

| Script | Purpose | Key flags |
|---|---|---|
| `scripts/ingest_nate_content.py` | Embed + upsert to `nate_content` | `--run`, `--changed-only`, `--limit N` |
| `scripts/tag_nate_articles.py` | Haiku-based article tagging | `--run`, `--slugs s1,s2`, `--batch N` |
| `scripts/download_paywalled_transcripts.py` | YouTube transcript download | `--run` |
| `scripts/regenerate_indexes.py` | Regenerate 3 markdown indexes | `--catalog PATH` |
| `scripts/verify_nate_ingest.py` | Post-ingest sanity check | (none) |
| `scripts/build_inventory.py` | Regenerate xlsx inventory | (none) |
| `scripts/check_env.py` | Verify .env keys | (none) |

---

## 9. Eval Criteria

**Pipeline correctness:**
- Every slug in the delta is either downloaded or logged with a specific reason it couldn't be.
- State file accurately reflects progress at every interruption point.
- Resume from state file skips completed work and picks up at the right slug.
- `--changed-only` works: a second run immediately after a successful update processes 0 rows.

**Safety:**
- No files outside `Context/NateBJones/`, `scripts/`, and project root are modified.
- Dropbox sync warning issued before Stage 3.
- Chrome MCP failures save state before yielding.
- Cost stays under $1.00 or user is asked.

**Output quality:**
- Articles match canonical markdown format (title, date, source, body, links).
- Prompt kits match existing `templates/promptkit/` header convention.
- Indexes reflect the full updated state after regeneration.
- End-of-run summary reports accurate counts and cost.

---

## 10. Version & Changelog

**v1.0.0 — 2026-05-25**
- **Initial release.** 7-stage resumable pipeline with state file.
- **Chrome MCP primary, Gmail MCP backup** for article downloads.
- **Prompt kits:** `promptkit.natebjones.com` only (v1). Notion, GDocs, GSheets, Drive, Guides deferred to v2.
- **Transcripts:** All downloaded as backups; only founding-tier (executive briefings) ingested into Open Brain.
- **`--changed-only` flag** added to `scripts/ingest_nate_content.py` — content-hash-based incremental ingest.
- **Design source:** Session #21 audit report (`session20_audit.md`), recommendations 4-7.
