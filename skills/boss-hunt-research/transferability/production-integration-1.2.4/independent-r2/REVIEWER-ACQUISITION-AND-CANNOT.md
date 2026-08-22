# Portable Reviewer Acquisition and CANNOT Boundary

The frozen subject is `/private/tmp/bosshunt-v122-recert-clean/dossier-evidence-complete.json`; the separate request is `reviewer-output/review-pending.json`. The prepared subject hash is `sha256:b309ce14b705d1f54170df0c5aa235bd7de42d9d754f8ae913d4371281c3f395`.

## Portable task

Use one of the two mechanisms stated in the authoring guide:

1. Assign a named human who did not author the dossier; or
2. In a harness that supports isolated contexts, start a new context with no author reasoning/history and provide only the frozen dossier, the prepared request, the raw permitted evidence pack, and this task.

The reviewer must inspect `RESOURCE_COVERAGE`, `ROUTE_HONESTY`, `CURRENT_ROLE`, `HOOK_ATTRIBUTION`, `CHANNEL_SEPARATION`, and `COLLISION_LIFECYCLE`; set each to `PASS` or `FAIL` with exact evidence references; set overall `PASS` only when all six pass; add a timezone-aware `reviewed_at` and concise note; and return only the completed `BossHuntIndependentReviewV2` record. The reviewer must not edit the dossier or infer missing facts.

## CANNOT boundary tested

This clean harness supplied neither a named human nor a second isolated reviewer context. Therefore the competent user **CANNOT COMPLETE INDEPENDENT REVIEW** in this run. The correct action is to retain the frozen dossier and pending request, report `REVIEW_PENDING`, and stop. `review_record.py attach` was tested against the pending record and refused it with exit `1`; no pending record was attached. This is a documented external dependency, not a transferability documentation gap.

The separate open gap is procedural: the current documentation does not state how to bind the prepared pending record into the dossier before validation. The test used a manual copy only to verify the expected single `REVIEW_PENDING` diagnostic; that intervention is not claimed as part of the transferable workflow.
