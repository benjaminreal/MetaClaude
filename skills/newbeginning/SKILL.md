---
name: newbeginning
description: "Session-opening brief for multi-session projects. Reads bounded project continuity notes, obtains current Tasks DB evidence when available, handles bootstrap and index-reconstruction recovery, and returns a concise status brief without starting work. MUST trigger on: 'newbeginning', 'new beginning', 'where did we leave off', 'what were we working on', 'pick up where we left off', 'catch me up', 'start session', 'open session', 'resume work', 'whats the status', 'brief me on this project'. Sibling skill: closingtime — use it when wrapping up a session."
metadata:
  version: "2.0.3"
---

# newbeginning

> *"Every new beginning comes from some other beginning's end."*
> — Semisonic, 1998

Resume an ongoing project from bounded, evidence-backed continuity state. Brief
the user, offer one hand-off question, then stop.

## 1. Purpose & Scope

Use this skill to orient at session start or whenever the user asks where the
project stands. Read narrative state from project notes and task state from a
current Tasks DB receipt. The live `task_urgency` table is authoritative for
task state. Never infer a live task claim from memory or the Markdown mirror.

Permitted writes are limited to:

- an explicitly approved `RECOVERY_BOOTSTRAP` or `RECOVERY_RECONSTRUCT` index;
- an explicitly approved post-brief Tasks DB task creation;
- approved Open Brain captures during pending-learning review.

Do not log the session, rewrite routine narrative state, select a task for the
user, or begin executing the hand-off. Those belong to `closingtime` or the
user's next instruction.

### Runtime resources

- Run deterministic local work through `scripts/runtime_cli.py`.
- Read `references/runtime_contract.md` when building or diagnosing an evidence
  envelope.
- Read `references/task_operations.md` only when querying or changing tasks.
- Read `references/candidate_quality_contract.md` only when pending-learning
  review or wording revision is selected.

Keep scratch envelopes and returned-row files outside the repository working
tree. If the helper is unavailable, name that degraded state; do not claim its
projection, validation, or conflict checks ran.

## 2. Pre-flight Checklist

1. **Resolve workspace and scope.** Walk to the project root containing the
   continuity files or git root. At a portfolio root, confirm project versus
   cross-project scope before reading project notes.
2. **Resolve instructions (`INSTRUCTION_RESOLUTION`).** Check, in order:
   - instruction files at the project root — use them;
   - instruction files in ancestor directories — resolve and read them
     explicitly; do not assume the harness walks ancestors;
   - no instruction file — state `instructions_absent` and continue.
   If resolved task-tracking instructions conflict, enter `conflicted` and stop.
3. **Observe capabilities.** Local capabilities are booleans:
   `shell_available`, `git_available`, `temporary_workspace_available`, and
   `parallel_read_only_available`. `tasks_mcp` and `open_brain` are each one of:
   `absent`, `present_unauthenticated`, `present_wrong_scope`, or `working`.
   Only a successful read in this invocation establishes `working`.
4. **Confirm brief depth.** Default to project state, latest `Next:`, top three
   tasks, blockers/flags, and one hand-off question. Honor a shorter request.
5. **Check sibling availability.** If `closingtime` is detectably absent, add one
   install pointer after the brief. Do not turn this into setup work.

## 3. Core Workflow

### `OBSERVATION_GATE` — snapshot and branch

Run `snapshot <workspace-root>`. Treat its projection, hashes, filename
resolution, parse warnings, and sync-conflict list as local evidence. Detect one
branch:

| Branch | Observed state | Action |
|---|---|---|
| `N-normal` | index and session log present | Continue to evidence collection |
| `N-index-only` | index only | Brief and name absent session history |
| `RECOVERY_RECONSTRUCT` | session log only | Draft an index, approve, write, verify, recapture |
| `RECOVERY_BOOTSTRAP` | neither file | Confirm location; scan content or interview; approve, write, verify, recapture |
| `N-conflicted` | parse contradiction or sync conflict | Stop; surface exact conflict; require separate reconciliation approval |

#### `RECOVERY_RECONSTRUCT`

Use the most recent five to ten entries plus observed git/file evidence to draft
`project_index.md`. Preserve unknown people or purpose fields as unknown. Show
the entire proposed file and obtain explicit approval before writing. Verify
the saved content, then run a fresh snapshot before continuing.

#### `RECOVERY_BOOTSTRAP`

If the workspace has a commit, README, or at least three source files, scan
those bounded signals and draft the index; ask the user to confirm name, people,
and purpose. If the workspace is empty, confirm it is the intended directory and
interview only. Write a minimal English `project_index.md` after approval,
verify it, and report that Session #1 will be logged by `closingtime`.

### Task evidence and envelope validation

If `tasks_mcp` is available, read `references/task_operations.md`, run the
appropriate current slice, save returned rows in scratch, and create a current
receipt. If it is non-working, create a named unavailable receipt and say:

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

Use only the validated bounded projection:

| Measure | Bound |
|---|---:|
| Project index | Full index within the helper projection |
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
6. one question offering pick up, create a task, or focus elsewhere; add
   pending-learning review only when the file exists and Open Brain is working.

Do not begin a task after emitting the brief.

### Allowed post-brief actions

For task creation, itemize the intended DB mutation, obtain explicit
approval, place that M3 scope and approval in a fresh envelope, and run
`validate` before the write. Use `returning`, rerun the current slice, and show
the verified result. Do not edit the Markdown task mirror.

For pending-learning review, use the shared `PENDING_LEARNING_LIFECYCLE`:
search each candidate or record the named unavailable state, present wording,
capture only approved items, and delete or retain the pending file according to
the user's explicit disposition. Read and apply
`references/candidate_quality_contract.md` before presenting or revising a
candidate and again after owner edits; show the complete repaired wording and
obtain fresh approval before capture. Language precedence is explicit user
preference, then the dominant session language when it is English or Spanish,
then English. Never cite `closingtime` by step number.

## 4. Harness Adaptations

**Required:** file reading and conversation. If file reading is unavailable,
ask the user to paste the index and last two session entries and label the local
snapshot helper unavailable.

**Optional capabilities:**

| Capability | Working path | Degraded path |
|---|---|---|
| Bundled Python runtime | Snapshot, projection, envelope validation | Name helper unavailable; do not claim its checks |
| Git | Adds head/dirty evidence | `git_available: false`; continue |
| Tasks MCP | Current tasks and approved creation | Named four-state warning; frozen mirror only |
| Open Brain | Review and capture approved pending items | Do not read pending content; say it must wait |
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
- The brief is at most 250 words, surfaces `Next:`, names gaps, and ends with one
  hand-off question.
- The skill stops after the brief unless the user chooses an allowed action.
- `instruction_bytes_loaded`, `projection_bytes_emitted`, and `brief_words` are
  reported in release evidence; total-token guesses are not a gate.
- `project_index.md`, `project_session.md`, and `pending_learnings.md` remain
  byte-format compatible with v1 readers.
- Pending-learning wording reviewed in this skill follows the candidate-quality
  contract and is never silently changed after approval.

On fabrication, unapproved mutation, or provenance failure, restart from
`OBSERVATION_GATE`. On wording or length failure, patch the brief in place.

## 7. Version & Changelog

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
is canonical source only; deployment waits for Phases 4 and 5.
