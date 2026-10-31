---
name: closingtime
description: "Session-closing capture for multi-session projects. Builds current local and Tasks DB evidence, drafts an approval-gated closeout, persists and verifies the session/index/task state, stages learning candidates before review, and closes from receipts. MUST trigger on: 'closingtime', 'closing time', 'close session', 'wrap up', 'we are done for now', 'end session', 'log this session', 'save the session', 'lets close this out', 'time to wrap'. Sibling skill: newbeginning — use it when starting or resuming a session."
metadata:
  version: "3.3.0"
---

# closingtime

> *"You don't have to go home, but you can't stay here."*
> — Semisonic, 1998

Observe, draft, approve, verify, review learnings, and close from receipts.

## 1. Purpose & Scope

Produce a v1-compatible entry and current index at session end, write only
approved Tasks DB changes, and stage candidates before presenting them.

Never mutate project truth, external truth, or repository state before explicit
approval. An M1 scratch envelope outside the repository is permitted before the
draft. Git branch, stage, commit, tag, and push remain M4 operations and require
a separate request in this invocation.

### Runtime resources

- Run local evidence, validation, append, audit, and sync checks through
  `scripts/runtime_cli.py`.
- Read `references/recovery.md` before persistence/recovery; use
  `references/envelope_examples.md` for constructor and receipt recipes.
- Read `references/runtime_contract.md` when constructing an envelope or
  handling a helper refusal.
- Read `references/task_operations.md` only when Tasks DB work is in scope.
- Read `references/candidate_quality_contract.md` only when generating,
  reviewing, or revising learning candidates.

The bundled helper is the only sanctioned writer of `project_session.md`. Audit checks consistency,
not provenance; a later snapshot can adopt an undetectable direct write. Use
`write-approved` for index, pending-learnings, decisions-archive and approved audit-policy transitions.

## 2. Pre-flight Checklist

1. **Resolve workspace and project.** Find the project root containing
   continuity files or git root. Confirm one project when the conversation spans
   several.
2. **Resolve instructions (`INSTRUCTION_RESOLUTION`).** Use the snapshot's
   `instructions` field: project-root files when present, otherwise ancestor
   files, otherwise `instructions_absent`. Explicitly read each unique path in `files` and `ancestor_files`, including files the harness may already have loaded; count each successfully read path once. Stop on
   conflicting task specifications. Never name an instruction file as if its
   location were guaranteed. Record the state in the closing evidence line.
3. **Observe capabilities.** Before probing, honor skips and owner choices. Local capabilities are booleans. `tasks_mcp` and
   `open_brain` each use `absent` (tools not listed), `present_unauthenticated`,
   `present_wrong_scope`, or `working` (a read in this invocation).
   Record `open_brain: not_used` for SKIP-learning, SKIP-openbrain or an owner
   instruction not to use Open Brain. It is a recorded choice, not a capability
   state; do not probe, search or capture.
4. **Choose depth and skips.** Default entry cap is 300 words; a short session may
   use three to five lines. Ask about ambiguous project scope, not routine facts.
   Record any `SKIP-tasks`, `SKIP-index`, `SKIP-learning`, `SKIP-openbrain`, or
   `SKIP-ritual` choice explicitly.

## 3. Core Workflow

### `OBSERVATION_GATE`

Run `new-envelope <workspace-root>` after this skill is invoked; it captures
start and `captured_at`. Use a new envelope for each later helper call chain;
never copy start times. One approval covers one envelope chain; each later chain in this conversation needs a new envelope and approval. Replace `unprobed` states before validation. The helper reads whole files and emits a bounded projection. Use the
index projection (name truncation), latest session state, git result or explicit no-git result,
parse warnings, and sync-conflict scan. Add conversation and bounded transcript
signals without treating memory as a file receipt. State the branch and changed
files only from the snapshot's `git` fields.

Resolve Tasks DB state. When working, read `references/task_operations.md`, run
the current project slice, and fingerprint returned rows (use
`fingerprint-rows -` on stdin when scratch writes are blocked). Use its
`fingerprinted_at` as the receipt time unless the tool result carries its own;
never type a time. Rows that cannot
be fingerprinted give no current receipt: make no current task claim and keep
task operations pending. Otherwise record the exact state and wording:

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

A current receipt regenerates `## Active TODOs` with `render-mirror`, even
without task changes;
without one, the mirror stays untouched. Include optional M2 `stage` permission
for `pending_learnings.md` unless learning is skipped; candidate wording waits
for `LEARNING_GATE`. Edits, dispositions and deletion need separate scopes.

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

Mode is `Code`, `Research`, `Chat`, or `Cowork`; Tool is the current harness.
Always populate `Next:`. Draft `Next:` and
`Blockers:` for the state that remains after a successful closeout; this
closeout's own approval and persistence steps belong in the live status, not in
the entry. Write the entry and index
in English unless the user explicitly asks for another language; never ask the
user which language to use for them. That default covers only the files: reply
to the user in every turn in their explicitly requested language, otherwise in
the language of their latest message.

