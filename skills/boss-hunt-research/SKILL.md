---
name: boss-hunt-research
description: Resolve evidence-backed candidate routes for an exact job or target company. Use for read-only hiring-manager, recruiter, sponsor, colleague, warm-connector, currentness, hook, or channel-hypothesis research; not for drafting, sending, inbox verification, live-system mutation, or outreach efficacy claims.
---

# Boss Hunt Research

## 1. Purpose & Scope

Produce a `BossHuntResearchDossierV3` at the strongest honest evidence ceiling. A result may be a confirmed/likely role owner, recruiter, sponsor, colleague, connector, apex/context route, `NOT_PUBLIC`, or `NO_SAFE_ROUTE`. Never force a hiring-manager name.

This skill is read-only research plus offline planning/validation. It does not draft outreach, contact anyone, open Gmail bodies without explicit permission, call live services without separate authorization, spend verification credits, mutate LinkedIn/Hunter/Gmail/trackers/Tasks, install itself, or authorize release. A dossier pass is not source truth, channel verification, drafting approval, sending authority, registration, or efficacy evidence.

[Section 1 certified — 2026-08-21 — competent user can: decide whether a request belongs to read-only Boss Hunt research and name every authority boundary before acting.]

## 2. Pre-flight Checklist

Before research:

1. Read [the process](references/process.md), [authoring guide](references/authoring-guide.md), [capability contract](references/dependency-capability-contract.md), [harness tool discovery](references/harness-tool-discovery.md), [source policy](references/source-policy.md), [dossier contract](references/dossier-contract.md), and [hook exhaustion rules](references/hook-exhaustion.md).
2. Validate one canonical `BossHuntTargetV2`; use `null` for absent optional fields and never translate `tracker_id` implicitly.
3. Bind current local role/lifecycle authority and owner scope.
4. Before any live operation, inspect the current session's tool and skill inventory
   without calling an external service. Use `scripts/check_session_tools.py` to
   classify Codex or Claude Code inventories, both authenticated-profile choices
   (external Chrome and the harness internal browser), and the three preferred
   Hunter operations. Tool exposure is not authentication, permission, account
   scope, or a live `AVAILABLE` capability receipt.
5. Record all eight capability receipts using the six named states.
6. Stop if identity/authority is missing, a guard cannot be evidenced, or the requested action exceeds read-only research.

Create the offline plan from the skill root. Set `BOSSHUNT_RUN_DIR` to a user-supplied isolated output directory that already exists; the examples use POSIX shell variable syntax, so use the equivalent path syntax in another shell:

```bash
python3 scripts/build_search_plan.py evals/fixtures/target.json --output "${BOSSHUNT_RUN_DIR}/search-plan.json"
```

For example, POSIX shell can use `export BOSSHUNT_RUN_DIR=/path/to/isolated-run`;
PowerShell can use `$env:BOSSHUNT_RUN_DIR = "C:\path\to\isolated-run"`. Create
that directory first in the current shell/environment.

[Section 2 independently re-certified — 2026-08-22 — candidate 1.2.8 builds a harness-specific Codex tree with one discoverable canonical skill and a separate Claude Code tree that preserves the delegating skills-dir loader; the cross-harness preflight and every intake/stop boundary remain unchanged.]

## 3. Core Workflow

Execute the generated order without skipping gates:

1. validate target authority;
2. evidence all five global guards;
3. freeze reporting hypotheses before names;
4. map employer, literal seat, alternatives, search owner, and adjacent routes;
5. bind one serialized authenticated-currentness observation to capability, identity, target, evidence, and freshness;
6. resolve an exact hook and candidate proof;
7. deduplicate structured intents and bind the selected hook's intent/URL/content hash/run;
8. run the bounded first-party email lane;
9. only then consider one Hunter discovery method when every Hunter precondition and capability receipt passes;
10. validate structurally, then by policy; obtain hash-bound per-check independent review; return one readiness label and owner summary.

Independent review is a real external dependency. Use a named human reviewer or,
when the current harness supports it, a newly isolated context that receives only
the frozen dossier, prepared review record, raw evidence, and the six-check task in
the authoring guide. The researcher cannot complete their own review. If neither
reviewer mechanism is available, stop truthfully at `REVIEW_PENDING`; do not attach
the pending record or claim a completed/draft-ready workflow.

