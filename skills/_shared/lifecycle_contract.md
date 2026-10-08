# Session-skill lifecycle contract — v1 (Phase 0 deliverable)

**Date:** 2026-08-03
**Status:** **Approved 2026-08-03** by the project owner. Parts A–C are frozen. Phase 0.5 is unblocked.
**Governs:** `skills/newbeginning/` and `skills/closingtime/`
**Parent plan:** `improvement_plan_v2.1.md`
**Change boundary:** This specification changes no live skill, installed copy, Tasks DB row, or Open Brain record.

**Reading order.** Parts A–C are normative and frozen on approval — helper implementations depend on them. Parts D–E specify helper interfaces. Parts F–J specify behavior, packaging, and policy. Appendix 1 is the 83-row exit-gate disposition table. Appendix 2 is the v2 check register.

**Relocation record.** This is the Phase 2 runtime copy under `skills/_shared/`.
The original approved artifact remains in the private evaluation trail so its
review history is not rewritten.

---

## Part A — Lifecycle invariants

### A.1 States

Every invocation of either skill occupies exactly one state at a time.

| State | Meaning | Entry condition | May mutate? |
|---|---|---|---|
| `unresolved` | Workspace, instruction sources, and capability profile not yet established | Invocation start | No |
| `observed` | Every required source has a current receipt or a named unavailable reason | Observation gate passed | No |
| `drafted` | Proposed changes shown to the user, nothing written | Draft gate passed | No |
| `approved` | User explicitly approved a stated mutation scope | Approval gate passed | Not yet |
| `mutating` | Mutations executing within the approved scope | Concurrency gate passed | Yes, within scope |
| `verified` | Every mutation has a readback or returned result | Verification gate passed | No |
| `closed` | Terminal success | Closing gate passed | No |

Degraded and terminal states:

| State | Meaning | Obligation |
|---|---|---|
| `unavailable` | A required capability is absent or not usable | Emit the named warning for that capability; omit all authoritative claims that depend on it |
| `conflicted` | A source changed after observation, or a sync-conflict artifact exists for a project-truth file | Stop, or reconcile with explicit user approval. Never merge silently |
| `interrupted` | The invocation ended before `verified` | Claim nothing as complete. Preserve only state that already reached `verified` |
| `recovery` | Bootstrap or reconstruction is required before the ordinary path | Obtain a separate approval for the recovery write, verify it, then re-enter at `unresolved` |

### A.2 Legal transitions

```
unresolved ──> observed ──> drafted ──> approved ──> mutating ──> verified ──> closed
     │             │            │            │            │            │
     │             └────────────┴────────────┴────────────┴────────────┘
     │                                  │
     │                                  └──> conflicted ──> (stop) or ──> observed
     │
     ├──> recovery ──> (approved write, verified) ──> unresolved
     │
     └──> unavailable ──> observed        (degraded, with named warning)

any state ──> interrupted                  (terminal; no completion claim)
```

Three transitions are forbidden and are test cases, not guidance:

1. `observed → mutating` — skipping draft and approval.
2. `drafted → mutating` — skipping approval.
3. `mutating → closed` — skipping verification.

### A.3 Invariants

| ID | Invariant |
|---|---|
| **INV-1** | Current evidence beats ambient context. Conversation history, however long, never establishes current file, git, DB, or Open Brain state. |
| **INV-2** | Capability changes the path, never the definition of *current*, *approved*, *written*, or *verified*. |
| **INV-3** | No authoritative claim about external state without a current receipt from this invocation. |
| **INV-4** | No mutation outside an explicitly approved scope. |
| **INV-5** | No completion claim without readback or a returned result. |
| **INV-6** | No model-name branch controls evidence, truth, mutation, or approval. |
| **INV-7** | Enforce mechanically where a local script can gate; where it cannot, construct evidence so that drift between claim and citation is detectable. |

---

## Part B — Mutation taxonomy

### B.1 Classes

