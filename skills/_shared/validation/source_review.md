# Candidate source review — 2026-10-08

Scope: session skill instructions, shared envelope/append/audit runtime,
generated package references, and regression fixtures. This is an implementer
review of the candidate PR, not independent transferability certification.

## Findings and repairs

1. **Session append accepted unrelated approval.** On a disposable project,
   an envelope with an empty M2 list and approval only for a task operation
   successfully appended Session #3. The helper now requires the resolved
   session filename in the approved M2 list before acquiring the lock or writing.
   Regression cases cover task-only and index-only scope and assert unchanged
   session bytes and no journal creation.
2. **First-close audit required a historical policy.** A first append correctly
   created Session #1 and its journal receipt, but audit returned `ENOPOLICY`.
   Missing policy now means a zero exemption ceiling. Exact journal receipts
   verify; existing entries without receipts remain unjournaled. A missing
   journal also no longer labels existing entries grandfathered. Regression
   cases cover first close, no journal, and no policy with historical entries.

The generated helpers/references are synchronized. Current packages are
newbeginning 2.0.3 and closingtime 3.0.4, bound by `candidate_manifest.json`.
Prior model receipts retain their original identities and are historical.

## Verification

Run using the workspace `uv run` environment:

- `python -B skills/_shared/run_contract_tests.py`: PASS, including both fixes.
- Both `evals/structural_eval.py` scripts: PASS, 9/9 each.
- Skill Creator `quick_validate.py` for both packages: PASS.
- `python -B skills/_shared/validation/verify_candidates.py`: hashes match.
- `git diff --check`: PASS.

No further blocker was found in this review scope. The focused model closing
test is prepared but NOT RUN and still requires specific owner authorization.
Candidate merge readiness remains pending that result. Production installation,
live Tasks/Open Brain operations, and independent transferability certification
are outside this source review.
