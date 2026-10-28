# Recovery and persistence contract (2.1.0 / 3.1.0)

This table is the test oracle. All sanctioned local writers and resume share a
same-host lock. Paths, conflicts and preimages are rechecked inside it. Dropbox
and other devices do not honor it: a residual check/replace or check/rollback
window remains. No cross-device lost-update guarantee is made.

| Boundary / observed bytes | Durable evidence | Outcome / next action |
|---|---|---|
| Refusal before intent | none | no project write |
| Intent temporary file, before atomic rename | possible foreign temporary file | no log write; preserve/report |
| Complete intent fsynced, renamed `.pending`, directory fsynced | root, target, existence, byte length/hash, number, exact append bytes/hash, receipt, invocation, scope, all approved M2 preimages/payload hashes | safe to attempt append |
| Log equals preimage (including absence) | `.pending` | `not_appended`; resume renames `.abandoned`, never deletes |
| Log equals preimage plus exactly intended bytes | `.pending` | `appended`; resume finalizes journal; safe to repeat |
| Log differs from both | `.pending` | `partial_or_conflicted`; preserve all bytes, stop |
| Append readback fails but bytes equal exact intended extension | `.pending` | conditional rollback; restore absence for first append; mark `.abandoned` |
| Rollback cannot prove extension or fails | `.pending` | `EPARTIAL_APPEND`; preserve evidence, resume |
| Journal commit rename/fsync fails | `.pending` or final record | `EPARTIAL_APPEND`; inspect bytes via resume, never reclose |
| Append verified; approved M2 operations remain | `.json` intent | unfinished; fresh freeze refuses `EUNFINISHED` |
| M2 replacement/deletion before mutation | atomic `.pending` transition intent | preimage unchanged: not applied; postimage exact: applied; otherwise stop |
| M2 readback/receipt failure | transition intent and actual bytes | resume classifies; do not infer success from presence |
| All local operations verified | `.done` intent / transition | finished locally; resume still checks actual entry and transitions |
| Explicit owner-approved abandon | `.abandoned` | retained evidence; never retries external operations |
| Legacy v1 record | unchanged `.json` and `_policy.json` | legacy consistency only; no automatic rewrite/recovery |

Tests simulate failures at write, fsync, readback, rename and unlink; seeded
crash boundaries exercise recovery. Real process kills, power loss and real
Dropbox races are not tested. Hashes and receipts are consistency checks, not
proof of owner approval, original provenance or authenticity. Direct writes
can be adopted by a later snapshot and are not reliably detectable.

## Commands and lifecycle

`new-envelope ROOT` derives skill/version from its package, captures a snapshot,
and leaves external capabilities `unprobed`. Record observed four-state service
states before validation. `snapshot ROOT --entries 1..10` changes projection
only; the concurrency tail always hashes two entries. The helper reads whole
files and emits a bounded projection; oversized latest entries are explicitly
truncated from their header, never silently shown as complete.

`freeze-draft ENVELOPE [ENTRY] [INDEX]` allows an index-only opening. It returns
canonical `scope_lines` (explicit kinds and normalized relative paths) and
`scope_sha256`. Show that exact text. `approve-draft RECEIPT SCOPE --owner-reply
TEXT` accepts only exact scope text. An exclusion requires revise/freeze again.
Owner words are retained separately and are not interpreted or authenticated.
Old draft receipts must be re-frozen; legacy journals remain supported.

Close order: append, approved Tasks writes and fresh read, one index transition.
`write-approved ENVELOPE RECEIPT PATH [PAYLOAD] --operation replace|delete
--expect SHA256|absent [--mirror-rows ROWS]` targets only the observed index,
pending learnings or decisions archive. Index requires the frozen draft; archive replacements require their exact
local_payload_hashes binding before freeze; only
its `## Active TODOs` body may be replaced by `render-mirror` derived content.
Each pending revision (stage, owner edit, mixed disposition, deletion) uses a
fresh explicit precondition; owner dispositions/edits need conversation approval.
An index is written at most once per draft. Absent and empty differ.