| Class | Members | Before approval | Gated by |
|---|---|---|---|
| **M0 — Read-only observation** | file reads, `git log`/`status`/`diff`, MCP reads | Allowed | — |
| **M1 — Ephemeral scratch** | temporary computation outside project truth and outside the repo working tree | Allowed if written under the session scratch path and never referenced as project state | Path rule (B.2) |
| **M2 — Project truth** | `project_session.md`, `project_index.md`, `pending_learnings.md` | Forbidden, except an approved `recovery` write | Approval gate + `append_session_entry` for the session log |
| **M3 — External truth** | Tasks DB, Open Brain, email, calendar, remote systems | Forbidden | Approval gate + verification gate |
| **M4 — Repository mutation** | `git add`/`commit`/`branch`/`tag`/`push` | Forbidden unless separately requested by the user in this invocation | Explicit separate request |

### B.2 The M1 boundary

`closingtime` check 6 ("draft before writing to any file") caused a literal failure when a run wrote a temporary verification script before presenting the draft. That write was harmless and is legalized here — but only under a rule a script can check:

> An M1 write must land under the harness-provided session scratch directory, or a path the user named for this purpose in this invocation. An M1 write inside the repository working tree, or to any path in M2, is an M2/M4 violation regardless of intent.

Rationale for the boundary rather than a judgment call: "was it really temporary?" is unscoreable; "was it under the scratch path?" is a string comparison.

### B.3 Named gates

| Gate | Precondition to pass | Enforced by |
|---|---|---|
| **Observation** | Every required source has a current receipt or a named unavailable reason, and no sync-conflict artifact exists for any M2 file | `validate_envelope` |
| **Draft** | Proposed M2/M3 changes shown; nothing written | Scored (Layer 3) |
| **Approval** | User explicitly approved a stated mutation scope, itemized by class | Scored; scope string recorded in the envelope |
| **Concurrency** | Tail hash and task preconditions rechecked and unchanged since observation | `append_session_entry` (refuses on mismatch) |
| **Verification** | Every mutation has a readback or returned result | Scored; readback hashes recorded |
| **Learning** | Candidates persisted to `pending_learnings.md` before review; Open Brain capture separately approved | Scored (Layer 3) |
| **Closing** | Every ritual/brief claim traces to a verified receipt | Scored (Layer 3) |

Only Observation and Concurrency are mechanically enforced. The rest are scored. This is stated plainly so no one reads a green scorecard as a hard guarantee.

---

## Part C — Data contracts (frozen on approval)

All four schemas carry `schema_version`. A helper receiving an unrecognized `schema_version` **refuses**; it does not attempt best-effort parsing.

### C.1 Capability profile

```jsonc
{
  "schema_version": "1.0",
  "local": {
    "shell_available": true,
    "git_available": true,
    "temporary_workspace_available": true,
    "parallel_read_only_available": true
  },
  "external": {
    "tasks_mcp":  "working",   // absent | present_unauthenticated | present_wrong_scope | working
    "open_brain": "absent"
  },
  "external_detail": {
    "tasks_mcp":  { "server_id": "<opaque>", "project_ref": "<tasks-project-ref>" },
    "open_brain": { "reason": "no capture_thought in tool list" }
  }
}
```

Local capabilities are boolean. External capabilities are **four-state**, because a boolean cannot express the two middle cases and the user's remedy differs between them:

| State | Meaning | Required user-facing wording | Authoritative claims |
|---|---|---|---|
| `absent` | No such tool in this harness | "not available in this harness" | Forbidden |
| `present_unauthenticated` | Tool listed, authorization not completed | "present but not authorized — authorize it, then re-run" | Forbidden |
| `present_wrong_scope` | Authorized, but not for the required project/scope | "authorized for a different project — reconfigure the scope" | Forbidden |
| `working` | Read succeeded this invocation | — | Permitted, with a receipt |

`present_unauthenticated` and `present_wrong_scope` are both observed in practice; conflating them sends the user to the wrong fix.

### C.2 MCP receipt

```jsonc
{
  "schema_version": "1.0",
  "capability": "tasks_mcp",
  "identity": { "project_ref": "<tasks-project-ref>", "view": "task_urgency" },
  "tool_result_id": "<harness-provided id, or null>",
  "observed_at": "2026-08-03T22:31:04Z",
  "operation_fingerprint": "sha256:<normalized query text>",
  "row_fingerprint": "sha256:<canonicalized returned rows>",
  "row_count": 8,
  "status": "current"          // current | unavailable | error | conflicted
}
```

**`row_fingerprint` is recomputed by `validate_envelope` from the returned content, not trusted as asserted.** Canonicalization: rows sorted by primary key, keys sorted, whitespace normalized, then SHA-256. A mismatch between the asserted and recomputed value is a hard failure.

