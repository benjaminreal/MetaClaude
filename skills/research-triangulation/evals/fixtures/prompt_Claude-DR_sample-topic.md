You are a senior research analyst conducting deep research on Sample Topic for Eval Fixtures.

# Research Brief: Sample Topic for Eval Fixtures

## Context
This is a synthetic research brief used only as a structural eval fixture. It is
not intended to produce actual research output. Its purpose is to provide a
realistic Phase 1 prompt file that can be validated against the skill's filename
and structural conventions.

## Primary Research Question
What structural properties should a Phase 1 prompt file have so that it is
trivially validatable by automated checks?

## Secondary Research Questions
1. Which metadata fields are strictly required on the downstream report?
2. Which filename components carry information used by consolidation?
3. Where does platform-pass independence need to be preserved end-to-end?

## Scope Boundaries
- **Time window**: Not applicable — fixture only.
- **Geography**: Not applicable.
- **Inclusions**: None specified.
- **Exclusions**: None specified.

## What We Already Know (Do Not Repeat)
The skill already documents its conventions in phase1-templates.md. This fixture
exists to verify that a generated prompt file follows them.

## Source Requirements
Not applicable — this is a structural fixture, not a research prompt.

## Evidence Standards
- Every cited source must include author(s), year, venue/publisher, and DOI or stable URL.
- If any field is missing, report the gap rather than fabricating.
- Apply the aspiration vs. demonstration distinction to every claim.

## Output Format

Produce your output as a single, self-contained markdown document. Begin with the
YAML metadata header, then follow the section order below exactly.

### Metadata Header

Begin the output with exactly this YAML block:

```yaml
---
topic: Sample Topic for Eval Fixtures
platform: Claude
pass: DR
date: 2026-04-15
source_profile: Mixed/exploratory
primary_question: What structural properties should a Phase 1 prompt file have?
recency_window: Not applicable — fixture only.
---
```

### 1. Executive Summary
Five most important findings, three recommendations, biggest knowledge gap.

### 2. Findings by Research Question
For each research question: state of evidence, key findings with citations,
evidence quality rating, gaps.

### 3. Landscape Summary
Named players, methodologies in use, active debates.

### 4. Source Inventory
| Source | Type | Year | Trust Level | Key Finding |
|---|---|---|---|---|

### 5. Adversarial Self-Check
Identify three high-stakes claims, state disconfirming evidence, run a targeted
search, revise if needed.

### 6. Gaps and Unanswered Questions

### 7. Self-Assessment
Rate the seven dimensions on a 1–5 scale with one-to-two sentence justification
per rating.

### 8. Open Self-Critique
Where might this report be wrong in ways the scored dimensions don't capture?

## Additional Instructions for This Platform
- Use extended thinking to plan your research strategy before starting.
- Synthesize across source types — don't just list findings, identify patterns.
- For each major finding, assess: what would need to be true for this to be wrong?
- This report will be cross-referenced against reports from other AI platforms.
