# Operational Process — Candidate v1.2.9

## 0. Pre-flight

Read `dependency-capability-contract.md`, `harness-tool-discovery.md`, `dossier-contract.md`, `source-policy.md`, and `hook-exhaustion.md`. Work only from `BossHuntTargetV2`; there is no implicit `tracker_id` to `target_id` translation. Before a live operation, inspect the native session inventory and serialize the preferred-tool exposure report with `scripts/check_session_tools.py`; this works from Codex or Claude Code inventories, makes no external call, and does not establish live capability `AVAILABLE`.

Run the canonical documented example after setting `BOSSHUNT_RUN_DIR` to a user-supplied isolated directory that already exists:

```bash
python3 scripts/build_search_plan.py evals/fixtures/target.json --output "${BOSSHUNT_RUN_DIR}/search-plan.json"
```

The target schema requires exact target identity, owner scope, local authority receipts, structured reporting hypotheses, intake mode, optional tracker/JD fields represented explicitly as values or `null`, and a complete capability profile.

After planning, initialize and populate a new dossier using `authoring-guide.md`. The completed valid fixture is an evaluator input, not an evidence template.

## 1. Target authority and guards

Validate the target before research. Then create current receipts for `NO_BYPASS`, `TERMINAL_OUTREACH`, `OWNER_CLOSED`, `COMPANY_COLLISION`, and `DISCONFIRMATION`. Each receipt records source, observation time, authority scope, evidence hash, and run ID. A guard receipt must be no more than 24 hours old at review.

Stop on missing authority, triggered no-bypass/terminal/owner-closed/disconfirmation, or unresolved collision. A closed posting is a status fact; it is not an automatic end to post-application relationship research. Before review, the validator emits one `REVIEW_PENDING` diagnostic and defers guard-age comparison; after review, every guard receipt must be no more than 24 hours older than `reviewed_at`.

## 2. Reporting hypotheses

Before names, record the literal stated boss and up to three alternatives, each with basis, supporting condition, and refuter. Search the literal seat first. `MISS` is useful evidence and never licenses silent apex substitution.

## 3. Public organization and route map

Record accessible `HIT`/`MISS` or `BLOCKED` for employer context, literal seat, alternatives, requisition/search owner, and adjacent routes. A snippet or aggregator generates a candidate; it does not prove a claim. A defensible named route must exist before the authenticated currentness gate. Domain Search is not a way to avoid that rule: its exception must be predeclared, tightly scoped, and still return to identity/currentness validation before channel promotion.

## 4. Authenticated currentness

Bind one serialized, read-only professional-profile observation to:

- the current `authenticated_profile` capability receipt;
- named surface and profile identity;
- recipient, company, and target ID;
- `CONFIRMED`, mismatch, or named unavailable result;
- observation and freshness deadline;
- evidence reference/hash and run ID.

If capability is unavailable, unauthenticated, wrong-scope, or blocked, return `PROFILE_CHECK` for a named route and use zero Hunter calls/credits.

## 5. Hook and candidate proof

Only after currentness passes, find an exact hook artifact and one candidate proof from an approved CV, portfolio, or owner-supplied source. Apply the V2 structured-intent fingerprint and exact evidence-binding rules. When an earlier gate stops the workflow before proof evaluation, use `NOT_EVALUATED` with null claim/source/kind/hash and a non-empty reason; it is permitted only below draft readiness. Without a supported hook and proof, return `RESEARCH_MORE` or `BLOCKED`; Hunter remains forbidden.

## 6. Channel sequence

1. Run exactly one bounded first-party lane: reuse a live professional address already encountered, otherwise one exact-person/domain query and at most one obvious employer result.
2. On a first-party `HIT`, stop and record the first-party channel.
3. Only after a first-party `MISS`/`BLOCKED`, all earlier gates, and `AVAILABLE` Hunter account/method receipts, consider one Finder call.
4. Domain Search is instead of Finder, limited to 10 filtered results without pagination, for a predeclared named-route exception.
5. Never call Verifier, spend verification credits, follow `nextAction`, or mutate leads/lists/campaigns.

Any Hunter non-available state produces the fallback/boundary in `dependency-capability-contract.md` and zero credits.

## 7. Adversarial gate and review

Validate V3 structurally first, then apply policy:

```bash
python3 scripts/validate_dossier.py evals/fixtures/valid_dossier.json
```

Attempt to refute route honesty, current role, requisition linkage, hook binding, channel separation, collision/lifecycle, and resource coverage. Use `scripts/review_record.py prepare` and `attach` as documented in `authoring-guide.md`. Independent review must be a separate `BossHuntIndependentReviewV2` record from a different human or fresh-context reviewer, bound to the frozen canonical dossier subject hash with per-check evidence.

## 8. Readiness and handoff

Return exactly one: `DRAFT_READY_VERIFY_CHANNEL`, `OWNER_DECISION`, `PROFILE_CHECK`, `BLOCKED`, or `RESEARCH_MORE`. Return the owner summary, limitations, disconfirmers, and one bounded next action or stop reason.

`DRAFT_READY_VERIFY_CHANNEL` means internal research gates passed and a channel candidate exists. It does not mean the channel is live-verified or authorize drafting, owner approval, outreach, sending, tracker mutation, registration, installation, or release.

## Compatibility

V2 dossiers and frozen pilot artifacts remain historical evidence. `validate_dossier.py` refuses V2 with `LEGACY_SCHEMA_REFUSED`. Do not rewrite or re-hash a frozen V2 unit. A new V3 run must re-observe all evidence that V3 requires; if doing so would require inventing evidence or modifying the frozen pilot, stop.
