# Final Stage 2–4 recertification recommendation

Date: 2026-08-21

## Recommendation: HOLD — do not certify transferability yet

Candidate 1.2.3 passes the bounded offline/read-only transfer test for Sections 1–5 and 7. The newly authored dossier was not copied from a completed fixture. It used only the supplied target and synthetic evidence, reached `REVIEW_PENDING` through the documented `prepare -> bind-pending -> validate` path, and could not attach a pending record. The six adversarial behavioral boundaries all failed closed as expected, including the schema-level zero-verification-credit limit.

The Stage 2–4 claim remains open for two reasons: Section 6 does not name its six behavioral fixtures or give a portable command for the complete suite, and the documented independent-review dependency could not be satisfied by this authoring context. The correct boundary is `CANNOT COMPLETE INDEPENDENT REVIEW`; no self-review, completed record, promotion, channel verification, drafting, sending, connector use, credit spend, installation, release, or workspace mutation is authorized.

## Exact command ledger

| Command/result | Exit |
|---|---:|
| `python3 scripts/build_search_plan.py evals/fixtures/target.json --output /private/tmp/bosshunt-v123-final-recert/search-plan.json` | 0 |
| `python3 scripts/init_dossier.py evals/fixtures/target.json --run-id recert-20260821-j000123 --researcher-id final-recert-researcher --output /private/tmp/bosshunt-v123-final-recert/dossier-initialized.json` | 0 (`INITIALIZED_INCOMPLETE`) |
| `python3 scripts/validate_dossier.py /private/tmp/bosshunt-v123-final-recert/dossier-initialized.json` | 1 (three structural minimum failures) |
| `python3 scripts/review_record.py prepare /private/tmp/bosshunt-v123-final-recert/dossier-authored.json --reviewer-id fresh-context-reviewer --output /private/tmp/bosshunt-v123-final-recert/review-pending.json` | 0 |
| `python3 scripts/review_record.py bind-pending /private/tmp/bosshunt-v123-final-recert/dossier-authored.json /private/tmp/bosshunt-v123-final-recert/review-pending.json --output /private/tmp/bosshunt-v123-final-recert/dossier-review-pending.json` | 0 |
| `python3 scripts/validate_dossier.py /private/tmp/bosshunt-v123-final-recert/dossier-review-pending.json --json` | 1 (exactly `REVIEW_PENDING`) |
| `python3 scripts/review_record.py attach /private/tmp/bosshunt-v123-final-recert/dossier-review-pending.json /private/tmp/bosshunt-v123-final-recert/review-pending.json --output /private/tmp/bosshunt-v123-final-recert/dossier-attach-pending.json` | 1 (pending attachment refused) |

Hashes: plan `sha256:cba0edf3c942499fadf990ec43e747ea63beaddfb58c1d6785affaf7791d01b3`; authored dossier `sha256:3da0132ca43cdd74b3d6947ea1c426c9e56769709033101d52956c4b157244d5`; prepared request `sha256:dbfc38730f12593bc8f189bddc3986b984ea24d736a31f112040c39cd69214e9`; bound pending dossier `sha256:50e7bcb555201e2a4a424bf2098b02785be00c02a863c7c2e51c90baef8ea4d4`.

Intervention ledger: the first Hunter-verification mutant expectation was corrected from policy `HUNTER_VERIFICATION_FORBIDDEN` to the earlier schema `STRUCT_MAXIMUM` result; no persisted dossier or skill file was changed. Nothing under the Job Hunting workspace was modified.
