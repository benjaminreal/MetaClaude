# Session runtime contract

Read this reference when a session skill needs to construct or validate an
evidence envelope, append a session entry, audit the journal, or diagnose a
helper refusal. Do not load it for a routine prose-only explanation.

## Runtime CLI

Use the bundled `scripts/runtime_cli.py` with Python 3:

```text
snapshot <workspace-root>
fingerprint-rows <returned-rows.json>
validate <envelope.json>
freeze-draft <envelope.json> <entry.md>
approve-draft <draft-receipt.json> "<exact scope>"
append <envelope.json> <entry.md> <approved-draft-receipt.json>
audit <workspace-root>
count-words <text-file>
render-mirror <returned-rows.json> <local-date>
verify-sync <canonical-dir> <target-dir> [<target-dir> ...]
```

Write envelopes, returned-row JSON, and draft entry files only under the
harness scratch directory. A scratch file inside the repository is a project
or repository mutation, not ephemeral computation. When the harness blocks
scratch writes, pass JSON on stdin with `-` in place of the file path
(`fingerprint-rows -`, `validate -`, `count-words -`, `render-mirror -`). If neither works, there is no current
receipt: say so and make no current-state claim.

`snapshot` also returns `instructions` (`state` is `project_root`, `ancestor`,
or `instructions_absent`; `files` are the governing files and `ancestor_files`
every instruction file above the root, each with path and bytes) and
`instruction_budget` (bytes of this skill's `SKILL.md` and each reference),
plus `local_date` and `local_utc_offset` for resolving relative dates. Its
`git` field reports `branch`, `dirty`, and up to 20 `changed_paths` with
`changed_path_count`; state git facts only from these fields.

Take every count and time you report from a helper result, never from your own
estimate: `count-words` for word counts, `freeze-draft`'s `entry_words` for the
entry, and `fingerprint-rows`'s `fingerprinted_at` as a receipt's `observed_at`
when the tool result shows no time of its own. `validate` refuses a receipt
time later than the helper clock (`FUTURE_RECEIPT`). `render-mirror` turns
current receipt rows into the `## Active TODOs` body; replace the section body
with its output unchanged.

`append` refuses without the approved draft receipt, or when the envelope's
snapshot, the entry, or the approval scope differs from the frozen draft, or
when times are not ordered snapshot <= drafted < approved <= now. This guards
against accidental rebasing, not deliberate forgery.
Explicitly read each unique file in `files` and `ancestor_files` before
relying on them;
conflicting task-tracking rules mean `conflicted`.

## Evidence envelope

Create schema version `1.0` with:

- invocation id, invocation start time, skill, skill version, and absolute
  workspace root;
- the complete local snapshot returned by `snapshot`;
- a capability profile: local capabilities are booleans; `tasks_mcp` and
  `open_brain` are each `absent`, `present_unauthenticated`,
  `present_wrong_scope`, or `working`;
- current MCP receipts or named unavailable receipts;
- returned rows under `returned_rows_by_capability` so the validator can
  recompute their fingerprints;
- proposed mutation scope by `M2`, `M3`, and `M4`;
- approval state and the exact approved scope string;
- source hashes used for the draft.

A current receipt contains capability identity, observed time, normalized
operation fingerprint, content-derived row fingerprint, row count, and
`status: current`. A non-current receipt has no row fingerprint and names the
non-working capability state. Only `working` plus a current receipt permits an
authoritative claim.

## Gates and refusal

- `OBSERVATION_GATE`: validate current sources and stop on sync conflicts.
- `DRAFT_GATE`: show proposed mutations before project or external writes.
- `APPROVAL_GATE`: record explicit approval for the itemized M2/M3 scope.
- `CONCURRENCY_GATE`: the append helper rechecks the observed session-tail
  hash; a local lock is only a same-host advisory guard.
- `VERIFICATION_GATE`: require returned results or readback hashes.
- `LEARNING_GATE`: persist candidates before presenting them.
- `CLOSING_GATE`: emit only claims supported by verified receipts.

`append` refuses an absent or invalid envelope, absent approval, a changed tail,
a new sync-conflict artifact, an over-cap entry, or a readback mismatch. It is
the only sanctioned writer of `project_session.md` and creates the journal
record inside the same operation.
List the resolved session filename (for example, `project_session.md`) in the
approved `mutation_scope.M2` list. Approval of index or external operations
alone does not authorize a session append.

`audit` matches exact journal receipts first. A project policy may list an
owner-approved `documented_unverified_exceptions` item with the session number,
exact entry SHA-256, local historical note path, and note SHA-256. The audit
checks both hashes and reports a matching entry in `documented_unverified`,
separately from `journaled` and `grandfathered`. A changed entry, changed note,
or unused exception remains an audit error. The exception records a known
historical gap; it does not verify the original append or its claims.
Without a policy, the historical exemption ceiling is zero: matching receipts
can verify a fresh project, while entries without receipts remain unjournaled.

## Compatibility

Keep `project_session.md`, `project_index.md`, and `pending_learnings.md`
readable by v1 skills: preserve headings, entry fields, `Updated:`, and the
read-only `## Active TODOs` mirror. New envelope and journal state must not be
embedded into those files.
