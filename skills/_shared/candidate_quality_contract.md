# Learning candidate quality contract

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
   missing context.
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
