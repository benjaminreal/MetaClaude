# Recovery and persistence contract (newbeginning 2.2.2 / closingtime 3.2.2)

All helpers require Python 3 and shell access; the runtime uses only the standard
library. Continuity files remain v1-readable. Hashes check consistency, not
conversation authority, authenticity or provenance.

## Scope, identity and lock

Opening writes only an approved bootstrap/reconstructed index. Task creation,
pending-learning edits/dispositions/deletion and Open Brain capture belong during
the session or closingtime: route the request there and stop. Searches remain reads.
A close covers session append, index and optional pending stage permission.
Learning edits/dispositions/deletion and archive writes require separate approval. Zero candidates or skipping learning leaves
nothing unfinished, and existing pending files remain untouched unless named.

Journal: `private-artifacts/session-journal/`. On the first approved journaled
write, `workspace.json` receives a random `workspace_id`, reported in snapshots.
Intents use relative targets and hashes; their absolute root is informational.
Moving/remounting the whole project preserves recovery and subsequent writes.
Different journal identities refuse `EWORKSPACEMISMATCH`. Legacy records lacking
identity remain readable; a legacy project's identity is created at its next
approved write. Copying an entire identity-bearing project also copies identity:
these checks cannot distinguish clones deliberately sharing that identity.
Traversal and symlink escapes are refused, including journal paths.

The one lock is `private-artifacts/session-journal/.lock`, created with O_EXCL
(exclusive creation), storing host, pid and start time. TMPDIR does not change it.
On the same host a dead process is stale immediately; a live pid blocks at any
age. On another host the lock expires after ten minutes. A legitimate long writer
on another host can therefore be expired. Recovery reports
`ELOCK_STALE_RECOVERED`; unreadable locks require inspection. The lock is excluded
from conflict scans and journal parsing. No shared lock can remove the residual
cross-device precheck/replace or rollback window, particularly on sync storage.

## State table and test oracle

| Boundary / bytes | Record | Outcome / next action |
|---|---|---|
| Target/alias/preimage refusal at freeze or append preflight | no append intent | log unchanged; reconcile, observe and approve again |
| Atomic intent publication fails | possible retained temporary file | no log write; inspect evidence |
| Durable append intent, log still preimage (including absence) | `.pending` | resume reports `not_appended`, renames `.abandoned`; no child obligation |
| Log exactly preimage plus intended bytes | `.pending` | resume reports `appended`, finalizes append `.done`; safe to repeat |
| Partial or foreign bytes | `.pending` | `partial_or_conflicted`; preserve everything and stop |
| Failed readback, exact extension provable | `.pending` | conditional rollback restores prior bytes/absence; append and unstarted child become `.abandoned` |
| Rollback or final rename fails | retained intent | `EPARTIAL_APPEND`; resume, never duplicate the close |
| Append read back | append `.done`, index child `.pending` | append already journaled; index is independently unfinished |
| Remaining index preimage changed | child `.pending` | `remaining_stale` plus current hash; continuation or child abandonment |
| Bound index transition verifies | write `.done`, child `.done` | parent remains journaled; no unfinished local work |
| Explicit child abandonment | child `.abandoned` plus approval note | no index obligation; append stays journaled |
| Stage interrupted, preimage unchanged | child write `.pending` | resume reapplies exact saved payload and readback; or approve child abandonment |
| Replacement/delete interrupted | write `.pending` | preimage: `not_applied`, abandoned; postimage: `applied`, final; other bytes: stop |
| Legacy append `.json` | original content retained | resume classifies bytes and separates child work; finalizes by rename |
| Legacy journal / `_policy.json` | unchanged legacy format | limited audit consistency; never invent original receipts |

Synthetic fixtures inject write/fsync/readback/rename/unlink faults and seeded
crash states. A controlled subprocess crash tests dead-pid recovery. Power loss
and uncontrolled Dropbox races remain unverified. A torn append requires separate
owner-approved reconciliation to known bytes before resume; never guess which
foreign bytes to truncate.

## Commands and approvals

`new-envelope ROOT` derives package identity/version, captures a fresh snapshot
and leaves services `unprobed`; replace them with observed four-state results.
`validate ENVELOPE` must pass before an authoritative brief. Snapshot `captured_at`
(fallback `observed_at` for legacy shapes) must be no older than six hours and no
more than 120 seconds ahead of wall clock. Freeze, approve, append and ordinary
write-approved also enforce this lifetime (`ESTALEEVIDENCE`).

`freeze-draft ENVELOPE [ENTRY] [INDEX]` or `--index-draft INDEX` supports index-only
opening. Every approved local target is resolved and its aliases/preimage checked
at freeze and again before append's first byte. The result binds snapshot, entry,
index draft, exact operations, preimages and canonical `scope_lines`/`scope_sha256`.
Journal metadata is part of the local approval scope. Show those exact lines.
`approve-draft RECEIPT SCOPE --owner-reply TEXT` requires exact scope equality.
An exclusion means revise, freeze and present again; the exclusion reply is not
approval. Each invocation gets one approved draft (`EINVOCATIONUSED` for another
approval or a different receipt). Discard superseded unapproved proposals: the
helper cannot know which pre-approval freeze was revoked in conversation.

