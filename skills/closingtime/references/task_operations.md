# Tasks DB operations

Read this reference only when a session invocation needs a Tasks DB read or an
approved task mutation. Resolve task-tracking instructions first; if resolved
instruction files disagree, stop and surface the conflict.

Use angle-bracket placeholders. Never place a dollar sign followed by a digit
in a skill body or reference: slash-command argument substitution may rewrite
it.


## Task-only gateway transport

When resolved task instructions authorize `tasks-mcp` and the actual tool is
available, call `urgency` with exactly `{"project":"<project>"}` or
`{"scope":"portfolio"}`. There are no implicit scope defaults. Otherwise keep
the existing approved SQL path; do not reconfigure a connection here.

Save the actual structured urgency result and the independently intended
operation `{"tool":"urgency","arguments":<exact arguments>}` to scratch. Run:

```text
runtime_cli.py gateway-receipt <result.json> <operation.json> --project <project|portfolio> --project-ref <expected-service-ref>
```

The expected service reference comes from resolved instructions, not the
response. Set the independently intended envelope project and run
`attach-evidence ENVELOPE PACKET` with the emitted packet. Preserve the retained
`gateway_result`, operation, transport, timestamp and truncation flag unchanged;
run `validate`. Only a successful urgency result can establish current task
state. A truncated result is a bounded slice, never a complete backlog. Server
time is evidence; do not replace it with a local time. The constructor is local,
read-only, and does not prove the service or installed client works.

## Current project slice

```sql
select id, urgency, priority, project, title, flagged, due, review_on, status, updated_at
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
insert into tasks (id, project, title, details, priority, cluster, origin)
values ('<reserved-task-uuid>'::uuid, '<project>', '<title>', '<details>', <priority>, '<cluster>', '<origin>')
returning id, project, title, priority, status, origin;

update tasks set status = 'done', completed_at = now(), updated_at = now()
where id = '<task-uuid>' and updated_at = '<observed-updated_at>'
returning id, status, priority, flagged, updated_at;

update tasks set priority = <priority>, flagged = <flagged>, updated_at = now()
where id = '<task-uuid>' and updated_at = '<observed-updated_at>'
returning id, status, priority, flagged, updated_at;

update tasks set status = 'parked', review_on = '<review-date>', updated_at = now()
where id = '<task-uuid>' and updated_at = '<observed-updated_at>'
returning id, status, priority, flagged, updated_at;

update tasks set status = 'cancelled', updated_at = now()
where id = '<task-uuid>' and updated_at = '<observed-updated_at>'
returning id, status, priority, flagged, updated_at;
```

After mutations, rerun the current project slice and rebuild the mirror from
the returned rows with `render-mirror <rows.json> <local-date>`. With no
mutations, a current read rebuilds it the same way. Never hand-edit task state
in Markdown.

## Receipt rule

Save the returned rows to scratch JSON and run `fingerprint-rows`. Put the
result, operation fingerprint, observed time (the helper's `fingerprinted_at`
unless the tool result carries its own), project identity, status, and row
count in the MCP receipt. Preserve the returned rows in the scratch envelope so
`validate` can recompute the fingerprint. A write also needs its `returning`
result or a follow-up current read before it is reported as verified.

Reserve the UUID before approval. After an uncertain insert, read that same
UUID before any retry; never substitute a fresh UUID. Every external retry
requires fresh approval and fresh preconditions. Updates use observed row
preconditions using the observed updated_at and returning. Zero returned rows is a conflict: read again and ask again; never retry blindly. The tasks_set_updated_at trigger refreshes updated_at on every update (verified read-only on 2026-10-28). No live call is needed to use these templates. If unavailable, retain the exact operation,
reserved id and "needs fresh approval" in the entry's Decisions/Next.

An authoritative receipt needs envelope.project = identity.project = every
row.project, including an explicit project identity for empty rows. Portfolio
mode is explicit (see runtime_contract.md). Fingerprint the exact query using
fingerprint-operation; do not lowercase or collapse whitespace in literals.

### Approved gateway mutations

The same exact-change approval and fresh-read rules apply to gateway calls.
Show the tool name and exact JSON arguments instead of SQL when this transport
is authorized. Reserve the create UUID before approval. `create_task` requires
`id`, `project`, `title` and `origin`; `update_task` requires `id`, the exact
last-read `expected_updated_at`, and `changes`. There is no delete or free SQL.
An explicit `status: "done"` refreshes `completed_at`; other status changes and
ordinary edits preserve it, matching the SQL templates. Timestamps are not
caller-editable fields. A duplicate create returns the existing row; a stale
update returns conflict and grants no retry. Use `get_task` for independent
readback, then a fresh `urgency` result and validated receipt for the mirror.
No gateway call is authorized by a receipt constructor or an opening brief.
