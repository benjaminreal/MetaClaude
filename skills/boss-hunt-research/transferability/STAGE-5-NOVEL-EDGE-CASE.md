# Stage 5 Novel Edge-Case Stress Test

**Date:** 2026-08-21  
**Scenario:** Mixed nested capabilities not represented by the historical pilot edge set

Hunter account details are `AVAILABLE`, Email Finder is `WRONG_SCOPE`, and Domain Search is `UNAUTHENTICATED`; the bounded first-party lane returned `MISS`.

## Walkthrough

The onboarding entry requirements preserve each method receipt independently. Decision Rule 3 says the selected method's state controls; an available account does not inheritably authorize Finder or Domain Search. The workflow therefore records both method limitations, uses zero connector calls/search/verification credits, and retains a professional-platform/recruiter fallback only if its own evidence and route gates pass. Otherwise it returns `RESEARCH_MORE` or `BLOCKED` with the capability cause.

## Result and patch

The pre-test Adaptations section could be read as relying only on the aggregate account capability. It was patched, and the same explicit mixed-state rule was added to Onboarding Section 5.

## Transferable design principle

Capability is leaf-specific: availability of a parent account or neighboring method never upgrades the selected operation. New connector methods must add their own receipt, unavailable result, budget, ordering gate, mutant, and section re-certification.