This does not make fabrication impossible — an agent could fabricate rows and their hash together. It makes *drift between a claim and its cited evidence* detectable, which is the failure mode the corpus actually shows: two compacted runs claimed live DB state with no observed SQL call, and pair 15 failed the provenance/degraded trio for both models.

`status: unavailable` requires `row_fingerprint: null` and a `capability_state` naming which of the three non-working states applies.

### C.3 Evidence envelope

```jsonc
{
  "schema_version": "1.0",
  "invocation_id": "<uuid>",
  "skill": "closingtime",              // closingtime | newbeginning
  "workspace_root": "/abs/path",
  "capability_profile": { /* C.1 */ },
  "local_snapshot": {
    "index":   { "path": "...", "sha256": "...", "mtime": "...", "words": 412 },
    "session": { "path": "...", "tail_sha256": "...", "latest_session_number": 38 },
    "pending_learnings": { "present": false },
    "git": { "available": true, "head": "21de708", "dirty": true, "diff_stat_sha256": "..." },
    "sync_conflicts": [],              // non-empty ⇒ state `conflicted`
    "projection_bytes_emitted": 3184
  },
  "mcp_receipts": [ /* C.2 */ ],
  "mutation_scope": {
    "M2": ["project_session.md", "project_index.md"],
    "M3": ["tasks:update:9e187e87", "tasks:insert:new"],
    "M4": []
  },
  "approval": { "granted": true, "scope_string": "<verbatim text shown to user>", "at": "..." },
  "source_hashes_used_for_draft": { "index": "...", "session_tail": "...", "tasks": "..." }
}
```

The envelope **combines** evidence; it never acquires it. "Atomic snapshot" means one validated envelope, not one process — a local script cannot reach MCP-only state, which is why local and MCP receipts are separate members of one envelope.

### C.4 Journal record

```jsonc
{
  "schema_version": "1.0",
  "invocation_id": "<uuid>",
  "envelope_sha256": "...",
  "session_number": 39,
  "entry_sha256": "...",
  "written_at": "2026-08-03T22:47:10Z",
  "skill_version": "closingtime@2.3.0"
}
```

One record per accepted append. Append-only, one file per record, never rewritten:
`private-artifacts/session-journal/<ISO8601>-<invocation_id>.json`

---

## Part D — Helper interfaces

Six helpers. Each has a frozen signature, error states, refusal conditions, and at least one named fixture. No helper holds or receives database credentials.

### D.1 `capture_local_snapshot(workspace_root) -> LocalSnapshot`

| | |
|---|---|
| **Class** | M0 only |
| **Returns** | `local_snapshot` member of C.3 |
| **Errors** | `ENOROOT` unresolvable root · `EPERM` unreadable project file · `EGITFAIL` git present but command failed |
| **Refuses** | Any path outside `workspace_root`; any call passing DB credentials or MCP config |
| **Notes** | Emits `projection_bytes_emitted`, hard-capped. Detects filename variants (`Project_Index.md`, `project.md`, `session_log.md`). Detects sync-conflict artifacts: `*(Conflicted copy*`, `*.sync-conflict-*`, `* (case conflict)*` |
| **Fixture** | `F1-normal`, `F6-sync-conflict` |

`git_available: false` is a first-class result, not an error.

### D.2 `assemble_evidence_envelope(local_snapshot, mcp_receipts, capability_profile, mutation_scope) -> Envelope`

| | |
|---|---|
| **Class** | M1 (writes the envelope to the scratch path only) |
| **Errors** | `ESCHEMA` unrecognized `schema_version` on any input |
| **Refuses** | Assembly when `local_snapshot.sync_conflicts` is non-empty — returns `conflicted` instead |
| **Fixture** | `F9-envelope-invalid` family |

### D.3 `validate_envelope(envelope, returned_rows_by_receipt) -> Verdict`

