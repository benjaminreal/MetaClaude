# Tasks DB operations

Read this reference only when a session invocation needs a Tasks DB read. Resolve task-tracking instructions first; if resolved
instruction files disagree, stop and surface the conflict.

Use angle-bracket placeholders. Never place a dollar sign followed by a digit
in a skill body or reference: slash-command argument substitution may rewrite
it.

## Current project slice

```sql
select id, urgency, priority, project, title, flagged, due, review_on, status
from task_urgency
where status = 'open' and project = '<project>'
order by (coalesce(flagged, false) or coalesce(review_on <= current_date, false)) desc,
         urgency desc, priority asc nulls last, created_at asc
limit 8;
```

For an explicitly requested portfolio brief, omit the project predicate and use
`limit 20`.

## Opening boundary

Task creation and all other writes belong during the session or at closingtime.
If requested at opening, say so and stop. This reference authorizes reads only.

## Receipt rule

Save the returned rows to scratch JSON and run `fingerprint-rows`. Put the
result, operation fingerprint, observed time (the helper's `fingerprinted_at`
unless the tool result carries its own), project identity, status, and row
count in the MCP receipt. Preserve the returned rows in the scratch envelope so
`validate` can recompute the fingerprint.

Every external retry needs fresh approval and fresh preconditions. An
instruction not to use Open Brain at all is SKIP-openbrain; a search sends
candidate text to the service. Authoritative Tasks receipts need explicit
project identity bound to envelope.project and every row.project (or explicit
portfolio mode); use fingerprint-operation for exact query identity.
