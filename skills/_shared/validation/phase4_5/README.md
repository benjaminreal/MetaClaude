# Phase 4.5 evidence and Phase 4 eligibility

2026-10-27 implementation eligibility note for newbeginning 2.1.0 and
closingtime 3.1.0. Deterministic Phase 3 eligibility is necessary; prior Phase 4
results apply only to their earlier candidate hashes. Material runtime and
workflow changes require fresh Phase 4 behavior in Claude Code and Codex,
English and Spanish, on the frozen repaired hashes before the next Phase 4.5.
Current Phase 4 eligibility for immediate Phase 4.5 certification: NOT YET
ESTABLISHED. Do not transfer the historical PASS. No model behavior was rerun
as part of this local implementation task.

Previous independent decision (newbeginning 2.0.7, closingtime 3.0.10): FAIL.
Reasons, reproduced by the reviewer: Dropbox-style conflict copies were not
detected; a repository without commits blocked the snapshot; evidence from
another workspace and contradictory or undated task receipts were accepted;
closingtime wrote a malformed multi-header entry before refusing and had no
safe recovery after an interrupted append. 2.1.0 / 3.1.0 address these; they
are not yet re-tested by fresh model sessions or re-reviewed.

The full decision, evidence packet and implementation report are kept in the
maintainers' private evaluation archive (`private-artifacts/`, not published).
This directory is a pointer, not a certificate. Deployment waits for
Phase 4.5 PASS and Phase 5.
