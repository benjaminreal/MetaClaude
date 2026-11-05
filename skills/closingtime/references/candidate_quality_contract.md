# Learning candidate quality contract

Mutation procedures here apply during session work or closingtime. Newbeginning
may use the wording rules for read-only discussion/search, but never edits pending
files or captures to Open Brain. Optional stage and conditional resolve permission may be in the close;
ordinary edits and captures keep separate approval scopes. Skips/zero candidates leave files untouched.

Read this reference only when generating, reviewing, or revising learning
candidates. It adds wording-quality rules to the existing
`PENDING_LEARNING_LIFECYCLE`; it does not change staging, approval, capture, or
disposition authority.

## Required outcome

The `Insight` text must stand on its own when retrieved without the source
session, pending file, or connection metadata.

1. **Language.** Follow an explicit user language choice first. Otherwise use
   the dominant session language when it is English or Spanish; fall back to
   English. An explicit request for another language overrides this default.
2. **Plain and standalone.** State the actor, object, situation, and lesson
   needed to understand the insight. Avoid unexplained pronouns and jargon.
   Define an essential technical term in the same candidate.
3. **One central insight.** Keep one transferable claim per candidate.
   Supporting context or one example may clarify it, but unrelated lessons
   become separate candidates.
4. **Evidence fidelity.** Preserve uncertainty and transfer limits. Do not turn
   a tentative observation into a universal or causal rule, and do not invent
   missing context. Keep a rule's scope: a journal requirement applies to
   workflows that require that journal, not to all local writes.
5. **Stable wording.** Keep volatile traceability outside `Insight`. Exclude
   session numbers, internal IDs or codes, model/version tokens, and absolute
   file paths unless the user explicitly chooses to retain an essential term
   after reviewing the complete wording. Put provenance in connection or
   source metadata instead.

Normally one to three sentences are enough, but clarity and fidelity take
priority over a mechanical length target.

## Review gate

Apply the contract before staging and presenting a new candidate. Apply it
again to owner-edited wording immediately before Open Brain capture. If a
quality repair changes the wording, show the complete revision and obtain
fresh approval; never silently normalize owner-approved text.

## Evaluation boundary

Deterministic checks may detect volatile references, missing fields, or the
wrong declared language. Plainness, standalone meaning, one-insight focus, and
uncertainty fidelity require a blinded rubric or owner review. Do not claim
that regex checks prove semantic quality.

## Pending file (reference-only procedure)

Existing pending blocks are opaque. Preserve them, unresolved wording
and unknown metadata; do not silently standardize legacy text. Existing
`Connection` or `Connects to`, with or without `Status`, remain valid layouts.
New blocks may use this v1-readable form:

```markdown
## Candidate 1
**Type:** <type>
**Insight:** <standalone wording>
**Connects to:** <verified connection or named unavailable state>
**Status:** pending
**Source:** <optional provenance outside Insight>
```

Read the existing bytes; stage preserves them exactly and appends new numbered
candidate blocks only. Do not renumber existing blocks under stage permission.
Use the close's optional approved stage line once after verified append, with
write-approved --operation stage --expect current SHA-256 (or absent initially).
Stage recognizes only new block structure, never parses legacy content.
`pending-blocks` emits the exact block hash plus `capture_wording` and
`capture_wording_sha256`: one nonempty Insight field, with edge whitespace
stripped and no heading or metadata. Ambiguous/multiline legacy wording returns
null; do not guess. Present this complete wording before capture approval.
Capture exactly the approved wording; never silently normalize it.

A saved disposition binds the current block hash, separately approved wording
hash and successful capture result. For owner-edited wording, include the exact
`wording`, its `payload_sha256`, the source `block_sha256` and actual owner words
in `capture_approval`; reapply this quality contract. Capture approval of that
edited text does not authorize an ordinary pending-file replacement. Resolve can
remove the original block using that explicit binding without first rewriting it.
If the owner wants the pending file edited/retained, freeze the exact replacement
and obtain approval; write/read back before capture.

Keep needs no write. With approved conditional resolve scope, record discarded
or successfully saved dispositions and run `resolve-pending`; partial cleanup
retains unresolved/unknown bytes, and full cleanup deletes the empty file.
No second cleanup-only owner round is needed within that scope. Without resolve
scope, edits, mixed disposition or deletion need their own frozen scope and
non-empty owner reply. Capture always needs separate approval. No parser
round-trip or semantic-quality guarantee is claimed.

Search before writing the proposed connection, then read back before presenting.
A search is a read; "do not update/capture" does not skip it. An instruction not
to use Open Brain at all is SKIP-openbrain, which skips both search and capture;
a search sends candidate text to the service. Extraction and pending storage
can continue under optional close staging permission or separate approval. After degraded external operations,
learning starts once all attempted local writes are read back and every
external operation is verified or recorded as pending.
