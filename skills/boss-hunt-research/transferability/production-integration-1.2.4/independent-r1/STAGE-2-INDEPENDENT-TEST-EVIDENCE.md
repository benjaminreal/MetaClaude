# Stage 2 Independent Test Evidence

Date: 2026-08-21
Artifact tested: `boss-hunt-research`, candidate 1.2.1
Tester posture: competent fresh user; no prior remediation plans, defect lists, intended answers, or author intervention.

## Scope and controls

- Read the complete Transferability Protocol (425 lines) before testing.
- Inspected the current skill documentation, executable references/scripts, `evals/fixtures/target.json`, and `evals/cold_handoff/SYNTHETIC_EVIDENCE.md`.
- Did not read the pre-existing `transferability/` evidence files, browse, use live connectors, install anything, spend credits, or mutate external state.
- All generated artifacts were written under `/private/tmp/bosshunt-v121-recert/`; no skill or Job Hunting production file was edited.
- Synthetic evidence was treated as fictional mechanics only, never as live source truth.

## Inputs and hashes

Key SHA-256 hashes at test time:

| Input | SHA-256 |
|---|---|
| `SKILL.md` | `5bb933235535f1be1d52568c7124d5d69c679dbdbcd429890e2980c1a27bead6` |
| `evals/fixtures/target.json` | `b738c2787977db7408413daf0b347207484a09b7a5662dc732ef0e83431c066e` |
| `evals/cold_handoff/SYNTHETIC_EVIDENCE.md` | `fbe9eb44c9203665877400b62c3044a282ef03e09a929a6538c3abf0b328a6d3` |
| `references/process.md` | `378bdf19d34cbc0f385317bc648cb6850e77dbd41249996ce59876c524d6c320` |
| `references/authoring-guide.md` | `ec5f2982f7b284347784453d0c721605f3610dea83b6a158f503351269dd77f2` |
| `references/dossier-contract.md` | `ac073017bc661edd33c5b6cda0d7a742efe5137d6f6530acad51c7d51357e6e2` |
| `evals/structural_eval.py` | `5b469422644266b103b50f91f92f9fd6bbfe8cb8f30f76db16927bd4dbf1208b` |

The helper command `python3 scripts/hash_evidence.py evals/cold_handoff/SYNTHETIC_EVIDENCE.md` returned exit 0 and `sha256:fbe9eb44c9203665877400b62c3044a282ef03e09a929a6538c3abf0b328a6d3`.

## Offline workflow commands and results

All commands below were run from the skill root.

| # | Command | Exit | Observed result/artifact |
|---:|---|---:|---|
| 1 | `BOSSHUNT_RUN_DIR=/private/tmp/bosshunt-v121-recert; python3 scripts/build_search_plan.py evals/fixtures/target.json --output "${BOSSHUNT_RUN_DIR}/search-plan.json"` | 0 | `search-plan.json`; SHA-256 `b469a850a8fe1e635efca481fddf4c51f6cb45a26f8fffa46a80b3ff546a07f5` |
| 2 | `python3 scripts/init_dossier.py evals/fixtures/target.json --run-id run-20260821-bosshunt-v121-recert --researcher-id recert-researcher --output /private/tmp/bosshunt-v121-recert/dossier.json` | 0 | `INITIALIZED_INCOMPLETE`; dossier SHA-256 `2ad7a8fe89119f4b045eda07645304b691032a3fef2c47c9c1a0d7c576bd26a5` |
| 3 | `python3 scripts/validate_dossier.py /private/tmp/bosshunt-v121-recert/dossier.json` | 1 | Three structural failures: `STRUCT_MIN_ITEMS` for `guards.receipts`, `hook_search.intents`, and `search.queries_run` |
| 4 | `python3 scripts/review_record.py prepare /private/tmp/bosshunt-v121-recert/dossier.json --reviewer-id recert-independent-reviewer --output /private/tmp/bosshunt-v121-recert/review.json` | 0 | Review request created; SHA-256 `b45412f9c3a6d7bb632924d8319e34f16da5b62343b12b17525b21e77f9e4d2c` |
| 5 | `python3 scripts/review_record.py attach /private/tmp/bosshunt-v121-recert/dossier.json /private/tmp/bosshunt-v121-recert/review.json --output /private/tmp/bosshunt-v121-recert/dossier-reviewed.json` | 0 | Review attached; SHA-256 `e708c1e8e5e92b3bd55fa7a25f2f5363ebdd6219a1dd61805ef742961b792af1` |
| 6 | `python3 scripts/validate_dossier.py /private/tmp/bosshunt-v121-recert/dossier-reviewed.json` | 1 | Same three structural failures; attaching a pending review did not make the incomplete dossier promotable |
| 7 | `python3 evals/structural_eval.py` | 0 | `PASS: 38 required files; ... 6 behavioral fixtures; 18 one-defect mutants; Hunter fail-closed states; authoring/review helpers` |
| 8 | `python3 -c 'import importlib.util,sys; from pathlib import Path; root=Path("."); s=importlib.util.spec_from_file_location("v", root/"scripts/validate_dossier.py"); v=importlib.util.module_from_spec(s); sys.modules["v"]=v; s.loader.exec_module(v); s=importlib.util.spec_from_file_location("f", root/"evals/behavioral_fixtures.py"); f=importlib.util.module_from_spec(s); sys.modules["f"]=f; s.loader.exec_module(f); [(print(name, "PASS" if not v.validate(factory(v)) else "FAIL", [i.code for i in v.validate(factory(v))])) for name,factory in f.NAMED_FIXTURES.items()]'` | 0 | All six named fixtures returned `PASS []`; details below |