| | |
|---|---|
| **Class** | M0 |
| **Returns** | `{valid: bool, failures: [{code, receipt, detail}]}` |
| **Failure codes** | `MISSING_RECEIPT` · `STALE_RECEIPT` (observed_at older than the invocation start) · `FINGERPRINT_MISMATCH` (recomputed ≠ asserted) · `CONTRADICTORY` (two receipts for one capability disagree on status) · `UNRECOGNIZED_SCHEMA` · `SCOPE_UNAPPROVED` (mutation_scope non-empty, approval absent) · `SYNC_CONFLICT` |
| **Refuses** | Returning `valid: true` when any failure is present. No partial validity |
| **Fixture** | `F7-db-receipt-states` (6 variants), `F9-envelope-invalid` |

### D.4 `append_session_entry(envelope, entry_text) -> AppendResult`

The **only sanctioned writer** of `project_session.md`.

| | |
|---|---|
| **Class** | M2 |
| **Returns** | `{session_number, entry_sha256, journal_record_path, readback_ok}` |
| **Sequence** | (1) acquire same-host advisory lock · (2) re-read tail, compare `tail_sha256`, re-run sync-conflict detection · (3) stop on mismatch · (4) allocate next session number under the lock · (5) append · (6) read back and hash · (7) **write the journal record** · (8) release lock |
| **Errors** | `ELOCK` lock unobtainable · `ESTALE` stale lock recovered (logged, then proceeds) · `EREADBACK` readback hash ≠ written hash |
| **Refuses** | `validate_envelope` returns invalid · `approval.granted` is false · tail hash differs from the envelope's · a sync-conflict artifact appeared · `entry_text` exceeds the word cap |
| **Fixture** | `F10-concurrency` (4 variants), `F9-envelope-invalid` |

**The journal record is written by this helper, inside the same operation, not by a separate writer.** A separate writer permits journal/log divergence — exactly what the auditor exists to detect, so it must not be creatable by normal operation.

**Concurrency control is the tail-hash comparison, not the lock.** A local lock cannot protect a Dropbox-synced tree against a write from a second device. The lock is a cheap same-host guard against a local double-run; the compare-and-swap detects a foreign change whatever produced it. Step (2) is the control that matters.

### D.5 `audit_session_log(workspace_root) -> AuditReport`

| | |
|---|---|
| **Class** | M0 |
| **Returns** | `{entries, journaled, unjournaled: [{session_number, entry_sha256}], orphan_records: [...]}` |
| **Semantics** | Every entry in `project_session.md` must have a journal record whose `entry_sha256` matches. An unjournaled entry indicates a bypassed write path |
| **Errors** | `ENOJOURNAL` journal directory absent — reported, not thrown, so pre-Phase-2 history is not a failure |
| **Grandfathering** | Entries with `session_number ≤ <last pre-Phase-2 session>` are exempt and reported separately. The exempt ceiling is recorded once, at Phase 2 start |
| **Fixture** | `F10-concurrency`, plus a bypassed-write mutant |

This closes the "the model can just call `Write`" hole by **detection**, not prevention. Prevention is not available to a script that does not control the tool layer; saying so plainly is part of the contract.

### D.6 `verify_skill_sync(canonical_dir, target_dirs) -> SyncReport`

| | |
|---|---|
| **Class** | M0 |
| **Returns** | per-target `{path, sha256, matches_canonical}` |
| **Refuses** | Reporting success on partial deployment — any target mismatch fails the whole report |
| **Fixture** | `F15-deploy` |

---

## Part E — Enforcement model

Hybrid, per the 2026-08-03 decision.

| Surface | Mechanism | Residual risk |
|---|---|---|
| `project_session.md` | `append_session_entry` refuses invalid envelopes; journal + `audit_session_log` detect bypass | A bypassed write is detected after the fact, not prevented |
| `project_index.md`, `pending_learnings.md` | Approval gate, scored | Not mechanically gated |
| Tasks DB / Open Brain | Content-derived fingerprints make claim/citation drift detectable | Coordinated fabrication of rows *and* hash is undetectable locally |
| Repository | Explicit separate request, scored | Not mechanically gated |

Stating the residual risk is deliberate. A contract that claims enforcement it does not have is worse than one that scopes it honestly, because the first invites reliance.

---

## Part F — Paths

### F.1 `newbeginning` branches

