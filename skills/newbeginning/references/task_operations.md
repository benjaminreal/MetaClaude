# Tasks DB operations

Read this reference only when a session invocation needs a Tasks DB read or an
approved task creation. Resolve task-tracking instructions first; if resolved
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

## Approved creation

```sql
insert into tasks (id, project, title, details, priority, cluster, origin)
values ('<reserved-task-uuid>'::uuid, '<project>', '<title>', '<details>', <priority>, '<cluster>', '<origin>')
returning id, project, title, priority, status, origin;
```

Reserve the UUID before approval. If a call has an uncertain outcome, read that
UUID before any retry and never substitute a fresh UUID. After creation, read
the exact ID and rerun the current project slice. Never hand-edit task state in
Markdown.

## Receipt rule

Save the returned rows to scratch JSON and run `fingerprint-rows`. Put the
result, operation fingerprint, observed time, project identity, status, and row
count in the MCP receipt. Preserve the returned rows in the scratch envelope so
`validate` can recompute the fingerprint. A write also needs its `returning`
result or a follow-up current read before it is reported as verified.