`resume ROOT [RECEIPT]` needs no scratch artifact; inspect durable intents and
actual bytes, including final records. Append intents retain the approved
envelope, receipt and index draft; resume returns recovery_inputs for remaining
local paths, so loss of scratch files does not force another close. Write
intents retain their payloads and recovery inputs too. It refuses wrong roots, malformed,
foreign or multiple conflicting records. It reports remaining local paths and
never retries Tasks/Open Brain. Fresh external retries recheck preconditions
and need fresh approval. `resume ROOT --abandon INTENT --owner-reply TEXT`
records explicit abandonment by rename, never deletion.

Pending Tasks operations belong in the entry's `Decisions:`/`Next:`: exact
operation, reserved insert UUID when relevant, and "needs fresh approval".
No separate queue file. Newbeginning reports unfinished operations before a
fresh close. Semantic narrative contradictions require stopping; a stale index
date alone is a gap. Opening bootstrap/reconstruction uses index-only freeze,
approve and write-approved; opening never appends (`ESKILL`).

## Errors and operator action

| Code | Action |
|---|---|
| ELOCK | wait or ask; never delete a live lock |
| ELOCK_STALE_RECOVERED | warning: helper recovered an expired same-host lock |
| SYNC_CONFLICT / EAMBIGUOUSNAME / EHISTORY | stop; owner reconciles files/history, then new snapshot/draft |
| EWORKSPACEMISMATCH / WORKSPACE_MISMATCH / EDRAFTMISMATCH / EDRAFTRECEIPT / ESKILL | stop; correct binding, re-freeze and approve |
| SCOPE_UNAPPROVED | revise proposal; exact scope needs approval |
| ESOURCECHANGED / ESTALE | preserve foreign content; new observation and approval |
| EENTRYFORMAT / EWORDCAP / INVALID_TIME / EINPUT | correct one input once; repeated failure is a blocker |
| ENTRY_DATE_SKEW | warning for header more than one day from local date; impossible dates refuse |
| EUNFINISHED | resume existing intent; do not draft another close |
| EJOURNAL | intent not safely persisted; log untouched; inspect journal path |
| EREADBACK | conditional rollback verified; inspect retained intent via resume |
| EPARTIAL_APPEND / EPARTIAL_WRITE / EPARTIAL / ERECOVERY | preserve all evidence; resume; ambiguous bytes stop |
| MISSING_RECEIPT / STALE_RECEIPT / FUTURE_RECEIPT / CONTRADICTORY / FOREIGN_ROWS / FINGERPRINT_MISMATCH | no authoritative external claim; correct evidence once |
| git unavailable/corrupt | named read-only degraded state; no git claim; unborn is normal |

Receipt clock tolerance is 120 seconds in both directions (past against start,
future against helper clock). All instants require timezone-aware ISO-8601.
Operation fingerprint normalization: CRLF to LF, then trim trailing whitespace
at the end of the entire text; preserve case and internal whitespace/literals.

Journal: `private-artifacts/session-journal/`; lock: temporary
`session-skill-locks/<resolved-root-sha256>.lock`. Intent temp and final paths
are contained under the workspace, with external symlinks refused. Directory
fsync follows intent/commit rename; power-loss durability remains platform-bound.
Historical policy filename `_policy.json`: `schema_version: "1.0"`, required
`grandfather_session_ceiling` nonnegative integer; optional
`documented_unverified_exceptions` entries contain `session_number`,
`entry_sha256`, `evidence_path`, `evidence_sha256`. Notes live under
`private-artifacts/session-journal/historical-exceptions/*.md`; do not invent
historical receipts. Legacy records are reported as legacy, not rewritten.

Conflict scan: workspace root and journal directory only. Generic conflicted
copy, sync-conflict and case-conflict names; continuity-only numbered, `copy`,
and `(number)` names stop. No recursive/OneDrive host-suffix reconciliation;
unrelated numbered files and `.orig`/`.bak` backups are negative controls.

## Stdin and package checks

At most one file argument can be `-` per invocation: validate envelope;
freeze envelope/entry/index; approve receipt; append envelope/entry/receipt;
write-approved envelope/receipt/payload/mirror rows; fingerprint-rows rows;
fingerprint-operation text; count-words text; render-mirror rows; resume receipt.
Scope and owner reply are literal arguments. Use `skip-plan tasks,index` for
callable skip policy. `verify-sync CANONICAL TARGET...` compares complete trees,
not just version numbers. No Python: output entry, index and task drafts;
nothing is persisted. No manual append fallback.