Rewrite the index Summary to the current state: replace stale statements
instead of appending history, and never copy a sentence from the entry's
`Done:`, `Next:`, or `Blockers:` into it. Rebuild Key Files from the current session, and
add the section when it is missing.

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

Apply the decision-overflow rule: a ninth active decision moves
the oldest to Archived; an eleventh archived decision moves the oldest to
`project_decisions_archive.md`. Write/read back that archive first, in its own
approved chain; only then may the close index draft drop the archived decision.

### `APPROVAL_GATE`

Show the entire draft and itemize mutation scope by class:

- M2: session, index and optional pending `stage`; other learning/archive writes need separate approval;
- M3: each task operation and Open Brain intent;
- M4: normally empty unless separately requested.

Obtain explicit approval for the stated scope. Corrections return to
`DRAFT_GATE`. Approval for one class never implies another.

Before showing the draft, save the entry and index and run `freeze-draft
<draft-envelope> <entry> <index-draft>` (omit skipped index). After the last edit,
run `count-words` on the exact final entry sent; state only that word count.
After explicit approval, run
`approve-draft <draft-receipt> "<exact scope_lines>" --owner-reply "<owner words>"`; the helper stamps the time.
Show helper-rendered `scope_lines` verbatim; an exclusion requires revise and
freeze again. An exclusion or correction is not approval: after re-freezing,
show the new `scope_lines` and stop until the owner approves them. Owner words are recorded, not authenticated. Never type approval/start times.
Add approval/scope to the draft envelope; keep `local_snapshot` unchanged,
include returned rows, and `validate` again.

### `CONCURRENCY_GATE` and persistence

Immediately before mutation, requery task preconditions when task writes are
approved. Then:

1. Run `append <approved-envelope> <entry> <approved-draft-receipt>`. The
   helper verifies the receipt, entry and draft-time snapshot, locks locally,
   rechecks the observed tail hash (frozen at draft time) and sync conflicts,
   allocates the next number, appends, reads back, and journals. Stop on any
   refusal; a changed draft returns to `DRAFT_GATE` and needs a new freeze and
   approval.
2. Apply approved Tasks DB operations with `returning`, then rerun the current
   slice; uncertain inserts reuse their reserved UUID and need fresh approval.
3. Run one `write-approved` index transition with the frozen index draft and
   `--expect <observed-sha256|absent>`. Attach the fresh `mirror_receipt` and
   `--mirror-rows <rows.json>`; the helper uses `render-mirror` for only the
   Active TODOs body. Without a current receipt keep the mirror untouched.
4. Record verification receipts for every mutation. List verified and failed writes.

After any persistence error, inspect `resume <workspace-root>` and `audit`.
Use `freeze-draft --continue <parent-intent>` for a stale remaining index,
or approve child abandonment; the verified append stays journaled.
All local writers share a lock; a residual cross-device check/replace window
remains. Pending is never journaled. Read `references/recovery.md`.

For a first session, the helper creates v1 `# Session Log` and Session #1; an
absent index uses the template above.

### `VERIFICATION_GATE`

Proceed only when each attempted mutation has a returned result or readback.
Recompute the task receipt from the final returned rows, read the index fields
that changed, and run `audit` after the session append. Unjournaled entries keep the close partial unless adopted; offer `adopt-history` once.
Orphan records, missing readback or stale task results also keep it partial.
Report `documented_unverified` entries separately: they have a hash-bound,
owner-approved historical exception, not a journal receipt. They do not make
the current close partial when `unjournaled`, `orphan_records`, and `errors`
are empty. Never count them as journaled or claim their original append verified.

### `LEARNING_GATE` — `PENDING_LEARNING_LIFECYCLE`

Learning is optional. Skips/zero candidates leave no child intent or unfinished
close; existing pending bytes stay untouched. Begin after attempted writes verify.
For `SKIP-learning`, acknowledge it, record Open Brain as `not_used` and create no candidates. Otherwise:

1. read `references/candidate_quality_contract.md`; identify at least two
   grounded candidates unless pure execution makes fewer honest. Each is
   plain, standalone, with one transferable insight;
2. unless `not_used`, search Open Brain per candidate or name its non-working state. A search is
   a read; an instruction not to update/capture does not skip it;
3. preserve existing bytes and append new candidate blocks. Use the close's
   optional `stage` permission with `write-approved ... pending_learnings.md
   <content> --operation stage --expect <current-sha256|absent>`. It permits one
   stage after the verified append; read back before presenting candidates. If
   staging was excluded, show a separate replacement's frozen `scope_lines`
   and obtain approval first. Failed staging is a resumable/abandonable child;
4. present types, wording and connections exactly as read back. Keep needs no
   write. When asking for edit/discard/delete, show that transition's frozen
   `scope_lines` in the same message, so the reply can approve it;
5. after owner edits, reapply the quality contract to the complete wording;
   obtain fresh approval for repairs. Write/read back edits before capture;
