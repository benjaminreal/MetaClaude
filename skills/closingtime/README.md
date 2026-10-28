# closingtime

> *"You don't have to go home, but you can't stay here."*

## Why this skill?

If you work on long-running projects across multiple sessions, you know the problem: every time you start a new conversation, the model has no memory of what came before. You lose decisions, context, and momentum. You can try to summarize manually, but at the end of a long session you'll miss things, and git log alone doesn't capture the *why* behind decisions or what you intended to do next.

**closingtime** captures your session while the full context is still in the model's memory. It drafts a structured entry (~300 words), updates compact project narrative notes, writes task changes to the Supabase Tasks database, and extracts insights worth keeping long-term. Together with its sibling [`newbeginning`](../newbeginning/), this creates a continuity loop: closingtime writes the notes and task changes, newbeginning reads the notes and queries the task database — getting you back to productive work from a bounded projection instead of thousands of tokens spent scanning files and guessing at priorities.

**Version:** 3.0.10 candidate

Phase 4 behavioral validation passed on 3.0.6 (six fresh sessions in Claude
Code and Codex), with targeted checks of later fixes. Independent
transferability review is recorded outside the package. See
[HANDOFF.md](HANDOFF.md) for prerequisites, limits, and validation status.

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/closingtime ~/.claude/skills/closingtime

# Project-scoped (available only in this project)
cp -r skills/closingtime .claude/skills/closingtime
```

**Codex** — copy the folder to `~/.codex/skills/closingtime` and invoke it as `$closingtime`.

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

Rewrites the narrative parts of `project_index.md` to reflect current state:

- Summary rewritten to describe where things stand now
- Key Decisions updated
- Key Files rebuilt from what's relevant now
- `## Active TODOs` refreshed only as a read-only mirror from Supabase `task_urgency`

### Task updates

Writes approved task changes to the Supabase Tasks database:

- Add new tasks
- Mark tasks done
- Reprioritize or flag tasks
- Park tasks until a review date
- Cancel tasks that should leave the active queue

The markdown TODO block is not the source of truth. It is a generated mirror for offline/at-a-glance use.

### Learning candidates

Optional, via Open Brain:

- Insights, patterns, or connections worth remembering beyond this project
- Written to `pending_learnings.md` first, then shown to you exactly as saved
- Plain, standalone wording in the user's chosen language, or the dominant
  English/Spanish session language
- One central insight per candidate, with uncertainty preserved and volatile
  session IDs, codes, model tokens, and absolute paths kept out of the insight
- Presented for your review — nothing saved without your explicit approval
- If you skip or defer, candidates are stored in `pending_learnings.md` for next time

### The closing ritual

After everything is saved, you'll see:

```
Session #N logged ✓
Tasks DB updated ✓
Project index narrative + task mirror updated ✓
[N] learning candidates ready for review ✓
```

Each line shows the real state (skipped, pending or partial) instead of a
false checkmark. An evidence line follows, then the closing line:

> *"You don't have to go home, but you can't stay here. Session closed."*

### What it won't do

- Start without showing you the draft first — you always review before it writes
- Save insights to Open Brain without your explicit approval
- Read the full session history — the helper reads a bounded projection (index and last two entries)
- Write `project_session.md` directly — only the bundled helper appends, after your approval
- Replace `newbeginning` — it doesn't brief you on past state or pick the next task

---

## How It Works (Under the Hood)

The skill follows a 7-part internal structure. You don't need to know this to use it, but it helps if you want to understand behavior or adapt it.

### 1. Purpose & Scope
Defines the boundary: capture, update, extract, close. Opening briefs and session resumption belong to `newbeginning`.

### 2. Pre-flight Checklist
Before gathering anything, the skill resolves the project root and instruction files, records which optional capabilities (Tasks DB, Open Brain) are working, and settles entry depth and any explicit skips. This prevents writing to the wrong project or attempting tools that aren't there.

### 3. Core Workflow
Seven named gates:

| Gate | What happens |
|---|---|
| Observation | Helper snapshot, current Tasks receipt or named unavailable state, validated evidence envelope |
| Draft | Session entry, index changes and task operations; frozen with `freeze-draft` before you see it |
| Approval | You approve the exact scope; the helper stamps the approval time |
| Concurrency + persistence | Helper append with tail-hash check, readback and journal; index and task writes read back |
| Verification | Every write has a returned result or readback; journal audit |
| Learning | Candidates saved to `pending_learnings.md`, searched in Open Brain, shown as saved; capture needs separate approval |
| Closing | Status lines, evidence line, closing line |

### 4. Harness Adaptations
The skill works across Claude Code, Cowork, and other environments. It requires file writing and conversation — everything else (git access, transcript tools, Supabase Tasks DB, Open Brain) is optional and degrades gracefully. If Supabase is unavailable, it names the exact state, logs the session, and keeps task changes pending without editing the markdown mirror.

### 5. Decision Rules
Behavioral guardrails: respects "skip" at any point, handles first-ever sessions (creates both files), treats Tasks DB state as authoritative, manages archived decisions overflow, and ensures the minimum viable handoff (`Next:` field) is always populated even in rushed closes.

### 6. Eval Criteria
Output quality (entry ≤ 300 words, narrative index concise, no duplication between entry and index, candidates that pass the quality contract), workflow correctness (draft shown and frozen before writing, every write verified, Open Brain capture gated on approval, counts and times taken from the helper), and failure response (restart from observation on boundary violations, edit in place on length/wording).

### 7. Version & Changelog

**v3.0.3 – v3.0.10 candidates** — 2026-10-08 to 2026-10-27
- Phase 4 fixes: no task claim without a fingerprinted receipt; frozen,
  helper-approved draft receipts for every append; helper-computed counts,
  times, git facts and task mirror; replies follow the owner's language;
  candidates are written before they are shown; one closing order.
- Full details are in SKILL.md section 7.

**v3.0.2 candidate** — 2026-08-29
- Matches exact session-number and entry-hash receipts before applying the
  grandfather ceiling, preventing valid historical receipts from appearing as
  orphan records.

**v3.0.1 candidate** — 2026-08-25
- Adds a progressively loaded bilingual learning-candidate quality contract.
- Rechecks owner-edited wording and requires fresh approval for semantic repairs.

**v3.0.0 candidate** — 2026-08-05
- Uses validated evidence envelopes and a collision-safe append/journal helper.
- Adds explicit skip, conflict, interruption, and four-state capability paths.
- Keeps continuity files compatible with earlier releases; deployment waits for validation.

**v2.2.0** — 2026-07-05
- Migrated task state to the Supabase Tasks database.
- `## Active TODOs` is now a read-only mirror regenerated from `task_urgency`.
- Added graceful degradation for harnesses without Supabase access.

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
