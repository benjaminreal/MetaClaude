# Boss Hunt Research — Colleague Onboarding Protocol

**Candidate:** 1.2.9  
**Date:** 2026-08-22  
**Scope:** one complete offline, read-only V3 research workflow

## 1. Description

Boss Hunt Research converts one exact job/company target and current evidence into an honest candidate-route dossier. It finds the strongest defensible hiring-manager, recruiter, sponsor, colleague, connector, or no-safe-route ceiling; it never forces a person. Use it to make research reproducible and fail closed before any drafting or outreach. It plans and validates locally but does not acquire live evidence, verify delivery, contact anyone, or mutate systems.

[Onboarding Section 1 certified — 2026-08-21 — colleague can: explain the workflow's purpose and stop boundary in plain language.]

## 2. Target user

The colleague can run CLI commands, edit JSON, interpret schema errors, distinguish evidence from inference, and work within explicit authority. They understand basic hiring-role/recruiter concepts and SHA-256 evidence binding. They need no prior repository, Boss Hunt, Hunter, or transferability-certification experience.

[Onboarding Section 2 certified — 2026-08-21 — colleague can: determine whether they meet the defined competence threshold without author judgment.]

## 3. Entry requirements

Before starting, the colleague must have:

- the candidate skill directory and local Python;
- one no-call Codex or Claude Code session inventory report covering external Chrome, the harness internal-browser alternative, and Hunter exposure;
- one `BossHuntTargetV2` with current local authority, owner scope, hypotheses, and all capability receipts;
- permission to inspect each supplied local/public/authenticated evidence surface;
- an isolated output directory;
- a different human or fresh-context reviewer available for the final six-check review.

If any item is absent, apply the capability result or stop; do not fabricate a receipt.

[Onboarding Section 3 certified — 2026-08-21 — colleague can: screen prerequisites and identify the first unavailable dependency.]

## 4. Workflow execution guide

1. Read `SKILL.md` and its routed operational references, including `harness-tool-discovery.md` and `authoring-guide.md`.
2. Run `python3 evals/structural_eval.py` from the skill root. Generic skill validation is a separate maintainer/release check only when the current harness exposes it.
3. Validate the target by generating `BossHuntSearchPlanV2` with `build_search_plan.py`.
4. Create a user-supplied isolated run directory, set `BOSSHUNT_RUN_DIR` to it using syntax appropriate to the current shell, and initialize a new dossier with `init_dossier.py`; never reuse the completed valid fixture as evidence.
5. Capture the exact local representation used for each authority, guard, currentness, hook, proof, query, and limitation; hash it with `hash_evidence.py`.
6. Populate five current guard receipts and derive the overall guard state.
7. Execute the plan order: literal seat before alternatives; named route before currentness; currentness before hook/proof; bounded first-party email before any Hunter method.
8. Capture two independent current-title/employer sources for draft readiness. Compute each structured hook fingerprint with `intent_fingerprint.py` and bind the selected intent exactly.
9. Populate channel, decision, limitations, disconfirmers, and owner summary. Run `validate_dossier.py`; repair only from evidence or lower the readiness ceiling.
10. Freeze the subject, prepare a review with `review_record.py`, give dossier/evidence/request to a different reviewer, attach the returned record, and validate again.
11. Return the dossier and owner summary. Stop before drafting, channel verification, sending, registration, installation, or release.

[Onboarding Section 4 independently re-certified — 2026-08-22 — candidate 1.2.8 preserves Claude Code skills-dir discovery while requiring a derived one-entry Codex install; the no-call browser/Hunter preflight and portable workflow remain unchanged.]

## 5. Decision rules for ambiguous cases

- If local authority is not `AVAILABLE`, then `BLOCKED` before any web research.
- If authenticated-profile state is unavailable, unauthenticated, wrong-scope, or blocked for a named route, then `PROFILE_CHECK` and zero Hunter calls/credits.
- If `AUTO` is used, prefer exposed external Chrome and fall back to an exposed harness internal browser; if the owner explicitly chose one, do not silently use the other or switch to bypass access controls.
- If Hunter account details are available but the chosen method is not, then the method-specific state controls; do not infer inherited access.
- If literal seat is `MISS`, then preserve the miss and use only an honestly labeled recruiter/sponsor/colleague/connector/apex ceiling.
- If two sources reproduce the same underlying biography, then give them one independence key and count them once.
- If the selected hook differs from its intent on ID, URL, content hash, or run, then reject it rather than relabeling evidence.
- If another search lacks named expected value, then stop with the honest boundary.

[Onboarding Section 5 certified — 2026-08-21 — colleague can: resolve the common ambiguous branches from observable state.]

## 6. Self-check rubric

1. Did every load-bearing claim trace to a current-run representation, hash, and exact scope?
2. Could Hunter occur only after guards, route, currentness, hook/proof, and first-party miss/block—and did unavailable methods use zero credits?
3. Does the selected hook exactly match one unique structured intent and captured content?
4. Does draft readiness include a real channel/address, two independent currentness sources, supported candidate proof, and a hash-bound independent review?
5. Does the owner summary state the weakest assumption and avoid any live truth, action, efficacy, or release overclaim?

[Onboarding Section 6 certified — 2026-08-21 — colleague can: detect the most consequential silent failures before handoff.]

## 7. Known failure modes and remedies

| Failure mode | Remedy |
|---|---|
| Copying the valid fixture and changing names | Initialize a new dossier; capture/hashes/run IDs must come from the current run. |
| Marking guards clear from memory | Create five current scoped receipts; otherwise use `UNKNOWN` and lower readiness. |
| Counting rephrased searches as separate hook intents | Use structured signatures and computed fingerprints; duplicate fingerprints fail. |
| Treating a profile plus copied bio as two independent sources | Share one independence key and obtain a separately maintained source. |
| Treating Hunter score/status as verified delivery | Keep Hunter at `VERIFY_CHANNEL`; live verification is a separate gate. |
| Treating skill loading as Claude Code tool provisioning | Record the missing provider; Claude MCP/plugin setup and credentials are separate owner-authorized dependencies. |
| Editing the dossier after independent review | Discard the stale review, recompute the subject hash, and rerun independent review. |

[Onboarding Section 7 certified — 2026-08-21 — colleague can: recognize and recover from six likely first-run failures.]
