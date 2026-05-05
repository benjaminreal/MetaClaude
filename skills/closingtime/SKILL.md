---
name: closingtime
description: "Session-closing capture for multi-session projects. Gathers session signals (git diff, conversation, file changes, transcript if available), drafts a session entry for user review, writes to project_session.md, updates project_index.md, extracts Open Brain learning candidates to pending_learnings.md, and executes the closing ritual. MUST trigger on: 'closingtime', 'closing time', 'close session', 'wrap up', 'we are done for now', 'end session', 'log this session', 'save the session', 'lets close this out', 'time to wrap'. Sibling skill: newbeginning — invoke that instead when starting or resuming a session."
version: 2.0.0
---

# closingtime

> *"You don't have to go home, but you can't stay here."*
> — Semisonic, 1998

Session-closing companion to `newbeginning`. Captures what happened, updates project state, extracts learnings, executes the close-out ritual.

---

## 1. Purpose & Scope

**Purpose:** Capture session work at the moment context is richest — while the model still holds everything in memory. Produces a structured handoff for the next session and maintains a compact project index that stays current across sessions. Designed to pair with `newbeginning`, which reads the notes this skill writes.

**Why not just take notes manually?** At session end, the model already holds the full context — decisions made, code written, directions explored. Manually summarizing is error-prone and time-consuming. Without structured capture, the next session starts cold: the model scans files, reads git log, guesses at priorities. This skill extracts a curated handoff (~300 words) and an updated project index (~400 words) while the context is still fresh — so the next `newbeginning` brief costs ≤ 2.5K tokens instead of thousands spent reconstructing from scratch.

**Does:**
- Reconstruct what happened this session from multiple signals (git, conversation, file changes, transcript if available)
- Draft a session entry for user review before writing
- Append the entry to `project_session.md` at the workspace root
- Update `project_index.md` to reflect current state (decisions, TODOs, key files)
- Surface candidate insights for Open Brain via `pending_learnings.md` and `capture_thought` (with explicit user approval)
- Execute the close-out ritual
- Create project files in English by default (if the user requests another language, follow their preference)

**Does NOT:**
- Brief on past state at session start (use `newbeginning` instead)
- Read the full `project_session.md` — only the last entry for context and session number
- Auto-save anything to Open Brain without explicit user approval

**Use newbeginning instead when:** opening a session, resuming work, asking "where did we leave off."

---

## 2. Pre-flight Checklist

Before drafting the entry, confirm:

1. **Workspace root identified.** Session-continuity files live at the workspace root. If invoking from a subdirectory or worktree, resolve to the actual project root.
2. **Right project.** If multiple projects share a shell or workspace, confirm which one to log. Don't split one session across multiple project logs.
3. **Entry depth.** Default is the full template (300 words max). For quick fixes or one-off questions, a 3–5 line entry is fine — confirm with the user if the session was small.
4. **Open Brain availability and intent.** Check the tool list for `capture_thought`. If present → default yes (minimum 2 candidates). If absent → write candidates to `pending_learnings.md` only; tell the user *"Open Brain isn't available in this harness — I'll save learning candidates to `pending_learnings.md` for your next session."* If the user says "skip the Open Brain part" regardless of availability, respect it and proceed directly to the close-out ritual after Step 3.

---

## 3. Core Workflow

### Step 1: Gather session information

Start by loading prior context:

- **`project_index.md`** — read in full (≤ 400 words). Gives you the existing TODOs, decisions, and summary to update against.
- **Last entry of `project_session.md`** — gives the previous `Next:` field (what was planned) and the current session number. Helps detect whether planned work was completed or deferred.

Then reconstruct what happened this session from multiple signals:

- `git log` and `git diff --stat` if in a git repo (concrete change record)
- Conversation history: decisions made, problems solved, directions chosen
- Files created, modified, or deleted during the session
- If a transcript tool is available, skim for key events — do not process the full transcript verbatim

