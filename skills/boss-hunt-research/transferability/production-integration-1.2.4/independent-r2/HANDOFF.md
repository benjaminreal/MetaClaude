# HANDOFF — BossHunt candidate 1.2.2 clean recertification

Date: 2026-08-21  
Scope: offline/read-only synthetic route research only.

## Sections certified to transfer standard

Sections 1, 2, 4, 5, and 7 passed the clean section-level test for the specific executable actions recorded in `STAGE-4-WEAKEST-SECTION-TEST.md`.

## Sections not yet certified

Sections 3 and 6 remain uncertified for the complete pending-review handoff. The missing operation is the binding of the separate `review_record.py prepare` output into the dossier's `quality_review` while preserving its canonical subject hash.

## Competent External User Definition

**Background:** A practitioner who has shipped at least one prompt-based or structured AI workflow, can use a POSIX-like CLI and Python helpers, understands JSON and versioned documentation, and has no prior Boss Hunt or transferability-certification context.

**Execution standard:** Using only the current skill, references, target, and permitted evidence, the person must be able to (1) create an isolated plan and new V3 dossier, (2) map evidence into the ordered research gates and run the local validator, and (3) prepare the independent-review request and stop at the correct authority boundary without author help.

**Failure signal:** If this user asks what to do with the prepared pending record, or manually guesses how to make the validator report the documented single `REVIEW_PENDING` state, the documentation is incomplete. The user is competent; the missing instruction is a transferability gap.

## What a competent user CAN do

- Determine read-only scope and authority limits (Section 1).
- Validate the canonical target and create a deterministic isolated search plan (Section 2).
- Initialize a deliberately incomplete shell and author a new evidence-backed V3 dossier without copying a completed fixture (Sections 2–3).
- Preserve fail-closed capability and route outcomes, including zero Hunter calls when unavailable (Section 4).
- Apply the named decision rules, exact hook fingerprints, channel invariants, and six route/edge cases (Section 5).
- Run the planner, initializer, validator, hash, fingerprint, prepare, and pending-attach commands with the exits recorded in Stage 2 (Section 6).
- Identify candidate 1.2.2 and its independent-review/release boundary (Section 7).

## What a competent user CANNOT yet do

- Produce the documented single `REVIEW_PENDING` validator state after `review_record.py prepare` without an undocumented manual copy into `quality_review` (Sections 3 and 6; open documentation/helper gap).
- Complete the six-check semantic review without either a named human reviewer or a fresh isolated reviewer context (Section 3; documented external dependency).
- Attach a still-pending review; the helper must refuse it (Section 3).
- Treat synthetic evidence, a validator pass, a channel candidate, or `DRAFT_READY_VERIFY_CHANNEL` as live source truth, deliverability, drafting approval, sending authorization, registration, installation, release, or efficacy evidence (Sections 1, 4, 6).
