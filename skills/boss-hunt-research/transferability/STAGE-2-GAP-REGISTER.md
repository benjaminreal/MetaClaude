# Stage 2 Independent Stress Test Gap Register

**Tester:** fresh-context `gpt-5.6-terra` independent agent  
**Initial artifact:** candidate 1.0.0  
**Initial test:** 2026-08-21  
**Patched artifact:** candidate 1.1.0  
**Rerun:** 2026-08-21

The tester received only the skill directory, Transferability Protocol, canonical synthetic target, and permitted synthetic evidence. It received no remediation plan, suspected defects, intended answers, or prior conclusions and made no external call or project edit.

| # | Cold-user gap | Responsible section | Patch | Rerun |
|---:|---|---|---|---|
| 1 | No end-to-end procedure to create and validate a new dossier; fixture reuse could silently masquerade as a new run. | Pre-flight, Core Workflow, process, dossier contract | Added `authoring-guide.md`, `init_dossier.py`, explicit non-promotable placeholders, and new-file validation commands. | Resolved |
| 2 | Narrative guard facts could not be converted into five scoped, fresh, hashed receipts without guessing. | Pre-flight, Decision Rules, authoring guide | Added observed-fact mapping, exact receipt fields, 24-hour freshness, scoped snapshot reuse rule, and evidence hash helper. | Resolved |
| 3 | The two-source current-title requirement lacked an executable capture/hash/independence procedure. | Core Workflow, source policy, authoring guide | Added per-source captured-representation/hash rules, concrete independence-key examples, and distinction between authenticated-gate and draft-readiness thresholds. | Resolved |
| 4 | No acquisition/construction procedure existed for a separate independent hash-bound review. | Core Workflow, Eval, authoring guide | Added `review_record.py prepare/attach`, frozen-subject rule, reviewer independence, six-check template, evidence references, and post-attach validation. | Resolved |

Initial evidence: `/private/tmp/bosshunt-cold-handoff.9kKyi2/COLD_HANDOFF_REPORT.md`. Patched rerun evidence: `/private/tmp/bosshunt-cold-handoff-rerun.LPbJ41/COLD_HANDOFF_RERUN.md`.

The rerun exercised plan generation, initializer, text/JSON evidence hashing, intentional non-promotability, review request generation, structural eval, and valid V3 validation. All four gaps were resolved sufficiently to continue without author intervention. The remaining requirement for a different reviewer is an explicit independence boundary, not a documentation gap.

Candidate 1.0.0 did not pass retroactively. Candidate 1.1.0 is the patched Stage 2 artifact; current candidate 1.1.1 inherits it and adds the separately evidenced portability correction.
