---
name: newbeginning
description: "Session-opening brief for multi-session projects. Reads existing project notes (or bootstraps them on a fresh project) and delivers a concise status brief: project state, last session's 'Next' items, top active TODOs, blockers. Hands off with options to pick up, adjust priorities, focus elsewhere, or review pending learnings. MUST trigger on: 'newbeginning', 'new beginning', 'where did we leave off', 'what were we working on', 'pick up where we left off', 'catch me up', 'start session', 'open session', 'resume work', 'whats the status', 'brief me on this project'. Sibling skill: closingtime — invoke that instead when wrapping up a session."
version: 1.0.0
---

# newbeginning

> *"Every new beginning comes from some other beginning's end."*
> — Semisonic, 1998

Session-opening companion to `closingtime`. Loads the minimum context needed to resume work, briefs the user, and gets out of the way.

---

## 1. Purpose & Scope

**Purpose:** Resume work on an ongoing multi-session project quickly — load just enough context to remember where things stand, without re-reading the whole history. Designed to pair with `closingtime`, which writes the project notes this skill reads.

**Why not just ask the model?** Without structured notes, the model must scan the project from scratch — listing files, reading source code, checking git history — to reconstruct context. That costs thousands of tokens, fills the context window with noise, and produces guesses instead of a curated handoff. This skill reads ~400 words of pre-written notes and delivers a brief in ≤ 2.5K tokens total (reads + output), keeping the context window clean for actual work.

**Does:**
- Brief the user on current project state from notes left by the previous session: one-line summary, last session's "Next" items, top active TODOs, blockers, staleness flags
- If Open Brain is in use and the prior `closingtime` left pending insights for review, surface them and save the ones the user approves

**Does NOT:**
- Replace `closingtime` — it doesn't log sessions, doesn't update project state after the hand-off, doesn't extract learnings from this session. (Light edits to `project_index.md` during the opening hand-off — e.g., reordering TODOs at user request — are part of opening.)
- Read the full session history — only the last two entries
- Pick the next task or start working on it — briefs and stops; the user drives the next action
- Require Open Brain — it's an optional integration; the brief works fine without it

**Use closingtime instead when:** wrapping up a session, logging what happened, extracting learnings, or updating project state.

---

## 2. Pre-flight Checklist

Before reading anything, confirm:

1. **Workspace root identified.** Project notes live at workspace root. If invoked from a subdir or worktree, walk up to the actual project root (containing `project_index.md`, or git root). If neither exists, use the current directory and proceed to cold-start (Step 1).
2. **Right project.** If the workspace holds multiple project subfolders, or the user juggles several from one shell, confirm which to brief before reading.
3. **Brief depth.** Default: full brief — one-line summary, last session's `Next:`, top 3 TODOs, blockers, staleness flags. If the user asked for "just the TODOs" or "30-second version," scope down.
4. **Open Brain availability** *(if `pending_learnings.md` exists)*. Check the tool list for `capture_thought`. Yes → surface in Step 2. No → don't read; tell the user *"You have pending learnings from previous sessions, but I don't see Open Brain access to save them."*
5. **Cold-start intent** *(if no project notes exist)*. Confirm before bootstrap (Step 1a). Workspace has prior content (defined in Step 1a) → scan + interview combined to fill gaps. Empty workspace → interview only. Skipping is valid; `closingtime` will capture at session end.
6. **Closingtime sibling available.** Check available-skills for `closingtime`. Absent and detectable → append install pointer at brief end (Step 5). Undetectable → proceed silently.

---

## 3. Core Workflow

### Step 1: Locate files

Look at workspace root for `project_index.md`, `project_session.md`, `pending_learnings.md`.

**Filename resolution:** If the exact filename isn't found, check case variants (`Project_Index.md`, `Project_Session.md`, etc.) and common alternatives (`project.md`, `session_log.md`). Use whatever exists; don't create duplicates.

Branch:
- **Both project files present** → Step 2.
- **Only `project_session.md`** (history but no current state) → reconstruct a draft `project_index.md` from the last 5–10 session entries (Summary from recent "Done" + "Decisions"; TODOs from "Next" items not yet completed; Key Files from `git log` and file mentions). Confirm with user, write it. Continue to Step 2.
- **Only `project_index.md`** → continue to Step 2.
- **Neither present** → Step 1a (cold-start), then jump to Step 5.

