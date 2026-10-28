# newbeginning 2.2.2 — candidate

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


Routine use returns an evidence-backed brief of at most 250 words and stops.
The hand-off question precedes the final evidence line. It does not begin work
or append a session. Five branches: normal, index-only, reconstruction,
bootstrap and conflicted (stop). An unborn branch is normal; corrupt git
explicitly degrades. Without a current Tasks receipt, tasks are unverified and
the Markdown mirror is read-only.

Approved bootstrap/reconstruction uses the shipped index_template.md,
index-only freeze-draft, approve-draft and write-approved --expect. These are
opening's only writes. Task creation, Open Brain captures and pending-file
edits/dispositions/deletion belong during the session or at closingtime: route
those requests there and stop. Searches remain reads; SKIP-openbrain means no
search or capture, since searches send candidate text to the service.

Report unfinished_operations and direct the operator to resume. A verified
append stays journaled; changed remaining indexes use a fresh index-only
freeze-draft --continue <parent-intent> with new approval, or approved child
abandonment. Opening never creates pending Tasks intent.

Use the whole folder; runtime and references are bundled independently of its
sibling. The original receipt survives a bound interrupted operation returned by resume;
otherwise re-observe and freeze a current receipt. New evidence expires after
six hours, with at most 120 seconds future skew. One draft approval per invocation;
discard superseded proposals before approval (conversation duty).
For re-certification, freeze the exact tree hash and use `python3 evals/structural_eval.py`,
the repository Phase 4 eligibility note and the Phase 4.5 implementation report.
No installation into personal skill directories occurs during implementation.