Initialize and author a new dossier with [authoring-guide.md](references/authoring-guide.md); never treat the completed valid fixture as evidence. Detailed stop rules and route ceilings are in [process.md](references/process.md). Hook exhaustion is in [hook-exhaustion.md](references/hook-exhaustion.md).

[Section 3 re-certified — 2026-08-21 — candidate 1.2.4 maps captured evidence into a new dossier, binds the prepared pending review without manual JSON intervention, executes every ordered gate, and either obtains a different reviewer or stops explicitly at the conditional dependency.]

## 4. Adaptations

- If authenticated-profile capability is unavailable, unauthenticated, wrong-scope, or blocked, return `PROFILE_CHECK` for a named route; do not use Hunter.
- If a preferred tool is not exposed, record that in the session tool report and
  use the existing non-available capability path. Never infer authentication or
  `AVAILABLE` merely because a tool name is exposed.
- If `AUTO` is used, prefer exposed external Chrome and use an exposed harness
  internal browser when Chrome is absent. Honor an explicit browser choice without
  silent substitution, and never switch surfaces to bypass authentication or
  access controls.
- If any Hunter capability is not `AVAILABLE`, use zero Hunter calls/credits and retain the documented first-party/platform/recruiter fallback or blocker.
- If a parent capability is `AVAILABLE` but a selected method is not (for example account details available and Finder wrong-scope), the method-specific state controls; a parent receipt never upgrades a child method.
- If a posting is closed after application, record closure but keep relationship research available unless another guard stops it.
- If the literal seat is a miss, retain `MISS` and route honestly; never substitute apex as hiring manager.
- If evidence lacks stable page bytes, hash the canonical captured representation and name it; never invent a content hash.
- If an earlier gate stops before candidate-proof evaluation, use `NOT_EVALUATED` with null evidence fields and a reason; it is forbidden at draft readiness.
- If given V2, return `LEGACY_SCHEMA_REFUSED`; do not rewrite, re-hash, or reinterpret frozen history.

[Section 4 locally verified — 2026-08-21 — candidate 1.2.6 adds explicit fail-closed browser selection and Claude Code aliases while preserving the exposure-versus-availability boundary and every prior adaptation; independent re-certification remains separate.]

## 5. Decision Rules

- If target identity or local authority is missing, then `BLOCKED` before web research.
- If a required guard lacks a current receipt, then it cannot be `CLEAR`.
- If a named route lacks current capability-backed authenticated evidence through review, then `PROFILE_CHECK`.
- If the hook and selected intent differ on ID, URL, content hash, or run ID, then fail `HOOK_EVIDENCE_MISMATCH`.
- If two intents share a structured-signature fingerprint, then neither duplicate can manufacture exhaustion.
- If `channel.kind=NONE`, then draft readiness must fail.
- If Hunter supplied the address, then channel state is at most `VERIFY_CHANNEL`.
- If `CONFIRMED_HM`, then requisition linkage must be explicit.
- If another bounded search lacks named expected value, then stop and preserve `NOT STATED ON SOURCE`, `NOT_PUBLIC`, or `UNREADABLE`.

[Section 5 certified — 2026-08-21 — competent user can: decide promotion versus PROFILE_CHECK, OWNER_DECISION, RESEARCH_MORE, or BLOCKED from observable fields.]

## 6. Eval Criteria

Run:

```bash
python3 evals/structural_eval.py
python3 scripts/release_privacy_scan.py
python3 scripts/init_dossier.py evals/fixtures/target.json --run-id run-example --researcher-id researcher-example --output "${BOSSHUNT_RUN_DIR}/dossier.json"
python3 scripts/validate_dossier.py evals/fixtures/valid_dossier.json
```

`python3 evals/structural_eval.py` is the single complete portable
structural-plus-behavioral suite command in the canonical source and either
derived harness install. `INSTALL-METADATA.json` selects the installed-tree mode:
all modes run the complete runtime workflow tests, while canonical-source mode
also builds and validates both harness packages and installer refusal cases. A
Codex install therefore does not falsely require its intentionally excluded
Claude-only loader. The suite also runs the offline privacy/secret gate documented
in [release-privacy.md](references/release-privacy.md). Maintainers must additionally
use `--require-git-tracked` on the staged publication surface. The suite runs these
six named route/edge
fixtures: `valid_literal_seat_hit`, `literal_seat_miss`, `generic_fallback`,
`recruiter_route`, `stale_person`, and `company_collision`. It also runs one-defect
mutants for target authority, ordering, channel, Hunter verification, hook binding,
intent duplication, guard evidence, authenticated currentness, structure, review
hash, review prepare/bind/attach boundaries, runtime-document portability, and
no-call Codex/Claude Code tool discovery with external Chrome/internal-browser
selection.
Success for the certified user workflow requires that complete suite, dossier
initialization in the user-supplied isolated directory, and the valid V3 fixture to
pass.

