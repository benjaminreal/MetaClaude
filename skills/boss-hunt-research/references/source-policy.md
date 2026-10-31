# Source and Search Policy

## Claim-specific source policy

There is no universal "primary source" that proves every BossHunt claim. Match source type to claim.

| Claim | Strong evidence | Insufficient alone |
|---|---|---|
| Role and stated boss title | Live/archived employer posting, owner-supplied JD artifact | Search snippet, copied job board without provenance |
| Current employer/title | Authenticated current profile plus independent employer/durable source | Snippet, aggregator, undated bio |
| Confirmed hiring manager | Explicit job-poster, hiring-team, "my team," or requisition-linked evidence | Seniority, org adjacency, matching title |
| Reporting scope | Employer org/leadership material, first-person role description, dated announcement, corroborated profile | Company size heuristic, apex assumption |
| Recipient hook | Exact recipient-authored or recipient-attributed artifact | Profile/homepage, unattributed company statement |
| Company/JD hook | Exact dated company/JD artifact with honest attribution | Rephrased as recipient belief or quote |
| Email/channel | Live published professional address or later separately authorized dedicated verifier | Hunter Finder score, pattern alone, catch-all, guessed personal address |

## Evidence receipts and independence

Every load-bearing observation records its run ID, observation time, source or evidence reference, authority scope where applicable, and a SHA-256 of the representation actually reviewed. A stable page-content hash is preferred. When the surface exposes no stable bytes, hash the canonical captured representation and name it; never label a guessed value as page content.

Two URLs are not independent when they reproduce the same underlying profile, press release, database, or snippet. Give every evidence item an `independence_key`. A current-title gate needs at least two distinct keys.

Examples:

- employer leadership page: `employer:first-party`
- authenticated LinkedIn profile: `linkedin:profile:<profile-id>`
- copied biography on two event sites: one shared key such as `syndicated:bio-2026`

## Exact artifact rule

An exact URL has a meaningful path to the referenced artifact. A generic domain root, profile index, search-results URL, or platform homepage does not establish the specific claim. A person-profile URL may establish identity/currentness but cannot stand in for a specific authored hook.

## Time and currentness

Every external evidence item records `observed_at` and the run ID. Authenticated currentness also binds the capability receipt, surface identity, selected recipient/company/target, result, freshness deadline, evidence reference, and evidence hash. Dated announcements can support historical facts but do not prove current employment indefinitely. When a source is stale or undated, say so.

## Search misses

- `MISS`: the recorded query/surface returned no usable candidate.
- `BLOCKED`: the surface was inaccessible, authenticated-only, or interrupted.
- `NOT_PUBLIC`: the bounded plan completed without defensible public resolution.

None proves the person or seat does not exist.

## Refutation

Actively seek:

- later employer or title;
- ended tenure;
- geography/scope mismatch;
- another leader owning the mandate;
- posting/requisition mismatch;
- hook attribution to someone else;
- active recruiter/sponsor route or same-company collision;
- signed rejection from the proposed recipient.

Persist disconfirmers so later batches do not revive a stale route without newer evidence.

## Access and privacy

- Use public professional data and permitted authenticated read-only surfaces.
- Search professional email first. Reuse first-party evidence already encountered; otherwise cap the separate public-address pass at one exact-person query and one obvious employer-page read.
- Use Hunter `Email Finder` for the resolved person/domain under the one-call/one-search-credit dossier cap. A Hunter result remains an unverified professional candidate. `Domain Search` is a filtered, non-paginated alternative to Finder, not an automatic second call.
- Check Hunter credit balance once per batch or from a less-than-24-hour snapshot. Record the method, result, connector calls, and credits used.
- Do not use Hunter `Email Verifier`, enrichment, leads/lists, recipients, or campaigns in this skill, and do not follow connector `nextAction` suggestions into them.
- Use professional-platform or recruiter fallback only after recording the email-discovery outcome.
- Do not bypass access controls, captchas, robots restrictions, or confidential-employer protections.
- Do not collect home addresses, private phone numbers, family data, or personal emails.
- Do not open Gmail bodies/threads without explicit owner permission.
- Do not interpret delivery telemetry as identity proof.
