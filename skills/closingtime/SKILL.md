---
name: closingtime
description: "Session-closing capture for multi-session projects. Gathers session signals (git diff, conversation, file changes, transcript if available), drafts a session entry for user review, writes to project_session.md, updates project_index.md narrative fields, writes task changes to the Supabase Tasks DB, refreshes a read-only task mirror, extracts Open Brain learning candidates to pending_learnings.md, and executes the closing ritual. MUST trigger on: 'closingtime', 'closing time', 'close session', 'wrap up', 'we are done for now', 'end session', 'log this session', 'save the session', 'lets close this out', 'time to wrap'. Sibling skill: newbeginning — invoke that instead when starting or resuming a session."
version: 2.2.0
---

# closingtime

> *"You don't have to go home, but you can't stay here."*
> — Semisonic, 1998

Session-closing companion to `newbeginning`. Captures what happened, updates project state, extracts learnings, executes the close-out ritual.

---

## 1. Purpose & Scope

**Purpose:** Capture session work at the moment context is richest — while the model still holds everything in memory. Produces a structured handoff for the next session, maintains compact project narrative notes, and writes task changes to the Supabase `Tasks` database. Designed to pair with `newbeginning`, which reads the notes and queries the task database.

**Why not just take notes manually?** At session end, the model already holds the full context — decisions made, code written, directions explored. Manually summarizing is error-prone and time-consuming. Without structured capture, the next session starts cold: the model scans files, reads git log, guesses at priorities. This skill extracts a curated handoff (~300 words) and an updated project index (~400 words) while the context is still fresh — so the next `newbeginning` brief costs ≤ 2.5K tokens instead of thousands spent reconstructing from scratch.

**Does:**
- Reconstruct what happened this session from multiple signals (git, conversation, file changes, transcript if available)
- Draft a session entry for user review before writing
- Append the entry to `project_session.md` at the workspace root
- Update `project_index.md` narrative fields to reflect current state (summary, decisions, key files, updated date)
- Write task changes to the Supabase `Tasks` database via the `supabase` MCP, following the canonical `## Task tracking` spec in root `CLAUDE.md`
- Refresh `project_index.md`'s `## Active TODOs` block only as a read-only mirror regenerated from `task_urgency`
- Surface candidate insights for Open Brain via `pending_learnings.md` and `capture_thought` (with explicit user approval)
- Execute the close-out ritual
- Create project files in English by default (if the user requests another language, follow their preference)

**Does NOT:**
- Brief on past state at session start (use `newbeginning` instead)
- Read the full `project_session.md` — only the last entry for context and session number
- Auto-save anything to Open Brain without explicit user approval
- Hand-edit `## Active TODOs` as project-local state. The database wins; the markdown block is only a mirror.

**Use newbeginning instead when:** opening a session, resuming work, asking "where did we leave off."

---

## 2. Pre-flight Checklist

Before drafting the entry, confirm:

1. **Workspace root identified.** Session-continuity files live at the workspace root. If invoking from a subdirectory or worktree, walk up to the directory containing `project_index.md`, or the git root, or the directory the user considers the project root.
2. **Right project.** If multiple projects share a shell or workspace, confirm which one to log. Don't split one session across multiple project logs.
3. **Entry depth.** Default is the full template (300 words max). Sessions under ~15 minutes or involving a single fix/question qualify for short entries (3–5 lines). For longer sessions, use the full template.
4. **Open Brain availability and intent.** Check the tool list for `capture_thought`. If present → default yes (minimum 2 candidates). If absent → write candidates to `pending_learnings.md` only; tell the user *"Open Brain isn't available in this harness — I'll save learning candidates to `pending_learnings.md` for your next session."* If the user says "skip the Open Brain part" regardless of availability, respect it and proceed directly to the close-out ritual after Step 3.
5. **Tasks DB availability.** Check whether the `supabase` MCP is available for the `Tasks` project. If present → use `execute_sql` for reads/writes. If absent → warn: *"Tasks DB isn't available in this harness. I'll log the session and update narrative notes, but task changes will be captured as pending DB operations, not written to frozen markdown TODOs."*

---

## 3. Core Workflow

### Step 1: Gather session information

Start by loading prior context:

