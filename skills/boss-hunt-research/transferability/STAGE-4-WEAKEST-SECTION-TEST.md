# Stage 4 Weakest-Section Cold Handoff and Re-certification

**Date:** 2026-08-21  
**Original weakest section:** Section 4, Adaptations  
**Weakest changed section for candidate 1.1.1:** Section 6, Eval Criteria

## Scenario

Hunter account details are `AVAILABLE`, Email Finder is `WRONG_SCOPE`, and Domain Search is `UNAUTHENTICATED`. The first-party email lane returned `MISS`. Could a competent user infer that the working account receipt upgrades either discovery method?

## Finding and patch

Before the test, the section said any Hunter capability not available means zero calls/credits, but it did not explicitly rule out inheritance from a parent/account capability. A reader could choose the wrong method despite the capability table.

Section 4 was patched: method-specific state controls, and a parent receipt never upgrades a child method. The correct result is zero Hunter calls/credits plus the documented fallback or blocker. This patch also clarifies the novel mixed-capability edge case used in Stage 5.

## Result

Pass after patch. The section now produces one deterministic action without an author question.

## Candidate 1.1.1 re-certification scenario

A competent external user receives the candidate on a machine without the author's home directory or Codex harness layout. Can they execute Section 6 and the onboarding workflow using only the skill?

## Re-certification finding and patch

No. Candidate 1.1.0 hard-coded an owner-machine generic-validator path and platform-specific scratch paths. The user would stall before reaching the skill's own suite. Section 6, the README, operational references, HANDOFF, and Onboarding Section 4 were patched to use skill-relative commands plus a user-supplied isolated directory. Generic skill validation is now a harness-discoverable maintainer/release check, not a certified runtime dependency. The structural suite now rejects owner/platform-specific absolute paths and `quick_validate.py` references in certified runtime documentation.

## Re-certification result

Pass after patch. A user meeting the Competent External User Definition can run the certified suite without the author's filesystem. Sections 6–7 and Onboarding Section 4 were re-certified in order. Historical exact commands remain evidence only in final-verification records.
