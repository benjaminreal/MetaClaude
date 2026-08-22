# Candidate 1.2.4 remediation verification

Date: 2026-08-21

This is a fresh verification of the current candidate. Candidate 1.2.3 results were treated as historical and were not transferred as evidence. I read current `SKILL.md` Sections 2, 6, and 7, current `README.md`, current `HANDOFF.md`, the current authoring guide, and the current runtime/eval files needed for the documented checks. Work was limited to the skill, current target fixture, synthetic evidence, and `/private/tmp/bosshunt-v124-remediation-verification`; no browsing, live connector, credit, install, external action, or skill/Job Hunting mutation occurred.

## Documentation reconciliation

| Requested claim | Current evidence | Finding |
|---|---|---|
| (a) Section 6 explicitly identifies `python3 evals/structural_eval.py` as the complete portable structural-plus-behavioral suite | `SKILL.md:96`, `SKILL.md:101-110`; `README.md:34-41` | **CONFIRMED**. It calls this the “single complete portable structural-plus-behavioral suite command.” |
| (b) All six fixtures are named exactly | `SKILL.md:102-104`: `valid_literal_seat_hit`, `literal_seat_miss`, `generic_fallback`, `recruiter_route`, `stale_person`, `company_collision` | **CONFIRMED**. |
| (c) Concrete POSIX and PowerShell isolated-run setup | `SKILL.md:26`, `SKILL.md:32-34`: `export BOSSHUNT_RUN_DIR=...`; `$env:BOSSHUNT_RUN_DIR = "C:\path\to\isolated-run"`; directory must be created first | **CONFIRMED**, with a minor usability note: assignment syntax and the create-first requirement are explicit, but no `mkdir -p`/`New-Item` example is supplied. The portable suite regression passed. |
| (d) Reviewer availability is a conditional dependency and the safe offline ceiling is `REVIEW_PENDING` | `SKILL.md:112-122`; `HANDOFF.md:31,34,48,54`; authoring guide Section 6 | **CONFIRMED**. The researcher cannot simulate review; when no different reviewer is available, the safe handoff stops at `REVIEW_PENDING`. |

Current candidate hashes: `SKILL.md` `b82ed1a0409154a83562996ced7ee10bf6ef495cc774f061e482ad5e925b4fa4`; `README.md` `a9cd56016fa144decbf7f2f67402c0c5fc5059b25174c23e68e3c0d6a6da4a81`; `HANDOFF.md` `87989d7a14ae2708ce9b7d16b60cc700fdd121bd07b571b43a4f3dfb986d2440`; `evals/structural_eval.py` `f0f5f34bdf2a8aa118bade315b1a9765c77a604e972e54499f78306287017f6b`.

## Complete suite and fixture checks

Exact command:

```text
python3 evals/structural_eval.py
```

Exit: `0`.

Output: `PASS: 38 required files; portable runtime docs; canonical target; structural-first validation; 6 behavioral fixtures; 18 one-defect mutants; Hunter fail-closed states; authoring/review helpers`.

Additional documented checks: `python3 scripts/validate_dossier.py evals/fixtures/valid_dossier.json` exited `0` with `PASS`; `python3 scripts/validate_dossier.py evals/fixtures/invalid_apex_dossier.json` exited `1` with `LEGACY_SCHEMA_REFUSED`, as required.

## Fresh isolated pending-review spot-check

Run directory: `/private/tmp/bosshunt-v124-remediation-verification/run`.

| Exact command | Exit / result |
|---|---|
| `export BOSSHUNT_RUN_DIR=/private/tmp/bosshunt-v124-remediation-verification/run && python3 scripts/build_search_plan.py evals/fixtures/target.json --output "${BOSSHUNT_RUN_DIR}/search-plan.json"` | `0` |
| `export BOSSHUNT_RUN_DIR=/private/tmp/bosshunt-v124-remediation-verification/run && python3 scripts/init_dossier.py evals/fixtures/target.json --run-id v124-20260821-j000123 --researcher-id v124-independent-recert --output "${BOSSHUNT_RUN_DIR}/dossier-initialized.json"` | `0`, `INITIALIZED_INCOMPLETE` |
| `python3 scripts/validate_dossier.py /private/tmp/bosshunt-v124-remediation-verification/run/dossier-initialized.json` | `1`, three expected structural minimum errors |
| `python3 scripts/review_record.py prepare /private/tmp/bosshunt-v124-remediation-verification/run/dossier-authored.json --reviewer-id v124-fresh-context-reviewer --output /private/tmp/bosshunt-v124-remediation-verification/run/review-pending.json` | `0`, `REVIEW_REQUEST` |
| `python3 scripts/review_record.py bind-pending /private/tmp/bosshunt-v124-remediation-verification/run/dossier-authored.json /private/tmp/bosshunt-v124-remediation-verification/run/review-pending.json --output /private/tmp/bosshunt-v124-remediation-verification/run/dossier-review-pending.json` | `0`, `REVIEW_PENDING_BOUND` |
| `python3 scripts/validate_dossier.py /private/tmp/bosshunt-v124-remediation-verification/run/dossier-review-pending.json --json` | `1`, exactly one `REVIEW_PENDING` diagnostic |
| `python3 scripts/review_record.py attach /private/tmp/bosshunt-v124-remediation-verification/run/dossier-review-pending.json /private/tmp/bosshunt-v124-remediation-verification/run/review-pending.json --output /private/tmp/bosshunt-v124-remediation-verification/run/dossier-attach-pending.json` | `1`, pending record refused |

The dossier was newly authored from the current target and synthetic evidence; it was not copied from a completed fixture or a 1.2.3 output. The prepare-to-bind transition required no manual JSON intervention. No completed review was fabricated: the current harness did not provide a different human or fresh isolated reviewer, so the safe result remains `REVIEW_PENDING`.

Spot-check artifact hashes: search plan `b469a850a8fe1e635efca481fddf4c51f6cb45a26f8fffa46a80b3ff546a07f5`; authored dossier `5f252bdb0dc3cac891388cfc241e29fe23c5538b23fa66733536f85dec3278d2`; prepared request `da418fe02555cfe68565b4dc9c17e23f10194266a0b84331979c034d7f3698b1`; bound pending dossier `dde4af46d408b331199f525f0dbdb29ffe15e2f8bdcc97d982f2b931ec51093b`.

## Non-blocking observation

The current `SKILL.md` contains a duplicated Section 7 heading and duplicated 1.2.4 changelog sentence at lines 130–132. This did not affect the portable suite or the tested workflow, but it is a cosmetic documentation cleanup item. No edit was made.