Draft a session summary and **present it to the user for review** before writing anything. The user may correct emphasis, add context, or flag missed items. Session logs should reflect what the user considers important, not just what the model observed.

### Step 2: Write session entry

**File:** `project_session.md` at workspace root.

**Filename resolution:** Look for `project_session.md` first. If not found, check case variants (`Project_Session.md`, `PROJECT_SESSION.md`, `project_Session.md`) and common alternatives (`session_log.md`, `sessions.md`). Use whatever exists; don't create a duplicate. If nothing exists, create `project_session.md`.

If the file doesn't exist, create it with `# Session Log` as the header. Append a new entry. Read only the last entry to determine the current session number; increment it. First entry → #1.

**Entry template (300 words max):**

```markdown

---

### Session #[N] | [YYYY-MM-DD] | [Code/Cowork/Chat/Codex]
**Focus:** [One line — main theme of the session]
**Done:** [What was accomplished. Be specific: name files, features, decisions.]
**Decisions:** [Choices made and brief rationale. Skip if none.]
**Next:** [What the next session should pick up first. This is the handoff to newbeginning.]
**Blockers:** [Anything stuck or waiting on external input. "None" if clear.]
```

**`Next:` is the most critical field** — `newbeginning`'s brief leads with it. Write it as actionable direction, not vague aspiration ("ship v1.6 scope" beats "consider next steps").

Short sessions (quick fix, one-off question) still get logged, but entries can be 3–5 lines. Not every session needs the full template.

### Step 3: Update project_index.md

**File:** `project_index.md` at workspace root.

**Filename resolution:** Look for `project_index.md` first. If not found, check case variants (`Project_Index.md`, `PROJECT_INDEX.md`, `project_Index.md`) and common alternatives (`project.md`, `index.md`). Use whatever exists; don't create a duplicate. If nothing exists, create `project_index.md`.

