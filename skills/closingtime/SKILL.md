---
name: closingtime
description: "Session-closing capture for multi-session projects. Builds current local and Tasks DB evidence, drafts an approval-gated closeout, persists and verifies the session/index/task state, stages learning candidates before review, and closes from receipts. MUST trigger on: 'closingtime', 'closing time', 'close session', 'wrap up', 'we are done for now', 'end session', 'log this session', 'save the session', 'lets close this out', 'time to wrap'. Sibling skill: newbeginning — use it when starting or resuming a session."
metadata:
  version: "3.0.3"
---

# closingtime

> *"You don't have to go home, but you can't stay here."*
> — Semisonic, 1998

Close a project session through observation, draft, approval, verified
persistence, learning review, and a receipt-backed ritual.

## 1. Purpose & Scope

Use this skill when the user ends a multi-session project session. Produce a
v1-compatible session entry and current-state index, write only approved task
changes to the Tasks DB, and preserve learning candidates before presenting
them.

Never mutate project truth, external truth, or repository state before explicit
approval. An M1 scratch envelope outside the repository is permitted before the
draft. Git branch, stage, commit, tag, and push remain M4 operations and require
a separate request in this invocation.

### Runtime resources

- Run local evidence, validation, append, audit, and sync checks through
  `scripts/runtime_cli.py`.
- Read `references/runtime_contract.md` when constructing an envelope or
  handling a helper refusal.
- Read `references/task_operations.md` only when Tasks DB work is in scope.
- Read `references/candidate_quality_contract.md` only when generating,
  reviewing, or revising learning candidates.

The bundled helper is the only sanctioned writer of `project_session.md`. A
direct write is detectable later by `audit`; do not use that as a normal path.

## 2. Pre-flight Checklist

1. **Resolve workspace and project.** Find the project root containing
   continuity files or git root. Confirm one project when the conversation spans
   several.
2. **Resolve instructions (`INSTRUCTION_RESOLUTION`).** Use project-root
   instruction files when present; otherwise explicitly walk ancestors; if none
   exist, record `instructions_absent`. Stop on conflicting task specifications.
   Never name an instruction file as if its location were guaranteed.
3. **Observe capabilities.** Local capabilities are booleans. `tasks_mcp` and
   `open_brain` each use `absent`, `present_unauthenticated`,
   `present_wrong_scope`, or `working`. Only a read in this invocation establishes
   `working`.
4. **Choose depth and skips.** Default entry cap is 300 words; a short session may
   use three to five lines. Ask about ambiguous project scope, not routine facts.
   Record any `SKIP-tasks`, `SKIP-index`, `SKIP-learning`, `SKIP-openbrain`, or
   `SKIP-ritual` choice explicitly.

## 3. Core Workflow

### `OBSERVATION_GATE`

Run `snapshot <workspace-root>` after this skill is invoked. Use the complete
index projection, latest session state, git result or explicit no-git result,
parse warnings, and sync-conflict scan. Add conversation and bounded transcript
signals without treating memory as a file receipt.

Resolve Tasks DB state. When working, read `references/task_operations.md`, run
the current project slice, and fingerprint returned rows. Otherwise record the
exact state and wording:

- `absent`: "Tasks DB isn't available in this harness."
- `present_unauthenticated`: "The Tasks DB is present but not authorized —
  authorize it, then re-run."
- `present_wrong_scope`: "The Supabase server is authorized for a different
  project — reconfigure the scope."

In a non-working state, preserve task-change intent as pending and never edit
the frozen Markdown mirror to compensate.

Build a read-only scratch envelope and run `validate`. Stop on a sync conflict,
unrecognized schema, stale/contradictory receipt, or fingerprint mismatch.
Correct one input error once; repeated failure becomes a named blocker.

### `DRAFT_GATE`

Draft one complete mutation proposal containing:

1. the session entry;
2. index narrative/mirror changes, unless skipped;
3. exact task operations, unless skipped or unavailable;
4. explicit pending operations and acknowledgements for every degraded/skip
   path.

Do not write project files, the DB, Open Brain, or repository state yet.

**Entry template — 300 words maximum:**

```markdown
### Session #[N] | [YYYY-MM-DD] | [Mode (Tool)]
**Focus:** [one-line theme]
**Done:** [specific verified work]
**Decisions:** [choices and rationale; omit only if none]
**Next:** [concrete first action for newbeginning]
**Blockers:** [exact blocker or None]
```