### Step 1a: Cold-start bootstrap *(only when no notes exist)*

Pre-flight item 5 already confirmed user opt-in.

**Workspace has prior content** (git repo with ≥1 commit, a `README`, or ≥3 source files):
1. Scan: `git log --oneline -20`, head of `README.md`, top-level files (`ls`), language manifest (`package.json`, `pyproject.toml`, etc.) if present.
2. Draft `project_index.md` — Project Name from repo or README, Summary from README intro, Key Files from observation, leave People blank.
3. Ask the user to fill gaps and confirm: name, people, anything missing from the summary.
4. Write the final file with user-confirmed content.

**Workspace is empty** (none of the above):
1. Confirm: *"This directory looks empty — is this the right place for the project?"* If no, ask the user to navigate elsewhere and re-invoke. If yes, continue.
2. Ask: project name, people involved, one-line purpose.
3. Write a minimal `project_index.md`.

Cold-start files are written in English by default. If the user requests another language, follow their preference.

**After bootstrap:** tell the user *"Project notes set up. Session #1 will log when you run `closingtime` at the end."* Skip Steps 2–4. Go to Step 5.

### Step 2: Read project files

- `project_index.md` → read in full (designed under 400 words; primary context load).
- `project_session.md` → read only the **last 2 entries**. Use `tail` or partial-read; don't load the whole file. Skip if absent.

### Step 3: Brief the user

Concise, scannable. ≤ 250 words:

- **One sentence:** project state (from index Summary).
- **Last session's `Next:`** — today's starting point. (Skip if no session history.)
- **Top 3 active TODOs** with priority labels.
- **Flagged:** blockers, stale ⚠️ TODOs, time elapsed if it's been a while.

End with options. Default: *"Ready to pick up, want to adjust priorities first, or focus on something else?"* If `pending_learnings.md` exists and Open Brain is available, include a fourth option: *"...or review the N pending learnings from last session?"*

### Step 4: Post-brief actions *(only if user picked option 2 or 4 from Step 3)*

**If "adjust priorities first":** Walk the user through what to reorder, re-prioritize, or remove. Update `project_index.md` with the changes — this is a permitted edit during the opening hand-off (see Section 1 boundary). Re-display the updated TODO list before continuing to Step 5.

**If "review pending learnings"** *(also requires `pending_learnings.md` exists AND Open Brain available)***:** Follow `closingtime` Step 4 (search connections, suggest types, save with explicit user approval, delete the file). If the user says "later" or "skip" partway through, leave remaining items untouched. Don't silently delete.

### Step 5: Hand off

The brief (and any pending review) is the deliverable. Don't pre-emptively start working on the top TODO; the user drives the next action.

If pre-flight item 6 flagged `closingtime` as absent: append once after the brief — *"FYI: `closingtime` isn't installed in this harness. You'll need it to log sessions. Install: https://github.com/benjaminreal/MetaClaude#install"*

<!-- TODO: update install URL once v2.0 closingtime + v1.0 newbeginning ship as GitHub Releases. Likely target: a release-assets page or the README's #install anchor (which itself may need a refresh). -->

---

## 4. Harness Adaptations

The skill's contract is: read project notes and deliver a brief. Everything else is optional and degrades cleanly. The harness exposes what it has; this skill works with whatever it gets.

**Required:**
- **Read files.** If unavailable, ask the user to paste `project_index.md` and the last 2 entries of `project_session.md`; brief from the paste.
- **Converse with the user.** To deliver the brief and resolve hand-off options.

**Optional capabilities (graceful degradation):**

