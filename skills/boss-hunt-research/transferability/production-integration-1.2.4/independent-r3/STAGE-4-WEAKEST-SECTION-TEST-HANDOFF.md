# Stage 4 — Section certification, weakest-section test, and handoff

Date: 2026-08-21

## Competent External User Definition

**Background:** A practitioner who has shipped at least one prompt-based AI workflow, can use a CLI and Python, understands JSON and versioned documentation, and can distinguish read-only research from live-system actions. They have no prior Boss Hunt or transferability-review context.

**Execution standard:** Using only the current skill, references, target fixture, and permitted synthetic evidence, they can (1) build and validate an offline plan, (2) author a new V3 dossier with evidence/capability/authority bindings, and (3) prepare, bind, validate, and safely hand off an independent review without editing JSON by hand or claiming promotion.

**Failure signal:** If this user must ask which gate, route, hash, review state, or stop boundary applies—or must infer a missing fixture command—the documentation has failed. The user is competent; the missing rule or command is a documentation gap.

## Ordered section results

| Section | Certification result | Concrete action tested |
|---|---|---|
| 1. Purpose & Scope | **PASS** | Identified the synthetic request as read-only route research and preserved the explicit no-drafting/no-mutation boundary. |
| 2. Pre-flight Checklist | **PASS** | Read the required references, accepted the canonical target, built the plan (exit 0), and recorded the eight capability states. |
| 3. Core Workflow | **PASS for documented offline ceiling** | Authored a fresh dossier, ran `prepare`, ran `bind-pending`, and validated the frozen pending handoff without manual JSON intervention. |
| 4. Adaptations | **PASS** | Applied offline synthetic capability states, retained a first-party channel, and used zero Hunter calls/credits when Hunter was unavailable. |
| 5. Decision Rules | **PASS** | Six adversarial cases produced fail-closed target-authority, ordering, channel/Hunter, hook-binding, and intent-duplication outcomes. |
| 6. Eval Criteria | **OPEN — weakest** | Planner, initializer, untouched-shell, pending-review, and refusal checks were executable. The complete six-fixture behavioral suite is not named or given a portable command in the section, so the suite-level transfer claim cannot be certified. |
| 7. Version & Changelog | **PASS** | Identified candidate 1.2.3 and kept independent recertification/release as separate gates; no candidate file was edited. |

## Weakest-section cold handoff: Section 6

Questions a competent user would ask:

1. Which six route/edge fixtures are the required behavioral cases?
2. Is `evals/structural_eval.py` the complete suite or only structural coverage?
3. How can the suite be run in a fresh environment without an owner-specific harness?

The first question is an open gap; the second is only partially answered (the text says structural/behavioral, but names only the structural command); the third is bounded by the user-supplied run directory for the documented local path but not solved for a complete behavioral suite. **Explicit CANNOT addition:** a fresh user must not claim full structural/behavioral coverage or release readiness from the commands currently documented.

## HANDOFF.md-equivalent result

### Sections certified to transfer standard

Sections 1, 2, 3 (through `REVIEW_PENDING`), 4, 5, and 7 for the tested offline/read-only scope, dated 2026-08-21.

### Section not yet certified

Section 6's complete structural/behavioral-suite claim, dated 2026-08-21.

### What a competent user CAN do

- Decide whether a request is in scope and state authority boundaries (Section 1).
- Validate target intake, generate an offline plan, and record capability receipts (Section 2).
- Produce a fresh evidence-complete dossier and a hash-bound pending review handoff (Section 3).
- Apply unavailable/blocked/wrong-scope adaptations and preserve zero-Hunter limits (Section 4).
- Apply route, currentness, hook, channel, collision, and review decision rules (Section 5).
- Identify the candidate version and its separate independent-review/release ceiling (Section 7).

### What a competent user CANNOT yet do

- Reproduce a named six-fixture behavioral suite from the documented Section 6 instructions alone.
- Complete independent semantic review without a different human or truly fresh isolated reviewer context.
- Attach a pending review, claim draft-ready promotion as completed review, verify a channel, draft/send, mutate systems, install, or release.
