# Stage 2 — Independent stress-test evidence and gap register

Date: 2026-08-21

Scope was restricted to the current `boss-hunt-research` skill, its references and scripts, `evals/fixtures/target.json`, and `evals/cold_handoff/SYNTHETIC_EVIDENCE.md`. I did not read prior transferability artifacts, reviewer outputs, remediation plans, defect lists, or author reasoning. The test user was a fresh context meeting the protocol's competent-user definition. No web, connector, credit, installation, drafting, or external mutation occurred.

## Evidence produced

- Canonical planner: exit 0; output hash `sha256:cba0edf3c942499fadf990ec43e747ea63beaddfb58c1d6785affaf7791d01b3`.
- Initializer: exit 0, `INITIALIZED_INCOMPLETE`; output hash `sha256:322f865180d9bc3d01df11f8b9a6023437f60e31888274bffaa548d5c0831b35`.
- Untouched initialized dossier validation: exit 1; three structural failures (`guards.receipts`, `hook_search.intents`, `search.queries_run` below minimum).
- Newly authored evidence-complete dossier: `dossier-authored.json`, hash `sha256:3da0132ca43cdd74b3d6947ea1c426c9e56769709033101d52956c4b157244d5`; pre-binding validation identified only the expected pending-review/hash placeholder state.
- Prepared review: exit 0; hash `sha256:dbfc38730f12593bc8f189bddc3986b984ea24d736a31f112040c39cd69214e9`.
- `bind-pending`: exit 0, no manual JSON intervention; bound dossier hash `sha256:50e7bcb555201e2a4a424bf2098b02785be00c02a863c7c2e51c90baef8ea4d4`.
- Bound dossier validation: exit 1 with exactly one diagnostic, `REVIEW_PENDING`.
- Attempt to attach that pending record: exit 1, `ValueError: review record is still PENDING; obtain a completed independent review before attach`.

## Gap register

| # | Cold-user question or assumption | Section that should cover it | Disposition | Evidence / boundary |
|---|---|---|---|---|
| 1 | “What are the six named behavioral cases I must run, and where is their portable command?” | Section 6 — Eval Criteria | **OPEN** | Section 6 says the suite covers six named route/edge fixtures but does not name them or provide a behavioral-suite command. I independently exercised six black-box boundaries below, but that is not evidence that the documented suite is transferable as written. |
| 2 | “How do I turn the prepared review request into the dossier's exact pending state without editing JSON?” | Section 3 — Core Workflow | **PASS** | `review_record.py prepare` followed by documented `bind-pending` succeeded with exit 0 and preserved the pending-review boundary. |
| 3 | “Can I attach the prepared review while it is still pending?” | Sections 3 and 6 — Core Workflow / Eval Criteria | **PASS** | `review_record.py attach` refused the pending record with exit 1 and the documented refusal message. |
| 4 | “Who starts the fresh-context reviewer, and what exact harness invocation makes it independent?” | Sections 3 and 6 — Core Workflow / Eval Criteria | **OPEN / CANNOT** | The guide names a human or fresh context and supplies the six-check task, but no harness-specific invocation is available in this test. The docs correctly say the researcher must stop at `REVIEW_PENDING`; no self-review was fabricated. |
| 5 | “How do I run this in a non-POSIX shell?” | Section 2 — Pre-flight | **OPEN (minor)** | The document says to use an equivalent path syntax but gives no concrete alternate-shell example. POSIX execution itself passed. |

The open items are documentation-transfer gaps, not defects patched in this recertification: the candidate and Job Hunting workspace were not modified.

## Six black-box behavioral cases exercised

These names follow the six categories named first in the current Section 6 sentence; no hidden fixture was opened.

| Case | Mutation / test | Expected fail-closed result | Result |
|---|---|---|---|
| Target authority | Remove `authority_sources` in-memory before `validate_target` | `TARGET_AUTHORITY` | PASS, exit 0 assertion |
| Ordering | Insert `HUNTER_DISCOVERY` before currentness/hook/first-party stages | `HUNTER_PREMATURE` | PASS, exit 0 assertion |
| Channel | Select Hunter Finder while its capability is `UNAVAILABLE` | `HUNTER_CAPABILITY_BLOCK` | PASS, exit 0 assertion |
| Hunter verification | Set `verification_credits_used=1` | structural `STRUCT_MAXIMUM` (schema maximum 0) | PASS after correcting the initial expectation; no dossier change |
| Hook binding | Change bound content SHA | `HOOK_EVIDENCE_MISMATCH` | PASS, exit 0 assertion |
| Intent duplication | Add a rephrased intent with the same structured fingerprint | `HOOK_INTENT_DUPLICATE_FINGERPRINT` | PASS, exit 0 assertion |

The first Hunter-verification assertion initially expected the policy code `HUNTER_VERIFICATION_FORBIDDEN`; the schema rejects the value earlier with `STRUCT_MAXIMUM`. I recorded that intervention and reran against the observed documented fail-closed behavior. No persisted artifact was changed.
