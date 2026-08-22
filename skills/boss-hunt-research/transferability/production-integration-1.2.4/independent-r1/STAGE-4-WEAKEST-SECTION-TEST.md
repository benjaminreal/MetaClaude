# Stage 4 Weakest-Section Test

Weakest section selected: **Section 3 — Core Workflow**.

## Cold read

The section gives a correct ordered list and links the detailed process, authoring guide, and hook-exhaustion rules. A competent user can run the planner, initialize a dossier, hash evidence, and prepare/attach a review record. The following questions remained when the synthetic pack was used without author intervention:

1. How is a separate human or fresh-context reviewer obtained or invoked in this offline handoff?
2. What exact evidence-pack statement maps to each required dossier receipt/ledger field when authoring a new dossier rather than inspecting the completed fixture?
3. What observable event changes the workflow from “review request prepared” to “independent review complete,” and who is authorized to perform that change?

The second and third questions are not blockers to preparing a request, but the first is a blocker to completing the reviewed workflow. The documentation does provide the exact `review_record.py prepare` and `attach` commands; it does not provide a reviewer source or a way to complete the six checks in the cold handoff.

## Required Stage 4 disposition

This simulation did not survive unchanged. Because the skill was not edited, I recorded an explicit CANNOT boundary in the independent handoff rather than pretending the gap was patched:

> A competent offline user **CANNOT claim a completed reviewed or draft-ready dossier** until a separate human or fresh-context reviewer has returned a completed six-check `BossHuntIndependentReviewV2` record whose subject hash matches the frozen dossier.

This is a documentation boundary, not an inference about live sources. It is tied to Section 3 and prevents a pending review from being mistaken for certification.
