# Sync Jobs Source Acquisition and Hardening Plan

Date: 2026-09-13
Target repository: MetaClaude
Target branch: `feat/sync-jobs-source-acquisition`
Target skill: `skills/sync-jobs`

## Objective

Make `sync-jobs` able to acquire, validate, archive, sync, and optionally triage owner-selected job postings from LinkedIn, direct employer pages, applicant-tracking systems, Indeed, and unfamiliar third-party job boards without forcing non-LinkedIn vacancies into LinkedIn identity fields.

The result must preserve the existing dry-run-first tracker protections, source
evidence, private-profile overlay boundary, and read-only job-board policy. A
failed or incomplete acquisition must remain a visible failure and must never
become a successful empty result or a partial description.

## Starting point and repository reconciliation

The MetaClaude repository initially contained a historical `sync-jobs` v1.0.0
consisting of `SKILL.md` and `README.md`. An installation-local v2.3.0 package
provided the current engine, tests and references plus an 80-test baseline.
Private profile overlays are excluded from the public release.

Before feature work:

1. Reconcile the v2.3.0 engine into `skills/sync-jobs` as the working baseline.
2. Preserve its separation from retired project scripts.
3. Record a privacy-safe baseline receipt without local paths or private-profile hashes.
4. Run all 80 existing tests and `skill-creator` validation in the branch before changing behavior.
5. Do not install or overwrite live skill locations during implementation. Public-engine and private-profile promotion are separate approval steps.

## Scope

### Included

- Source-neutral URL acquisition.
- Official public ATS endpoints.
- Anonymous HTTP and structured-data extraction.
- Generic public HTML extraction.
- Browser fallback instructions and capture contracts.
- LinkedIn account-state acquisition through an authorized authenticated browser.
- Direct employer, ATS, Indeed, and unfamiliar job-board URLs.
- Method-specific provenance and completeness validation.
- Source and cross-source identity handling.
- Dependency qualification.
- Deterministic fixtures, adversarial tests, integration tests, and bounded live canaries.
- Skill prompt and reference restructuring under skill-creator standards.

### Excluded without additional approval

- Applying to jobs, messaging, outreach, saving, or unsaving.
- Exporting cookies, CSRF tokens, local storage, or credentials.
- CAPTCHA bypass, proxy rotation, fingerprint evasion, or access-control circumvention.
- Re-enabling retired Apply Pack or project-owned pipelines.
- Bulk crawling or general job discovery beyond owner-selected URLs or the authorized LinkedIn Saved/In Progress index.
- Writing to the live Job Hunting tracker during development tests.
- Installing the completed branch into live Codex/Claude skill locations.

## Architecture

### 1. Source-neutral acquisition command

Add a non-mutating command such as:

```text
sync_jobs.py ... acquire-url --url <posting-url> --out <bundle.json>
```

Support multiple explicitly supplied URLs while accounting for each URL exactly once as either a passing record or a retained failure.

`acquire-url` must not open or write the tracker. Its output feeds the existing ingest path after validation.

### 2. Adapter interface

Every adapter implements the same conceptual contract:

```text
recognize -> acquire -> normalize -> validate -> record or structured failure
```

Initial adapter priority:

1. Greenhouse public Job Board API.
2. Lever public Postings API.
3. SmartRecruiters public Posting API.
4. Generic schema.org `JobPosting` JSON-LD.
5. Generic public HTML.
6. Indeed public posting pages.
7. LinkedIn user-visible browser capture.
8. Unknown-provider generic fallback.

Provider adapters should be small and return a shared normalized schema. Provider recognition must not be required for the generic fallback.

### 3. Acquisition fallback protocol

Default order for an owner-selected posting URL:

1. Official public ATS/API endpoint.
2. Anonymous HTTP request.
3. Embedded JSON-LD or other supported structured page data.
4. Public HTML main-content extraction.
5. An authorized user-visible browser surface selected for the current environment.
6. Another authorized browser surface when the first cannot produce complete evidence.
7. Owner-supplied HTML, PDF, or text artifact.
8. Structured unresolved failure.

Exceptions and boundaries:

- LinkedIn Saved/In Progress is account state and begins in an authorized authenticated browser.
- LinkedIn acquisition must not depend on an unauthorized scraping library or private endpoint automation.
- Browser cookies and tokens remain inside the browser session.
- Browser surface ordering, if any, belongs in a private installation-local profile. A missing capability is recorded, not invented.
- Use one normal attempt and at most one bounded retry per transport before moving on.
- A successful public acquisition does not authorize application or other site mutation.

### 4. Normalized capture schema

Introduce a versioned source-neutral capture schema containing at least:

- supplied/discovery URL;
- redirected final URL;
- canonical posting URL;
- provider and ATS, when detected;
- provider job ID and requisition ID, when explicitly available;
- title, company, location, employment type, posting date, and full description;
- description hash and source-record hash;
- authentication state;
- acquisition method and attempt history;
- capture timestamp;
- completeness evidence and end-boundary evidence;
- source-availability state;
- structured failure reason when capture does not pass.

