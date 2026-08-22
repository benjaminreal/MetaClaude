# Candidate 1.2.4 Stage 2–4 Re-certification Reconciliation

Date: 2026-08-21

## Result

Candidate 1.2.4 passes Transferability Protocol Stages 2–4 for the documented
portable offline/read-only workflow. The certified ceiling includes a truthful
`REVIEW_PENDING` handoff when no different reviewer is available. Completed
independent review remains a declared conditional dependency; source truth, live
access, drafting, sending, installation, production promotion, and efficacy remain
outside this certification.

## Non-retroactive iteration ledger

| Iteration | Candidate | Independent result | Disposition |
|---|---|---|---|
| R1 | 1.2.1 | HOLD; five documentation/helper gaps | Superseded; evidence retained in `independent-r1/` |
| R2 | 1.2.2 | HOLD; missing prepare-to-pending binding | Superseded; evidence retained in `independent-r2/` |
| R3 | 1.2.3 | HOLD; Section 6 suite/fixture/setup clarity | Superseded; evidence retained in `independent-r3/` |
| R4 | 1.2.4 | PASS for documented offline/read-only scope | Current independent recommendation in `independent-r4/` |

No failed iteration was re-labeled as a later pass. Each material remediation
received a new candidate version and later independent evidence.

## Current executable evidence

- Generic skill validation: exit 0, `Skill is valid!`.
- `python3 evals/structural_eval.py`: exit 0; 38 required files, portable runtime
  docs, six named behavioral fixtures, 18 one-defect mutants, Hunter fail-closed
  states, and authoring/review helpers.
- Independent R4 spot-check: planner 0, initializer 0 with
  `INITIALIZED_INCOMPLETE`, `prepare` 0, `bind-pending` 0, validation 1 with exactly
  `REVIEW_PENDING`, and pending `attach` refused with exit 1.
- No live connectors, credits, installs, external actions, or Job Hunting mutations
  were used by the independent reviews.

## Authority boundary

Transferability PASS is not release or installation authorization. Job Hunting may
separately promote an explicitly source-pinned consumer after its own integration,
failure/resume, no-mutation, Part II entry, and production-policy checks pass.