Use `Code`, `Research`, `Chat`, or `Cowork` for Mode and the current harness for
Tool. Keep `Next:` populated even in a rushed close.

The index remains v1-compatible:

```markdown
# [Project Name]
**People:** [names and roles]
**Updated:** [YYYY-MM-DD]

## Summary
[current state, not history; at most 200 words]

## Key Decisions
[at most 8 active]

## Active TODOs
_Read-only mirror regenerated from Supabase `task_urgency`. Do not hand-edit; DB wins._

## Key Files
[at most 15; prefer 8–10]

## Archived Decisions
[at most 10]
```

Use `scripts/workflow.py` decision-overflow policy: a ninth active decision moves
the oldest to Archived; an eleventh archived decision moves the oldest to
`project_decisions_archive.md`.

### `APPROVAL_GATE`

Show the entire draft and itemize mutation scope by class:

- M2: session log, index, pending learnings;
- M3: each task operation and Open Brain intent;
- M4: normally empty unless separately requested.

Obtain explicit approval for the stated scope. Corrections return to
`DRAFT_GATE`. Approval for one class never implies another.

Write the approved scope string and time into a fresh envelope; include returned
rows so fingerprints can be recomputed. Run `validate` again.

### `CONCURRENCY_GATE` and persistence

Immediately before mutation, requery task preconditions when task writes are
approved. Then:

1. Save the approved entry draft in scratch and run `append`. The helper locks
   locally, rechecks the observed tail hash and sync conflicts, allocates the
   next number, appends, reads back, and journals. Stop on any refusal.
2. Apply approved index narrative changes and read them back. Do not duplicate
   session detail in the index.
3. Apply approved Tasks DB operations with `returning`, then rerun the current
   slice. Rebuild the read-only mirror only from that result.
4. Record verification receipts for every mutation. A partial failure remains
   partial; list what verified and what did not.

For a first session, the helper creates the v1 `# Session Log` header and Session
#1. If the index is absent, its approved draft uses the template above.

### `VERIFICATION_GATE`

Proceed only when each attempted mutation has a returned result or readback.
Recompute the task receipt from the final returned rows, read the index fields
that changed, and run `audit` after the session append. Any unjournaled entry,
orphan record, missing readback, or stale task result keeps the close partial.
Report `documented_unverified` entries separately: they have a hash-bound,
owner-approved historical exception, not a journal receipt. They do not make
the current close partial when `unjournaled`, `orphan_records`, and `errors`
are empty. Never count them as journaled or claim their original append verified.

### `LEARNING_GATE` — `PENDING_LEARNING_LIFECYCLE`

Begin only after session/index/task persistence is verified. If
`SKIP-learning`, acknowledge it and create no candidates. Otherwise:

1. read `references/candidate_quality_contract.md`, then identify at least two
   grounded candidates unless the session was pure execution and fewer are
   honest; each candidate must be plain, standalone, and centered on one
   transferable insight;
2. search Open Brain per candidate, or record its exact non-working state;
3. write and verify `pending_learnings.md` before presenting candidates;
4. present types, wording, and connections;
5. after owner edits, reapply the quality contract to the complete final
   wording and obtain fresh approval for any repair; then capture only
   explicitly approved items;
6. delete the file after approved/discarded disposition, or retain unresolved
   candidates exactly as requested.

Language precedence is explicit user preference, then the dominant session
language when it is English or Spanish, then English. Keep volatile session
numbers, internal IDs/codes, model tokens, and absolute paths out of `Insight`;
traceability belongs in separate metadata.

`SKIP-openbrain` keeps candidate extraction and the pending file but performs no
capture. Never write "New thread" unless a search actually found no match.

### `CLOSING_GATE`

Emit only lines supported by verified receipts. Normal form:

```text
Session #N logged ✓
Tasks DB updated ✓
Project index narrative + task mirror updated ✓
[N] learning candidates ready for review ✓
```

Replace skipped, unavailable, partial, or saved lines with the exact observed
state; never leave a false checkmark. Unless `SKIP-ritual`, finish:

> *"You don't have to go home, but you can't stay here. Session closed."*

### Skip and interruption paths