| Branch | Trigger | Approval required before write |
|---|---|---|
| **N-normal** | both project files present | None (no write) |
| **N-index-only** | only `project_index.md` | None; brief notes absent session history |
| **N-reconstruct** | only `project_session.md` | Yes — show drafted index, confirm, write, verify, then re-enter |
| **N-bootstrap-content** | neither file; workspace has ≥1 commit / README / ≥3 source files | Yes — scan, draft, gap-fill interview, confirm, write, verify |
| **N-bootstrap-empty** | neither file; workspace empty | Yes — confirm location, interview, write, verify |
| **N-corrupted** | files present but unparseable or mutually contradictory | Enter `conflicted`; surface the drift; do not auto-reconcile |

### F.2 `closingtime` skip paths

Each is an explicit test case, never an implicit omission. Every skip requires an acknowledgement line naming what was skipped.

`SKIP-tasks` · `SKIP-index` (narrative and mirror; task-write intent clarified separately) · `SKIP-learning` · `SKIP-openbrain` (candidates still written to `pending_learnings.md`) · `SKIP-ritual` (checkmarks retained, Semisonic line dropped)

### F.3 Interrupted path

On interruption: claim nothing as complete; list what reached `verified`; name what did not. The rushed-close minimum is a session entry with `Next:` populated — a *minimum*, not a licence to skip the approval gate.

### F.4 Unavailable and conflicted paths

`unavailable` → emit the named warning from C.1, omit dependent authoritative claims, continue with what remains. `conflicted` → stop by default. Reconciliation requires its own approval and its own verification.

---

## Part G — Trigger semantics (21, frozen)

Frontmatter is excluded from the slimming target. All 21 phrases must activate the intended skill in both harnesses, and must not activate the sibling.

**`newbeginning` (11):** `newbeginning` · `new beginning` · `where did we leave off` · `what were we working on` · `pick up where we left off` · `catch me up` · `start session` · `open session` · `resume work` · `whats the status` · `brief me on this project`

**`closingtime` (10):** `closingtime` · `closing time` · `close session` · `wrap up` · `we are done for now` · `end session` · `log this session` · `save the session` · `lets close this out` · `time to wrap`

Negative set (must activate neither): `wrap this function` · `close this file` · `start the server` · `resume the download` · `whats the status of the build`.

---

## Part H — Fixture catalog and mutant sensitivity

### H.1 Families

| ID | Family | Variants | Exercises |
|---|---|---:|---|
| F1 | normal | 1 | happy path, both skills |
| F2 | no-git | 2 | `git_available:false`, git-present-but-failing |
| F3 | filename-variant | 3 | `Project_Index.md`, `project.md`, `session_log.md` |
| F4 | missing-notes | 3 | index-only, session-only, neither |
| F5 | corrupted-notes | 2 | unparseable entry, index/session contradiction |
| F6 | sync-conflict | 2 | conflicted copy of index, of session log |
| F7 | db-receipt-states | 6 | present · empty · unavailable · stale · malformed · contradictory |
| F8 | projection-cap | 2 | at cap, over cap |
| F9 | envelope-invalid | 5 | missing receipt · unapproved scope · unrecognized schema · fingerprint mismatch · sync-conflict present |
| F10 | concurrency | 4 | tail changed · duplicate number attempt · stale lock · readback mismatch |
| F11 | archive-overflow | 1 | 9th decision archives the oldest |
| F12 | skip-paths | 5 | one per F.2 skip |
| F13 | interrupted | 2 | pre-draft, post-approval |
| F14 | open-brain-states | 4 | one per C.1 external state |
| F15 | deploy | 2 | matched hashes, partial deployment |
| **Total** | | **44** | |

### H.2 Mutant rules

1. Each valid fixture spawns mutants by removing **exactly one** of: a receipt, an approval, a readback, or a required warning.
2. Each mutant declares the v2 check ID it is expected to fail. A mutant that fails a *different* check is a scorer defect, not a pass.
3. The validator/scorer must fail **every** mutant. A single surviving mutant blocks Phase 1's exit gate.
4. One defect per mutant. Compound mutants are not admissible evidence of sensitivity.

This proves sensitivity without pretending historical transcripts can execute new behavior.

---

## Part I — Data-format compatibility

vNext **must** keep `project_session.md`, `project_index.md`, and `pending_learnings.md` readable by the v1 skills: same headings, same entry template, same `Updated:` field, same `## Active TODOs` mirror shape.

All new state lives in new files: `private-artifacts/session-journal/`, scratch-path envelopes. Neither is required for a v1 skill to function.