- **`project_index.md`** — read in full (≤ 400 words). Gives you the existing decisions, summary, key files, and current read-only task mirror. If the mirror disagrees with the DB, the DB wins.
- **Last entry of `project_session.md`** — gives the previous `Next:` field (what was planned) and the current session number. Helps detect whether planned work was completed or deferred.

If neither file exists, this is the first session — see Decision Rule: *First session ever on a project* (Section 5).

Then reconstruct what happened this session from multiple signals:

- `git log` and `git diff --stat` if in a git repo (concrete change record)
- Conversation history: decisions made, problems solved, directions chosen
- Files created, modified, or deleted during the session
- If a transcript tool is available, skim for key events — do not process the full transcript verbatim

Draft the session entry using the Step 2 template and **present it to the user for review** before writing anything. The user may correct emphasis, add context, or flag missed items. Session logs should reflect what the user considers important, not just what the model observed.

### Step 2: Write session entry

**File:** `project_session.md` at workspace root.

**Filename resolution:** Look for `project_session.md` first. If not found, check case variants (`Project_Session.md`, `PROJECT_SESSION.md`, `project_Session.md`) and common alternatives (`session_log.md`, `sessions.md`). Use whatever exists; don't create a duplicate. If nothing exists, create `project_session.md`.

If the file doesn't exist, create it with `# Session Log` as the header. Append a new entry. Read only the last entry to determine the current session number; increment it. First entry → #1.

**Entry template (300 words max):**

```markdown

---

### Session #[N] | [YYYY-MM-DD] | [Mode (Tool)]
**Focus:** [One line — main theme of the session]
**Done:** [What was accomplished. Be specific: name files, features, decisions.]
**Decisions:** [Choices made and brief rationale. Skip if none.]
**Next:** [What the next session should pick up first. This is the handoff to newbeginning.]
**Blockers:** [Anything stuck or waiting on external input. "None" if clear.]
```

**Session-type labels:** The header uses `Mode (Tool)` format. Mode describes the work pattern; Tool names the harness.
- **Code** — coding session with file edits, script runs, tool use
- **Research** — study, reading, analysis, note-taking (no significant code changes)
- **Chat** — pure conversation, Q&A, planning discussion
- **Cowork** — collaborative session with another person present

Tool is the harness used: `Claude Code`, `Cursor`, `ChatGPT`, `Codex`, or similar. Example: `Code (Claude Code)`, `Research (ChatGPT)`, `Chat (Claude Code)`.

**`Next:` is the most critical field** — `newbeginning`'s brief leads with it. Write it as actionable direction, not vague aspiration ("ship v1.6 scope" beats "consider next steps").

Short sessions (quick fix, one-off question) still get logged, but entries can be 3–5 lines. Not every session needs the full template.

### Step 3: Update project_index.md and Tasks DB

**File:** `project_index.md` at workspace root.

**Filename resolution:** Look for `project_index.md` first. If not found, check case variants (`Project_Index.md`, `PROJECT_INDEX.md`, `project_Index.md`) and common alternatives (`project.md`, `index.md`). Use whatever exists; don't create a duplicate. If nothing exists, create `project_index.md`.

If it doesn't exist, create it — interview the user briefly for project identity (name, people involved, one-line summary). If it exists, update it to reflect current narrative state.

**Update procedure:** Each session, update these fields:
- **Summary** — rewrite to reflect current state (not history)
- **Key Decisions** — add new decisions from this session; archive overflow per the max-8 rule
- **Active TODOs** — regenerate from `task_urgency` as a read-only mirror only. Do not hand-edit task state in markdown.
- **Key Files** — rebuild from this session's activity (see Key Files regeneration below)
- **Updated** — set to today's date

**Task source of truth:** The canonical schema, field conventions, and connection live in root `CLAUDE.md` under `## Task tracking`. Reference tasks by `id` or by a stable filter, never by row position.

**Task write procedure:** Translate the reviewed closeout into explicit DB operations. Show the intended changes to the user before writing if there is any ambiguity about task identity, status, priority, due/review date, or cluster. Prefer `returning` on write queries so the result proves what changed.

