# V3 Dossier Authoring Guide

Use this guide after the canonical plan is generated. Work in a user-supplied isolated run directory that already exists. Set `BOSSHUNT_RUN_DIR` to that directory; examples use POSIX shell variable syntax, so use the equivalent path syntax in another shell. Never copy a completed fixture as evidence.

## 1. Initialize

```bash
python3 scripts/init_dossier.py evals/fixtures/target.json \
  --run-id run-YYYYMMDD-target \
  --researcher-id researcher-id \
  --output "${BOSSHUNT_RUN_DIR}/dossier.json"
```

Initializer output is deliberately non-promotable. Replace every `REPLACE_`/`PENDING` value and empty required ledger from evidence observed in this run.

## 2. Capture and hash exact evidence

Save the exact local representation reviewed under the isolated run directory. For JSON, the helper hashes canonical sorted compact JSON; for other files, it hashes exact bytes:

```bash
python3 scripts/hash_evidence.py "${BOSSHUNT_RUN_DIR}/evidence/guard-history.json"
```

Record the returned `sha256:` value with that file's path as `source_ref`/`evidence_ref`. Do not hash a URL string or invent a page-content hash.

Use this evidence-pack map when populating a new dossier:

| Captured representation | Dossier destinations |
|---|---|
| local role, JD, lifecycle, collision/history | `role.authority_sources`, `capabilities.local_role_authority`, five `guards.receipts` as scoped |
| ordered public search trace | `search.queries_run`, route candidates, `disconfirmers` |
| authenticated profile observation | `capabilities.authenticated_profile`, `search.authenticated_currentness`, one `recipient.currentness_sources` record |
| separately maintained employer/current-title source | a second `recipient.currentness_sources` record with a distinct independence key |
| exact hook artifact/readback | selected `hook_search.intents[].content_sha256` and matching `hook.evidence_binding` |
| approved CV, portfolio, or owner proof | `candidate_proof` |
| first-party or guarded Hunter result | method capability receipt, `channel`, and `channel.hunter_usage` |

A single captured file may support several fields only when its authority scope truly covers each. Every load-bearing hash must resolve to the exact representation supplied to the reviewer.

## 3. Serialize guards

Create exactly one receipt for each named guard. Map facts as follows:

| Observed fact | Receipt result | Overall effect |
|---|---|---|
| Evidence shows no restriction/conflict | `CLEAR` | May contribute to `CLEAR` |
| A documented collision is resolved into one sequence | `CONSOLIDATED` for `COMPANY_COLLISION` | Overall may be `CONSOLIDATED` |
| Evidence triggers no-bypass, terminal, owner-closed, collision, or disconfirmation | `TRIGGERED` | Overall is blocking/conflict as applicable |
| Authority or current evidence is incomplete | `UNKNOWN` | Cannot be draft-ready |

Use the same run ID as the dossier. `authority_scope` states exactly what target/company/history the source governs. Receipts must be observed within 24 hours of review. Reusing one current company-history snapshot for multiple guards is allowed when its scope actually covers each; keep one receipt per guard and the same exact snapshot hash.

## 4. Capture currentness and independence

For a named route, record the authenticated observation and at least two supported current-title/employer sources before draft readiness. An authenticated profile and an employer team page are independent when they are separately maintained; use keys such as `profile:<stable-id>` and `employer:team:<stable-id>`. Two pages reproducing one biography share an independence key and count once.

Each source gets its own captured representation/hash, exact URL, observation time, run ID, support result, source family, and independence key. The authenticated observation also binds the current capability receipt, surface/profile, selected recipient, company, target, result, and freshness deadline. Profile confirmation alone satisfies the authenticated gate but not the two-source draft-readiness gate.

## 5. Complete hook, proof, query, channel, and summary

Follow `hook-exhaustion.md` for signatures/fingerprints and exact evidence binding. Compute each structured signature fingerprint without rewriting the query:

```bash
python3 scripts/intent_fingerprint.py \
  --subject "Jordan Example" \
  --claim "authored operating model artifact" \
  --surface-family "employer authored content"
```

Candidate proof comes only from an approved CV, portfolio, or owner-supplied source. If an earlier guard or currentness gate stops the workflow before proof is evaluated, record `support_state=NOT_EVALUATED`, keep claim/source/kind/hash null, add `not_evaluated_reason`, and retain a non-draft readiness. Record every search/access outcome, every non-available capability in `query_access_limitations`, and the channel cross-fields in `dossier-contract.md`. Populate the owner summary from observed ceilings, not aspirations.

Run the validator on the new file:

```bash
python3 scripts/validate_dossier.py "${BOSSHUNT_RUN_DIR}/dossier.json"
```

Before independent review, exactly one `REVIEW_PENDING` diagnostic is expected; guard-age evaluation waits for `reviewed_at`. Any unrelated failure must be fixed or converted to a truthful non-promotable readiness state.

## 6. Obtain and attach independent review

Freeze the completed dossier subject; do not edit it while review is pending. Prepare a separate review request:

```bash
python3 scripts/review_record.py prepare "${BOSSHUNT_RUN_DIR}/dossier.json" \
  --reviewer-id independent-reviewer-id \
  --output "${BOSSHUNT_RUN_DIR}/review.json"
python3 scripts/review_record.py bind-pending "${BOSSHUNT_RUN_DIR}/dossier.json" \
  "${BOSSHUNT_RUN_DIR}/review.json" \
  --output "${BOSSHUNT_RUN_DIR}/dossier-review-pending.json"
```

Use `dossier-review-pending.json` as the frozen subject sent to the reviewer and
validate it before handoff; an otherwise complete dossier must return exactly
`REVIEW_PENDING`. `bind-pending` is not completed-review attachment and grants no
promotion. The review subject hash excludes `quality_review`, so this binding does
not change the frozen subject.

Obtain the reviewer through one of two portable mechanisms:

1. assign a named human who did not author the dossier; or
2. if the current harness supports isolated contexts, start a new context with no
   author reasoning/history and give it only the frozen dossier, prepared review
   record, raw evidence pack, and the task below.

Reviewer task: inspect `RESOURCE_COVERAGE`, `ROUTE_HONESTY`, `CURRENT_ROLE`,
`HOOK_ATTRIBUTION`, `CHANNEL_SEPARATION`, and `COLLISION_LIFECYCLE`; set every
check to `PASS` or `FAIL` with exact evidence references; set the overall verdict
to `PASS` only when all six pass; add a timezone-aware `reviewed_at` and concise
note; return only the completed `BossHuntIndependentReviewV2` record. The reviewer
must not edit the dossier or infer missing facts.

The researcher cannot fill this record. If neither reviewer mechanism is available,
the correct complete handoff is the frozen dossier plus pending request and the
explicit boundary `CANNOT COMPLETE INDEPENDENT REVIEW`; stop at `REVIEW_PENDING`.

Attach without changing the subject:

```bash
python3 scripts/review_record.py attach "${BOSSHUNT_RUN_DIR}/dossier-review-pending.json" \
  "${BOSSHUNT_RUN_DIR}/review.json" \
  --output "${BOSSHUNT_RUN_DIR}/dossier-reviewed.json"
python3 scripts/validate_dossier.py "${BOSSHUNT_RUN_DIR}/dossier-reviewed.json"
```

Any subject edit after review invalidates the hash; prepare and obtain a new review.
`review_record.py attach` refuses a still-pending record. A completed `FAIL` may be
retained as review evidence but is non-promotable and the validator reports it.