## Six named behavioral/edge cases

| Fixture | Result |
|---|---|
| `valid_literal_seat_hit` | PASS |
| `literal_seat_miss` | PASS |
| `generic_fallback` | PASS |
| `recruiter_route` | PASS |
| `stale_person` | PASS |
| `company_collision` | PASS |

The generated plan showed the required monotonic order: target authority, guards, reporting hypotheses, organization/seat/alternatives/owner/adjacent routes, authenticated currentness, hook artifact/gate, first-party email, Hunter, adversarial gate, handoff. Hunter was fail-closed as `UNAVAILABLE`/`NOT_APPLICABLE` with zero permitted credits.

## Seven-section coverage and cross-section check

| SKILL section | Fresh-user action/test | Result |
|---|---|---|
| 1 Purpose & Scope | Read scope and authority boundary before any command; excluded live actions and release claims | Transferable boundary was clear |
| 2 Pre-flight Checklist | Applied the canonical target, isolated run directory, capability map, and planner command | Plan exited 0; G1 is a missing pre-flight reference |
| 3 Core Workflow | Followed the plan through initialization, hashing, structural validation, review preparation, and attachment | Transferable through review-request preparation; completion stopped at G2 |
| 4 Adaptations | Exercised Hunter-unavailable fallback, literal-seat miss, stale person, collision, V2 refusal, and channel/proof behavior through the suite | Six fixtures and mutant checks passed |
| 5 Decision Rules | Checked readiness/route invariants and observed validator outcomes for the named branches | Decisions were mechanically testable |
| 6 Eval Criteria | Ran the portable structural/behavioral suite and direct fixture validator | Exit 0 in the later observed tree |
| 7 Version & Changelog | Checked candidate version, supersession notes, and section annotation against the re-certification requirement | Cross-section contradiction: Section 7 explicitly remains pending (G3) |

Cross-section consistency was therefore not fully clean: Section 2 omits a reference required by Sections 3/process, Section 6 depends on the Section 2 run-directory precondition without repeating it, and Section 7 says re-certification is pending while the candidate is the current build.

## Completion judgment

The fresh user completed the offline setup, plan generation, dossier initialization, hash capture, and hash-bound review-request preparation/attachment without author help. The user did **not** complete a valid, fully populated dossier or a completed independent semantic review: the supplied evidence pack does not supply the second reviewer, and the initializer intentionally leaves required ledgers empty. Therefore the complete workflow was **not completed without author/external-reviewer help**. This is an honest workflow boundary, not a live-evidence failure.

## Environment race observed

The first file inventory during this test did not contain `BACKLOG.md` or `HANDOFF.md`, although `structural_eval.py` lists both as required. When the evaluator was run later, both files existed and the evaluator returned PASS. I did not create or edit either file. Because the shared workspace changed concurrently, the structural PASS should be treated as a result of the later observed tree, not as proof that the initial tree was stable.
