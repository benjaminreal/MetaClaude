# Session-skills candidate validation — 2026-10-08

Candidates: **newbeginning 2.0.2** and **closingtime 3.0.3**.
Exact package identities are frozen in `candidate_manifest.json` and verified
by `verify_candidates.py`. Hashing excludes Python caches and `.DS_Store`.
Any package change requires a fresh identity and eligibility decision.

## Current evidence

- Local deterministic tests: PASS; see `local_checks.json`.
- Instruction-presence comparison with the August interim baseline: PASS;
  see `instruction_comparison.json`. This is not a model-behavior comparison.
- Raw traces reviewed for the two approved synthetic preflights. Codex passed
  the scoped discovery/Tasks-absent opening preflight. Claude discovered both
  packages but its envelope validation was permission-blocked. Its approved
  retest prevented cache writes, but scratch-envelope creation was still denied,
  so its opening preflight remains incomplete. See
  `preflight_execution.json` and `preflight_review.md`. Neither run is certification.
- Fresh controlled behavioral validation: NOT RUN for these hashes.
- Independent transferability review: NOT RUN for these hashes.
- Production promotion: NOT AUTHORIZED by a draft source PR.

The previous packet targeted newbeginning 2.0.1 / closingtime 3.0.1 and older
package hashes. Its preflight receipts and July transfer certificates are
historical evidence. Neither certifies the current candidates. Installed
copies were not changed by this source preparation.

## Reproduce local checks

Run with the workspace's Python runner, or Python 3 directly in a fresh clone:

```text
python skills/_shared/run_contract_tests.py
python skills/newbeginning/evals/structural_eval.py
python skills/closingtime/evals/structural_eval.py
python skills/_shared/validation/verify_candidates.py
git diff --check
```

The public runner covers contract fixtures, deliberate one-defect variants,
helper filesystem tests, skip/interruption behavior, package regeneration,
opening-only task scope, and the bilingual candidate-quality fixture catalog.
The latter declares semantic expectations; a regex does not grade plainness
or standalone meaning. A private historical scorer is not included.

## Behavioral validation preparation

Preserve the ten-cell integration smoke-test design: two independent harnesses
each execute opening normal/degraded, closeout normal/degraded, and closeout
conflict. Every cell starts in a fresh session with the frozen package. Use
disposable projects for all induced failures and all local mutations.

Before any external AI run, approve its exact model, provider/harness, purpose,
data exposure, and maximum additional cost. Configured models are not evidence
of working preflight. Do not substitute a different model after approval.

1. Fresh preflight per selected harness: native skill discovery, package hash,
   raw trace availability, current Tasks read, and isolated Tasks-absent mode.
2. Freeze per-cell prompts, applicability, approvals/refusals, expected terminal
   state, allowed paths, fixture hashes, and scoring denominators before runs.
3. Run the ten cells and the required negative paths. Record actual receipts,
   raw traces, readbacks, audits, language/candidate quality, and defects.
4. Score retained/mapped invariants and report coverage limits separately.

Normal cells require approved real read-only Tasks evidence. If that cannot be
isolated and observed, mark those cells blocked rather than substituting a
synthetic receipt and calling it a live read. Tasks writes and Open Brain
capture are outside this validation scope.

Negative paths must exercise stale receipt, fingerprint mismatch, foreign-tail
change, pre/post-approval interruption, forbidden external mutation, and
learning-before-presentation ordering. Deterministic tests provide primary
assurance for races; live smoke tests must not induce races in real projects.

## Independent transferability and production

After behavioral validation passes, a reviewer who did not implement the
change receives only the published skill packages, prerequisites, realistic
requests, and raw fixture artifacts. The reviewer must execute normal and
degraded paths without author coaching, audit documentation claims, test
ambiguity/approval/interruption paths, and return a hash-bound PASS,
CONDITIONAL, or FAIL with evidence. The implementer cannot self-certify.

Any repair invalidates affected model/transfer evidence and needs a fresh
eligibility decision. Passing this process permits a separate production
decision and limited approved external-write canaries; it does not itself
authorize installation, live task writes, or Open Brain capture.
