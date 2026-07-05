# newbeginning

> *"Every new beginning comes from some other beginning's end."*

## Why this skill?

When you start a new session and ask an LLM "where did we leave off?" in a multi-session project, it has no memory of your last conversation. Without structured notes, it has to scan your project from scratch — listing files, reading source code, checking git history — burning through tokens and context window just to reconstruct what you already knew yesterday. On a large project that can cost thousands of tokens before any real work begins, and the context it builds is noisy because it's guessing at priorities, not reading them.

**newbeginning** solves this. It reads compact project notes (~400 words) left by its sibling skill [`closingtime`](../closingtime/), queries the Supabase Tasks database for current task state, and delivers a focused brief in under 2.5K tokens total — reads and output combined. You get the same situational awareness in seconds, with a clean context window ready for actual work.

**Version:** 1.1.0

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/newbeginning ~/.claude/skills/newbeginning

# Project-scoped (available only in this project)
cp -r skills/newbeginning .claude/skills/newbeginning
```

**GitHub CLI** (v2.90.0+):

```bash
gh skill install benjaminreal/MetaClaude newbeginning --agent claude-code
```

**Cowork:** Import the `.skill` file from the [GitHub Releases](https://github.com/benjaminreal/MetaClaude/releases) page.

> If this is the first skill you install and `~/.claude/skills/` didn't exist before, restart Claude Code so it picks up the new directory.

---

## How to Use

Say any of these to start:

> `newbeginning` · `new beginning` · `where did we leave off` · `catch me up` · `start session` · `pick up where we left off` · `whats the status` · `brief me on this project`

That's it. The skill reads your project files and delivers a brief. No setup required if you've already used `closingtime` to close a previous session.

### First time on a project?

If there are no project notes yet, newbeginning offers to set things up for you. It looks at what's already in the directory (git history, README, source files) and asks a few questions — project name, who's involved, what it's about. It creates a lightweight `project_index.md` so future sessions have something to read. You can also skip this and let `closingtime` handle it at the end of your first session instead.

### What the brief looks like

You'll get a short summary (under 250 words) covering:

- **Project state** — one sentence on where things stand
- **Last session's handoff** — the "Next" items from your previous `closingtime` wrap-up. This is today's starting point.
- **Top 3 tasks** — from Supabase `task_urgency`, with priority labels
- **Flags** — blockers, DB-flagged tasks, review-due tasks, due dates, or a note if it's been a while since your last session

Then it asks what you'd like to do:

1. **Pick up** where you left off
2. **Adjust priorities** — reprioritize, park, cancel, or mark tasks done before starting
3. **Focus on something else** — the skill steps aside, no pressure
4. **Review pending learnings** — if your last `closingtime` session left insights you hadn't reviewed yet (requires Open Brain)

### What it won't do

newbeginning is read-mostly by design. It won't start working on your top task, won't log this session, and won't update narrative project state — those are `closingtime`'s jobs. The only time it writes anything is during first-time setup/index reconstruction or when you explicitly ask to adjust task priorities in the Tasks DB, and both require your confirmation first.

---

## How It Works (Under the Hood)

The skill follows a 7-part internal structure. You don't need to know this to use it, but it helps if you want to understand why it behaves a certain way or if you're adapting it.

### 1. Purpose & Scope
Defines the boundary: brief and hand off, nothing more. All session logging and state updates belong to `closingtime`.

### 2. Pre-flight Checklist
Before reading any files, the skill confirms it's in the right workspace, checks whether Open Brain and `closingtime` are available, and asks how much detail you want. This prevents it from briefing the wrong project or referencing tools that aren't there.

### 3. Core Workflow
The main logic. Adapts to four situations depending on which project files exist:

| What's in your workspace | What happens |
|---|---|
| Both `project_index.md` + `project_session.md` | Full narrative brief from both files plus task brief from Supabase |
| Only `project_session.md` (no index) | Reconstructs a draft narrative index from recent sessions, confirms with you, then briefs |
| Only `project_index.md` (no history) | Briefs from the index and Supabase tasks; notes there's no session history yet |
| Nothing (new project) | Offers cold-start setup, then hands off |

### 4. Harness Adaptations
The skill works across Claude Code, Cowork, and other environments. It only requires file reading and conversation — everything else (shell access, Supabase Tasks DB, Open Brain, skill-list introspection) is optional and degrades gracefully. If Supabase is unavailable, it warns you and treats any markdown TODO block as frozen read-only context, not as authoritative task state.

### 5. Decision Rules
Behavioral guardrails: respects "skip" at any point, flags drift between the index and session log, works mid-session if you just want a refresh (not only at session start), and surfaces conflicts rather than guessing.

### 6. Eval Criteria
How the skill judges its own output — the brief should be under 250 words, the "Next" field should be front and center, task claims should come from `task_urgency`, and it should never fabricate information that isn't in your project files or the DB result.

### 7. Version & Changelog

**v1.1.0** — 2026-07-05
- Migrated active task sourcing from per-project markdown TODO blocks to Supabase `task_urgency`.
- Defaults to project-only task briefs, with flagged/review-due tasks surfaced inside the project query.
- Uses cross-project task slices only for portfolio/root invocations or explicit user requests.
- Added graceful degradation for harnesses without Supabase access.

**v1.0.1** — 2026-05-05
- Small corrections to the documentation making sure a new user understand how to use the skill.
- Section Transfer Certifications added to Sections 1–7, asserting each section is executable by a competent external user without needing to ask the LLM for clarification.
- Open Brain defined inline at first mention (Section 1) so users without the framework context aren't blocked.

**v1.0.0** — 2026-05-01
- Initial release. Extracted from `closingtime` v1.0's newbeginning mode.
- Cold-start bootstrap for new projects.
- Capability-based harness adaptation (works across environments).
- Unified hand-off question with 3–4 options.

---

## Pair with closingtime

newbeginning reads. closingtime writes. Together they maintain continuity across work sessions:

1. Start a session → `newbeginning` briefs you
2. Do your work
3. End the session → `closingtime` logs what happened, updates the project index, and extracts learnings

You can use either one independently, but they're designed as a pair. If newbeginning detects that `closingtime` isn't installed, it'll let you know.

---

_Part of [MetaClaude](https://github.com/benjaminreal/MetaClaude) — a personal skills workspace._

_The Open Brain integration uses [Open Brain](https://github.com/NatheBJ/open-brain) by Nathe B. Jones._

_"Closing Time" — Semisonic, 1998. Written by Dan Wilson._
