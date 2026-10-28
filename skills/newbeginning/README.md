# newbeginning

> *"Every new beginning comes from some other beginning's end."*

## Why this skill?

When you start a new session and ask an LLM "where did we leave off?" in a multi-session project, it has no memory of your last conversation. Without structured notes, it has to scan your project from scratch — listing files, reading source code, checking git history — burning through tokens and context window just to reconstruct what you already knew yesterday. On a large project that can cost thousands of tokens before any real work begins, and the context it builds is noisy because it's guessing at priorities, not reading them.

**newbeginning** solves this. It reads compact project notes (~400 words) left by its sibling skill [`closingtime`](../closingtime/), queries the Supabase Tasks database for current task state, and delivers a focused brief capped at 250 words, from a bounded set of reads. You get the same situational awareness in seconds, with a clean context window ready for actual work.

**Version:** 2.2.2 candidate

Phase 4 behavioral validation passed on earlier candidates; the repairs in
this version still need a fresh behavioral check and an independent
transferability review (the round-2 review failed both skills). It is not
certified for deployment. A public summary of the review status is in
[`skills/_shared/validation/phase4_5/`](../_shared/validation/phase4_5/README.md).
See [HANDOFF.md](HANDOFF.md) for prerequisites, limits, and recovery.

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/newbeginning ~/.claude/skills/newbeginning

# Project-scoped (available only in this project)
cp -r skills/newbeginning .claude/skills/newbeginning
```

**Codex** — copy the folder to `~/.codex/skills/newbeginning` and invoke it as `$newbeginning`.

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

You'll get a short summary (250 words or fewer, in your language) covering:

- **Project state** — one sentence on where things stand
- **Last session's handoff** — the "Next" items from your previous `closingtime` wrap-up. This is today's starting point.
- **Top 3 tasks** — from Supabase `task_urgency`, with priority labels, only when the rows were read and fingerprinted in this session
- **Flags** — blockers, DB-flagged tasks, review-due tasks, due dates, or a note if it's been a while since your last session

Then it asks what you'd like to do:

1. **Pick up** where you left off
2. **Discuss a task** — leave any creation for session work
3. **Focus on something else** — the skill steps aside, no pressure

The final evidence line reports instruction state, instruction/projection bytes,
and the complete brief's word count.

### What it won't do

newbeginning is read-only except approved first-time index setup or index
reconstruction. It won't start your top task, log the session, create tasks,
change pending learnings or capture to Open Brain. Those requests wait for
session work or `closingtime`; the opening skill says so and stops.

---

## How It Works (Under the Hood)

The skill follows a 7-part internal structure. You don't need to know this to use it, but it helps if you want to understand why it behaves a certain way or if you're adapting it.

### 1. Purpose & Scope
Defines the boundary: brief and hand off, nothing more. All session logging and state updates belong to `closingtime`.

### 2. Pre-flight Checklist
Before reading project notes, the skill confirms it's in the right workspace, resolves instruction files, records which optional capabilities (Tasks DB, Open Brain) are working, and honors a request for a shorter brief. This prevents it from briefing the wrong project or referencing tools that aren't there.

### 3. Core Workflow
The main logic. Adapts to five situations depending on which project files exist:

| What's in your workspace | What happens |
|---|---|
| Both `project_index.md` + `project_session.md` | Brief from the helper's bounded projection (index and last two entries) plus task brief from Supabase |
| Only `project_session.md` (no index) | Reconstructs a draft narrative index from recent sessions, confirms with you, then briefs |
| Only `project_index.md` (no history) | Briefs from the index and Supabase tasks; notes there's no session history yet |
| Nothing (new project) | Offers cold-start setup, then hands off |
| A sync-conflict copy or contradiction | Stops and names it; reconciliation needs separate approval |

### 4. Harness Adaptations
The skill works across Claude Code, Cowork, and other environments. It requires Python 3, shell access, file reading and conversation for its verified paths — Supabase Tasks DB, Open Brain and skill-list introspection are optional and degrade gracefully. Without Python or shell, only unverified drafts are available. If Supabase is unavailable, it names the exact state and treats any markdown TODO block as possibly stale, read-only context, not as current task state.

### 5. Decision Rules
Behavioral guardrails: respects "skip" at any point, stops when the index and session log contradict each other (a merely older index is reported as a gap), works mid-session if you just want a refresh (not only at session start), and surfaces conflicts rather than guessing. Dropbox/Syncthing conflicts and iCloud/Finder numbered continuity copies stop the brief. Copies of non-continuity files, subfolders and OneDrive names are not covered.

### 6. Eval Criteria
How the skill judges its own output — the brief is 250 words or fewer, the "Next" field is front and center, task claims come from a fingerprinted `task_urgency` read, counts and dates come from the helper, and it never fabricates information that isn't in your project files or the DB result.

Opening is read-only except an approved index setup/reconstruction. Requests to
create tasks, change pending learnings or capture to Open Brain are handed back
for session work or closingtime. New evidence expires after six hours (at most
120 seconds ahead); one draft can be approved per invocation. Later independent
helper chains use a new envelope; capture over fifteen minutes after start is
refused. Any reported count uses count-words on the final text after all edits. Portable journal
identity permits remounts. Conflicts in non-continuity iCloud copies remain a
limit; see `references/recovery.md` for the lock, aliases and recovery rules.

### 7. Version & Changelog

**v2.2.2 candidate** — 2026-10-28
- Real project logs no longer block: `# Session Log — …` titles, subheadings such as
  `## Session Context`, letter-suffixed supplements (`#12A`) and v1 `## Session N —`
  headings are read as legacy; new entries continue after the highest number. Open
  Brain is `absent` only when its tools are not listed.

**v2.2.1 candidate** — 2026-10-28
- Optional append-only learning staging, exact operation scopes, final-text counts
  and a new envelope per helper call chain.

**v2.2.0 candidate** — 2026-10-28
- Round-3 scope reduction, portable recovery, project lock, target preflight,
  shared history parsing and evidence/approval limits.

**v2.1.0 candidate** — 2026-10-27
- Phase 4.5 repairs: Dropbox and iCloud conflict names; repositories without
  commits; evidence tied to one project folder; stricter receipt times and
  project identity; envelope constructor and recipes; its own index template
  for first-time setup; the brief ends with the evidence line after the
  hand-off question.

**v2.0.2 – v2.0.7 candidates** — 2026-10-08 to 2026-10-27
- Phase 4 fixes: no task claim without a fingerprinted receipt; instruction
  files read explicitly; absolute dates against the local date; helper-computed
  word counts, receipt times and git facts; replies follow the owner's
  language; exactly three hand-off options plus pending learnings.
- Full details are in SKILL.md section 7.

**v2.0.1 candidate** — 2026-08-25
- Applies the bilingual candidate-quality contract during pending-learning
  review and after owner edits.

**v2.0.0 candidate** — 2026-08-05
- Uses a bundled bounded-snapshot and evidence-envelope runtime.
- Adds explicit bootstrap, reconstruction, conflict, and four-state capability paths.
- Keeps continuity files compatible with earlier releases; deployment waits for validation.

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
