# Independent review: <change-id>

**Reviewer:** <harness / model / session id — must differ from the implementer>
**Commit:** <full or ≥12-character sha reviewed>
**Verdict:** <PASS | CONDITIONAL | FAIL>
**Date:** <YYYY-MM-DD>

The install tool accepts only `**Verdict:** PASS` for the exact commit above.
CONDITIONAL means the change must be repaired and reviewed again.

## Procedure

1. Read `skills/STANDARDS.md`, REQUEST.md, PACKET.md and the full diff
   `git diff <base> <commit>`.
2. Re-run the gate yourself from the main checkout's tool. Paste the verdict
   and failures. Do not rely on the implementer's GATE.json.
3. For level 2–3, check out the base commit, run each added test, and confirm it
   fails. Then confirm it passes on the commit.
4. Check that the change does what REQUEST.md asks, and nothing outside it.
5. Walk STANDARDS.md §4 A–G and record each item as followed, exception or
   violation.
6. Level 3 only: reproduce at least one failure path independently (an
   adversarial input or a mutant), and record the command and result.

## Findings

| Severity | File:line | Finding | Required fix |
|---|---|---|---|

## Gate re-run

## Test-first confirmation

## Standards walk

## Not verified
