---
name: sync-jobs
description: Acquire and capture owner-selected LinkedIn, employer, ATS, Indeed, or unfamiliar job-board postings; sync validated jobs into a local Excel tracker and archive; and optionally triage them with an explicitly selected candidate profile. Use for posting URLs, saved-job sync, direct-source intake, sync-plus-triage, and owner-requested archive rechecks; excludes applications, cover letters, outreach, and general job discovery.
metadata:
  version: "2.5.0"
---

# Sync jobs

Use skill-owned code and references. This skill does not delegate to retired project prompts or scripts. Public packages contain only the synthetic `example` profile. Real candidate profiles are private installation-local overlays and require separate review and promotion; never copy them into a public repository.

## Resolve the three layers

1. **Engine and adapters:** `scripts/` handles deterministic ingestion, tracker writes and reporting. Read [workflow](references/workflow.md) and [tracker contract](references/tracker_contract.md).
2. **Profile:** for triage, read the explicitly selected private `profiles/<profile-id>/profile.json` and its referenced policy before judgment. The profile owns candidate facts, thresholds, exclusions and preferences. The bundled `example` profile is synthetic test data, not a recommendation. Read [layer ownership](references/design_and_objective.md) when changing the skill.
3. **Workspace and evidence:** explicitly resolve the project root and tracker. Live postings, tracker rows, current sponsorship evidence and run reports remain outside the skill. Missing or old evidence is not a candidate preference and must not become a standing rule.

Eligibility evidence is a source-only sidecar separate from compensation and candidate judgment. Read [eligibility evidence](references/eligibility_evidence.md) before interpreting or changing it. `NO_MATCHES_DETECTED` displays as `NOT STATED ON SOURCE`, means only that an automated span scan found no supported wording, and never means “no sponsorship.” Historical sidecars may be missing; normal worklists report that without creating them.

Use `python3 scripts/sync_jobs.py --project-root <root> --profile <profile-id> <command> ...` for tracker and triage commands. Acquisition-only commands do not require a workspace or profile. Sync and triage commands need `openpyxl`; `requirements.txt` declares the dependency. Acquisition commands use only the Python standard library. Install missing dependencies into an isolated runtime outside the skill; do not delete/rebuild an existing environment automatically.

For owner-selected employer, ATS, Indeed, or unfamiliar job-board URLs, read [source acquisition](references/source_acquisition.md). `acquire-url` is non-mutating and accounts for every URL as a validated record or retained failure. It tries supported official public ATS endpoints, schema.org `JobPosting`, and bounded public HTML. LinkedIn is deliberately returned as a browser-required handoff; do not route it through an unauthorized scraping library or private endpoint.

For an incomplete non-LinkedIn source-neutral bundle, `resume-url` merges an exactly covering set of retained browser/manual fallback outcomes. It preserves accepted records and selected scope, replaces only failures, appends attempts, and revalidates evidence bytes, hashes, URL identity and completion claims. It refuses LinkedIn outcomes: `acquire-save` producing `SelectedPostingAcquisitionV1` remains the only LinkedIn capture route.

For acquisition-only work on owner-selected posting IDs, read [LinkedIn adapter](references/linkedin_adapter.md) and [capture quality](references/acquisition_quality.md). This mode captures evidence without opening the tracker or archive gates and cannot label selected IDs as official new jobs or claim a completed sync.

For validated external captures, read [direct-source intake](references/direct_source_intake.md). `external-ingest` accepts complete `SourcePostingAcquisitionV2` bundles or compatible legacy direct records, rehearses by default, and never treats a board or careers landing page as one job unless the evidence binds one unambiguous role. V2 identity prefers provider plus stable provider job ID; canonical URL is the fallback.

For owner-requested rechecks or updates of existing archives, read [source verification](references/source_verification.md). `audit-existing` freezes selection before fresh browser capture and comparison; `refresh-existing` previews exact selected differences before an authorized commit. Both are strictly on demand and never run as part of normal sync or triage. Local-only checks cannot claim source completeness.

## Execute

- Obtain the saved and in-progress indexes using an authenticated browser, following [LinkedIn adapter](references/linkedin_adapter.md). Only use capabilities actually available in that browser tool. Never save cookies or CSRF tokens to disk. A missing browser capability is a blocker to acquisition, not authorization for another transport.
- `diff` finds new IDs. Download descriptions only for those IDs. Retain acquisition errors and check pagination completeness before reconciliation.
- `ingest` rehearses by default; inspect its staged outputs. New descriptions and tracker-only JD recovery must carry recomputable, passing `CaptureQualityV1` source evidence. Acquisition bundles with failures, blocked records or incomplete selected-ID coverage stop before writes. Add `--commit` only for an authorized live sync. With zero new IDs, use `reconcile` directly; no dummy ingest is needed.
- For full sync-plus-triage, create a `worklist`, read the JDs, and fill judgments according to the selected profile. Explicitly select the current batch's Tracker IDs; the worklist selector can include older pending rows. Run `score`, then validate `report` to a staging location **before** writing verdicts. Missing discarded reasons or links block the write.
- `write` rehearses by default. Inspect it, then use `--commit` for the authorized triage write. Produce the final `report` and verify tracker changes and retained lifecycle states.

Excel must be closed for live writes. Back up before mutation. Sync appends new rows; triage has a limited header allowlist and preserves advanced lifecycle states. The board is read-only: cleanup lists do not authorize unsaving, applying or sending. Fit scores come from explicit agent judgment, never title-only guesses. Missing profile/evidence must be reported rather than inferred.

Browser choice, batch review thresholds and other personal operating preferences belong only in a private installation-local profile. The public engine does not prescribe them. Screenshots are not accepted as description text because they do not satisfy the text/hash contract.
