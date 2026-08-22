# Stage 2 Independent Test Evidence — BossHunt candidate 1.2.2

Date: 2026-08-21  
Run directory: `/private/tmp/bosshunt-v122-recert-clean`  
Subject: `J-000123` / Example Company / Director of Product Design  
Tester: clean-context competent AI-workflow practitioner; no prior Boss Hunt transferability artifacts, reviewer outputs, remediation plans, defect lists, or author reasoning were read.

## Allowed evidence and controls

Only the current `SKILL.md`, its `references/` and executable helper files, `evals/fixtures/target.json`, and `evals/cold_handoff/SYNTHETIC_EVIDENCE.md` were used. No browsing, installs, live connectors, credits, authentication, external actions, or Job Hunting mutations occurred. The dossier was authored as a new V3 record from the target and synthetic pack; `valid_dossier.json`, `invalid_apex_dossier.json`, and all prior transferability material were not used.

Hashes of exact local representations:

| Representation | SHA-256 |
|---|---|
| `evals/fixtures/target.json` | `sha256:6ae32adfc773f2a5d29c65d251ae6e86cf7d02b757f088fc508bf362e8a5d6fb` |
| `evals/cold_handoff/SYNTHETIC_EVIDENCE.md` | `sha256:fbe9eb44c9203665877400b62c3044a282ef03e09a929a6538c3abf0b328a6d3` |
| generated `search-plan.json` | `sha256:cba0edf3c942499fadf990ec43e747ea63beaddfb58c1d6785affaf7791d01b3` |
| initialized shell | `sha256:55d25f6f24842e91ff389530a95095f3ffafc270380accb208dbea06610cbf5a` |
| evidence-complete dossier with pending review | `sha256:394a5d94b9dbd5a9de31aef08e53faba27559e505cd2df996b90256296d0a3cc` |
| prepared pending review request | `sha256:1c1822adf9f68b547a155459a5774dc9f3c005666287b163de2e84376e23662c` |

## New-dossier path and exact CLI results

1. `mkdir -p /private/tmp/bosshunt-v122-recert-clean/evidence /private/tmp/bosshunt-v122-recert-clean/reviewer-output` — exit `0`.
2. `python3 .../build_search_plan.py .../target.json --output .../search-plan.json` — exit `0`; planner output was written and hashed above.
3. `python3 .../init_dossier.py .../target.json --run-id run-20260821-clean-j000123 --researcher-id reviewer-clean --output .../dossier-initial.json` — exit `0`; stdout `INITIALIZED_INCOMPLETE: .../dossier-initial.json`.
4. `python3 .../validate_dossier.py .../dossier-initial.json` — exit `1`; structural failures were exactly `STRUCT_MIN_ITEMS` for `guards.receipts`, `hook_search.intents`, and `search.queries_run`. This is a deliberately non-promotable shell, not a false pass.
5. A new evidence-complete dossier was authored from the target and synthetic pack. It includes all five current guard receipts, all eight capability receipts, ordered traces, bound authenticated currentness, independent current-title sources, an exact recipient hook and fingerprint, candidate proof, first-party channel, zero Hunter usage, limitations, and owner summary.
6. `python3 .../validate_dossier.py .../dossier-evidence-complete.json` before binding the prepared request — exit `1`; it returned `REVIEW_PENDING` plus `REVIEW_HASH_MISMATCH`. This exposed the gap recorded below.
7. `python3 .../review_record.py prepare .../dossier-evidence-complete.json --reviewer-id independent-fresh-context --output .../reviewer-output/review-pending.json` — exit `0`; stdout `REVIEW_REQUEST: .../review-pending.json`. Prepared subject hash: `sha256:b309ce14b705d1f54170df0c5aa235bd7de42d9d754f8ae913d4371281c3f395`.
8. The prepared record was manually copied into the dossier's `quality_review` field as a test intervention (the helper has no bind-pending command). After that intervention, `python3 .../validate_dossier.py .../dossier-evidence-complete.json` — exit `1` with exactly one diagnostic: `REVIEW_PENDING`.
9. `python3 .../review_record.py attach .../dossier-evidence-complete.json .../reviewer-output/review-pending.json --output .../reviewer-output/should-not-attach.json` — exit `1`; it raised `ValueError: review record is still PENDING; obtain a completed independent review before attach`. No output dossier was created.
10. `python3 .../intent_fingerprint.py --subject "Jordan Example" --claim "explains product operating model change" --surface-family "employer authored content"` — exit `0`; `sha256:b52dafc1cdfb63b537c42e3b6217848b64524d1692ebbd15b1ae4bb143f7d517`.
11. `python3 .../intent_fingerprint.py --subject "Jordan Example" --claim "artifact attribution belongs to Jordan" --surface-family "attribution challenge"` — exit `0`; `sha256:f503de7e26072bdd6fe4a5c5fd5b983c78ff167791beed953750fd9da9aa0cfe`.

## Six named behavioral cases

The six cases were rebuilt against the fresh dossier (not the bundled completed fixture). The local control harness exercised each case in two modes: pending review (expected exactly `REVIEW_PENDING`) and completed-review control (all six checks PASS, not attached to the certification dossier). Every completed-review control returned no validator issues; every pending case returned only `REVIEW_PENDING`.

| Named case | Control mutation | Pending result | Completed-review control |
|---|---|---|---|
| `valid_literal_seat_hit` | baseline dossier | exactly `REVIEW_PENDING` | pass, no issues |
| `literal_seat_miss` | literal seat `MISS`; sponsor route; `OWNER_DECISION` | exactly `REVIEW_PENDING` | pass, no issues |
| `generic_fallback` | seven deduplicated intents; company mandate selected; exact binding | exactly `REVIEW_PENDING` | pass, no issues |
| `recruiter_route` | literal seat `MISS`; explicitly linked recruiter; recruiter response | exactly `REVIEW_PENDING` | pass, no issues |
| `stale_person` | disconfirmation triggered; currentness mismatch; blocked/no-channel; proof `NOT_EVALUATED` | exactly `REVIEW_PENDING` | pass, no issues |
| `company_collision` | collision guard triggered; blocked; proof `NOT_EVALUATED` | exactly `REVIEW_PENDING` | pass, no issues |

The control harness exited `0`. The completed-review controls demonstrate validator mechanics only; they are not an obtained independent review and do not promote the certification dossier.

## Stage 2 conclusion

The clean user can execute the documented read-only research and author a new evidence-complete dossier through preparation of the independent review request. The test found one actionable documentation/helper gap: the path from `review_record.py prepare` to the documented “exactly one `REVIEW_PENDING` diagnostic” requires an undocumented manual copy of the prepared record into the dossier. The external reviewer itself is a documented dependency, not a transferability documentation gap. This gap is carried into Stage 3 and the Stage 4 CANNOT boundary; the skill was not modified.