`write-approved ENVELOPE RECEIPT PATH [PAYLOAD] --operation replace|delete|stage
--expect SHA256|absent [--mirror-rows ROWS] --owner-reply TEXT` requires explicit
preconditions; absent and empty differ. The allowlist is independent of snapshot
labels: `project_index.md`, `Project_Index.md`, `project.md`, `index.md`,
`pending_learnings.md`, `project_decisions_archive.md`. The session log and journal
are never writer targets. Newbeginning further restricts writes to index replacement.
Snapshot aliases: session `project_session.md`, `Project_Session.md`,
`session_log.md`, `sessions.md`; pending `pending_learnings.md`, `Pending_Learnings.md`.
An existing noncanonical pending alias must be reconciled separately before a
canonical pending write. Alternate histories/target aliases stop persistence.
An ordinary website's lone `index.md` is an index alias: confirm project scope.

Close order: append → approved Tasks operations and fresh read → one index write.
An index child cannot write until its parent append verifies. The index payload is frozen; only its Active TODOs body may be regenerated using
validated `mirror_receipt` and actual `--mirror-rows`. Archive replacements bind
exact payload hashes in `local_payload_hashes`. A plain pending path next to the
session defaults to `stage`; otherwise to `replace`. Delete is always explicit,
including for the decisions archive. Stage renders `(optional; new candidate
blocks only)` and permits exactly one transition after verified parent append:
`write-approved ENV RECEIPT pending_learnings.md CONTENT --operation stage
--expect <current-sha256|absent>`. It uses the close's approval/owner words.
No child exists until a valid staging payload is attempted; I/O failure keeps a
resumable/abandonable child, without unjournaling the append. Abandoning consumes
that close's stage permission. Prefix changes refuse ESTAGE. A new suffix must
start on a new line and contain only `## Candidate <ASCII number>` blocks with
non-empty Type, Insight and Connection/Connects to fields; optional Status must
be pending. Existing bytes (including unknown fields/line endings) are opaque
and unchanged; no legacy parser or semantic-quality guarantee is imposed.
Read back before presenting. Keep needs no write; show frozen scope_lines with
any further edit/discard/delete question. Those transitions require their own
approval, current --expect and non-empty --owner-reply per revision. Pending
approval expires after six hours. Open Brain capture stays separately approved.

## Interrupted operations and stale-index continuation

`resume ROOT [RECEIPT]` inspects durable records and actual bytes, needs no scratch
files and never retries external calls. It explicitly reports that bound recovery
is exempt from snapshot freshness. It returns saved `recovery_inputs` for an
unfinished index: use that exact envelope/receipt/index with `write-approved`.
Only a journal-bound unfinished child qualifies; old receipts otherwise need
fresh observation, freeze and approval. Completed writes are inspected, and
later edits can be reported without blocking new closes.

If the index changed, do not reuse its old preimage:

1. Observe a fresh envelope, containing only the remaining index replacement.
2. Run `freeze-draft ENVELOPE --index-draft INDEX --continue
   private-artifacts/session-journal/<parent>.done`.
3. Present the new draft and `scope_lines`, obtain owner approval, approve it,
   then `write-approved ... --expect <current-sha256>`.

`EUNFINISHED` permits this continuation, not a duplicate append or unrelated write.
Alternatively use `resume ROOT --abandon <child-intent> --owner-reply TEXT`.
Only unfinished child intents can be abandoned; a verified append cannot be
unjournaled. Records are renamed, never deleted. Pending Tasks intent belongs in
closingtime's entry Decisions/Next with exact operation, reserved insert UUID
where relevant and “needs fresh approval”; opening does not create that intent.
A blocked close emits truthful status/evidence without the “Session closed” ritual.
A close waiting only on learning dispositions is complete; include the ritual
unless SKIP-ritual. Final-text word counts use count-words after the last edit.

Each independent later helper call chain starts with new-envelope, which stamps
both start and captured_at; do not copy start times. Capture more than fifteen
minutes after invocation start refuses ESTALEEVIDENCE. Retain the frozen envelope
inside its approval/write chain. Bound interrupted recovery remains exempt.

## History, projection and conflicts

One parser feeds snapshot, validation, append and audit. Writers emit `---`, a
blank line, then `### Session #N | YYYY-MM-DD | Mode (Tool)`. The legacy first
entry may follow `# Session Log` directly and is counted. Numbers/dates use ASCII
digits. Duplicate numbers, malformed headers and impossible dates refuse
`EHISTORY`; non-monotonic numbers warn `session_non_monotonic` in the brief.
Entries need populated Focus, Done, Next, Blockers; Decisions is optional.
`Session #[N]` is substituted; embedded headers/separators are refused.
Date skew over one day from local_date warns; impossible draft dates refuse.