Without this rule, rollback is one-way — v1 would be left reading files it did not write. With it, Phase 5's "retain previous versions for rollback" is a real control.

---

## Part J — Canonical source and deployment

**Canonical (only editable source):** `skills/newbeginning/`, `skills/closingtime/`

**Deployment targets:** Claude install dir · Codex install dir · Antigravity (`~/.gemini/config/skills/`)

Policy: edit canonical only · deploy one harness at a time · `verify_skill_sync` after each · partial deployment fails the whole report · retain the previous version per target · promote only after five observed real invocations per skill/model with no critical-gate regression, read from the envelope journal rather than reconstructed by hand.

**Root instruction resolution — three cases:**

1. instruction file at project root → use it;
2. instruction file in an **ancestor** directory → resolve explicitly. Claude Code walks ancestors; Codex does not. This is the live case: this project root has `AGENTS.md` and no `CLAUDE.md`, while the canonical `## Task tracking` spec is two levels up at `038_AI/CLAUDE.md`;
3. absent → named warning, never an unconditional reference.

Known case-2 defects to fix in Phase 3: `skills/closingtime/SKILL.md` lines 27, 124, 218, 357.

Cross-skill references use named anchors or concepts, never step numbers. Known defect: `newbeginning` references "closingtime Step 4."

---

## Appendix 1 — Exit-gate disposition table (83 rows)

**Totals:** 71 frozen checks — **38 retained**, **31 mapped**, **2 retired** — plus 12 Opus recommendations.

Retired checks require user sign-off and are excluded from **both** numerator and denominator of the frozen rate (see `improvement_plan_v2.1.md`, Layer 3).

### A1.1 `newbeginning` — 29 frozen checks (15 retained / 13 mapped / 1 retired)

| # | Frozen check | Disposition | v2 | Note |
|---|---|---|---|---|
| 1 | Both files present → full brief | Retained | REC-1 | |
| 2 | Session-only → reconstructs draft index, confirms | Mapped | REC-3 + APR-1 | Approval gate now explicit |
| 3 | Index-only → briefs, notes no history | Retained | REC-2 | |
| 4 | Neither → cold-start | Mapped | REC-4 | Splits into content/empty branches |
| 5 | Fuzzy filename resolution | Mapped | OBS-2 | Now helper-deterministic |
| 6 | Brief ≤ 250 words | Retained | BRF-1 | |
| 7 | `Next:` surfaced explicitly | Retained | BRF-2 | |
| 8 | Top 3 tasks with priority labels + scope | Mapped | BRF-3 | Now requires OBS-5 receipt |
| 9 | Flagged / review-due / due surfaced | Retained | BRF-4 | |
| 10 | Long gap (>14d) noted | Retained | BRF-5 | |
| 11 | No fabrication | Mapped | VER-1 + OBS-6 | Splits: narrative provenance vs. fingerprint match. **Pair-15 defect** |
| 12 | Honest about gaps | Retained | BRF-6 | |
| 12a | Portfolio scope confirmed first | Retained | BRF-7 | |
| 13 | Options as a single question | Retained | CLS-1 | |
| 14 | 3 options, 4 with pending + OB | Mapped | CLS-2 | Keyed to C.1 four-state |
| 15 | Stops after brief | Retained | CLS-3 | |
| 16 | "Adjust priorities" → DB update, re-query, stop | Mapped | APR-3 + VER-3 | |
| 17 | Confirms before bootstrapping | Mapped | REC-5 | |
| 18 | Content workspace → scan before interview | Retained | REC-6 | |
| 19 | Empty workspace → interview only | Retained | REC-7 | |
| 20 | User confirms before write | Mapped | APR-1 | Now the general M2 approval gate |
| 21 | English by default | Retained | REC-8 | |
| 22 | OB unavailable → no `pending_learnings.md` read | Mapped | CAP-3 | |
| 23 | OB unavailable → no review option | Mapped | CAP-4 | |
| 24 | OB unavailable → shows message | Mapped | CAP-5 | Must name **which** of 4 states |
| 25 | Sibling absent → install pointer | Retained | CAP-6 | |
| 25a | Supabase unavailable → warns | Mapped | CAP-1 | Must name which of 4 states |
| 25b | Frozen mirror is read-only, not authoritative | Retained | CAP-2 | |
| 26 | Total tokens ≤ 2.5K | **Retired** | BUD-1/2/3 | **Sign-off required.** Unachievable: the skill body alone (2,936 words) exceeds the budget before any read. Replaced by fixed/marginal split |

