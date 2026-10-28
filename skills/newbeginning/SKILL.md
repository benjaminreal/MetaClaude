---
name: newbeginning
description: "Session-opening brief for multi-session projects. Reads bounded project continuity notes, obtains current Tasks DB evidence when available, handles bootstrap and index-reconstruction recovery, and returns a concise status brief without starting work. MUST trigger on: 'newbeginning', 'new beginning', 'where did we leave off', 'what were we working on', 'pick up where we left off', 'catch me up', 'start session', 'open session', 'resume work', 'whats the status', 'brief me on this project'. Sibling skill: closingtime — use it when wrapping up a session."
metadata:
  version: "2.2.2"
---

# newbeginning

> *"Every new beginning comes from some other beginning's end."*
> — Semisonic, 1998

Brief from bounded continuity evidence, offer one hand-off question, then stop.

## 1. Purpose & Scope

Orient at session start or on request. Read project notes and a
current Tasks DB receipt. The live `task_urgency` table is authoritative for
task state. Never infer a live task claim from memory or the Markdown mirror.

Permitted writes are limited to an explicitly approved `RECOVERY_BOOTSTRAP`
or `RECOVERY_RECONSTRUCT` index through index-only freeze/approve/write-approved.
Task creation, pending-learning edits/dispositions/deletion and Open Brain
captures belong during the session or at closingtime: say so and stop.

Do not log, rewrite routine state, select a task, or execute the hand-off;
wait for the user's next instruction.

### Runtime resources

- Run deterministic local work through `scripts/runtime_cli.py`.
- Read `references/recovery.md` before persistence/recovery; use
  `references/envelope_examples.md` for constructor and receipt recipes.
- Read `references/runtime_contract.md` when building or diagnosing an evidence
  envelope.
- Read `references/task_operations.md` only when querying tasks.
- Read `references/candidate_quality_contract.md` only for read-only candidate searches.

Keep scratch envelopes and returned-row files outside the repository working
tree. If the helper is unavailable, name that degraded state; do not claim its
projection, validation, or conflict checks ran.

## 2. Pre-flight Checklist

1. **Resolve workspace and scope.** Walk to the project root containing the
   continuity files or git root. At a portfolio root, confirm project versus
   cross-project scope before reading project notes.
2. **Resolve instructions (`INSTRUCTION_RESOLUTION`).** Use the snapshot's
   `instructions` field, which applies this order:
   - instruction files at the project root — use them;
   - instruction files in ancestor directories — read each listed file
     explicitly; do not assume the harness walks ancestors;
   - no instruction file — `instructions_absent`; continue.
   Explicitly read each unique path in `files` and `ancestor_files`, including files the harness may already have loaded; count each successfully read path once. If task-tracking rules conflict,
   enter `conflicted` and stop. Record the state in the evidence line.
3. **Observe capabilities.** Local capabilities are booleans:
   `shell_available`, `git_available`, `temporary_workspace_available`, and
   `parallel_read_only_available`. `tasks_mcp` and `open_brain` are each one of:
   `absent` (tools not listed), `present_unauthenticated`, `present_wrong_scope`,
   or `working` (a successful read in this invocation).
4. **Confirm brief depth.** Default to project state, latest `Next:`, top three
   tasks, blockers/flags, and one hand-off question. Honor a shorter request.
5. **Check sibling availability.** If `closingtime` is detectably absent, add one
   install pointer after the brief. Do not turn this into setup work.

## 3. Core Workflow

### `OBSERVATION_GATE` — snapshot and branch

Run `new-envelope <workspace-root>` to capture evidence and helper-stamped
start and `captured_at`. For each later helper call chain use a new envelope;
never copy start times. Replace `unprobed` states before validation.
Use `snapshot <workspace-root> --entries 10` for reconstruction. Treat its projection, hashes, filename
resolution, parse warnings, and sync-conflict list as local evidence. State the
branch and changed files only from its `git` fields. Detect one branch:

| Branch | Observed state | Action |
|---|---|---|
| `N-normal` | index and session log present | Continue to evidence collection |
| `N-index-only` | index only | Brief and name absent session history |
| `RECOVERY_RECONSTRUCT` | session log only | Draft an index, approve, write, verify, recapture |
| `RECOVERY_BOOTSTRAP` | neither file | Confirm location; scan content or interview; approve, write, verify, recapture |
| `N-conflicted` | parse contradiction or sync conflict | Stop; surface exact conflict; require separate reconciliation approval |

#### `RECOVERY_RECONSTRUCT`

Use `snapshot --entries 10` for the most recent five to ten entries plus observed git/file evidence to draft
`project_index.md`. Preserve unknown people or purpose fields as unknown. Show
the entire proposed file after index-only `freeze-draft`; obtain explicit approval
before writing through exact-scope `approve-draft` and
`write-approved --expect <sha256|absent>`. Use the shipped
`references/index_template.md`, verify the saved content, then recapture with
a fresh snapshot before continuing.

