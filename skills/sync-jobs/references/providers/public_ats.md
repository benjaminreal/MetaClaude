# Public ATS adapters

Read this only when maintaining a supported public ATS adapter. The source code
constructs documented public detail endpoints from one owner-selected posting
URL; it does not crawl job lists or submit applications.

## Greenhouse

- Recognized pages: `boards.greenhouse.io/<board>/jobs/<id>` and
  `job-boards.greenhouse.io/<board>/jobs/<id>`.
- Public detail endpoint: `boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>`.
- Bind the response `id` to the page ID. Use `content` as the description and
  retain `absolute_url` and `requisition_id` when present.
- Some responses omit a defensible company name. That is a structured missing
  field and triggers public-page/browser fallback; never humanize the board
  token and present it as source evidence.

## Lever

- Recognized page: `jobs.lever.co/<site>/<posting-id>`.
- Public detail endpoint: `api.lever.co/v0/postings/<site>/<posting-id>`.
- Bind response `id`. Preserve `descriptionPlain`, ordered list sections and
  `additionalPlain`; do not discard the final section.
- Some responses omit company. Preserve that gap and fall back rather than
  treating the site slug as verified company identity.

## SmartRecruiters

- Recognized page: `jobs.smartrecruiters.com/<company>/<id>-<slug>`.
- Public detail endpoint:
  `api.smartrecruiters.com/v1/companies/<company>/postings/<id>`.
- Bind response `id`, use the stated company and location, and concatenate the
  ordered public `jobAd.sections` without inventing missing sections.

All adapters use anonymous GET requests and the shared URL, redirect, response,
identity, and quality controls. A failed endpoint may fall back to the exact
selected public page. Provider drift belongs in a retained attempt and a dated
canary report, not an empty success.