`--entries 1..10` changes projection only; the tail digest always covers two
entries. Whole files are read, with at most 16,384 bytes emitted. Older entries
are dropped before latest-entry truncation; index text may also be truncated.
When Next is truncated, name it unknown rather than reconstructing it.

Conflict scans cover root and journal only: generic conflicted-copy, sync-conflict
and case-conflict names, plus continuity stems with ` 2`, ` copy`, ` copy 2`, or
` (2)` names. iCloud-style copies of non-continuity files, recursive subfolders
and OneDrive host-suffix names remain undetected. Unrelated numbered files and
`.orig`/`.bak` backups are negative controls.

## Error catalogue

| Code | Action |
|---|---|
| EINVALIDENVELOPE | inspect enclosed codes; includes sync-conflict refusal at freeze; correct evidence once |
| ELOCK | live/foreign/unreadable lock; wait or inspect; never delete a live lock |
| ELOCK_STALE_RECOVERED | warning: dead same-host pid or expired other-host lock recovered |
| SYNC_CONFLICT / EAMBIGUOUSNAME / EHISTORY | stop; owner reconciles files/history; observe again |
| ESTALEEVIDENCE | new work needs fresh evidence; only bound interrupted recovery is exempt |
| EINVOCATIONUSED | invocation already approved another draft; use the approved draft or a genuinely new invocation |
| EWORKSPACEMISMATCH / WORKSPACE_MISMATCH | different journal identity or inconsistent legacy snapshot root; correct workspace |
| EDRAFTMISMATCH / EDRAFTRECEIPT / ESKILL | correct skill, scope, receipt or payload; refreeze with approval |
| ESTAGE | invalid candidate suffix/prefix change, wrong target, missing close or already consumed staging permission; use separate approval for edits/dispositions |
| SCOPE_UNAPPROVED | approval missing/different, or pending revision lacks owner words; obtain exact approval |
| ESOURCECHANGED / ESTALE | changed preimage, tail or allocated entry number; pre-append refreeze; post-append continue index or abandon child |
| EUNFINISHED | resume; only remaining-target continuation bypasses fresh-freeze block |
| EENTRYFORMAT / EWORDCAP | correct complete rendered entry once; no log write |
| ECHRONOLOGY / INVALID_TIME | correct timezone-aware observation/draft/approval order |
| EINPUT / EBADROWS | correct CLI input or returned-row shape |
| ENOROOT / EPERM | resolve an existing contained root/file; no traversal, directories or symlink escapes |
| EMISSINGVERSION | use constructor-derived package version |
| EPROJECTIONCAP | projection metadata cannot fit; report unavailable, do not hand-truncate evidence |
| EJOURNAL | intent not durable; inspect path; log untouched before intent |
| EREADBACK | conditional rollback verified; inspect retained intent via resume |
| EPARTIAL_APPEND / EPARTIAL_WRITE / ERECOVERY | preserve evidence; resume; ambiguous bytes require reconciliation |
| ENTRY_DATE_SKEW | warning; show actual date discrepancy |
| ENOJOURNAL / ENOPOLICY / EBADPOLICY / EUNMATCHED_EXCEPTION | audit historical coverage/configuration; do not fabricate receipts |
| BAD_STATUS / MISSING_RECEIPT / STALE_RECEIPT / FUTURE_RECEIPT / CONTRADICTORY / FOREIGN_ROWS / FINGERPRINT_MISMATCH | no authoritative external claim; correct evidence once |
| BAD_SESSION_NUMBER / UNRECOGNIZED_SCHEMA / MISSING_LOCAL_CAP / MISSING_EXTERNAL_CAP / LOCAL_CAP_NOT_BOOL / EXTERNAL_CAP_NOT_FOUR_STATE | correct schema and observed capability fields |
| git unavailable/corrupt | name read-only degraded state; unborn branch is normal |

Receipt timestamps allow 120 seconds of skew against invocation start and wall
clock. Operation fingerprints normalize only CRLF to LF and whole-text trailing
whitespace; case/internal literals retain identity. Historical `_policy.json`
uses a nonnegative grandfather_session_ceiling; exception numbers must exceed it,
with entry hash and hash-bound evidence under journal/historical-exceptions/.
Legacy policy schema labels are not authenticated or automatically rewritten.

At most one file argument can be `-` per CLI call; scope and owner reply are literal
arguments. `verify-sync CANONICAL TARGET...` compares package trees excluding
`__pycache__` and `.DS_Store`. Run `python3 evals/structural_eval.py` from a package.
Without Python/shell, output unverified drafts only; no manual persistence fallback.