| Capability | Used by | If missing |
|---|---|---|
| Write / Edit files | Cold-start (Step 1a), priority adjustment (Step 4), index reconstruction (Step 1) | Output the proposed file content as text; ask user to save it manually |
| Shell access (`git log`, `ls`, `tail`) | Cold-start scan (Step 1a), efficient tail-reads (Step 2) | Read whole files; ask user to summarize repo structure during cold-start |
| Tool-list introspection | Open Brain check (Pre-flight 4) | Assume Open Brain unavailable; tell user pending learnings will wait |
| Skill-list introspection | Closingtime check (Pre-flight 6) | Skip the install pointer; assume `closingtime` is present |
| Transcript / session-log access | Optional enrichment (corroborate last session's "Done") | Trust the project notes as the source of truth |

**Path-selection preference:** prefer the most efficient available — `tail` over read-whole-file, `Read` with offset over loading the full file, native skill-list introspection over filesystem checks.

**Unknown harness fallback:** assume all optional capabilities present, try them, degrade on first error. Tell the user when something didn't work.

---

## 5. Decision Rules

Cross-cutting rules not bound to a single step. (Per-step branches and conditional firing live in Sections 2 and 3.)

| Situation | Action |
|---|---|
| User says "skip" any step | Respect it. The skill serves the user, not its process. |
| Long gap since last session (>14 days, by `Updated:` field or git timestamps) | Note elapsed time in the brief; suggest a TODO/decision staleness check before the user dives in. |
| User invokes mid-session ("remind me where we are" rather than actual opening) | Brief anyway — same skill works mid-flow. |
| User picks "adjust priorities first" from the hand-off | Permitted edit to `project_index.md` — the only write newbeginning makes outside cold-start. After persisting, return to the brief's hand-off. |
| User picks "focus on something else" from the hand-off | Step out cleanly. Don't push toward the top TODO; don't re-offer the brief. The skill's job is done. |
| `project_index.md` and `project_session.md` disagree (e.g., index lists TODO X but a recent session marked X done) | Trust the session log (chronological truth); flag the drift to the user; offer to reconcile at next `closingtime`. |
| Cold-start scan finds conflicting signal (repo name ≠ README title ≠ user expectation) | Surface the conflict during the gap-fill interview; let the user choose. Don't pick. |

---

## 6. Eval Criteria

Three lenses. Different failure modes get different responses.

**Output quality** (does the brief look right?)
- **Snappy:** brief ≤ 250 words; total reads + brief ≤ 2.5K tokens. Section 1's "feel instant" is the goal; these are the proxies.
- **`Next:` surfaced:** the last session's `Next:` field is named explicitly in the brief — it's the handoff, and burying it defeats the file format's design.
- **Honest about gaps:** if `Next:` was empty, blockers absent, or session history thin, the brief says so. Don't paper over.
- **No fabrication:** every claim traces back to a line in the files. "Files don't say" is a valid statement; inference is not.

**Workflow correctness** (did the right path fire?)
- **Right Step 1 branch:** the branch taken matches observed file state (both / session-only / index-only / neither).
- **Edits gated:** any write to `project_index.md` happened only during cold-start (Step 1a) or "adjust priorities" (Step 4); cold-start writes were user-confirmed before persisting.
- **Conditionals respected:** Open Brain unavailable → no read of `pending_learnings.md`, no review option offered. Closingtime sibling absent → install pointer appended at hand-off.
- **Hand-off as single question:** the 3-or-4 post-brief options were offered together, not stacked.
- **Brief, then stop:** the skill doesn't begin executing the top TODO unless the user explicitly says go.

**Failure response**
- **Restart the brief** on fabrication or boundary violations (wrote a file outside permitted moments, fabricated a TODO, claimed something the files don't support).
- **Patch in place** on length, pacing, or wording — trim a sentence; don't redo the whole brief.

---

## 7. Version & Changelog

**v1.0.0 — 2026-05-01**
- **Initial release.** Extracted from `closingtime` v1.0's `newbeginning` mode. Triggers narrowed to opening-only phrases; closing delegated to sibling `closingtime` v2.0+.
- **Cold-start bootstrap (Step 1a):** newbeginning can initialize a `project_index.md` on a project that's never used these skills — scan + interview when the workspace has prior content, interview-only when empty.
- **Index reconstruction:** when only `project_session.md` exists, newbeginning reconstructs a draft index from the last 5–10 entries.
- **Optional integrations gated:** Open Brain (`capture_thought`) checked before reading `pending_learnings.md`; sibling `closingtime` checked at hand-off and install pointer appended if absent.
- **Hand-off as a single question:** brief closes with 3–4 options (pick up / adjust priorities / focus elsewhere / review pending learnings). "Adjust priorities" is the only edit newbeginning makes outside cold-start.
- **Capability-based harness adaptation:** the skill enumerates capabilities and degradation rules rather than naming specific products.