Preserve V1 compatibility or provide an explicit, tested migration. Do not silently reinterpret historical provenance.

### 5. Method-specific quality validation

Extend the quality contract beyond `rendered_dom_text` and `native_text`:

- `official_api`: validate endpoint identity, response status, provider ID, required fields, description, and source hash.
- `public_json_ld`: bind one `JobPosting` object to the final URL and validate its complete description.
- `public_html`: bind a single posting container, verify the ending, and reject navigation or login-wall text.
- `rendered_dom_text`: retain expanded-description and end-marker checks.
- `native_text`: retain ordered-node, link-label, scope, and truncation protections.
- `owner_provided_artifact`: hash and attribute the artifact without claiming current live availability.

A HTTP 200, nonempty string, or copied suffix alone never proves completeness.

### 6. Identity and deduplication

Maintain two distinct concepts:

- Source identity: provider plus stable provider job ID, or canonical URL when no stable ID exists.
- Cross-source match candidate: employer, role, location, requisition, and description evidence.

Automatic identity may use a stable exact provider/requisition binding. Similar titles alone may only propose a review candidate. Preserve both discovery provenance and preferred employer-source provenance when a board redirects to an employer ATS.

### 7. Security and operational controls

- Accept only HTTP(S) URLs.
- Reject localhost, loopback, link-local, private-network, `file:`, and unsafe redirected destinations.
- Bound redirects, response bytes, decompression, timeouts, and retries.
- Validate content type and encoding.
- Never execute downloaded page scripts.
- Do not persist cookies, authorization headers, CSRF tokens, or browser storage.
- Sanitize retained HTML/source evidence or retain only normalized evidence plus hashes according to the chosen retention policy.
- Record 401, 403, 404, 410, 429, CAPTCHA, login-wall, expired-job, and capability-missing outcomes distinctly.

## Dependency qualification

Define the adapter and output contracts before selecting libraries. Then run an isolated, non-mutating bake-off against representative fixtures and a small number of current owner-selected public pages.

Candidates:

- Python standard library for official JSON APIs.
- `httpx` for redirects, encodings, timeouts, and HTTP behavior.
- `extruct` for JSON-LD and embedded metadata.
- `trafilatura`, BeautifulSoup, `lxml`, or another bounded parser for generic HTML.
- Playwright only if a script-controlled browser is demonstrably necessary and compatible with the target runtime.
- JobSpy as a separate Indeed/discovery experiment, not a trusted LinkedIn acquisition dependency.

Evaluate:

- Description fidelity and verified ending.
- Python compatibility on the current host and declared minimum version.
- Maintenance and release activity.
- License compatibility.
- Security and transitive-dependency exposure.
- Installation reliability and dependency weight.
- Redirect, encoding, timeout, and size-limit behavior.
- 403, 429, CAPTCHA, and login-wall handling.
- Whether operation would require prohibited credential transfer or access-control circumvention.

Prefer the smallest dependable core. Keep official ATS JSON acquisition standard-library-only when practical. Pin accepted direct dependencies and test installation in a clean isolated environment.

## Test and acceptance matrix

### Static and packaging

- `quick_validate.py skills/sync-jobs` passes.
- Frontmatter remains valid and the description includes direct employer, ATS, job-board, and owner-selected URL triggers.
- No imports or runtime references to retired Job Hunting project scripts.
- No unfinished scaffold files, accidental secrets, local personal paths, source identifiers or private profile data.
- Runtime references are discoverable from `SKILL.md` through progressive disclosure.

### Existing regression

- All 80 current tests pass before and after the change.
- Existing LinkedIn Saved/In Progress, ingest, triage, refresh, rollback, and workbook safety behavior remains compatible unless an explicitly documented schema migration is approved.

### Unit and adapter contract

- URL classification and provider recognition.
- Redirect and canonical URL handling.
- Tracking-parameter removal without deleting identity-bearing parameters.
- Stable provider/requisition ID extraction.
- JSON-LD selection when a page contains multiple structured objects.
- Unicode, HTML entities, whitespace, inline links, and multilingual text.
- Equivalent normalized output across adapters.
- Schema rejection for unsupported or contradictory provenance.
- Deterministic failure classification.

### Fixture integration

Use sanitized, immutable fixtures for:

- Greenhouse, Lever, and SmartRecruiters.
- Generic `JobPosting` JSON-LD.
- Generic static HTML.
- JavaScript shell with no server-rendered posting.
- Indeed-like public posting.
- Unknown job board that succeeds through the generic path.
- Board-to-employer redirect.
- Multiple jobs on one landing page.
- Login wall, CAPTCHA, 403, 404, 410, 429, and expired vacancy.
- Truncated description and mismatched title/URL/ID.

Fixtures must test semantic output and evidence bindings, not wording or headings in generated prose.

### End-to-end pipeline

- Owner URL -> acquisition bundle -> validation -> dry-run external ingest -> archive, compensation sidecar, eligibility sidecar, and workbook preview.
- Every selected URL appears exactly once as record or failure.
- Any incomplete selected URL blocks the original batch from committing.
- An owner-approved successful subset requires a newly narrowed manifest rather than silently dropping failures.
- Re-running the same source is idempotent.
- Cross-posted roles produce review candidates and do not merge on title similarity alone.
- No live tracker or installed skill is changed during tests.

