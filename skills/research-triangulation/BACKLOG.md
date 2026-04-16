# Backlog — research-triangulation

Deferred items with pointers to the full analysis in `design-notes/phase1-diagnosis-2026-04-15.md`. One line per item. When an item gets picked up, move it to the skill's changelog.

---

## Important — high-leverage, worth v1.2

- **D6 follow-up — eval the tightened citation format in practice.** Run real triangulations and observe how each platform handles the author + year + venue + DOI constraint. Which platforms comply? Which substitute plausible-sounding fabrications? Which report gaps honestly? → Drives D6 refinement. [design-notes → D6]
- **D7 — platform wrapper symmetry.** Claude DR has a role opener; Perplexity, Gemini, ChatGPT don't. Either add tuned role openers to the other three wrappers, or remove it from Claude. Current asymmetry is arbitrary. [design-notes → D7]
- **D10 — convergence-threshold awareness in Phase 1 prompts.** Add a line to Evidence Standards informing the model that downstream analysis applies a ±15% convergence threshold, so it produces point estimates with uncertainty ranges where possible. [design-notes → D10]
- **D14 — source hierarchy injection contract.** `{{INJECTED_SOURCE_PROFILE}}` currently relies on the assembling agent pasting correctly. Define a structured export block in `source-profiles.md` that every profile produces identically. [design-notes → D14]

## Nice-to-have — could roll into v1.2 if scope allows

- **D8 — mandatory Year column in Source Inventory.** Require every row to have a year or explicit "Undated" marker, never blank. Enables the Tier 1 "recency compliance" dimension to be audited reliably. [design-notes → D8]
- **D11 — strengthen "Do not repeat" phrasing.** Rephrase "What We Already Know (Do Not Repeat)" with a positive frame that explains *why* restating basics wastes effort. [design-notes → D11]
- **D13 — context-window truncation priority rules.** Specify which sections the model should complete first if length-limited (metadata header, Source Inventory, Executive Summary, recommendations) before less-critical sections. [design-notes → D13]

## Minor — batch in any future cleanup pass

- **D16 — handoff magic-phrase dependence.** The handoff "Next Step" section names one specific trigger phrase. SKILL.md's Phase 2 triggers are broader. Align the handoff to list the broader trigger options. [design-notes → D16]
- **D20 — path reference `/mnt/user-data/outputs/` staleness.** SKILL.md line 126 references a path that may no longer match the current Cowork workspace convention. Verify and either update or parameterize. [design-notes → D20]

## Cross-file consistency

- **Convert `consolidation-template.md` to `{{VAR}}` double-brace convention.** Phase 1 templates now use double-brace; consolidation template still uses single-brace (`{TOPIC_TITLE}`, `{OUTPUT_LANGUAGE}`, etc.). Mechanical conversion, touches ~10 placeholders. Should happen before or during v1.2.

## Meta / skill infrastructure

*No open items in this section.*

## Closed decisions (not actionable)

Kept here as the record of what was *decided* rather than *deferred*, to prevent re-litigation.

- **"Overview" section convention** (closed 2026-04-15, v1.3). The `skill-doc-generator` validator flags the absence of a top-level Overview section as INFO. This skill opens with Purpose & Scope, which fills the same role (does / does not do / decision table). Renaming would trade accurate framing ("Purpose & Scope" says what the section contains) for validator compliance. Decision: keep Purpose & Scope, accept the INFO flag as a known divergence from the validator's default expectation. Not a bug, not a regression.

- **Description optimization** (closed 2026-04-15, v1.3). Ran `skill-creator`'s `run_loop.py` for 5 iterations with a 20-query eval set (10 should-trigger, 10 should-not-trigger, drawn from realistic user phrasings including names of the user's actual active projects). All five iterations — including three substantially rewritten descriptions that explicitly named the four platforms and restructured the trigger list — produced identical pass rates: 6/12 train, 4/8 test. The loop correctly kept the original as "best" since nothing improved over it. **Conclusion**: the ~50% trigger rate is a structural ceiling, not a descriptive one. Claude's skill-selection logic treats research-methodology queries like *"design a research process for my thesis"* or *"run the full research process on SAFE notes"* as tasks it can handle directly, independent of how the skill's description is phrased. This matches the skill-creator docs' caveat that simple queries may not trigger a skill even on a perfect description match. Artifacts preserved in `evals/description-optimization/2026-04-15_174301/` for future reference. Two related validator INFO flags (description length 721 chars, vague term "multiple") are also closed as a consequence — length is load-bearing (carrying the trigger phrases that DO fire reliably), and "multiple" is a semantically correct use of the word (the skill literally coordinates multiple AI platforms). Re-opening this item would require a fundamentally different approach, e.g., splitting the skill into phase-specific sub-skills with narrower scope each.

---

## How to use this file

1. When starting v1.2, read this file first and pick scope.
2. Every item links to its full analysis in `design-notes/phase1-diagnosis-2026-04-15.md`.
3. When an item ships, move its line to the SKILL.md changelog with the shipped version number and delete it from here.
4. New diagnoses go into a new dated design note under `design-notes/`, and their one-liners come here.
