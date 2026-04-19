---
name: closingtime
description: "Session continuity manager for multi-session projects. Two modes: invoke as 'closingtime' to close a work session (log what happened, update project index, extract insights for Open Brain) or as 'newbeginning' to open a session (load project context, brief on status, resume work). MUST trigger on: 'closingtime', 'closing time', 'close session', 'wrap up', 'end session', 'newbeginning', 'new beginning', 'start session', 'open session', 'where did we leave off', 'what were we working on', 'pick up where we left off', 'catch me up'. Also trigger when the user references starting or ending a work session, resuming a project, or doing a session handoff."
---

# closingtime

> *"Every new beginning comes from some other beginning's end."*
> — Semisonic, 1998

Session continuity skill for multi-session projects. Maintains two compact files in the project workspace and integrates with Open Brain for persistent learning. All files are written in English regardless of session language.

Two modes: **closingtime** (end of session) and **newbeginning** (start of session).

## Detecting Mode

Determine which mode from the user's invocation:

- **closingtime**: "closingtime", "close session", "wrap up", "we're done for now", "end session"
- **newbeginning**: "newbeginning", "new beginning", "where did we leave off", "catch me up", "start session", "pick up where we left off"

If ambiguous, ask. Don't guess — the wrong mode wastes tokens.

---

## MODE: newbeginning

**Goal:** Get the user productive with minimal token cost. Read only what's needed, brief concisely.

### Steps

1. **Locate project files** in the workspace root: `project_index.md` and `project_session.md`.

2. **Check for pending learnings.** If `pending_learnings.md` exists, there are unreviewed insights from the last session. Mention this to the user early: *"You had unreviewed learnings from last session. Want to review them now or after we get going?"* If they want to review, present the candidates following the Open Brain approval flow in closingtime Step 4. If they defer, leave the file and move on.

