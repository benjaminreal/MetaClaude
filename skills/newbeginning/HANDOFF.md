# newbeginning 2.1.0 — candidate

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

Use `python3 /path/to/newbeginning/scripts/runtime_cli.py new-envelope ROOT` to
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


Routine use returns an evidence-backed brief of at most 250 words and stops.
The hand-off question precedes the final evidence line. It does not begin work
or append a session. Five branches: normal, index-only, reconstruction,
bootstrap and conflicted (stop). An unborn branch is normal; corrupt git
explicitly degrades. Without a current Tasks receipt, tasks are unverified and
the Markdown mirror is read-only.

Approved bootstrap/reconstruction uses the shipped index_template.md,
index-only freeze-draft, approve-draft and write-approved --expect. Approved
post-brief actions include reserved-UUID task creation, Open Brain captures,
and pending-file owner edits/dispositions/deletion. Task update/completion/
parking/cancellation remain outside opening scope. A search is a read; an
instruction not to capture does not skip it. SKIP-openbrain means no use at all
and skips search and capture; search sends candidate text to the service.

Report unfinished_operations and direct the operator to resume before a new
close. Pending Tasks intent lives in the session Decisions/Next with exact
operation, reserved UUID if applicable, and "needs fresh approval".

Use the whole folder; runtime and references are bundled independently of its
sibling. Do not copy an old draft receipt forward: freeze a new current receipt.
For re-certification, freeze the exact tree hash and use README.md's checks,
the repository Phase 4 eligibility note and the Phase 4.5 implementation report.
No installation into personal skill directories occurs during implementation.