### A1.2 `closingtime` — 42 frozen checks (23 retained / 18 mapped / 1 retired)

| # | Frozen check | Disposition | v2 | Note |
|---|---|---|---|---|
| 1 | Reads full index before drafting | Mapped | OBS-1 | Now snapshot-receipt-backed. **Failed in 7 Fable runs** |
| 2 | Reads last session entry | Mapped | OBS-3 | **Failed in 7 Fable runs** |
| 3 | Uses `git log`/`diff --stat` when available | Mapped | OBS-4 | |
| 4 | Reconstructs from conversation when no git | Mapped | CAP-7 | 3 and 4 now mutually auditable |
| 5 | Fuzzy filename resolution | Mapped | OBS-2 | Shared with opening |
| 6 | Draft before writing to any file | Mapped | DRF-1 | Redefined via B.2: M1 scratch is legal |
| 7 | User can correct emphasis | Retained | DRF-2 | |
| 8 | Feedback reflected in final entry | Retained | DRF-3 | |
| 9 | Entry ≤ 300 words | Retained | BRF-8 | |
| 10 | All template fields present | Retained | BRF-9 | |
| 11 | `Next:` concrete and actionable | Retained | BRF-10 | |
| 12 | Short session → 3–5 line entry | Retained | BRF-11 | |
| 13 | Session number correctly incremented | Mapped | CNC-2 | Allocated under compare-and-swap |
| 14 | English by default | Retained | BRF-12 | |
| 15 | Summary rewritten, not appended | Retained | BRF-13 | |
| 16 | Summary ≤ 200 words | Retained | BRF-14 | |
| 17 | Narrative index ≤ 400 words | Retained | BRF-15 | |
| 18 | Decisions ≤ 8; 9th archives oldest | Retained | BRF-16 | |
| 19 | New tasks inserted with `origin` | Mapped | APR-2 + VER-2 | |
| 20 | Key Files rebuilt, not appended | Retained | BRF-17 | |
| 21 | Completed → `done` + `completed_at` | Mapped | VER-2 | Requires returned result |
| 22 | Task ops use `tasks`, not markdown | Retained | APR-4 | |
| 23 | No duplication entry vs. index | Retained | BRF-18 | |
| 24 | `Updated:` = today | Retained | BRF-19 | |
| 24a | Mirror regenerated, labeled read-only | Mapped | VER-4 | Requires a current receipt |
| 24b | Supabase unavailable → warns, records pending ops | Mapped | CAP-1 | |
| 25 | ≥2 candidates unless pure execution | Retained | LRN-1 | |
| 26 | Candidates grounded in a session moment | Retained | LRN-2 | |
| 27 | `search_thoughts` called per candidate | Mapped | LRN-3 | Or an explicit unavailable record. **Failed 6 Fable / 4 Sol** |
| 28 | Written to `pending_learnings.md` before review | Retained | LRN-4 | **Failed 5 / 5** — fixed by reordering in F.2 |
| 29 | Nothing saved without explicit approval | Retained | LRN-5 | |
| 30 | After save: `pending_learnings.md` deleted | Mapped | LRN-6 | Disposition follows approval: delete or retain |
| 31 | Skip OB → no candidates, no file | Retained | LRN-7 | |
| 32 | `capture_thought` unavailable → file only, tells user | Mapped | CAP-5 | |
| 33 | Ritual checkmarks displayed | Mapped | CLS-4 | Emitted only from verified receipts |
| 34 | Semisonic line verbatim | Retained | CLS-5 | |
| 35 | "Drop ritual line" → checkmarks kept | Retained | CLS-6 | |
| 36 | First session ever → both files, #1 | Mapped | REC-9 | |
| 37 | Partial state → works, offers to create | Mapped | REC-10 | |
| 38 | Skip index → respected, task intent clarified | Retained | CLS-7 | |
| 39 | Rushed close → entry with `Next:` | Mapped | CLS-8 | Interrupted path, F.3 |
| 40 | Total tokens reasonable for complexity | **Retired** | BUD-4 | **Sign-off required.** Unscoreable — no threshold, no measurement. Becomes a diagnostic |

