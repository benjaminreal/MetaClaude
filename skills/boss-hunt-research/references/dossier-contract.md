# BossHuntResearchDossierV3 Contract

V3 is intentionally incompatible with V2. The preserved V2 schema remains at `bosshunt_dossier_v2.schema.json`. The validator returns `LEGACY_SCHEMA_REFUSED` for V2 and never reinterprets frozen history. A historical V2 unit may inform a new run, but every V3 authority, guard, currentness, hook, proof, capability, and review receipt must come from newly observed or explicitly owner-supplied evidence.

## Validation order

1. Load `bosshunt_dossier_v3.schema.json`.
2. Reject structural errors, missing required fields, malformed nested objects, and unknown properties.
3. Only when structure passes, evaluate cross-field policy.

Structural errors therefore cannot be hidden behind later policy messages.

## Sections

| Section | Contract |
|---|---|
| `role` | Canonical target identity, optional source tracker ID, intake mode, verified company domain when known, local authority receipts, and owner scope. |
| `capabilities` | Complete eight-capability profile using the states and receipts in `dependency-capability-contract.md`. |
| `guards` | Five named guard receipts plus derived overall state. A written `CLEAR` without current receipts is rejected. |
| `search` | Structured reporting hypotheses, literal-seat result, ordered trace, and capability-bound authenticated-currentness observation. |
| `recipient` | Selected route, linkage ceiling, profile binding, and independent current-title/employer sources with content hashes. |
| `hook` | Exact supported artifact and `evidence_binding` to one selected intent's ID, URL, content SHA-256, and run ID. |
| `hook_search` | V2 intent policy using structured signatures and recomputed canonical fingerprints. Duplicate/rephrased signatures cannot count twice. |
| `candidate_proof` | One exact approved-CV, portfolio, or owner-supplied proof claim with source, hash, run binding, and support state. If an earlier gate stops the workflow, `NOT_EVALUATED` uses null evidence fields plus a reason and is valid only below draft readiness. It is drafting input, not generated prose. |
| `channel` | One candidate route plus Hunter budget receipt. Cross-field kind/address/basis/state consistency is mandatory. |
| `decision` | One readiness label, route-permitted response, owner flag, reason, and bounded next search when applicable. |
| `quality_review` | Separate review record bound to the canonical dossier hash excluding `quality_review`; six check objects each carry verdict and evidence references. |
| `query_access_limitations` | Matching record for every non-`AVAILABLE` capability. |
| `owner_summary` | Executable handoff: route summary, weakest assumption, capability limits, next action/stop, and authority boundary. |
| `disconfirmers` | Reusable negative evidence. |

## Hash rules

- SHA fields use `sha256:<64 lowercase hex>`.
- Intent fingerprint input is the normalized structured signature `{subject, claim, surface_family}`, serialized with sorted keys and compact JSON.
- Review subject hash is canonical sorted compact JSON of the complete dossier excluding `quality_review`.
- A supported selected hook must match its selected intent on intent ID, exact result URL, content SHA-256, and run ID.

## Channel invariants

- `NONE` requires `address=null`, `basis=NONE`, and `state=UNAVAILABLE`.
- `EMAIL` requires a syntactic address, an email basis, and `VERIFIED` or `VERIFY_CHANNEL`.
- `PROFESSIONAL_PLATFORM` requires an exact profile URL in `address`, matching basis, and `VERIFY_CHANNEL`.
- `RECRUITER_ROUTE` requires a non-empty route reference, matching basis, and `VERIFY_CHANNEL`.
- Pattern- and Hunter-derived addresses can never be `VERIFIED` here.
- `DRAFT_READY_VERIFY_CHANNEL` cannot pass with `kind=NONE` or a missing address/route.

## Review and proof invariants

- A pending independent review produces one `REVIEW_PENDING` diagnostic. Guard age is evaluated only when a completed review time exists.
- The attach helper refuses a pending review record; retaining the separate request is the truthful external-dependency boundary.
- The `bind-pending` helper binds the prepared request into `quality_review` without changing the review-subject hash; it is required before asserting the single `REVIEW_PENDING` diagnostic.
- A draft-ready subject may wait at that single pending gate; authenticated freshness through review and every readiness condition are enforced when the completed review is attached.
- A completed review requires a valid `reviewed_at`; pending review must keep it null.
- A completed `FAIL` emits `REVIEW_FAILED`; any completed non-passing check emits `REVIEW_CHECK_FAILED`; an overall `PASS` with a non-passing check also emits `REVIEW_VERDICT_DRIFT`.
- `NOT_EVALUATED` candidate proof requires null claim/source/kind/hash plus a non-empty stop reason, and cannot coexist with `DRAFT_READY_VERIFY_CHANNEL`.
- Evaluated proof states require all proof evidence fields and cannot carry a not-evaluated reason.

## Validator authority

The validator can prove structural conformance and internal policy consistency. It cannot prove that sources are true, identities are correct, an inbox exists, a route is appropriate, or outreach works. A pass is candidate-route research evidence only; it is not drafting approval, owner review, channel verification, sending authorization, registration, installation, or release.
