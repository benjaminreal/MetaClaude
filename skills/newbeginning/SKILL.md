---
name: newbeginning
description: "Session-opening brief for multi-session projects. Reads project_index.md and the last entries of project_session.md from the workspace root, surfaces any pending learnings from the prior closingtime, and delivers a concise status brief: project state, last session's 'Next' items, top active TODOs, blockers. MUST trigger on: 'newbeginning', 'new beginning', 'where did we leave off', 'what were we working on', 'pick up where we left off', 'catch me up', 'start session', 'open session', 'resume work', 'whats the status', 'brief me on this project'. Sibling skill: closingtime — invoke that instead when wrapping up a session."
version: 1.0.0
---

# newbeginning

> *"Every new beginning comes from some other beginning's end."*
> — Semisonic, 1998

Session-opening companion to `closingtime`. Loads the minimum context needed to resume work, briefs the user, and gets out of the way.

---

## 1. Purpose & Scope

**Does:**
- Locate and read the two compact session-continuity files (`project_index.md`, `project_session.md`) at the workspace root
- Surface any unreviewed learning candidates from the prior closingtime (`pending_learnings.md`)
- Deliver a concise status brief: project state, last session's "Next" items, top active TODOs, blockers, staleness flags

**Does NOT:**
- Write or update any project files (that's `closingtime`'s job)
- Read the full `project_session.md` — only the last 2 entries, since the file grows over time
- Capture new Open Brain thoughts (only reviews pending ones if the user wants)
- Decide what to work on next — that's the user's call after the brief

**Use closingtime instead when:** wrapping up a session, logging what happened, extracting learnings, or updating project state.

**Token target:** ~1.5–2.5K tokens total for reads + briefing output. This skill should feel instant.

---

## 2. Pre-flight Checklist

Before reading anything, confirm:

1. **Workspace root identified.** Session-continuity files live at the workspace root, not in subdirectories. If invoked from a subdirectory or worktree, walk up to find the actual project root (the directory containing `project_index.md`, or failing that, the git root).
2. **Right project.** If the workspace contains multiple project subfolders, or the user works on several projects from one shell, confirm which project to brief on before reading.
3. **Brief depth.** Default is "full brief." If the user said something like "just the TODOs" or "30-second version," scope down — don't over-deliver context the user explicitly didn't ask for.

---

## 3. Core Workflow

### Step 1: Locate files

Look for `project_index.md` and `project_session.md` at the workspace root. Also check for `pending_learnings.md` (signal that the prior closingtime left unreviewed candidates).

### Step 2: Handle pending learnings (if any)

If `pending_learnings.md` exists, mention it early — but don't process it yet:

> *"You had unreviewed learnings from the last session. Want to review them now or after we get going?"*

If "now": present the candidates and follow the Open Brain approval flow from `closingtime`'s Step 4 (search for connections, suggest types, save with explicit user approval, then delete the file). If "later" or "skip": leave the file untouched and continue. **Do not silently delete pending learnings.**

### Step 3: Read project files (efficient reads only)

- **`project_index.md`** — read in full. It's designed to stay under 400 words; this is the primary context load.
- **`project_session.md`** — read only the **last 2 entries**. The full file grows over time; reading it whole defeats the skill's purpose. Use `tail` or partial-read; don't load the whole file "for completeness."

### Step 4: Brief the user

Concise, scannable. Aim for ≤ 250 words of output:

- **One sentence:** what this project is and its current state (from `project_index.md` Summary)
- **Last session:** focus on the **`Next:`** items — these are today's starting point
- **Top 3 active TODOs** from the index, with priority labels
- **Flagged items:** blockers, stale TODOs marked ⚠️, time elapsed if it's been a while

End with: *"Ready to pick up, or want to adjust priorities first?"*

### Step 5: Stay out of the way

The brief is the deliverable. Do not pre-emptively start working on the top TODO. The user drives the next action.

---

## 4. Harness Adaptations

This skill works in any harness with file-read access. Adjust by environment:

- **Claude Code (CLI / IDE):** Full file access. Use `Read` for `project_index.md` and a `tail -n` Bash call (or `Read` with `offset`) for the session file's last entries. Git-aware — can check time elapsed via `git log -1 --format=%ar` if `Updated:` is missing or stale.
- **Cowork:** File access works. If a transcript tool is available, you may also skim recent transcript events to corroborate the last session's claimed "Done" — useful if the previous closingtime was hasty. Don't read transcripts verbatim; sample.
- **Claude.ai (chat):** No persistent filesystem in standard chat. Degrade gracefully: ask the user to paste `project_index.md` and the last 2 entries of `project_session.md`. Brief from the pasted content. Skip pending-learnings handling unless the user pastes that too.
- **Codex (OpenAI CLI):** Read tool present but invocation differs. Prefer absolute paths. Tail-equivalent: read with offset rather than loading whole; if not feasible, read whole and explicitly summarize only the last two entries to keep output budget tight.

If the harness is unknown, default to Claude Code behavior and degrade if a tool errors. The skill's contract is the brief — the means of getting there can flex.

---

## 5. Decision Rules

| Situation | Action |
|---|---|
| Both files exist | Standard flow (Steps 1–5) |
| Only `project_session.md` exists | Brief from last 2 entries; note no index; offer to create one at next closingtime |
| Only `project_index.md` exists | Brief from index; note no session history; do not invent past sessions |
| Neither file exists | New project. Offer two paths: (a) brief identity interview now to create `project_index.md`; (b) start working and let the next closingtime capture everything |
| Long gap since last session (>14 days) | Note elapsed time in the brief; suggest a TODO/decision staleness check before diving in |
| Multiple projects detected at workspace root | Ask which to brief on; do not guess |
| User says "skip" any step | Respect it. The skill serves the user, not its process |
| `pending_learnings.md` exists but user defers | Leave the file untouched; mention it remains available for next time |
| User invokes mid-session (not actually opening) | Brief anyway — same skill works for "remind me where we are" mid-flow |

---

## 6. Eval Criteria

Output is good when:

- **Token budget:** total reads + briefing under 2.5K tokens. Over budget usually means too much of `project_session.md` was loaded.
- **Brief length:** ≤ 250 words of conversational output. Over = trim to essentials.
- **`Next:` surfaced:** the last session's `Next:` field is named explicitly in the brief (it's the handoff — burying it defeats the file format's design).
- **Pending learnings raised early:** if `pending_learnings.md` exists, it's mentioned before the TODO list, not buried at the end.
- **No fabrication:** every claim in the brief traces back to a line in `project_index.md` or `project_session.md`. If something seems important but isn't in the files, say "files don't say" — don't infer.
- **No premature work:** the skill briefs and stops. It doesn't begin executing the top TODO unless the user explicitly says go.

If output fails any of these, restart the brief — don't patch.

---

## 7. Version & Changelog

**v1.0.0 — 2026-05-01**
- Initial release. Extracted from `closingtime` v1.0's `newbeginning` mode.
- Behavior is identical to invoking `closingtime` v1.0 and saying "newbeginning" — same workflow, now callable directly without mode disambiguation.
- Added explicit Pre-flight Checklist, Decision Rules table, Eval Criteria, and Harness Adaptations covering Claude Code, Cowork, claude.ai, and Codex.
- Trigger set narrowed to opening-only phrases; closing phrases removed (delegated to sibling skill `closingtime`).
