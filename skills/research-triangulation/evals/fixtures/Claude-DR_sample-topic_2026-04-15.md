---
topic: Sample Topic for Eval Fixtures
platform: Claude
pass: DR
date: 2026-04-15
source_profile: Mixed/exploratory
primary_question: What structural properties should a Phase 1 prompt file have?
recency_window: Not applicable — fixture only.
---

# Research Report: Sample Topic for Eval Fixtures

This fixture exists as a structural target for automated checks. It is not a
real research output. Its job is to demonstrate that a compliant report file:

- is named following `{{PLATFORM}}-{{PASS}}_{{SLUG}}_{{DATE}}.md`;
- begins with a YAML front-matter block containing exactly the required keys;
- uses a pass type the file-naming table declares valid for its platform;
- carries enough structure that downstream consolidation can parse it without
  manual normalization.

## 1. Executive Summary

Structural conformance is a necessary-but-not-sufficient condition for a report
to be usable in consolidation. A file can be perfectly named and headered and
still be wrong on the substance — that's what the Tier 1 quality rubric is for.
This fixture exists only to exercise the structural lane.

## 2. Findings by Research Question

### Q1: Required metadata fields

- State of evidence: Strong — the schema is declared explicitly in
  phase1-templates.md.
- Key findings: Seven fields are required (topic, platform, pass, date,
  source_profile, primary_question, recency_window).
- Evidence quality: Strong.
- Gaps: None for the fixture.

### Q2: Filename components

- State of evidence: Strong — declared in the File Naming Convention table.
- Key findings: Platform, pass, slug, date. The platform-pass hyphenation is
  load-bearing for Perplexity's Web vs. Academic independence.
- Evidence quality: Strong.
- Gaps: None for the fixture.

## 4. Source Inventory

| Source | Type | Year | Trust Level | Key Finding |
|---|---|---|---|---|
| phase1-templates.md § File Naming Convention | Skill reference | 2026 | High (canonical) | Defines the required metadata keys and filename pattern. |

## 5. Adversarial Self-Check

No adversarial pass is run on fixtures — this file has no substantive claims
that would benefit from disconfirmation. This section is present only to
demonstrate section coverage.

## 6. Gaps and Unanswered Questions

None for the fixture.

## 7. Self-Assessment

- Source traceability: 5 — every claim traces to the skill's own source files.
- Source quality distribution: 5 — canonical source only.
- Hallucination risk: 5 — no external citations.
- Coverage breadth: n/a (fixture).
- Coverage depth: n/a (fixture).
- Recency compliance: 5 — fixture is dated to match file date.
- Actionability: n/a (fixture).

## 8. Open Self-Critique

This fixture is deliberately minimal. It tests the structural lane, not the
quality lane. A structurally perfect report can still be substantively wrong;
that failure mode is covered by the Tier 1 scoring rubric in
`references/quality-rubric.md`, not here.
