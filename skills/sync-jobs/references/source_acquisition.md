# Source-neutral posting acquisition

Read this for an owner-selected employer, ATS, Indeed, or unfamiliar job-board
URL. This workflow is evidence collection only. It does not apply, save,
unsave, message, discover additional jobs, open the tracker, or authorize later
workspace writes.

## Public acquisition

Run from the skill directory. `acquire-url` does not require a workspace,
candidate profile or tracker.

```bash
python3 scripts/sync_jobs.py acquire-url \
  --url "https://employer.example/jobs/123" \
  --out /private/tmp/sync-jobs-run/acquisition.json
```

Repeat `--url` for a bounded owner-selected batch. Each supplied URL appears
exactly once in `SourcePostingAcquisitionV2` as a passing record or retained
failure. An existing output is never overwritten. `--commit` is invalid for
this command.

The deterministic acquisition order is:

1. A recognized official public Greenhouse, Lever, or SmartRecruiters endpoint.
2. An anonymous request for the selected page.
3. One URL-bound schema.org `JobPosting` object.
4. One structurally closed public HTML job-description container.
5. A structured browser or manual-artifact handoff.

Provider recognition is an optimization, not a requirement. An unfamiliar
board can pass through JSON-LD or static HTML. HTTP 200, nonempty text, or a
copied suffix is insufficient: the method-specific quality evidence must bind
one posting and a structural end boundary.

When changing provider endpoint recognition or field mapping, read
[public ATS adapters](providers/public_ats.md).

LinkedIn short-circuits to its browser workflow without an anonymous scripted
request. For a selected numeric LinkedIn ID, read [LinkedIn adapter](linkedin_adapter.md)
and save the user-visible capture with `acquire-save`. Saved/In Progress indexes
require an authorized authenticated browser session. Never transfer cookies,
tokens, browser storage, or credentials to shell code.

## Output and identity

Each passing V2 record preserves:

- the supplied discovery URL, final transport URL, and canonical posting URL;
- provider, ATS, provider job ID, and requisition ID when explicitly available;
- title, company, location, employment type, posting date, and full description;
- description, source-record, response, and bundle hashes;
- authentication state, method-specific provenance, attempts, and quality;
- source identity and a cross-source review fingerprint.

Source identity is a stable provider/job-ID binding when available, otherwise
the canonical posting URL. The cross-source fingerprint only proposes review;
it never authorizes an automatic merge. Similar titles alone are not identity.
When a board redirects to an employer posting, retain the board URL as discovery
provenance and the employer URL as the canonical source.

The generic canonicalizer removes fragments and only unambiguous advertising
parameters (`utm_*`, `fbclid`, `gclid`). It preserves unfamiliar `source`,
`ref`, `locale`, duplicate, and other query parameters because they may carry
identity. Provider-specific normalization may become stricter only with tests.

## Failure and fallback

Read every failure's `failure_kind`, attempt ledger, and `next_action`. Keep
401/403, 404/410, 429, login wall, CAPTCHA, bot challenge, expired posting,
JavaScript shell, multiple postings, identity mismatch, unsupported content,
network error, and unsafe URL distinct. Never turn any of them into an empty
successful capture.

Use each authorized browser surface actually available in the environment. A
private installation-local profile may express an order; the public skill does
not. At each selected surface:

1. Confirm the selected URL or explicit redirect, exact title, company, and
   provider job ID or requisition when visible.
2. Expand the actual description and wait for the page to settle.
3. Capture description-only rendered DOM text, or ordered native text and link
   labels when that is the documented capability.
4. Verify the final section independently from the transferred suffix.
5. Retain the surface, method, timestamp, URL binding, attempts, and uncertainty.

Allow one normal attempt and one corrective retry per transport unless the
active private profile supplies a different bound. A missing surface is
`capability_missing`. A login or
security prompt requiring owner action stops that attempt. Do not use
screenshots, hidden requests, private endpoints, proxy rotation, CAPTCHA bypass,
or copied authentication material.

The current CLI emits the browser handoff but does not itself control a browser
or merge browser output back into a V2 bundle. For non-LinkedIn browser captures,
prepare the existing strict direct-record input described in
[direct-source intake](direct_source_intake.md); preserve the failed V2 bundle
as provenance. A batch may proceed with a successful subset only after the
owner explicitly selects that subset and a new input accounts for exactly that
narrowed scope. Do not silently remove failures from the original bundle.

An owner-supplied HTML, PDF, or text artifact is the final fallback. Hash and
attribute the artifact and state that current live availability was not
verified. Do not infer omitted text or source dates.

## Security limits

The public transport accepts only HTTP(S), rejects embedded credentials,
localhost, literal and DNS-resolved private/loopback/link-local destinations,
unsafe redirects, disallowed ports, excess redirects, oversized responses,
unsupported content types, and unsupported compression. It requests static
JSON or HTML and never executes downloaded scripts.

Do not add a new external extraction dependency merely to support one observed
page. Read [dependency evaluation](dependency_evaluation.md) before changing the
core. Live failures are maintenance evidence, not permission to weaken URL or
quality checks.

For the dated 2.4 canary results and outstanding promotion gates, read
[release evidence](release_evidence_2026-09-13.md). Do not treat dated canaries
as a permanent guarantee that a board remains anonymously accessible.

## Ingestion gate

Only a complete, hash-valid, quality-complete V2 bundle can feed
`external-ingest`. Rehearse without `--commit` first. A V2 commit writes the
canonical external URL only to `Link puesto empresa`, leaves the historical
LinkedIn-labelled field blank, and writes a durable
`PostingSourceProvenanceV2` sidecar alongside compensation and eligibility
evidence. Legacy direct-record inputs retain their historical column behavior.

Tampering with selection coverage, description, response, attempts,
provenance, embedded quality, record hash, or bundle hash blocks before tracker
writes. The acquisition bundle never claims that tracker/archive gates ran.
