# closingtime

> *"You don't have to go home, but you can't stay here."*

## Why this skill?

If you work on long-running projects across multiple sessions, you know the problem: every time you start a new conversation, the model has no memory of what came before. You lose decisions, context, and momentum. You can try to summarize manually, but at the end of a long session you'll miss things, and git log alone doesn't capture the *why* behind decisions or what you intended to do next.

**closingtime** captures your session while the full context is still in the model's memory. It drafts a structured entry (~300 words), updates a compact project index (~400 words), and extracts insights worth keeping long-term. Together with its sibling [`newbeginning`](../newbeginning/), this creates a continuity loop: closingtime writes the notes, newbeginning reads them — getting you back to productive work in ≤ 2.5K tokens instead of thousands spent scanning files and guessing at priorities.

**Version:** 2.0.0

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/closingtime ~/.claude/skills/closingtime

# Project-scoped (available only in this project)
cp -r skills/closingtime .claude/skills/closingtime
```

**GitHub CLI** (v2.90.0+):

```bash
gh skill install benjaminreal/MetaClaude closingtime --agent claude-code
```

**Cowork:** Import the `.skill` file from the [GitHub Releases](https://github.com/benjaminreal/MetaClaude/releases) page.

> If this is the first skill you install and `~/.claude/skills/` didn't exist before, restart Claude Code so it picks up the new directory.

---

## How to Use

Say any of these when you're done working:

> `closingtime` · `closing time` · `close session` · `wrap up` · `we are done for now` · `end session` · `log this session` · `save the session` · `lets close this out` · `time to wrap`

The skill gathers what happened, drafts a summary, and shows it to you for review before saving anything.

### Session entry

Appended to `project_session.md`:

- Focus, Done, Decisions, Next, Blockers
- The **Next** field is the most important — it's what `newbeginning` will lead with next time

### Project index update

Rewrites `project_index.md` to reflect current state:

- Summary rewritten to describe where things stand now
- Key Decisions and Active TODOs updated
- Key Files rebuilt from what's relevant now
- Stale TODOs (3+ sessions) flagged for your attention

### Learning candidates

Optional, via Open Brain:

- Insights, patterns, or connections worth remembering beyond this project
- Presented for your review — nothing saved without your explicit approval
- If you skip or defer, candidates are stored in `pending_learnings.md` for next time

### The closing ritual

After everything is saved, you'll see:

```
Session #N logged ✓
Project index updated ✓
[N] learning candidates ready for review ✓
```

Followed by the closing line:

> *"You don't have to go home, but you can't stay here. Session closed."*

### What it won't do

- Start without showing you the draft first — you always review before it writes
- Save insights to Open Brain without your explicit approval
- Read the full session history — it only checks the last entry for the session number
- Replace `newbeginning` — it doesn't brief you on past state or pick the next task

---

## How It Works (Under the Hood)

The skill follows a 7-part internal structure. You don't need to know this to use it, but it helps if you want to understand behavior or adapt it.

### 1. Purpose & Scope
Defines the boundary: capture, update, extract, close. Opening briefs and session resumption belong to `newbeginning`.

### 2. Pre-flight Checklist
Before gathering anything, the skill confirms: right workspace, right project, entry depth (full or short), and whether Open Brain is available and desired. This prevents writing to the wrong project or attempting tools that aren't there.

### 3. Core Workflow
Five steps:

| Step | What happens |
|---|---|
| 1. Gather | Reads git diff, conversation history, file changes, transcript (if available) |
| 2. Write session entry | Drafts → user reviews → appends to `project_session.md` |
| 3. Update index | Rewrites `project_index.md` to reflect current state |
| 4. Extract learnings | Identifies candidates, searches Open Brain for connections, presents for approval |
| 5. Close out | Confirmation checkmarks + closing line |

### 4. Harness Adaptations
The skill works across Claude Code, Cowork, and other environments. It requires file writing and conversation — everything else (git access, transcript tools, Open Brain) is optional and degrades gracefully. If something isn't available, it tells you and works around it.

### 5. Decision Rules
Behavioral guardrails: respects "skip" at any point, handles first-ever sessions (creates both files), flags stale TODOs, manages archived decisions overflow, and ensures the minimum viable handoff (`Next:` field) is always populated even in rushed closes.

### 6. Eval Criteria
Three lenses — output quality (entry ≤ 300 words, index ≤ 400 words, no duplication), workflow correctness (draft shown before writing, Open Brain gated on approval, ritual executed), and failure response (restart the step on boundary violations, edit in place on length/wording).

### 7. Version & Changelog

**v2.0.0** — 2026-05-01 — BREAKING
- `newbeginning` mode extracted to its own skill.
- Triggers narrowed to closing-only. Mode-detection removed.
- Capability-based harness adaptations (Required/Optional table).
- 3-bucket eval criteria (output quality / workflow correctness / failure response).

**v1.0** — 2026-04-09
- Initial release. Single skill, two modes (`closingtime`, `newbeginning`).

---

## Pair with newbeginning

closingtime writes. newbeginning reads. Together they maintain continuity across work sessions:

1. Start a session → `newbeginning` briefs you
2. Do your work
3. End the session → `closingtime` captures what happened

You can use either one independently, but they're designed as a pair. Install both for the full loop.

---

_Part of [MetaClaude](https://github.com/benjaminreal/MetaClaude) — a personal skills workspace._

_The Open Brain integration uses [Open Brain](https://github.com/NatheBJ/open-brain) by Nathe B. Jones._

_"Closing Time" — Semisonic, 1998. Written by Dan Wilson._