#### `RECOVERY_BOOTSTRAP`

If the workspace has a commit, README, or at least three source files, scan
those bounded signals and draft the index; ask the user to confirm name, people,
and purpose. If the workspace is empty, confirm it is the intended directory and
interview only. Write a minimal English `project_index.md` after approval,
use index-only freeze/approve/write-approved from `references/recovery.md`,
verify it, and report that Session #1 will be logged by `closingtime`. An unborn
git branch (no commits) is normal; corrupt git explicitly degrades.

### Task evidence and envelope validation

If `tasks_mcp` is available, read `references/task_operations.md`, run the
appropriate current slice, save returned rows in scratch (or pass them on stdin
with `fingerprint-rows -` when scratch writes are blocked), and create a current
receipt whose time is the helper's `fingerprinted_at` unless the tool result
carries its own; never type a time. If the rows cannot be fingerprinted or the envelope cannot be
validated, there is no current receipt: do not present tasks as current, label
any task list "unverified" with the reason, and name the gap. If it is
non-working, create a named unavailable receipt and say:

- `absent`: "Tasks DB isn't available in this harness."
- `present_unauthenticated`: "The Tasks DB is present but not authorized —
  authorize it, then re-run."
- `present_wrong_scope`: "The Supabase server is authorized for a different
  project — reconfigure the scope."

In every non-working state, treat frozen markdown TODOs as read-only, possibly
stale context. Never call them current or authoritative.

Assemble the scratch evidence envelope with no mutation scope for a routine
opening. Run `validate`. A failed envelope cannot support the brief: fix the
input once, otherwise name the failure and degrade or stop according to its
code. A sync conflict always stops.

### Opening projection and brief

The helper reads whole files and emits a bounded projection. Report
`unfinished_operations` and direct recovery to `resume`; do not start another
close. A non-monotonic history warns; parse ambiguity or semantic narrative contradictions stop; a stale index
date alone is a gap. Use only the validated bounded projection:

| Measure | Bound |
|---|---:|
| Project index | Bounded text; explicitly report truncation |
| Session log | Last two entries |
| Project task slice | 8 rows |
| Portfolio task slice | 20 rows |
| `projection_bytes_emitted` | 16,384 bytes |
| `brief_words` | 250 words |

The brief contains:

1. one sentence on current project state;
2. **Last session's `Next:`** when present;
3. the top three current tasks with priorities only when a current receipt
   exists;
4. blockers, flagged/review-due work, dates, and a gap over fourteen days;
5. the provenance/degraded state and honest gaps;
6. one question offering exactly three options — pick up, discuss a task, or
   focus elsewhere;
7. a final evidence line: `Evidence: instructions <state>; instruction_bytes_loaded <n>; projection_bytes_emitted <n>; brief_words <n>`.
   `instruction_bytes_loaded` is `instruction_budget.skill_md_bytes`, plus the
   bytes of each reference you read, plus each resolved instruction file.

Use absolute session dates. Resolve "today", "yesterday", and gaps only
against the snapshot's `local_date`; never against the UTC date.

The whole reply, including the question and the evidence line, stays within
250 words; `brief_words` counts all of it. After the last edit, run
`count-words -` on the exact final reply sent; report only that count. Write the
brief in the user's explicitly requested language, otherwise in the language
of their message. Do not begin a task after emitting the brief.

### Post-brief boundary — `PENDING_LEARNING_LIFECYCLE`

Stop after the brief. Do not edit the Markdown task mirror. Opening performs
no task creation, pending-file transition or capture. A search remains a read;
`SKIP-openbrain` prohibits search too, which sends candidate text to the service.
Read `references/candidate_quality_contract.md` before presenting or revising
wording as a discussion, including after owner edits; any later capture needs
fresh approval during the session or closingtime. Language precedence is
explicit user preference, then the dominant session language when it is English
or Spanish, then English. These quality rules grant no opening write authority.

## 4. Harness Adaptations

**Required for helper paths:** Python 3, file reading and conversation.
Without Python nothing is persisted; output an unverified brief or index draft only. If file reading is unavailable,
ask the user to paste the index and last two session entries and label the local
snapshot helper unavailable.

**Optional capabilities:**

| Capability | Working path | Degraded path |
|---|---|---|
| Bundled Python runtime | Snapshot, projection, envelope validation | Name helper unavailable; do not claim its checks |
| Git | Adds head/dirty evidence | `git_available: false`; continue |
| Tasks MCP | Current tasks only | Named four-state warning; frozen mirror only |
| Open Brain | Read-only candidate searches | Do not read pending content; say it must wait |
| Parallel reads | Gather independent M0 evidence concurrently | Sequential reads are equivalent |