6. separately approve edits/mixed disposition with current `--expect` and
   non-empty `--owner-reply`; bind replacement hashes (delete: `absent`) before
   each new freeze/approval. Retain unresolved blocks and unknown fields.
   Delete only after all dispositions; approval expires after six hours.
   Capture only explicitly approved items.

Language precedence is explicit user preference, then the dominant session
language when it is English or Spanish, then English. Keep volatile session
numbers, internal IDs/codes, model tokens, and absolute paths out of `Insight`;
traceability belongs in separate metadata.

`SKIP-openbrain` keeps candidate extraction and the pending file but performs no
search or capture. An instruction not to use Open Brain at all is
`SKIP-openbrain`; record `not_used` and do not probe. A search sends candidate text to the service. Never write "New thread" unless a search actually found no match.

### `CLOSING_GATE`

Emit only lines supported by verified receipts. Always print these four status
lines, in this order, as separate lines; normal form:

```text
Session #N logged ✓
Tasks DB updated ✓
Project index narrative + task mirror updated ✓
[N] learning candidates ready for review ✓
```

Replace skipped, unavailable, partial, or saved lines with the exact observed
state; never leave a false checkmark. Follow them with one evidence line:
`Evidence: instructions <state>; instruction_bytes_loaded <n>`, where the bytes
are `instruction_budget.skill_md_bytes`, plus each reference you read, plus each
resolved instruction file. A blocked close ends there without "Session closed". Waiting only on learning
dispositions is a complete close and includes the ritual line.
Order: status lines, then the evidence line, then, unless blocked or `SKIP-ritual`, the
ritual line as the very last line:

> *"You don't have to go home, but you can't stay here. Session closed."*

### Skip and interruption paths

Run `scripts/runtime_cli.py skip-plan <kind>` for each skip acknowledgement.
`SKIP-index` does not imply `SKIP-tasks`; clarify task intent separately.

On interruption, claim only artifacts already verified, list everything not completed,
and retain a concrete `Next:`. Pre-draft interruption permits no
mutation. Post-approval interruption does not upgrade attempted writes to done.

## 4. Harness Adaptations

**Required for helper paths:** Python 3, file write/readback and conversation.
Without Python nothing is persisted; output entry, index and task drafts. If file writing is
unavailable, output the proposed artifacts and state that no close was persisted.

**Optional capabilities:**

| Capability | Working path | Degraded path |
|---|---|---|
| Bundled Python runtime | Snapshot, validate, append, journal, audit | Output drafts only; nothing persisted |
| Git | Head, status, diff evidence | `git_available: false`; reconstruct from other evidence |
| Tasks MCP | Current reads and approved verified writes | Named four-state warning; operations pending |
| Open Brain | Search and approved capture | Pending file only, or skip as requested |
| Transcript access | Bounded corroborating evidence | Conversation and files only |
| Parallel reads | Concurrent M0 collection | Sequential reads are equivalent |

No model or harness name changes mutation authority, gates, or receipt rules.

## 5. Decision Rules

| Situation | Action |
|---|---|
| User corrects or excludes | Revise, re-freeze, show new scope; wait for approval |
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
- Entry ≤300 words, index narrative at most 400 words; active/archive limits hold; formats
  remain v1-readable.
- Every skip is explicit. Interruption output distinguishes verified from
  incomplete state.
- Pending learnings exist before presentation, the draft shows no candidate
  wording, and presented wording matches the file; Open Brain capture has
  separate approval.
- Replies follow the user's language; only the entry and index default to
  English. The Summary repeats no entry sentence; a current receipt
  regenerates the task mirror.
- Every word count uses `count-words` on exact final text sent after the last edit;
  times and git facts use helper results.
- Candidate wording passes the progressively loaded quality contract before
  presentation and again after owner edits: language is resolved, meaning is
  standalone, one central insight remains, and uncertainty is preserved.
- The ritual reflects receipts rather than intent.
- The closing message shows status lines, evidence with the instruction state
  and `instruction_bytes_loaded`, then the ritual line
  last (a `conflicted` stop ends with the evidence line); total-token estimates
  are diagnostic only.

Restart from `OBSERVATION_GATE` after unapproved mutation, fabricated evidence,
or a provenance/collision failure. Patch wording and length issues in place.

## 7. Version & Changelog

**v3.3.0 — 2026-10-28 — candidate**

- Round 4: legacy grammar/projection, root binding, frozen pending payloads,
  owner words, mirror controls, read-only opening recovery, historical adoption,
  task preconditions and skip/approval/archive guidance. See bundled recovery.md.
- 3.2.2 and earlier: portable recovery, optional staging, exact scope approval,
  receipts, candidate quality, instruction reads and v1 continuity compatibility.
  Detailed history remains in README and git.

Install by copying the whole folder. Releases hold earlier versions; repository
review links may be missing from standalone copies. This source candidate still
needs independent recertification and Phase 5 before deployment.