Run `scripts/workflow.py` skip policy so each skip produces an acknowledgement.
`SKIP-index` does not imply `SKIP-tasks`; clarify task intent separately.

On interruption, claim only artifacts already verified, list everything not completed,
and retain a concrete `Next:`. Pre-draft interruption permits no
mutation. Post-approval interruption does not upgrade attempted writes to done.

## 4. Harness Adaptations

**Required:** file write/readback and conversation. If file writing is
unavailable, output the proposed artifacts and state that no close was persisted.

**Optional capabilities:**

| Capability | Working path | Degraded path |
|---|---|---|
| Bundled Python runtime | Snapshot, validate, append, journal, audit | Do not directly append; output draft for manual save |
| Git | Head, status, diff evidence | `git_available: false`; reconstruct from other evidence |
| Tasks MCP | Current reads and approved verified writes | Named four-state warning; operations pending |
| Open Brain | Search and approved capture | Pending file only, or skip as requested |
| Transcript access | Bounded corroborating evidence | Conversation and files only |
| Parallel reads | Concurrent M0 collection | Sequential reads are equivalent |

No model or harness name changes mutation authority, gates, or receipt rules.

## 5. Decision Rules

| Situation | Action |
|---|---|
| User corrects draft | Revise and show the complete scope again |
| User skips a branch | Emit its acknowledgement; preserve independent branches |
| Task or tail precondition changed | Stop; reconcile and request new approval |
| Sync-conflict artifact appears | Enter `conflicted`; no project mutation |
| Tasks DB non-working | Keep operations pending; mirror stays untouched |
| Open Brain non-working | Persist candidates before review; do not capture |
| Multiple projects | Choose one log with the user |
| Unexpected interruption | Report verified/not-completed state; never claim full close |
| User drops ritual line | Keep receipt lines; omit only the Semisonic line |

## 6. Eval Criteria

- All seven named gates follow their preconditions; no approval or evidence is
  inherited from ambient context.
- `append` refuses absent/invalid envelopes and changed tails; every accepted
  entry has a matching journal record and readback hash.
- Every task claim has a current receipt; every mutation has a returned result
  or readback.
- Entry is at most 300 words, index narrative at most 400 words, active/archive
  limits hold, and file formats remain readable by v1.
- Every skip is explicit. Interruption output distinguishes verified from
  incomplete state.
- Pending learnings exist before presentation; Open Brain capture has separate
  approval.
- Candidate wording passes the progressively loaded quality contract before
  presentation and again after owner edits: language is resolved, meaning is
  standalone, one central insight remains, and uncertainty is preserved.
- The ritual reflects receipts rather than intent.
- `instruction_bytes_loaded` is reported in release evidence; total-token
  estimates are diagnostic only.

Restart from `OBSERVATION_GATE` after unapproved mutation, fabricated evidence,
or a provenance/collision failure. Patch wording and length issues in place.

## 7. Version & Changelog

**v3.0.3 — 2026-10-08 — candidate**

- Refreshed the candidate package and handoff status for a new validation cycle; shared runtime behavior is unchanged from 3.0.2.
- Earlier validation hashes and transfer certificates do not certify this package.

**v3.0.2 — 2026-08-29 — candidate**

- Audit now consumes exact `(session_number, entry_sha256)` receipts before
  applying the grandfather ceiling, so valid historical receipts are not
  misclassified as orphan records.

**v3.0.1 — 2026-08-25 — candidate**

- Added a progressively loaded bilingual candidate-quality contract. Learning
  wording must be plain, standalone, source-faithful, and centered on one
  transferable insight; volatile trace identifiers stay in metadata.
- Rechecks owner-edited wording before capture and requires fresh approval for
  any semantic repair.

**v3.0.0 — 2026-08-05 — candidate**

- Rebuilt closeout around validated evidence, itemized approval, tail-hash
  compare-and-swap append, readback, and append-only journal evidence.
- Added named skip, conflict, and interruption paths plus deterministic archive
  overflow policy.
- Added four-state external capabilities and three-case instruction resolution.
- Moved schemas, SQL, hashing, and long rationale into bundled scripts and
  progressive-disclosure references.
- Preserved v1 continuity-file formats and all ten trigger semantics.

Earlier releases remain in git and GitHub Releases for rollback. This candidate
is canonical source only; deployment waits for Phases 4 and 5.