### A1.3 Opus recommendations — 12 rows

| # | Recommendation | Disposition | Where |
|---|---|---|---|
| 1 | Split snapshot helper and MCP query | Accepted | C.3, D.1 |
| 2 | Replace frozen-transcript regression with fixtures | Accepted | H.1 |
| 3 | Dual-score frozen + vNext | Accepted | Appendix 1; Layer 3 denominator rule |
| 4 | Restore cold-start and reconstruction | Accepted | F.1 |
| 5 | Hard projection cap instead of budget percentage | Accepted, modified | BUD-2; cap chosen in Phase 2 |
| 6 | Remove the 5-point shared-invariant gate | Accepted | Removed in v2 |
| 7 | Model-neutral DB provenance | Accepted | INV-6, OBS-5/6 |
| 8 | Independently selected scenarios | Accepted, modified | Layer 5; all deterministic fixtures must pass |
| 9 | Anchors, conditional root pointer, canonical hashes | Mostly accepted | Part J; line-count claim rejected as wrong |
| 10 | Trigger activation and slimming A/B | Accepted | Part G; Layer 4 |
| 11 | Inject a race and add locking | **Partly accepted, narrowed** | D.4. Race injection kept; lock **downgraded** to same-host advisory — it cannot protect a synced tree. Tail-hash CAS is the control. DB session sequence rejected |
| 12 | Publish per-pair denominators | Accepted as clarity | Layer 3 reporting |

---

## Appendix 2 — v2 check register

Checks with no frozen ancestor. These are additions, and they are why the v2 denominator differs from the frozen one.

| ID | Check |
|---|---|
| OBS-5 | Authoritative task claim carries a `status: current` receipt from this invocation |
| OBS-6 | Recomputed `row_fingerprint` matches the asserted value |
| OBS-7 | Sync-conflict detection ran and reported for every M2 file |
| CNC-1 | Tail hash rechecked immediately before append |
| CNC-3 | Injected foreign modification is detected and stops the append |
| ENF-1 | `append_session_entry` refuses an invalid or absent envelope |
| ENF-2 | A journal record exists for every accepted append |
| ENF-3 | `audit_session_log` reports zero unjournaled entries above the grandfather ceiling |
| CAP-8 | Root instruction resolution handles all three cases |
| ACT-1 | All 21 trigger phrases activate the intended skill |
| ACT-2 | Negative phrases activate neither skill |
| ACT-3 | No cross-skill step-number reference |
| BUD-1 | `instruction_bytes_loaded` reported |
| BUD-2 | `projection_bytes_emitted` at or below the frozen cap |
| BUD-3 | `brief_words` ≤ 250 |
| BUD-4 | Marginal-cost diagnostics recorded (non-blocking) |
| VER-5 | Every M2/M3 mutation has a recorded readback or returned result |

---

## Sign-off record — 2026-08-03

All open items resolved. Approved by the project owner.

| Item | Resolution |
|---|---|
| Retire frozen check 26 (`newbeginning` ≤2.5K total tokens) | **Approved — retired.** Excluded from both numerator and denominator of the frozen rate. Replaced by BUD-1/2/3 |
| Retire frozen check 40 (`closingtime` tokens "reasonable") | **Approved — retired.** Excluded from both numerator and denominator. Becomes non-blocking diagnostic BUD-4 |
| Grandfather ceiling for `audit_session_log` | **Approved.** Ceiling = highest session number existing at Phase 2 start. Recorded once, at Phase 2 start |
| Contract as a whole | **Approved.** Parts A–C frozen; Phase 0.5 and Phase 1 unblocked |

The frozen checklists in `../newbeginning/behavioral_checklist.md` and `../closingtime/behavioral_checklist.md` are **not** edited. They remain the frozen baseline; retirement is recorded here, in the disposition table, and applied by the Phase 1 scorer.

---

## Known defects to carry into Phase 3

- `skills/closingtime/SKILL.md` lines 27, 124, 218, 357 — unconditional "root `CLAUDE.md`" (case-2 defect).
- `skills/newbeginning/SKILL.md` — cross-skill reference to "closingtime Step 4."
- Both `behavioral_checklist.md` files report stale totals in their Summary sections (26 and 40), omitting the sub-lettered checks. Actual: 29 and 42.
