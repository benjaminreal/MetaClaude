# Remediation Defect Dispositions

**Date:** 2026-08-21  
**Candidate:** 1.1.1  
**Rule:** no defect disappears; `FIXED` means implemented and locally evidenced, not live-production proof

| ID | Disposition | Implementation evidence | Regression evidence |
|---|---|---|---|
| R1 | `FIXED` | Stage 1–5 artifacts, ordered certifications, `HANDOFF.md`, onboarding, audit, edge test, statement | Required-file gate plus independent Stage 2 initial/rerun evidence |
| R2 | `FIXED` | `BossHuntTargetV2`, target schema, canonical example/fixture/planner; `source_tracker_id` optional | Documented planner CLI passes; missing identity/authority actionable-error tests |
| R3 | `FIXED` | Eight-capability map, six states, receipts, exact non-available results | Planner tests unavailable/unauthenticated/wrong-scope Hunter states and zero-credit fallback |
| R4 | `FIXED` | Planner sequence gates Hunter behind guards, route/exception, authenticated currentness, hook/proof, and first-party miss/block | Monotonic stage-order and six-precondition assertions; `HUNTER_PREMATURE` mutant path |
| R5 | `FIXED` | Channel kind/address/basis/state invariants; draft readiness requires non-`NONE` address/route | `draft-ready without channel` mutant fails `READY_CHANNEL` |
| R6 | `FIXED` | Selected hook binding requires intent ID, exact URL, captured content hash, and run ID | mismatch mutant fails `HOOK_EVIDENCE_MISMATCH` |
| R7 | `FIXED` | Structured intent signature and recomputed canonical fingerprint | rephrased duplicate mutant fails `HOOK_INTENT_DUPLICATE_FINGERPRINT` |
| R8 | `FIXED` | Five named guard receipts with source, time, authority scope, hash, run; 24-hour review freshness | stale clear-guard mutant fails `GUARD_RECEIPT_STALE`; missing/duplicate receipt gates |
| R9 | `FIXED` | Capability-bound surface/identity/result/evidence/freshness authenticated-currentness object | unbound receipt fails `AUTH_CAPABILITY_BINDING`; expired freshness fails `AUTH_FRESHNESS` |
| R10 | `FIXED` | Dependency-free schema subset validates V3 before policy and rejects unknown properties | unknown and malformed nested mutants fail only `STRUCT_*` first |
| R11 | `FIXED` | Required `candidate_proof`, `query_access_limitations`, and `owner_summary` sections; initializer/authoring guide | valid fixture plus six behavior fixtures require and exercise the fields |
| R12 | `FIXED` | Separate `BossHuntIndependentReviewV2` preparation/attachment, frozen subject hash, six per-check verdict/evidence records | hash mutation fails `REVIEW_HASH_MISMATCH`; same reviewer fails independence |
| R13 | `FIXED` | UI now says evidence-backed candidate-route ceilings, not verified evidence | required UI file and generic skill validation pass |

No defect is deferred or refuted. All fixes remain bounded to offline mechanics, documentation, and transferability; none establishes live evidence truth, deliverability, efficacy, installation, or release.

Post-remediation portability review also corrected two documentation discrepancies outside R1–R13: the certified workflow no longer depends on an owner-machine validator path, and the backlog no longer claims that a missing V1-to-V2 adapter exists. Neither correction expands live or migration scope.
