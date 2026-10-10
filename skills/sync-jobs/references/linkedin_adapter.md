# LinkedIn acquisition adapter

Use this provider-specific workflow only for explicit posting IDs or an
authorized Saved/In Progress index. It does not authorize applying, saving,
unsaving, messaging, crawling, or exporting authentication material.

## Transport boundary

Read LinkedIn only through user-visible pages and controls in an explicitly
authorized browser session. This boundary also applies to posting-age and
open/closed-status checks. Do not call LinkedIn API endpoints, including public
guest job endpoints, or use API scripts as a fallback. An endpoint being public
does not authorize using it. Record unavailable date or status evidence as
unknown instead of changing transports.

## Saved and In Progress indexes

Use only user-visible controls and content in an explicitly authorized browser
session. The public package deliberately ships no LinkedIn endpoint scripts.
Do not read cookies or tokens and do not call private HTTP, GraphQL or Voyager
endpoints. A browser tool may inspect already rendered DOM when its documented
capabilities allow that, but the DOM inspection must not issue network
requests.

Read posting dates and open/closed wording from the visible posting page. Keep
the observed wording and observation time; a displayed refresh or repost date
does not by itself establish a new hiring process. Board membership alone does
not establish that a posting is open. Candidate-specific freshness calculations
remain in the selected private profile.

Visit each explicitly requested card and paginate or scroll with visible UI
controls until the surface provides an independently verifiable terminal
state. Require exact `count == total`, complete pagination and unique numeric
job IDs before making a complete-index claim. One exception: LinkedIn's SAVED
total is advisory and may exceed the unique jobs shown. Accept that positive
surplus only with `error` null, `card` SAVED, `pagination_complete` true and
`termination` `total_reached`, `empty_page`, or a validated `last_page`, and log the exact gap. It never
covers IN_PROGRESS, a retrieved count above the total, or incomplete
pagination. A guard limit, any other count mismatch,
empty result inconsistent with the visible board, missing metadata or a
virtualized list whose unseen entries cannot be enumerated is incomplete and
blocks sync. Save normalized records through `acquire-save`; do not save
browser storage or raw account-state exports.

For a populated last UI page with no enabled Next control, retain the actual
`termination: "last_page"` and a `pagination_evidence` array. Each item records
the selected `page` number, `visible_pages` from the pagination controls,
`reported_total`, numeric string `job_ids` from all rendered posting cards,
and `next_control` (`enabled`, `disabled`, or `absent`). Retain the underlying
rendered page observations in the private run evidence. For example:

```json
{
  "card": "SAVED", "count": 2, "total": 3, "error": null,
  "pagination_complete": true, "termination": "last_page",
  "jobs": [{"id": "1111111111"}, {"id": "2222222222"}],
  "pagination_evidence": [
    {"page": 1, "visible_pages": [1, 2], "reported_total": 3,
     "job_ids": ["1111111111"], "next_control": "enabled"},
    {"page": 2, "visible_pages": [1, 2], "reported_total": 3,
     "job_ids": ["2222222222"], "next_control": "absent"}
  ]
}
```

The validator requires consecutive pages starting at 1, a stable total,
unique IDs covering the index exactly, an enabled Next control on every
intermediate page, and an absent or disabled Next control on the final page
whose highest visible page number is selected. This validation also applies
when `count == total`. A terminal label alone, skipped pages, changing totals,
or duplicate page IDs block the index. An empty ending uses `empty_page`.

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
