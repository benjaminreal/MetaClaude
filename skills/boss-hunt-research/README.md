# boss-hunt-research

**Status:** Release candidate  
**Candidate version:** 1.2.9  
**Authority:** Read-only route research and local consistency validation only

Candidate 1.2.9 preserves the independently recertified 1.2.8 research and
harness-install behavior and adds a deterministic release privacy/publication gate.
The gate scans the entire publishable source for owner-local paths, non-synthetic
emails, credential material, binary files, and—when requested—files absent from the
Git index. The canonical source remains one package, while
`scripts/build_harness_install.py` derives a one-entry Codex tree and a Claude Code
tree that retains the nested `skills-dir` loader. Source, Codex, and Claude trees
are recorded independently rather than assumed hash-identical.

This skill produces an evidence-backed candidate-route dossier without forcing a hiring-manager name. The canonical input is `BossHuntTargetV2`; the current output is `BossHuntResearchDossierV3`. The preserved V2 schema and frozen pilot remain history and are never silently reinterpreted.

The planner and validator are offline. They do not fetch pages, open authenticated sessions, call Hunter, verify an inbox, establish source truth, draft outreach, authorize contact, send messages, install the skill, or mutate Job Hunting, Tasks, LinkedIn, Gmail, or Hunter state.

## Key files

- `SKILL.md`: concise routing and seven-function transfer documentation
- `.claude-plugin/plugin.json`: Claude Code plugin identity; the root `SKILL.md` remains the single portable skill
- `skills/boss-hunt-research/SKILL.md`: minimal Claude `skills-dir` loader that delegates to the canonical root skill
- `references/process.md`: executable ordered workflow
- `references/authoring-guide.md`: initialize, capture/hash, serialize, review, and validate a new dossier
- `references/dependency-capability-contract.md`: six-state capability map and fail-closed results
- `references/harness-tool-discovery.md`: Codex/Claude Code inventories, aliases, setup boundary, and browser-selection rules
- `scripts/check_session_tools.py`: no-call cross-harness tool/skill inventory classifier
- `scripts/build_harness_install.py`: deterministic Codex/Claude Code install-tree builder and duplicate-discovery guard
- `scripts/release_privacy_scan.py`: offline privacy, secret, and Git publication-surface gate
- `references/release-privacy.md`: release scan scope, command, limitations, and review boundary
- `INSTALL-METADATA.json`: generated only inside derived installs; selects the harness-aware evaluation mode and binds the canonical source identity
- `references/dossier-contract.md`: V3 fields, hashes, review binding, and compatibility
- `references/hook-exhaustion.md`: structured intent fingerprints and evidence binding
- `references/bosshunt_target_v2.schema.json`: canonical input contract
- `references/bosshunt_dossier_v3.schema.json`: current dossier contract
- `references/bosshunt_dossier_v2.schema.json`: preserved historical contract
- `scripts/build_search_plan.py`: deterministic offline planner
- `scripts/validate_dossier.py`: structural-first, dependency-free V3 validator
- `scripts/init_dossier.py`, `hash_evidence.py`, `intent_fingerprint.py`, and `review_record.py`: non-promotable initialization, exact representation/fingerprint hashing, and independent-review handoff
- `evals/`: synthetic fixtures, mutants, and behavior suite
- `transferability/`: five-stage evidence and handoff artifacts

## Portable local verification

Set `BOSSHUNT_RUN_DIR` to a user-supplied isolated directory that already exists. The commands below use only skill-relative paths:

```bash
python3 evals/structural_eval.py
python3 scripts/release_privacy_scan.py
python3 scripts/build_search_plan.py evals/fixtures/target.json --output "${BOSSHUNT_RUN_DIR}/search-plan.json"
python3 scripts/validate_dossier.py evals/fixtures/valid_dossier.json
python3 scripts/validate_dossier.py evals/fixtures/invalid_apex_dossier.json
```

The first command runs from either the canonical source or a derived install and
includes the privacy gate. In source mode it additionally builds and checks both
harness packages; in an installed tree it uses generated `INSTALL-METADATA.json`
and retains the complete runtime suite without requiring files intentionally
excluded for another harness. The last command intentionally fails with
`LEGACY_SCHEMA_REFUSED`, proving that the historical V2 fixture is not
reinterpreted as V3. Green local tests establish only mechanics and internal
consistency—not live evidence truth, deliverability, efficacy, production
readiness, installation approval, or release authorization.

Maintainers preparing installation or release should additionally run the generic skill validator discoverable in their current harness, when available. That harness-owned check is separate from the portable runtime workflow and no machine-specific validator path is part of this skill's user instructions.
