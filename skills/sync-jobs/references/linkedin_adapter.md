# LinkedIn acquisition adapter

Use this provider-specific workflow only for explicit posting IDs or an
authorized Saved/In Progress index. It does not authorize applying, saving,
unsaving, messaging, crawling, or exporting authentication material.

## Saved and In Progress indexes

Use only user-visible controls and content in an explicitly authorized browser
session. The public package deliberately ships no LinkedIn endpoint scripts.
Do not read cookies or tokens and do not call private HTTP, GraphQL or Voyager
endpoints. A browser tool may inspect already rendered DOM when its documented
capabilities allow that, but the DOM inspection must not issue network
requests.

Visit each explicitly requested card and paginate or scroll with visible UI
controls until the surface provides an independently verifiable terminal
state. Require exact `count == total`, complete pagination and unique numeric
job IDs before making a complete-index claim. A guard limit, count mismatch,
empty result inconsistent with the visible board, missing metadata or a
virtualized list whose unseen entries cannot be enumerated is incomplete and
blocks sync. Save normalized records through `acquire-save`; do not save
browser storage or raw account-state exports.

## Selected-ID capture

For an explicit numeric posting ID, confirm the visible URL, title, company and
ID before accepting text. Expand the actual description, wait for the page to
settle, and independently verify its final section. Use a currently available
authorized browser surface; a private installation-local profile may express a
preference, but the public skill defines no browser order.

Prefer documented rendered-DOM text when available. Native accessibility text
is acceptable only when the surface exposes ordered description-only text and
link labels. A DOM evaluation may inspect only the already rendered DOM and
must not call `fetch`, XHR, GraphQL, private endpoints or another transport.

Bound retries per the active profile or operator instruction. If no such bound
is supplied, make one normal attempt and one corrective retry on a surface,
then retain the failure or try another authorized surface. A stale, shifted or
uncertain URL/title/text binding stops that posting. Never substitute a partial
description.

When direct export is unavailable, transfer the complete observed text into a
local JSON input and save it with `acquire-save`. The acquisition command does
not require a workspace or candidate profile:

```bash
python3 scripts/sync_jobs.py acquire-save \
  --records-json /tmp/run/captured.json --out /tmp/run/acquisition.json \
  --selected-id 1111111111 --selected-id 2222222222
```

Example synthetic input:

```json
{
  "records": [{
    "id": "1111111111",
    "title": "Example role",
    "company": "Example organization",
    "location": "Example location",
    "status": "Saved",
    "url": "https://www.linkedin.com/jobs/view/1111111111/",
    "description": "Complete synthetic description with a verified ending.",
    "provenance": {
      "browser": "authorized-browser-a",
      "method": "rendered_dom_text",
      "captured_at": "2030-01-01T00:00:00Z",
      "complete_text": true,
      "completion_evidence": "Expanded the description and independently observed its final section.",
      "status_certain": false,
      "status_uncertainty": "The detail page did not prove current board membership."
    },
    "quality_evidence": {
      "end_verified": true,
      "end_marker": "verified ending.",
      "truncation_flags": []
    }
  }],
  "failures": [{
    "id": "2222222222",
    "reason": "Complete text unavailable after bounded fallback.",
    "attempts": ["authorized-browser-a", "authorized-browser-b"],
    "status_uncertainty": "Current board state was not reliably visible."
  }]
}
```

Every selected ID must appear exactly once as a record or retained failure.
`acquire-save` recomputes quality, hashes the bundle, writes atomically and
verifies readback. A passing capture is eligible for later validation; it does
not independently prove board membership or authorize tracker writes.

For owner-requested comparison of existing archives, follow
[source verification](source_verification.md). Freeze selection before fresh
capture and keep unavailable, failed, unvisited and identity-mismatched states
distinct.
