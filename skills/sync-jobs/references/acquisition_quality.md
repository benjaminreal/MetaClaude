# Capture quality contract

Read this when capturing a description or preparing `ingest` input. The checks
bind capture evidence to description bytes and detect known failure shapes. A
`PASS` makes a record eligible for ingestion; it does not prove that the source
is true or complete beyond the supplied evidence.

## Supported captures

`provenance.method` identifies the actual acquisition path:

- `rendered_dom_text` or `native_text` for user-visible browser captures;
- `official_api` for one ID-bound public ATS response;
- `public_json_ld` for one URL-bound schema.org `JobPosting` object;
- `public_html` for one structurally closed posting-description container;
- `owner_provided_artifact` for a hashed owner-supplied artifact that explicitly
  does not claim current live availability.

Do not label endpoint JSON, screenshots, inferred text, or one method's
evidence as another method.

Official API evidence requires HTTP 200, a response hash, an HTTPS endpoint,
the exact provider job ID and a single-job binding. JSON-LD evidence requires
HTTP 200, a response hash, `structured_type: "JobPosting"`, a positive object
count and one URL-bound job. Public HTML requires HTTP 200, a response hash,
exactly one bound container and `container_closed: true`. These structural
checks accompany the independently established end marker; status 200 or a
copied suffix alone never passes.

An owner artifact requires its retained path and SHA-256 plus
`availability_verified: false`. It binds evidence bytes but cannot establish
that the current source is still open or unchanged.

A rendered-DOM capture needs a verified ending and an `end_marker` copied from
the ending independently observed on the expanded source, then matched against
the whitespace-normalized end of `description`. Copying an unverified captured
suffix into `end_marker` does not establish the boundary. A healthy DOM capture
does not require a second browser when no truncation signal exists.

A native capture also needs:

- `quality_evidence.native_scope: "job_description_only"`;
- `native_nodes` as a nonempty ordered list of JD-only text and inline link
  labels, each shaped as `{"role":"text"|"link","text":"..."}`;
- `description` equal to those node values in order after whitespace
  normalization.

Build `description` with the skill-owned
`acquisition_quality.ordered_native_text(native_nodes)` helper. Scope the nodes
to the JD: exclude navigation, company panels and other UI containers, preserve
inline link labels as `role:"link"`, and never silently drop a link label.

An exact 512-character native node or nonempty `truncation_flags` is a legacy
conservative suspicion signal. It blocks ingestion unless a distinct complete
capture has the exact same description bytes and SHA-256. It is not a universal
length rule or proof that every 512-character paragraph is truncated.

## Independent resolution

Use `quality_evidence.independent_check` only for a separately captured exact
description. It must have exactly these fields:

```json
{
  "kind": "independent_comparison",
  "browser": "authorized-browser-b",
  "method": "rendered_dom_text",
  "captured_at": "2030-01-01T00:01:00Z",
  "description": "The exact same complete description bytes...",
  "description_sha256": "64 lowercase hexadecimal characters",
  "complete": true,
  "evidence": "Expanded the rendered JD and verified its final section."
}
```

`kind` may also be `reacquisition`. `method:"reference_description"` means a
previously saved complete description with its own source provenance, not an
arbitrary label or inferred text. The independent browser and method must both differ
from the flagged native source, compared without case sensitivity. A later
timestamp on the same browser/native path is not independent. The independent
description, its hash and the primary description must match exactly. Otherwise
retain the blocked capture and reacquire; never reconstruct missing text.

## Runnable rendered-DOM input

Replace the example values with observed evidence:

```json
{
  "records": [{
    "id": "1234567890",
    "title": "Example role",
    "company": "Example Company",
    "location": "Example location",
    "status": "Saved",
    "url": "https://www.linkedin.com/jobs/view/1234567890/",
    "description": "Responsibilities and requirements. Equal opportunity employer.",
    "provenance": {
      "browser": "authorized-browser-a",
      "method": "rendered_dom_text",
      "captured_at": "2030-01-01T00:00:00Z",
      "complete_text": true,
      "completion_evidence": "Expanded the JD and verified the visible final sentence.",
      "status_certain": false,
      "status_uncertainty": "Detail-page Saved label does not prove current board membership."
    },
    "quality_evidence": {
      "end_verified": true,
      "end_marker": "Equal opportunity employer.",
      "truncation_flags": []
    }
  }],
  "failures": []
}
```

Run:

```bash
python3 scripts/sync_jobs.py acquire-save \
  --records-json /tmp/run/captured.json --out /tmp/run/acquisition.json \
  --selected-id 1234567890
```

The saved `SelectedPostingAcquisitionV1` bundle embeds a recomputed
`CaptureQualityV1` result. Any retained failure or blocked record makes
`complete` and `quality_complete` false. The record remains diagnostic evidence,
but the whole bundle is ineligible for ingestion.

## Ingest enforcement

Pass the complete acquisition bundle directly as `--jobs-json`. Ingest checks
its schema, selected-ID coverage, empty failures and both completion flags, then
re-runs the acquisition record validator and quality calculation for every
description it would write. It does not trust an embedded `quality` object.

Legacy bare lists and `jobs` wrappers remain parseable for compatibility, but a
new description or tracker-only JD recovery still needs all current capture and
quality source fields. They cannot bypass the gate. Archive-only recovery reuses
existing archive bytes without claiming fresh capture quality. Already-canonical
tracker/archive rows are skipped without rewriting their descriptions.