Create the isolated directory and set `BOSSHUNT_RUN_DIR` before running this section.
Expected command semantics are: planner `0` creates a plan; initializer `0` plus
`INITIALIZED_INCOMPLETE` creates a non-promotable authoring shell; validating that
untouched shell returns `1`; an evidence-complete dossier waiting for review returns
`1` with exactly `REVIEW_PENDING`; the structural suite and completed clean dossier
return `0`; attaching a still-pending review is refused.

The certified portable offline ceiling includes a correct stop and handoff at
`REVIEW_PENDING` when no different reviewer is available. Completed independent
review is a declared conditional dependency, not a capability the researcher may
simulate; certification never asserts that every harness supplies it.

A maintainer preparing installation or release should also run the generic skill validator exposed by that maintainer's current harness, if one is discoverable there. Its harness-owned location is not a runtime dependency and is not part of the competent external user's certified workflow.

These tests do not establish live source truth, identity correctness, inbox existence, deliverability, response/screen efficacy, production readiness, installation, or release.

[Section 6 release delta locally verified — 2026-08-22 — candidate 1.2.9 adds a complete-tree privacy/secret gate and Git publication-surface check while preserving candidate 1.2.8's independently re-certified research workflow, harness builds, and conditional-reviewer ceiling.]

## 7. Version & Changelog

**Candidate 1.2.9 — 2026-08-22 — privacy and Git publication hardening.**
Preserves candidate 1.2.8's independently re-certified research and harness-install
behavior. Adds `scripts/release_privacy_scan.py`, a portable release gate covering
owner-local paths, non-synthetic email domains, credential/private-key patterns,
binary publication files, and optional Git-index completeness. Public historical
evidence now uses named portable roots instead of owner-machine paths. The complete
source and installed-tree suites exercise the gate and three new privacy mutants.
This delta adds no research, live-access, Hunter, drafting, send, registration, or
mutation authority.

**Candidate 1.2.8 — 2026-08-22 — harness-specific install remediation.** Adds
`scripts/build_harness_install.py` so a Codex install deterministically excludes
the Claude-only nested loader and exposes exactly one canonical `SKILL.md` with
its root `agents/openai.yaml`, while a Claude Code install preserves the full
package and delegating `skills-dir` loader. The canonical-source suite now builds
both trees, rejects duplicate Codex discovery, and tests fail-clean manifest
handling; each installed tree runs the same command in its declared harness mode.
Source and harness installs have separate recorded hashes and file counts; byte
parity is no longer claimed.
The first frozen 1.2.8 attempt failed independent Stage 3 because its evaluator
still required the intentionally excluded Claude loader in the Codex tree and its
external-manifest handling was not fail-clean. This remediated build makes the
evaluator harness-aware, adds generated install metadata, refuses derived sources
and embedded/pre-existing manifests before finalization, and passes all three tree
modes locally. Fresh independent Stage 2–4 re-certification passed for this
remediated behavior; release remains a separate gate.

**Candidate 1.2.7 — 2026-08-21 — Claude skills-dir loader build.** Adds one
minimal nested Claude Code skill component that delegates immediately to the
canonical root `SKILL.md`. This closes the observed gap where explicit
`--plugin-dir` loading found the root skill but the global `skills-dir` plugin
inventory found zero skills. The plugin manifest, portable suite, Codex validator,
Claude strict validator, global Claude component inventory, and installed-tree
hash parity are locally verified. It does not bundle MCP servers or change the
research workflow; independent re-certification remains pending.

**Candidate 1.2.6 — 2026-08-21 — cross-harness browser-selection build.** Keeps
portable Agent Skill frontmatter, adds a strict-valid Claude Code plugin manifest,
treats `agents/openai.yaml` as a Codex-only
dependency optimization, recognizes Claude in Chrome and harness-neutral Hunter
operation names, and adds the harness internal browser as an explicit authenticated-
profile alternative. `AUTO` prefers external Chrome and falls back to an exposed
internal browser; explicit choices are never silently substituted. The new
`BossHuntSessionToolAvailabilityV2` report still makes zero calls and proves no
authentication, account scope, permission, credit, or live `AVAILABLE` state. The
increment is locally validated; candidate 1.2.4 remains the last independently
Stage 2–4 re-certified build.

**Candidate 1.2.5 — 2026-08-21 — session-tool-discovery build.** Declares the
Hunter connector provider and Chrome runtime as session dependencies, identifies
the exact preferred Hunter operations and Chrome authenticated-profile surface,
and adds a no-call inventory report that distinguishes `EXPOSED` from live
capability `AVAILABLE`. It makes no authentication, account-scope, credit, or live
access claim. The incremental change is locally validated; candidate 1.2.4 remains
the last independently Stage 2–4 re-certified build until a fresh review of 1.2.5.

**Candidate 1.2.4 — 2026-08-21 — unreleased transferability-remediation build.** Preserves 1.2.3 and names the complete portable suite command plus all six fixtures, adds concrete POSIX/PowerShell isolated-directory setup, and defines the safe pending-review handoff as the certified ceiling when the declared reviewer dependency is unavailable. All seven sections are re-certified for the documented offline/read-only workflow; independent reconciliation and release remain separate gates.

**Candidate 1.2.3 — 2026-08-21 — superseded after final clean-context Stage 2 test.** Added `bind-pending`; the rerun confirmed the path and exposed only Section 6 naming/setup/conditional-dependency clarity gaps. Its partial result does not transfer retroactively to 1.2.4.

**Candidate 1.2.2 — 2026-08-21 — superseded after clean-context Stage 2 test.** Remediated 1.2.1's five gaps, but the clean rerun found the missing prepare-to-pending binding operation. Its partial result does not transfer retroactively to 1.2.3.

**Candidate 1.2.1 — 2026-08-21 — superseded after independent Stage 2 test.** Preserved the 1.2.0 pending-review and `NOT_EVALUATED` corrections, permitted a draft-ready subject to wait at the single `REVIEW_PENDING` gate without false freshness/readiness findings, and added explicit completed-review failure diagnostics. The cold test exposed five documentation/helper gaps.

**Candidate 1.2.0 — 2026-08-21 — superseded before re-certification.** Replaced repeated false `GUARD_RECEIPT_STALE` messages during pending review with one `REVIEW_PENDING` diagnostic and deferred guard-age evaluation until a completed review time exists. Added constrained `NOT_EVALUATED` candidate proof for early-stop, non-draft dossiers.

**Candidate 1.1.1 — 2026-08-21 — superseded as current build; last Stage-5-certified candidate.** Removed an owner-machine validator path from the certified workflow, replaced platform-specific scratch paths with a user-supplied isolated run directory, moved generic skill validation to a harness-discoverable maintainer/release check, added a portability regression, and re-certified Sections 6–7 plus affected Stage 5 documentation. Corrected the backlog to state that no migration adapter is present and aligned the Hunter budget wording with the implemented contract.

**Candidate 1.1.0 — 2026-08-21 — superseded after portability review.** Patched four independent cold-handoff gaps with an executable dossier initializer, exact evidence/fingerprint hashing, end-to-end authoring guide, guard/currentness serialization rules, and prepare/attach independent-review workflow. Rerun resolved all four gaps, but its certified Eval Criteria still relied on an owner-specific validator path.

**Candidate 1.0.0 — 2026-08-21 — superseded after Stage 2 test.** Introduced canonical `BossHuntTargetV2`, explicit capabilities, ordered gates, `BossHuntResearchDossierV3`, structural-first validation, channel invariants, exact hook binding, structured intent fingerprints, guard/currentness receipts, candidate proof, limitations/owner summary, and hash-bound review. Preserved the V2 schema and added explicit V2 refusal. It exposed four documented cold-handoff gaps and did not pass retroactively.

Candidate 1.2.9 is the release candidate. Its research and harness behavior inherit
no new claims beyond candidate 1.2.8's independent Stage 2–4 recertification; the
1.2.9 release delta requires its own privacy, clean-checkout, installed-tree, and
production-pin evidence.

[Section 7 release delta locally verified — 2026-08-22 — competent user can identify candidate 1.2.9's bounded release-hardening scope, preserve candidate 1.2.8's independent evidence and failed first attempt as history, and keep live-operation gates non-retroactive.]
