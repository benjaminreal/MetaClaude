# closingtime 3.2.2 — candidate

This package is canonical source, not installed or certified for deployment.
Prior Phase 4 behavior results apply to earlier hashes only. The previous
Phase 4.5 decision was FAIL; the full record is in the maintainers' private
evaluation archive, and a public summary is in the repository's
`skills/_shared/validation/phase4_5/README.md`.
A fresh Phase 4 eligibility determination precedes the next Phase 4.5;
deployment waits for Phase 4.5 PASS and Phase 5.

Python 3 and shell access are required for every bundled helper; only the
standard library is used. Without Python, output drafts and say nothing was
persisted. Optional Git, Tasks MCP and Open Brain are observed separately;
no credentials or network client are bundled.

Use `python3 /path/to/closingtime/scripts/runtime_cli.py new-envelope ROOT` to
start. It captures start/captured_at and derives this package's name/version. Later
independent helper chains use new-envelope; never copy earlier start times.
Capture more than fifteen minutes after start refuses ESTALEEVIDENCE. Word
counts use count-words on exact final text sent, after the last edit.
Discover services and replace both `unprobed` states before validation. Read
`references/envelope_examples.md` for complete JSON recipes and
`references/recovery.md` for exact command syntax, state tables, stdin support,
errors and historical migration. At most one file argument per call may be
`-`; do not assume every literal argument supports stdin.

All project writes need the displayed approval scope. Freeze returns canonical
scope_lines, approve compares that exact text and records owner_reply
separately. An exclusion requires a revised freeze; the exclusion reply is not
approval, so show the new scope_lines and wait. Hashes are consistency
checks, not proof of conversation authority, provenance or authenticity.

The helper reads whole continuity files and emits a bounded projection (16,384
bytes); it does not bound filesystem bytes read. It explicitly reports index
or latest-entry truncation. Snapshot --entries 1..10 changes projection only;
the concurrency digest always covers two entries. Ancestor instruction
files still need explicit reading. Semantic narrative contradictions stop;
a stale index date alone is a gap.

Conflict detection covers workspace root and journal directory only: conflicted
copy, sync-conflict, case-conflict and continuity-specific numbered/copy names.
Aliases are reported or refused when ambiguous. There is no recursive/OneDrive host-suffix reconciliation or detection of
iCloud numbered copies for non-continuity files; Finder continuity " copy 2" is detected. Writers share `private-artifacts/session-journal/.lock` across TMPDIR values.
Same-host dead pids recover immediately; live pids block regardless of age.
Other-host locks expire after ten minutes, even during a legitimate long write.
Recovery warnings are reported. Other devices can write in the residual precheck/replace or rollback window. No
absolute cross-device lost-update guarantee is made.

Legacy v1 continuity layouts, journals and _policy.json stay readable and are
never automatically rewritten. Legacy journal matching is limited consistency
evidence, not crash recovery. Legacy pending blocks stay opaque: preserve
Connection/Connects to, absent Status and unknown metadata without data loss.

Not validated here: live Tasks writes, live Open Brain, real process kills,
power loss, actual Dropbox races, other languages or fresh behavior in both
harnesses. Deterministic faults and seeded crash states are synthetic.

## Operator handoff


Parent scope permits session, index and optional pending stage. Other learning
or archive writes require separate approval; skips/zero candidates create no child.
Close order: observe → draft entry/index/operations → freeze → show exact scope
→ approve → append → Tasks writes and fresh read → one write-approved index
transition with mirror_receipt/--mirror-rows → verify/audit → learnings.
Index content is bound before approval; only Active TODOs is regenerated from
fresh receipt rows. Archive overflow names project_decisions_archive.md in M2
and binds its exact payload in local_payload_hashes. Pending edits/dispositions
use --expect current SHA-256 and non-empty --owner-reply; stage uses the close's
recorded owner words. Pending approval expires
after six hours. Only started stage writes become child obligations; an unused
optional permission never holds the close open. A failed stage resumes/abandons
independently and never unjournals the verified append.

Search candidate connections (or name unavailability), then append only new
blocks with write-approved --operation stage --expect current-sha256|absent.
Preserve the existing bytes; stage once after verified parent append. Read back
pending_learnings.md before presenting candidates. Keep needs no write; show
frozen scope_lines with any edit/discard/delete question so the reply approves it. Owner edits are
written/read back before approved capture. Mixed disposition retains unresolved
blocks, deletion follows complete disposition. Capture requires separate
approval. SKIP-openbrain skips search and capture but retains separately
approved extraction/storage; an instruction not to capture alone does not skip
search. Search sends candidate text to the service.

Append writes a durable intent before any log bytes. On error use resume ROOT
and audit, not another logical close. Unfinished children block fresh freezes except a remaining-target continuation.
Resume inspects actual bytes even for final records and needs no scratch file;
it never retries external calls. Fresh retries need preconditions and approval.
The append finalizes at readback; its index is a child intent. For remaining_stale,
freeze-draft --continue <parent-intent> with only the index, approve new scope,
then write-approved; alternatively abandon only the unfinished child. Verified
appends cannot be abandoned. Intent records are renamed, never deleted. Consider ignoring
private-artifacts/session-journal/ in git according to project policy.

Degraded Tasks operations remain in entry Decisions/Next, with exact operation,
reserved insert UUID and "needs fresh approval"; the mirror stays untouched.
Waiting only for learning dispositions is complete and includes the ritual
unless SKIP-ritual. Learning may proceed once attempted local writes read back and each external
operation is verified or recorded pending. A blocked close omits the "Session closed" ritual. Status lines must describe actual
verified, partial, skipped or pending state; evidence then ritual line last.

Use the whole folder; runtime and references are bundled independently of its
sibling. The original receipt survives a bound interrupted operation returned by resume;
otherwise re-observe and freeze a current receipt. New evidence expires after
six hours, with at most 120 seconds future skew. One draft approval per invocation;
discard superseded proposals before approval (conversation duty).
For re-certification, freeze the exact tree hash and use `python3 evals/structural_eval.py`,
the repository Phase 4 eligibility note and the Phase 4.5 implementation report.
No installation into personal skill directories occurs during implementation.
