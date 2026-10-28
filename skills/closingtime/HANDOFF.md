# closingtime 3.1.0 — candidate

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
start. It captures the snapshot and derives this package's name/version.
Discover services and replace both `unprobed` states before validation. Read
`references/envelope_examples.md` for complete JSON recipes and
`references/recovery.md` for exact command syntax, state tables, stdin support,
errors and historical migration. At most one file argument per call may be
`-`; do not assume every literal argument supports stdin.

All project writes need the displayed approval scope. Freeze returns canonical
scope_lines, approve compares that exact text and records owner_reply
separately. An exclusion requires a revised freeze. Hashes are consistency
checks, not proof of conversation authority, provenance or authenticity.

The helper reads whole continuity files and emits a bounded projection (16,384
bytes); it does not bound filesystem bytes read. It explicitly reports index
or latest-entry truncation. Snapshot --entries 1..10 changes projection only;
the concurrency digest always covers two entries. Ancestor instruction
files still need explicit reading. Semantic narrative contradictions stop;
a stale index date alone is a gap.

Conflict detection covers workspace root and journal directory only: conflicted
copy, sync-conflict, case-conflict and continuity-specific numbered/copy names.
Aliases are reported or refused when ambiguous. There is no recursive or
OneDrive host-suffix reconciliation. Same-host writers share a lock; other
devices can write in the residual precheck/replace or rollback window. No
absolute cross-device lost-update guarantee is made.

Legacy v1 continuity layouts, journals and _policy.json stay readable and are
never automatically rewritten. Legacy journal matching is limited consistency
evidence, not crash recovery. Pending files have no runtime parser: preserve
Connection/Connects to, absent Status and unknown metadata without data loss.

Not validated here: live Tasks writes, live Open Brain, real process kills,
power loss, actual Dropbox races, other languages or fresh behavior in both
harnesses. Deterministic faults and seeded crash states are synthetic.

## Operator handoff


Close order: observe → draft entry/index/operations → freeze → show exact scope
→ approve → append → Tasks writes and fresh read → one write-approved index
transition with mirror_receipt/--mirror-rows → verify/audit → learnings.
Index content is bound before approval; only Active TODOs is regenerated from
fresh receipt rows. Archive overflow names project_decisions_archive.md in M2
and binds its exact payload in local_payload_hashes. Pending revisions each
use --expect current SHA-256 and record conversation-approved wording.

Search candidate connections (or name unavailability), then merge/stage and
read back pending_learnings.md before presenting candidates. Owner edits are
written/read back before approved capture. Mixed disposition retains unresolved
blocks, deletion follows complete disposition. Capture requires separate
approval. SKIP-openbrain skips search and capture but retains separately
approved extraction/storage; an instruction not to capture alone does not skip
search. Search sends candidate text to the service.

Append writes a durable intent before any log bytes. On error use resume ROOT
and audit, not another logical close. Unfinished intents block fresh freezes.
Resume inspects actual bytes even for final records and needs no scratch file;
it never retries external calls. Fresh retries need preconditions and approval.
Intent records are renamed, never deleted. Consider ignoring
private-artifacts/session-journal/ in git according to project policy.

Degraded Tasks operations remain in entry Decisions/Next, with exact operation,
reserved insert UUID and "needs fresh approval"; the mirror stays untouched.
Learning may proceed once attempted local writes read back and each external
operation is verified or recorded pending. Status lines must describe actual
verified, partial, skipped or pending state; evidence then ritual line last.

Use the whole folder; runtime and references are bundled independently of its
sibling. Do not copy an old draft receipt forward: freeze a new current receipt.
For re-certification, freeze the exact tree hash and use README.md's checks,
the repository Phase 4 eligibility note and the Phase 4.5 implementation report.
No installation into personal skill directories occurs during implementation.