```sql
-- List current project tasks before deciding what to change.
select id, urgency, priority, project, title, flagged, due, review_on, status
from task_urgency
where status = 'open' and project = $1
order by urgency desc, priority asc nulls last, created_at asc;

-- Add a task.
insert into tasks (project, title, details, priority, cluster, origin)
values ($1, $2, $3, $4, $5, $6)
returning id, project, title, priority, status, origin;

-- Complete a task.
update tasks
set status = 'done', completed_at = now(), updated_at = now()
where id = $1
returning id, project, title, status, completed_at;

-- Reprioritize or flag a task.
update tasks
set priority = $2, flagged = $3, updated_at = now()
where id = $1
returning id, project, title, priority, flagged;

-- Park a task until a review date.
update tasks
set status = 'parked', review_on = $2, updated_at = now()
where id = $1
returning id, project, title, status, review_on;

-- Cancel a task.
update tasks
set status = 'cancelled', updated_at = now()
where id = $1
returning id, project, title, status;
```

**Read-only mirror procedure:** After DB writes, query `task_urgency` for the current project and regenerate `## Active TODOs` in `project_index.md` from the result. Label the block as a DB mirror.

```sql
select id, urgency, priority, project, title, flagged, due, review_on
from task_urgency
where status = 'open' and project = $1
order by urgency desc, priority asc nulls last, created_at asc
limit 8;
```

Mirror format:

```markdown
## Active TODOs
_Read-only mirror regenerated from Supabase `task_urgency`. Do not hand-edit; DB wins._
- [P1] ⚠️ Task title (id: `uuid`; due: YYYY-MM-DD; review: YYYY-MM-DD)
```

If there are no open tasks for the project, write:

```markdown
## Active TODOs
_Read-only mirror regenerated from Supabase `task_urgency`. Do not hand-edit; DB wins._
- None.
```

**Format:**

```markdown
# [Project Name]
**People:** [Names and roles, comma-separated]
**Updated:** [YYYY-MM-DD]

## Summary
[What this project is and where it stands right now. 200 words max. Current state, not history — rewrite each session to reflect reality.]

## Key Decisions
[Max 8 active. When adding a 9th, move oldest to Archived Decisions.]
- [Decision statement] (Session #N)

## Active TODOs
_Read-only mirror regenerated from Supabase `task_urgency`. Do not hand-edit; DB wins._
- [P1] [Task] (id: `uuid`)

## Key Files
[Max 15, prefer 8–10. Files the next session is likely to need.]
- `path/to/file` — one-line purpose

## Archived Decisions
[Max 10. When 11th arrives, move oldest to project_decisions_archive.md.]
[Include only if there are archived items.]
```

**Priority labels:** Use the database priority convention from root `CLAUDE.md`: P0 is most urgent, then P1/P2/P3; null priority means unprioritized/track item.

**Staleness rule:** Staleness now comes from `task_urgency` and task fields (`flagged`, `review_on`, due-date pressure, age drift), not from counting sessions in markdown. When a task is flagged or review-due, ask explicitly: still open, done, park, cancel, or blocked?

**Key Files regeneration:** Rebuild this list each session from: files touched in this session's git diff (if available), files discussed in conversation, and structurally important files (entry points, configs). Remove files that no longer exist. This section is a "start here" pointer for the next session, not a file inventory.

**Archived decisions overflow:** When `Archived Decisions` reaches 10 and an 11th needs to be added, move the oldest entries to `project_decisions_archive.md` (separate file at workspace root). That file is never read by `newbeginning` unless explicitly requested. Long-term record only.

### Step 4: Extract learnings for Open Brain

The reflective step. Review the session for things worth persisting beyond the project log:

- Insights about the domain, the tools, or the approach
- Decisions with implications beyond this session
- Patterns, surprises, mistakes, or things that worked unexpectedly well
- Connections to broader thinking (strategy, methodology, research)

**Process:**

1. **Identify candidates.** Minimum 2 per session. No forced ceiling — capture what's genuinely worth keeping. Don't manufacture filler; if the session was pure execution, 2 honest observations are enough.

2. **Search Open Brain for connections.** For each candidate, run `search_thoughts` with a targeted query (1–2 queries per candidate). If related thoughts exist, surface the connection: *"This builds on your earlier thought: [existing thought]"*

3. **Suggest a thought type:**
   - `observation` — something noticed about how things work
   - `idea` — a possibility worth exploring later
   - `reference` — a pointer to something useful (tool, resource, method)
   - `task` — something to do that emerged from the work
   - `person_note` — insight about a colleague's working style, preferences, or strengths

