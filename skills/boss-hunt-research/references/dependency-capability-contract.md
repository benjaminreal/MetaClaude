# Dependency and Capability Contract

Read this before planning or executing a Boss Hunt research run. A capability receipt records what the current invocation can actually use; it never grants permission.

## Session tool discovery: exposure before capability

At skill activation, inspect the session's native tool and skill inventory without
calling any external service. Use [harness-tool-discovery.md](harness-tool-discovery.md)
to serialize a Codex, Claude Code, or other compatible inventory. The preferred
stack is:

- authenticated professional profile: permitted external Chrome first, with the
  harness internal browser as an explicit alternative;
- Hunter account observation, named-person Email Finder, and predeclared Domain
  Search exception, matched by operation rather than a harness-specific provider
  name.

Serialize the inventory through `scripts/check_session_tools.py`. Its states are
`EXPOSED`, `PARTIAL`, `NOT_EXPOSED`, and `INVENTORY_UNAVAILABLE`. These describe
names in the current session only. They do not prove login, account identity,
scope, source access, authorization, or credits and must never be copied into the
six-state live capability fields as `AVAILABLE`.

If inventory discovery is unavailable, record `INVENTORY_UNAVAILABLE`; do not probe
by calling a connector. If a preferred surface is partial or absent, use the
existing capability-specific fallback. In `AUTO`, an exposed internal browser may
replace absent external Chrome; an explicit surface choice must not be silently
substituted. Never switch surfaces to bypass authentication or access controls.
Do not request unrelated Hunter operations or follow `nextAction`.

## Named states

| State | Meaning |
|---|---|
| `AVAILABLE` | The required read succeeded in the current invocation and the receipt is bound to the required scope. |
| `UNAVAILABLE` | The capability is absent or cannot be reached in this harness. |
| `UNAUTHENTICATED` | The surface exists, but the required account is not authenticated. |
| `WRONG_SCOPE` | Access exists, but its identity, account, project, company, or target scope does not match. |
| `BLOCKED` | Access was attempted within scope but a permitted surface denied or interrupted observation. |
| `NOT_APPLICABLE` | The branch is not required for this target; the receipt must state why. |

Do not translate one state into another. Every non-`AVAILABLE` state appears in `query_access_limitations` with the same receipt reference.

## Capability map and fail-closed result

| Capability | Evidence required for `AVAILABLE` | Non-available result |
|---|---|---|
| `local_role_authority` | Current local role/lifecycle authority receipt bound to target and owner scope | `BLOCKED`; no web research |
| `public_web` | Permitted public-research surface receipt | `RESEARCH_MORE` for unavailable/blocked; otherwise `BLOCKED` |
| `authenticated_profile` | Read-only authenticated professional-profile capability bound to the intended identity/surface | `PROFILE_CHECK`; no Hunter |
| `hunter_account_details` | Account-details receipt less than 24 hours old and correct account scope | No Hunter; continue only with documented first-party/platform/recruiter fallback, otherwise `RESEARCH_MORE`/`BLOCKED` |
| `hunter_email_finder` | Finder capability and verified company-domain scope | No Hunter; same fallback ceiling; zero calls/credits |
| `hunter_domain_search` | Domain Search capability plus a predeclared named-route exception and verified domain | No Hunter; same fallback ceiling; zero calls/credits |
| `local_python` | Current local interpreter can run the planner/validator | `BLOCKED`; do not claim validation |
| `schema_validation` | V3 schema loads and the structural validator completes | `BLOCKED`; do not run policy checks or promote |

## Receipts

Every receipt contains `state`, `observed_at`, `scope`, `receipt_ref`, and `evidence_sha256`. For authenticated currentness, the dossier also records the surface, identity binding, observation result, freshness deadline, evidence reference/hash, and run ID.

`AVAILABLE` does not authorize a call. Hunter is only considered after guards pass, a defensible named route or documented Domain Search exception exists, authenticated currentness passes, the hook/proof gate passes, and the bounded first-party email lane records `MISS` or `BLOCKED`.

## Offline and synthetic work

For offline evaluation, record live services as `UNAVAILABLE` or `NOT_APPLICABLE`; never fabricate an `AVAILABLE` receipt. Synthetic evidence may validate mechanics but cannot establish source truth, address deliverability, outreach efficacy, production readiness, installation, or release authorization.