No model-name branch may change evidence, approval, or mutation rules.

## 5. Decision Rules

| Situation | Action |
|---|---|
| User says skip | Acknowledge and omit that optional path |
| Index and DB task mirror disagree | Current DB receipt wins; mirror remains read-only |
| Index and session narrative disagree | Enter `conflicted`; do not auto-reconcile |
| Long gap | Suggest a staleness check before execution |
| Mid-session status request | Brief normally, then stop |
| User chooses another focus | Step aside without re-offering the top task |
| Invocation is interrupted | Claim only validated observations; name missing evidence |

## 6. Eval Criteria

- `OBSERVATION_GATE` passed or an exact degraded/conflicted state is named.
- Recovery writes were drafted, explicitly approved, and read back before a
  new snapshot.
- Every authoritative task claim traces to a current receipt whose returned-row
  fingerprint validates.
- The brief is at most 250 words, surfaces `Next:`, names gaps, and places one
  hand-off question immediately before the final evidence line.
- The skill stops after the brief and routes requested mutations to the session or closingtime.
- Every brief ends with the evidence line reporting the instruction state,
  `instruction_bytes_loaded`, `projection_bytes_emitted`, and `brief_words`;
  total-token guesses are not a gate. Counts, receipt times, and git facts come
  from helper results; the brief follows the user's language.
- `project_index.md`, `project_session.md`, and `pending_learnings.md` remain
  byte-format compatible with v1 readers.
- Pending-learning wording reviewed in this skill follows the candidate-quality
  contract and is never silently changed after approval.

On fabrication, unapproved mutation, or provenance failure, restart from
`OBSERVATION_GATE`. On wording or length failure, patch the brief in place.

## 7. Version & Changelog

**v2.2.2 — 2026-10-28 — candidate**

- Legacy log headings readable. 2.2.0–2.2.1: index-only opening writes, portable
  recovery, fixed targets, fresh evidence, one approval per invocation.

**v2.1.0 — 2026-10-27 — candidate**

- Phase 4 and 4.5 fixes, packaging: exact canonical scope approval; root/project
  identity and parsed times; conflict/alias stops; read-only git evidence.
- Atomic append intents, conditional rollback, resume and unfinished-operation
  guard; approved local transitions share a lock and explicit preimages.
- Standalone constructor, recipes, recovery/error catalogue and lifecycle rules.
- Prior Phase 4/4.5 results certify only their earlier hashes; fresh eligibility
  and independent recertification remain required. This is not deployment.

**v2.0.7 — 2026-10-27 — candidate**

- Documentation refresh for the Phase 4.5 review (HANDOFF and README); no
  runtime or workflow change.

**v2.0.6 — 2026-10-27 — candidate**

- Phase 4 findings O-01 to O-04: the brief follows the user's language;
  `brief_words` comes from `count-words`; receipt times come from
  `fingerprinted_at`; git facts come from snapshot `git.branch` and
  `changed_paths`; `validate` refuses future receipt times.

**v2.0.5 — 2026-10-27 — candidate**

- Snapshot reports `local_date` and `local_utc_offset`; briefs use absolute
  dates and resolve relative ones against the local date.
- Instruction files are read explicitly and counted once.

**v2.0.4 — 2026-10-27 — candidate**

- Phase 4 fixes: no current-task claim when the receipt cannot be produced;
  `fingerprint-rows`/`validate` accept stdin; the snapshot resolves
  instruction files; every brief ends with an evidence line; the 250-word cap
  covers the whole reply; the hand-off offers exactly three options.

**v2.0.3 — 2026-10-08 — candidate**

- Shared append now requires the session filename in approved M2 scope; first-close audit needs no historical policy.
- Prior preflights remain evidence for earlier package hashes.

**v2.0.2 — 2026-10-08 — candidate**

- Preserved creation-only task guidance and reserved-ID retry protection during package regeneration.
- Earlier validation hashes and transfer certificates do not certify this package.

**v2.0.1 — 2026-08-25 — candidate**

- Added the progressively loaded bilingual candidate-quality contract to
  pending-learning review and owner-edit handling.

**v2.0.0 — 2026-08-05 — candidate**

- Replaced model-authored file scanning with the bounded snapshot/projection
  helper and validated evidence envelope.
- Added explicit bootstrap, reconstruction, and conflicted branches.
- Added four-state external capabilities and three-case instruction resolution.
- Moved schemas, SQL, hashing, and long rationale into bundled scripts and
  progressive-disclosure references.
- Preserved the v1 continuity-file formats and all eleven trigger semantics.

Earlier releases remain in git and GitHub Releases for rollback. This candidate
is canonical source only; deployment waits for Phase 4.5 PASS and Phase 5.