4. **Write candidates to `pending_learnings.md`** at workspace root:
   ```markdown
   ## Candidate [N]
   **Type:** [suggested type]
   **Insight:** [the learning, clearly stated]
   **Connects to:** [related Open Brain thought, or "New thread"]
   **Status:** pending
   ```
   This file is the safety net — if the session ends before user review, candidates survive for the next `newbeginning`.

5. **Present candidates to the user** with their types and Open Brain connections. Ask which to save, which to discard, whether to edit the wording. **Do NOT save anything to Open Brain until the user explicitly approves.**

6. **Save approved items** via `capture_thought` with the user's final wording. Delete `pending_learnings.md` after all approved items are saved. If the user approved some candidates and skipped or discarded others, save the approved ones and still delete the file — skipped candidates are treated as discarded for file lifecycle purposes.

### Step 5: Close out (the ritual)

Always execute. Don't skip, don't abbreviate.

After Steps 1–3 are complete and Step 4 candidates are presented (whether or not the user has reviewed them yet), give the closing confirmation in exactly this format:

```
Session #N logged ✓
Tasks DB updated ✓
Project index narrative + task mirror updated ✓
[N] learning candidates ready for review ✓
```

(If learnings were already reviewed: "[N] insights saved to Open Brain" instead. If partial: "[N] insights saved to Open Brain, [M] skipped.")

Then end with the closing line — every time, no exceptions:

> *"You don't have to go home, but you can't stay here. Session closed."*

The session is closed once files are written. Open Brain review can happen now or at the next `newbeginning` — `pending_learnings.md` ensures nothing is lost either way.

---

## 4. Harness Adaptations

The skill's contract: gather session signals, draft an entry, update project state, surface learnings. Everything else is optional and degrades cleanly. The harness exposes what it has; this skill works with whatever it gets.

**Required:**
- **Write / Edit files.** To append the session entry and update narrative notes. If unavailable, output the file edits as text for the user to save manually.
- **Converse with the user.** To present the draft for review, resolve Open Brain approvals, and deliver the closing ritual.

**Optional capabilities (graceful degradation):**

| Capability | Used for | If missing |
|---|---|---|
| Shell access (`git log`, `git diff --stat`) | Concrete change signal for Step 1 | Rely on conversation history + file modification observations |
| Read files | Reading last entry for session number, verifying index state | Ask user for the current session number |
| Transcript / session-log access | Enriching "Done" from longer sessions | Trust conversation context; sample, don't load full transcripts |
| `supabase` MCP (`execute_sql`) | Reading/writing the Tasks DB and regenerating the task mirror | Warn; do not write frozen markdown TODOs. Log task-change intent as pending DB operations and keep any existing mirror read-only |
| `capture_thought` (Open Brain) | Saving approved learnings in Step 4 | Write candidates to `pending_learnings.md` for next-session review |
| Skill-list introspection | Verifying `newbeginning` sibling is installed | Skip; assume present |

**Path-selection preference:** prefer the most efficient available — `git diff --stat` over reading every modified file, partial reads over full-file loads, transcript skimming over verbatim processing.

**Unknown harness fallback:** assume all optional capabilities present, try them, degrade on first error. Tell the user when something didn't work. If the harness lacks `capture_thought` but the user wants Open Brain capture, write `pending_learnings.md` anyway — the user can process it at the next session in a capable harness.

---

## 5. Decision Rules

| Situation | Action |
|---|---|
| First session ever on a project | Interview for identity (name, people, summary), create both files, start at #1 |
| Partial state (one file exists, not the other) | Work with what's there; offer to create the missing file |
| User says "skip Open Brain" | Skip Step 4 entirely — no candidates identified, no `pending_learnings.md` written. Proceed directly to Step 5. Ritual still runs. |
| User says "skip the index update" | Respect it for narrative notes and mirror refresh; still ask whether requested task changes should be written to the DB |
| User says "skip task updates" | Respect it; log the session and note that DB task state was intentionally left unchanged |
| Multiple projects in one session | Ask which to log; don't split across files |
| Stale or flagged DB tasks | Ask explicitly: still open, done, park, cancel, or blocked? Apply the corresponding DB write if approved |
| Tasks DB unavailable | Warn; read frozen markdown TODOs only as degraded context, never as writable state. Capture task-change intent as pending DB operations |
| `Archived Decisions` reaches 11 | Move oldest entries to `project_decisions_archive.md` |
| No git repo | Use conversation history + file modification times. Git is a bonus signal, not a requirement |
| Session ended unexpectedly / no time for full process | Write at least the session entry with `Next:` populated; defer index update with a note. The `Next:` field is the minimum viable handoff |
| User says "drop the closing ritual line" | Skip the Semisonic line; keep the checkmark confirmation |