### Mutation safety

- Excel-lock rejection.
- Backup and readback.
- Cross-filesystem staged publication through a verified destination sibling.
- Crash recovery and durable intent.
- Concurrent unrelated edits are preserved.
- Tampered capture, schema, manifest, staged artifact, or hash is rejected before writes.
- Rollback or partial-commit state is explicit and recoverable.

### Browser qualification

For each configured and actually available authorized surface, verify:

- correct URL, title, and job-ID binding;
- expansion of collapsed description text;
- complete ending and link-label preservation;
- download/export or bounded transfer and exact readback;
- no cookie/token export;
- a retained failure when the surface truncates, shifts jobs, requires login, or lacks the necessary capability.

Browser qualification is dated evidence. It must not be treated as a permanent capability guarantee.

### Live canaries

Run only after deterministic tests pass, without tracker writes:

- one current Greenhouse posting;
- one current Lever or SmartRecruiters posting;
- one current generic employer page;
- one current anonymous Indeed posting, if publicly accessible;
- one unfamiliar board using the generic adapter;
- one LinkedIn public detail capture through a permitted user-visible method;
- one authenticated LinkedIn Saved/In Progress index check when explicitly authorized.

Live failures are reported separately from deterministic regressions. Test one real end-to-end case before any batch-scale trial.

### Behavioral skill evaluation

Forward-test realistic prompts in an isolated workspace. Verify that the skill:

- activates for employer, ATS, Indeed, LinkedIn, and unfamiliar owner-selected posting URLs;
- does not activate for applications, cover letters, outreach, or general market research;
- selects acquisition references progressively rather than loading every provider guide;
- does not claim fixture success as live success;
- preserves source identity and authorization boundaries;
- stops rather than fabricating missing fields or completion.

Use an independent evaluator only when separately authorized and provide it the skill plus realistic raw artifacts, not the intended conclusion.

## Skill structure and authoring standards

- Keep `SKILL.md` concise: purpose, routing, essential invariants, and links.
- Put shared acquisition policy in `references/source_acquisition.md`.
- Put provider-specific details in focused files under `references/providers/` only when they materially change decisions.
- Put reusable deterministic code under `scripts/acquisition/` or an equivalently clear package.
- Keep browser preferences in private installation-local profiles rather than universal engine rules or public fixtures.
- Ship only a clearly synthetic example profile in the public repository.
- Do not copy external manuals into the skill.
- Do not create redundant installation guides or changelogs.
- Preserve automatic invocation unless the owner requests explicit-only use.
- Use version `2.4.0` if CLI and V1 inputs remain compatible; use `3.0.0` only for an intentional breaking change.
- Remove or consolidate the redundant README only after checking repository packaging and callers.
- Add or update `agents/openai.yaml` only if UI metadata or invocation policy provides concrete value.

## Implementation sequence and gates

### Gate 0 — Clean branch baseline

- Reconcile the v2.3.0 public engine into the branch.
- Verify a privacy-safe import receipt.
- Pass 80 tests and skill validation.

### Gate 1 — Contract and dependency decision

- Approve schemas, adapter protocol, fallback states, source policy, and retention policy.
- Complete isolated dependency bake-off.
- Record accepted and rejected dependencies with evidence.

### Gate 2 — Deterministic acquisition core

- Implement URL safety, attempts, normalization, provenance, quality, and structured failures.
- Pass unit, adversarial, and fixture tests without network access.

### Gate 3 — Provider and generic adapters

- Implement official ATS adapters, JSON-LD, generic HTML, and Indeed handling.
- Pass adapter contract and cross-source identity tests.

### Gate 4 — Browser fallback and pipeline integration

- Update browser acquisition references and schemas.
- Connect passing captures to dry-run external ingest.
- Pass full pipeline and mutation-safety tests.

### Gate 5 — Live qualification

- Run bounded read-only canaries.
- Complete one supervised end-to-end dry run.
- Resolve or explicitly accept all observed gaps.

### Gate 6 — Release readiness

- All deterministic tests pass.
- Skill validation passes.
- Behavioral evaluation passes.
- Branch diff contains only intended skill and plan changes.
- Final tree and publishable history contain no private profile data or local personal paths.
- No live installation, tracker mutation, job-board mutation, or credential artifact occurred.
- Produce a concise release report with test commands, results, known limitations, dependency decisions, and promotion steps requiring owner approval.

## Definition of done

The branch is ready for owner review when an owner-selected posting URL from a supported ATS, Indeed, a direct employer page, or an unfamiliar board can either produce a source-bound complete acquisition record or a precise retained failure; every selected URL is accounted for; tracker ingestion remains dry-run-first and fail-closed; the existing 80-test baseline plus the new deterministic suite passes; bounded live canaries demonstrate current behavior; and no prohibited authentication, scraping, browser, or mutation shortcut has been introduced.
