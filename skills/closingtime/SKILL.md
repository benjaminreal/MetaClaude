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

**Does:**
- Reconstruct what happened this session from multiple signals (git, conversation, file changes, transcript if available)
- Draft a session entry for user review before writing
- Append the entry to `project_session.md` at the workspace root
- Update `project_index.md` to reflect current state (decisions, TODOs, key files)
- Surface candidate insights for Open Brain via `pending_learnings.md` and `capture_thought` (with explicit user approval)
- Execute the close-out ritual

**Does NOT:**
- Brief on past state at session start (use `newbeginning` instead)
- Read the full `project_session.md` — only the last entry, for the session number
- Auto-save anything to Open Brain without explicit user approval
- Write project files in any language other than English (file content is always English regardless of session language)

**Use newbeginning instead when:** opening a session, resuming work, asking "where did we leave off."

---

## 2. Pre-flight Checklist

Before drafting the entry, confirm:

1. **Workspace root identified.** Session-continuity files live at the workspace root. If invoking from a subdirectory or worktree, resolve to the actual project root.
2. **Right project.** If multiple projects share a shell or workspace, confirm which one to log. Don't split one session across multiple project logs.
3. **Entry depth.** Default is the full template (300 words max). For quick fixes or one-off questions, a 3–5 line entry is fine — confirm with the user if the session was small.
4. **Open Brain step desired?** Default yes (minimum 2 candidates). If the user says "skip the Open Brain part," respect it and proceed directly to the close-out ritual after Step 3.

---

## 3. Core Workflow

### Step 1: Gather session information

Reconstruct the session from multiple signals:

- `git log` and `git diff --stat` if in a git repo (concrete change record)
- Conversation history: decisions made, problems solved, directions chosen
- Files created, modified, or deleted during the session
- If a transcript tool is available (Cowork), skim for key events — do not process the full transcript verbatim

Draft a session summary and **present it to the user for review** before writing anything. The user may correct emphasis, add context, or flag missed items. Session logs should reflect what the user considers important, not just what the model observed.

### Step 2: Write session entry

**File:** `project_session.md` at workspace root.

If the file doesn't exist, create it with `# Session Log` as the header. Append a new entry. Read only the last entry to determine the current session number; increment it. First entry → #1.

**Entry template (300 words max):**

```markdown

---

### Session #[N] | [YYYY-MM-DD] | [Cowork/Code/Chat/Codex]
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

This skill works wherever you can read git, write files, and converse. Adjust by environment:

- **Claude Code (CLI / IDE):** Full power. `git log` and `git diff --stat` via Bash; `Read` for files; `Write`/`Edit` for the entry append and index update. Open Brain capture via `mcp__*__capture_thought` if installed.
- **Cowork:** File writes work. If a transcript tool is available, skim for key events to enrich the "Done" — do not read the transcript verbatim (token-expensive, low return). Cowork sessions tend toward longer transcripts than Code sessions; sample, don't load.
- **Claude.ai (chat):** No persistent filesystem in standard chat. Degrade: produce the session entry as text in the conversation for the user to paste into their files manually. Same for the index update — show the diff. Open Brain step is only feasible if `capture_thought` is available; otherwise list candidates as text and tell the user to log them externally.
- **Codex (OpenAI CLI):** `Edit` tool present; use absolute paths for `Write` to avoid CWD ambiguity. Git access via shell. No `capture_thought` analog by default — list Open Brain candidates as text for the user to handle externally.

If the harness lacks `capture_thought` but the user wants Open Brain capture, write `pending_learnings.md` anyway — the user can process it at the next session in a capable harness.

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

Output is good when:

- **Session entry:** ≤ 300 words. `Next:` is concrete and actionable, not aspirational ("verify the YAML fix on the next Gemini run" beats "keep iterating").
- **Project index:** ≤ 400 words total. Decisions and TODOs each ≤ 8 active. Summary describes current state, not history.
- **No duplication:** the session log holds details; the index holds current state. If the same sentence appears in both, one of them is wrong.
- **Open Brain candidates:** minimum 2 unless the session was pure execution. Each is grounded in a specific moment from the session, not a generic platitude.
- **Pending file lifecycle:** `pending_learnings.md` exists exactly while there are unreviewed candidates. After save (or explicit discard), it's deleted.
- **Closing ritual executed:** the three checkmarks + Semisonic line appear verbatim (unless the user opted out of the line).
- **English regardless of session language:** all file content is English even if the session ran in another language.

If output fails on entry length or duplication, edit before writing. Don't ship a bloated entry "to get it done."

---

## 7. Version & Changelog

**v2.0.0 — 2026-05-01 — BREAKING**
- `newbeginning` mode extracted to its own skill (sibling: `newbeginning` v1.0).
- Triggers narrowed to closing-only phrases. Mode-detection step removed entirely.
- Restructured per the 7-part skill review frame: Purpose & Scope, Pre-flight Checklist, Core Workflow, Harness Adaptations, Decision Rules, Eval Criteria, Version & Changelog.
- Harness Adaptations expanded to cover Claude Code, Cowork, claude.ai, and Codex (v1.0 implicitly assumed Code/Cowork only).
- **Migration:** users who previously invoked `closingtime` and said "newbeginning" should now invoke the `newbeginning` skill directly. All other workflows unchanged — file formats, ritual line, Open Brain flow, and templates are byte-for-byte compatible with v1.0.

**v1.0 — 2026-04-09**
- Initial release. Single skill, two modes (`closingtime`, `newbeginning`). Shipped publicly via [benjaminreal/MetaClaude](https://github.com/benjaminreal/MetaClaude).
