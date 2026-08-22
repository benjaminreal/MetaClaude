# Stage 4 Weakest-Section Test — 2026-08-21

## Weakest section: Section 3 — Core Workflow

Cold-handoff questions a competent user could ask:

1. After `review_record.py prepare` returns a pending request, what exact documented command binds that request to the dossier's `quality_review`?
2. Should the dossier be edited while the review is pending, given the instruction to freeze the completed dossier subject?
3. What should validation return before a reviewer is available?

Observed result: the prepare command creates a separate record and exits `0`. Validating the unchanged dossier returned two diagnostics (`REVIEW_PENDING` and `REVIEW_HASH_MISMATCH`). The documented single `REVIEW_PENDING` state was obtained only after a manual intervention: copying the prepared record into `quality_review`. `review_record.py attach` correctly refuses that still-pending record with exit `1`.

No skill patch was made because this recertification is read-only with respect to the skill. The exact gap is added to the CANNOT boundary below. This is the required Stage 4 weakest-section change: an explicit CANNOT addition rather than silently filling the gap with author knowledge.

## Section-level certification record

- **Section 1 — Purpose & Scope:** certified for deciding that the task is read-only Boss Hunt research and naming the non-authorizing boundaries.
- **Section 2 — Pre-flight Checklist:** certified for reading the required references, validating `BossHuntTargetV2`, creating the isolated plan, and recording capability limits.
- **Section 3 — Core Workflow:** **not certified** for the complete pre-review handoff; the pending-record binding action is undocumented.
- **Section 4 — Adaptations:** certified for fail-closed behavior across unavailable Hunter, closed-posting, literal-seat miss, V2 refusal, and synthetic/offline conditions.
- **Section 5 — Decision Rules:** certified for deriving route/readiness outcomes and preserving `NOT_PUBLIC`, `PROFILE_CHECK`, `OWNER_DECISION`, `RESEARCH_MORE`, and `BLOCKED` boundaries.
- **Section 6 — Eval Criteria:** **not certified** for the exact pre-review single-diagnostic expectation until pending binding is documented or implemented.
- **Section 7 — Version & Changelog:** certified for identifying candidate 1.2.2, superseded versions, and the separate independent-review/release gates.