---

## 6. Eval Criteria

Three lenses. Different failure modes get different responses.

**Output quality** (do the artifacts look right?)
- **Session entry:** ≤ 300 words. `Next:` is concrete and actionable ("verify the YAML fix on the next Gemini run" beats "keep iterating").
- **Project index:** ≤ 400 words excluding the read-only task mirror. Decisions ≤ 8 active. Summary describes current state, not history.
- **No duplication:** session log holds details; index holds current state. If the same sentence appears in both, one is wrong.
- **English by default:** file content is written in English unless the user explicitly requests another language.
- **Open Brain candidates:** minimum 2 unless pure execution. Each grounded in a specific session moment, not a generic platitude.

**Workflow correctness** (did the right steps fire?)
- **Draft presented before writing:** the user reviewed and approved the session entry before it was persisted.
- **Pending file lifecycle:** `pending_learnings.md` exists exactly while there are unreviewed candidates. After save (or explicit discard), it's deleted.
- **Open Brain gated:** no `capture_thought` calls without explicit user approval. If `capture_thought` unavailable, candidates written to `pending_learnings.md` only.
- **Closing ritual executed:** the three checkmarks + Semisonic line appear verbatim (unless user opted out of the line).
- **Tasks DB correctness:** task additions, completions, reprioritizations, parking, cancellation, and blocking are written to `tasks` and verified with `returning` or a follow-up `task_urgency` query.
- **Mirror discipline:** `## Active TODOs` is regenerated from `task_urgency`, labeled read-only, and never treated as the source of truth.

**Failure response**
- **Restart the step** on boundary violations (wrote before user approved, saved to Open Brain without confirmation, fabricated a decision not discussed).
- **Edit in place** on length, wording, or duplication — trim a sentence; don't redo the whole entry.

---

## 7. Version & Changelog

**v2.2.0 — 2026-07-05**
- Migrated task state from per-project markdown TODO editing to the Supabase `Tasks` database as the source of truth, following root `CLAUDE.md` `## Task tracking`.
- Added concrete SQL examples for listing, adding, completing, reprioritizing, parking, and cancelling tasks via `execute_sql`.
- Changed `## Active TODOs` handling to a read-only mirror regenerated from `task_urgency`; markdown TODOs are no longer hand-edited.
- Added graceful degradation when the `supabase` MCP is unavailable: warn, read frozen markdown only as context, and capture pending DB operations without writing stale task state.

**v2.1.0 — 2026-05-25**
- Transferability Protocol audit applied (Stages 1–4). 10 patches across Sections 2, 3, and 5.
- Pre-flight: workspace root resolution chain added; entry-depth threshold defined; "skip Open Brain" rule unified with Decision Rules.
- Core Workflow: first-session cross-reference; draft scope clarified; session-type labels defined as Mode (Tool) format; explicit index update procedure; Key Files rebuild method specified; partial-approval lifecycle rule for `pending_learnings.md`; mixed-state ritual format.
- Decision Rules: "skip Open Brain" action aligned with Pre-flight item 4.
- HANDOFF.md produced with section certifications, competent user definition, and CAN/CANNOT lists.

**v2.0.0 — 2026-05-01 — BREAKING**
- `newbeginning` mode extracted to its own skill (sibling: `newbeginning` v1.0).
- Triggers narrowed to closing-only phrases. Mode-detection step removed entirely.
- Restructured per the 7-part skill review frame: Purpose & Scope, Pre-flight Checklist, Core Workflow, Harness Adaptations, Decision Rules, Eval Criteria, Version & Changelog.
- Harness Adaptations rewritten as capability-based Required/Optional table with graceful degradation (v1.0 listed specific products).
- **Migration:** users who previously invoked `closingtime` and said "newbeginning" should now invoke the `newbeginning` skill directly. All other workflows unchanged — file formats, ritual line, Open Brain flow, and templates are byte-for-byte compatible with v1.0.

**v1.0 — 2026-04-09**
- Initial release. Single skill, two modes (`closingtime`, `newbeginning`). Shipped publicly via [benjaminreal/MetaClaude](https://github.com/benjaminreal/MetaClaude).