3. **If both project files exist:**
   - Read `project_index.md` in full (designed to be under 400 words — this is the primary context load)
   - Read only the last 2 entries from `project_session.md`. The full file may be long — read efficiently from the end rather than loading everything.
   - Present a brief:
     - One sentence: what this project is and its current state
     - What happened last session — focus on "Next" items (these are today's starting point)
     - Top 3 active TODOs from the index, with priority
     - Any flagged blockers or stale TODOs (items marked ⚠️)
   - Ask: *"Ready to pick up, or want to adjust priorities first?"*

4. **If only one file exists (partial state):**
   - Work with what's there. If only `project_session.md` exists, read the last 2 entries and brief from those — note that a project index is missing and offer to create one at session end. If only `project_index.md` exists, read it and brief normally — note there's no session history yet.

5. **If neither file exists:**
   - This is a new project. Tell the user no session history was found.
   - Offer two options: (a) establish the project identity now and create the files, or (b) start working and run closingtime at the end to capture everything.
   - If option (a): interview the user briefly for project name, who's involved, and a one-line summary. Create `project_index.md` with what you have — the rest fills in at closingtime.

### Token Target
~1.5-2.5K tokens total for reads + briefing output. This mode should feel instant.

---

## MODE: closingtime

**Goal:** Capture session work, update project state, extract learnings. Then close out.

### Step 1: Gather Session Information

Reconstruct what happened this session. Use multiple signals:

- `git log` and `git diff --stat` if in a git repo (shows what changed concretely)
- Conversation history — decisions made, problems solved, directions chosen
- Files created, modified, or deleted during the session
- If a transcript tool is available (Cowork), use it to review the session — skim for key events, don't process the full transcript verbatim

Draft a session summary and **present it to the user for review** before writing anything. The user may correct emphasis, add context, or flag things you missed. Session logs should reflect what the user considers important, not just what the model observed.

### Step 2: Write Session Entry

**Location:** `project_session.md` in workspace root.

If the file doesn't exist, create it with a `# Session Log` header. Then append a new entry. Check the last entry for the current session number and increment. If this is the first entry, start at #1.

**Entry template (strict — 300 words max):**
```markdown

---

### Session #[N] | [YYYY-MM-DD] | [Cowork/Code]
**Focus:** [One line — the main theme of this session]
**Done:** [What was accomplished. Be specific: name files, features, decisions.]
**Decisions:** [Choices made and brief rationale. Skip if none.]
**Next:** [What the next session should pick up first. This is the handoff.]
**Blockers:** [Anything stuck or waiting on external input. "None" if clear.]
```

The **Next** field is the most critical — the next session's newbeginning briefing leads with it. Write it as actionable direction, not vague aspiration.

Short sessions (quick fix, one-off question) still get logged, but entries can be 3-5 lines. Not every session needs the full template.

### Step 3: Update project_index.md

**Location:** `project_index.md` in workspace root.

If it doesn't exist, create it — interview the user for project identity (name, people involved, summary). If it exists, update it to reflect current state.

**Format:**
```markdown
# [Project Name]
**People:** [Names and roles, comma-separated]
**Updated:** [YYYY-MM-DD]

## Summary
[What this project is and where it stands right now. 200 words max. This is current state, not history — rewrite each session to reflect reality.]

## Key Decisions
[Max 8 active. When adding a 9th, move the oldest to Archived Decisions.]
- [Decision statement] (Session #N)

## Active TODOs
[Max 8. Ordered by priority.]
- [P1] [Task description] (since Session #N)
- [P2] [Task description] (since Session #N)

## Key Files
[Only files the next session is likely to need. Keep this short — 15 absolute max, prefer 8-10.]
- `path/to/file` — one-line purpose

## Archived Decisions
[Max 10. When the 11th arrives, move the oldest to `project_decisions_archive.md`.]
[Only include this section when there are archived items.]
```

**Priority labels:** P1 = do next session. P2 = important, not urgent. P3 = when time allows.

**Staleness rule:** Any TODO present for 3+ sessions gets flagged with ⚠️. Ask the user: is this blocked, completed, or should we drop it? Don't silently carry stale items.

**Key Files regeneration:** Don't just append to this list. Each session, rebuild it from recently modified files + structurally important files. Remove files that no longer exist. This section helps the next session orient quickly — it's a "start here" pointer, not a file inventory.

**Archived decisions overflow:** When `Archived Decisions` reaches 10 entries and an 11th needs to be added, move the oldest entries to `project_decisions_archive.md` (a separate file in the workspace root). That file is never read by newbeginning unless someone explicitly asks for decision history. It exists purely as long-term record.

### Step 4: Extract Learnings for Open Brain

The reflective step. Review the session for things worth persisting beyond the project log:

- Insights about the domain, the tools, or the approach
- Decisions with implications beyond this session
- Patterns, surprises, mistakes, or things that worked unexpectedly well
- Connections to broader thinking (strategy, methodology, research)

**Process:**

1. **Identify candidates.** Minimum 2 per session. No forced ceiling — capture what's genuinely worth keeping. Don't manufacture filler insights; if a session was pure execution, 2 honest observations are enough.

2. **Search Open Brain for connections.** For each candidate, run `search_thoughts` with a targeted query (1-2 queries per candidate). If related thoughts exist, surface the connection explicitly: *"This builds on your earlier thought: [existing thought]"*

3. **Suggest a thought type** for each candidate:
   - `observation` — something noticed about how things work
   - `idea` — a possibility worth exploring later
   - `reference` — a pointer to something useful (tool, resource, method)
   - `task` — something to do that emerged from the work
   - `person_note` — insight about a colleague's working style, preferences, or strengths

4. **Write candidates to `pending_learnings.md`** in the workspace root. Format each as:
   ```markdown
   ## Candidate [N]
   **Type:** [suggested type]
   **Insight:** [the learning, clearly stated]
   **Connects to:** [related Open Brain thought, or "New thread"]
   **Status:** pending
   ```
   This file is the safety net — if the session ends before the user reviews, the candidates survive for next time.

5. **Present candidates to the user** with their types and Open Brain connections. Ask which to save, which to discard, and whether they want to edit the wording. Do NOT save anything to Open Brain until the user explicitly approves.

6. **Save approved items** using `capture_thought` with the user's final wording. After all approved items are saved, delete `pending_learnings.md`.

### Step 5: Close Out

This step is the ritual. Always execute it — don't skip it, don't abbreviate it.

After Steps 1-3 are complete and Step 4 candidates are presented (whether or not the user has reviewed them yet), give the user the closing confirmation. Use exactly this format:

```
Session #N logged ✓
Project index updated ✓
[N] learning candidates ready for review ✓
```

(If learnings were already reviewed, say "[N] insights saved to Open Brain" instead.)

Then end with the closing line — every time, no exceptions:

> *"You don't have to go home, but you can't stay here. Session closed."*

The session is considered closed after the files are written. The Open Brain review can happen now or next session — the `pending_learnings.md` file ensures nothing is lost either way.

---

## Token Efficiency

This skill reduces friction between sessions. If it burns excessive tokens doing its job, it's self-defeating.

**Reads:** Never read the full `project_session.md` when only the last few entries matter. In newbeginning, the last 2 entries. In closingtime, only the last entry for the session number. Never read files "for completeness" — read what the current step requires, nothing more.

**Writes:** `project_index.md` must stay under 400 words total. Session entries: 300 words max. Err toward terse.

**Open Brain:** Targeted searches only — 1-2 queries per candidate. Don't enumerate existing thoughts looking for connections; search by meaning.

**General:** Don't repeat information across files — the session log has details, the project index has current state. They complement, not duplicate. Keep confirmations to the user short. The files are the deliverable, not the conversation about them.

---

## Edge Cases

**First session on a new project:** Both files created from scratch. Interview the user briefly for project identity. This is Session #1.

**Partial state (one file exists, not the other):** Work with what's there. Offer to create the missing file. This can happen if someone manually created one file, or if a previous closingtime was interrupted.

**Returning after a long gap:** newbeginning should note the time elapsed since last session. If it's been weeks, suggest reviewing whether TODOs and decisions are still current before diving in.

**Multiple projects in one session:** Ask the user which project to log. Don't split one session across multiple logs.

**User wants to skip a step:** Respect it. "Skip the Open Brain part" or "just show me the TODOs" — do what they ask. The skill serves the user, not its own process.

**No git repo:** Rely on conversation history and file modifications for the session summary. Git is a bonus signal, not a requirement.

**Creating files in newbeginning:** If the user chooses to establish the project during newbeginning (rather than waiting for closingtime), create a minimal `project_index.md` with whatever identity info the user provides. The full file structure gets completed at closingtime.
