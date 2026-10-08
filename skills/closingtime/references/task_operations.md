# Tasks DB operations

Read this reference only when a session invocation needs a Tasks DB read or an
approved task mutation. Resolve task-tracking instructions first; if resolved
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

## Approved mutations

```sql
insert into tasks (project, title, details, priority, cluster, origin)
values ('<project>', '<title>', '<details>', <priority>, '<cluster>', '<origin>')
returning id, project, title, priority, status, origin;

update tasks set status = 'done', completed_at = now(), updated_at = now()
where id = '<task-uuid>'
returning id, project, title, status, completed_at;

update tasks set priority = <priority>, flagged = <flagged>, updated_at = now()
where id = '<task-uuid>'
returning id, project, title, priority, flagged;

update tasks set status = 'parked', review_on = '<review-date>', updated_at = now()
where id = '<task-uuid>'
returning id, project, title, status, review_on;

update tasks set status = 'cancelled', updated_at = now()
where id = '<task-uuid>'
returning id, project, title, status;
```

After mutations, rerun the current project slice and rebuild the mirror from
the returned rows. Never hand-edit task state in Markdown.

## Receipt rule

Save the returned rows to scratch JSON and run `fingerprint-rows`. Put the
result, operation fingerprint, observed time, project identity, status, and row
count in the MCP receipt. Preserve the returned rows in the scratch envelope so
`validate` can recompute the fingerprint. A write also needs its `returning`
result or a follow-up current read before it is reported as verified.