If it doesn't exist, create it — interview the user briefly for project identity (name, people involved, one-line summary). If it exists, update it to reflect current state.

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
[Max 8. Ordered by priority.]
- [P1] [Task] (since Session #N)
- [P2] [Task] (since Session #N)

## Key Files
[Max 15, prefer 8–10. Files the next session is likely to need.]
- `path/to/file` — one-line purpose

## Archived Decisions
[Max 10. When 11th arrives, move oldest to project_decisions_archive.md.]
[Include only if there are archived items.]
```

**Priority labels:** P1 = do next session. P2 = important, not urgent. P3 = when time allows.

**Staleness rule:** Any TODO present for 3+ sessions gets flagged with ⚠️. Ask the user: blocked, completed, or drop? Don't silently carry stale items.

**Key Files regeneration:** Rebuild this list each session from recently modified + structurally important files. Remove files that no longer exist. This section is a "start here" pointer for the next session, not a file inventory.

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

6. **Save approved items** via `capture_thought` with the user's final wording. Delete `pending_learnings.md` after all approved items are saved.

### Step 5: Close out (the ritual)

Always execute. Don't skip, don't abbreviate.

After Steps 1–3 are complete and Step 4 candidates are presented (whether or not the user has reviewed them yet), give the closing confirmation in exactly this format:

```
Session #N logged ✓
Project index updated ✓
[N] learning candidates ready for review ✓
```

(If learnings were already reviewed: "[N] insights saved to Open Brain" instead.)

Then end with the closing line — every time, no exceptions:

> *"You don't have to go home, but you can't stay here. Session closed."*

The session is closed once files are written. Open Brain review can happen now or at the next `newbeginning` — `pending_learnings.md` ensures nothing is lost either way.

---

## 4. Harness Adaptations

The skill's contract: gather session signals, draft an entry, update project state, surface learnings. Everything else is optional and degrades cleanly. The harness exposes what it has; this skill works with whatever it gets.

**Required:**
- **Write / Edit files.** To append the session entry and update the index. If unavailable, output both as text for the user to save manually.
- **Converse with the user.** To present the draft for review, resolve Open Brain approvals, and deliver the closing ritual.

**Optional capabilities (graceful degradation):**

| Capability | Used for | If missing |
|---|---|---|
| Shell access (`git log`, `git diff --stat`) | Concrete change signal for Step 1 | Rely on conversation history + file modification observations |
| Read files | Reading last entry for session number, verifying index state | Ask user for the current session number |
| Transcript / session-log access | Enriching "Done" from longer sessions | Trust conversation context; sample, don't load full transcripts |
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
| User says "skip Open Brain" | No `pending_learnings.md` written; candidates not surfaced; ritual still runs |
| User says "skip the index update" | Respect it; warn that next `newbeginning` will see stale state |
| Multiple projects in one session | Ask which to log; don't split across files |
| Stale TODOs (3+ sessions) | Flag ⚠️ in the index; ask explicitly: blocked, done, or drop? |
| `Archived Decisions` reaches 11 | Move oldest entries to `project_decisions_archive.md` |
| No git repo | Use conversation history + file modification times. Git is a bonus signal, not a requirement |
| Session ended unexpectedly / no time for full process | Write at least the session entry with `Next:` populated; defer index update with a note. The `Next:` field is the minimum viable handoff |
| User says "drop the closing ritual line" | Skip the Semisonic line; keep the checkmark confirmation |

---

## 6. Eval Criteria

Three lenses. Different failure modes get different responses.

**Output quality** (do the artifacts look right?)
- **Session entry:** ≤ 300 words. `Next:` is concrete and actionable ("verify the YAML fix on the next Gemini run" beats "keep iterating").
- **Project index:** ≤ 400 words total. Decisions and TODOs each ≤ 8 active. Summary describes current state, not history.
- **No duplication:** session log holds details; index holds current state. If the same sentence appears in both, one is wrong.
- **English by default:** file content is written in English unless the user explicitly requests another language.
- **Open Brain candidates:** minimum 2 unless pure execution. Each grounded in a specific session moment, not a generic platitude.

**Workflow correctness** (did the right steps fire?)
- **Draft presented before writing:** the user reviewed and approved the session entry before it was persisted.
- **Pending file lifecycle:** `pending_learnings.md` exists exactly while there are unreviewed candidates. After save (or explicit discard), it's deleted.
- **Open Brain gated:** no `capture_thought` calls without explicit user approval. If `capture_thought` unavailable, candidates written to `pending_learnings.md` only.
- **Closing ritual executed:** the three checkmarks + Semisonic line appear verbatim (unless user opted out of the line).
- **Index staleness enforced:** TODOs at 3+ sessions flagged ⚠️ and surfaced to user.

**Failure response**
- **Restart the step** on boundary violations (wrote before user approved, saved to Open Brain without confirmation, fabricated a decision not discussed).
- **Edit in place** on length, wording, or duplication — trim a sentence; don't redo the whole entry.

---

## 7. Version & Changelog

**v2.0.0 — 2026-05-01 — BREAKING**
- `newbeginning` mode extracted to its own skill (sibling: `newbeginning` v1.0).
- Triggers narrowed to closing-only phrases. Mode-detection step removed entirely.
- Restructured per the 7-part skill review frame: Purpose & Scope, Pre-flight Checklist, Core Workflow, Harness Adaptations, Decision Rules, Eval Criteria, Version & Changelog.
- Harness Adaptations rewritten as capability-based Required/Optional table with graceful degradation (v1.0 listed specific products).
- **Migration:** users who previously invoked `closingtime` and said "newbeginning" should now invoke the `newbeginning` skill directly. All other workflows unchanged — file formats, ritual line, Open Brain flow, and templates are byte-for-byte compatible with v1.0.

**v1.0 — 2026-04-09**
- Initial release. Single skill, two modes (`closingtime`, `newbeginning`). Shipped publicly via [benjaminreal/MetaClaude](https://github.com/benjaminreal/MetaClaude).
