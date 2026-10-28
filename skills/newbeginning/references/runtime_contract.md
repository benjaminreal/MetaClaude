# Session runtime contract

Run the bundled `scripts/runtime_cli.py` with `python3` (standard library only).
Python is required for every helper path. Without it, output entry, index and
task drafts; nothing is persisted. No manual append fallback.

```text
new-envelope <workspace-root>
snapshot <workspace-root> --entries 2
fingerprint-rows <rows.json|->
fingerprint-operation <query.sql|->
validate <envelope.json|->
freeze-draft <envelope.json> [<entry.md>] [<index.md>]
freeze-draft <envelope.json> --index-draft <index.md>
approve-draft <draft-receipt.json> "<exact scope_lines>" --owner-reply "<owner words>"
append <envelope.json> <entry.md|-> <approved-receipt.json>
write-approved <envelope.json> <approved-receipt.json> <observed-relative-path> [<payload|->] --operation replace|delete --expect <sha256|absent>
resume <workspace-root> [<approved-receipt.json>]
audit <workspace-root>
skip-plan tasks,index
count-words <text-file|->
render-mirror <rows.json|-> <local-date>
verify-sync <canonical-dir> <target-dir> [<target-dir> ...]
```

Read [envelope_examples.md](envelope_examples.md) when assembling evidence;
[recovery.md](recovery.md) before persistence, recovery or a helper refusal.
It contains the state table, exact stdin matrix, errors and migration policy.
Opening bootstrap/reconstruction also uses `index_template.md`
(shipped only by newbeginning); closingtime's entrypoint includes its template.

Keep envelopes, rows, entry and index drafts in harness scratch outside the
repository. At most one stdin argument per call. A failed input may be
corrected once; repeated failure is a named blocker.

## Evidence authority

`new-envelope` derives its skill/version from its package, mints an invocation
id, copies snapshot observed_at to invocation_started_at, and deliberately sets
services to `unprobed`. That is not evidence of absence. Discover services and
record observed states: absent, present_unauthenticated, present_wrong_scope or
working. Both working capabilities require current receipts. Receipt times and
snapshot/start are timezone-aware instants; tolerance is 120 seconds in both
directions. Copy observed times from the tool or fingerprinted_at, never type
live times. `fingerprint-operation` normalizes only CRLF to LF and trailing
whitespace at the end of the entire text; quoted literals retain identity.

Authoritative Tasks evidence requires envelope.project, receipt.identity.project
and every returned row.project to agree. Missing identity refuses authority,
including empty result sets. Explicit portfolio mode uses envelope.project
"portfolio" and receipt.identity.scope "portfolio", with row projects present.
Service project_ref/account identity must agree with capability external_detail
for both services. Preserve actual rows so validate recomputes fingerprints.
These are consistency checks, not proof of authenticity or source provenance.

## Snapshot and gates

The helper reads whole continuity files and emits at most 16,384 projection
bytes. --entries accepts 1..10 (default 2); the concurrency tail always hashes
two entries. Older complete entries are dropped before truncating the latest;
latest_entry_truncated names an oversized entry, retained from its header.
Index text can be truncated too. Do not claim a full index when truncated.
Git evidence uses --no-optional-locks and NUL porcelain paths, scopes changes
to the requested root before capping at 20, distinguishes unborn from corrupt,
and explicitly degrades failed git reads without retrying with optional locks.
Snapshot reports up to 20 depth-one subprojects and unfinished_operations.

Instructions resolution reports project_root/ancestor/instructions_absent,
files and ancestor_files with bytes. Read every unique file explicitly, even
when the harness preloaded it; conflicting task rules or semantic narrative
contradictions stop. A stale Updated date alone is a gap. Session-unparseable,
duplicate numbers, malformed headers, alternate histories or sync conflicts
stop persistence and the opening brief; reconcile only with separate approval.

Freeze binds root/snapshot/entry/index, scope kinds and paths. Show scope_lines
verbatim. An exclusion requires a revised freeze; owner_reply is recorded
separately, not interpreted or authenticated. Append is closingtime-only.
write-approved is the sanctioned non-session writer and takes the same lock.
Journal effects appear in the append scope line. Archive overflow must name
project_decisions_archive.md in M2 and bind its payload SHA-256 in
local_payload_hashes before freeze. Pending candidate payloads are approved
in conversation at each revision and bound in each transition intent.

Close order: append → approved Tasks operations and fresh read → one index
write. For a current read, attach its mirror_receipt and use --mirror-rows;
write-approved regenerates only the Active TODOs body. Without current rows,
retain the frozen mirror. No task changes still requires fresh mirror rows.
Every local mutation needs readback; every external mutation needs returned
results/readback or an exact pending operation in Decisions/Next, reserved UUID
for inserts and "needs fresh approval". A partial result remains partial.

Audit separates final journal matches, pending_journal, pending_records,
legacy_records, grandfathered, documented_unverified, unjournaled, orphans and
foreign_files. Pending is never journaled. Old v1 records/_policy.json remain
unchanged; historical exceptions name a hash-bound local note and never prove
the original append. New receipt versions do not certify old drafts.

Continuity headings, entry fields, Updated and Active TODOs remain v1-readable.
Runtime metadata lives only in the journal. Hashes cannot reliably identify a
direct write adopted by a later snapshot or authenticate supplied approvals.
