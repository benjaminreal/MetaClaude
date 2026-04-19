# Backlog — research-triangulation

Deferred items. One line per item. When an item gets picked up, move it to the skill's changelog.

---

## Important — high-leverage, worth v1.2

- **Platform-specific Core Brief section profiles (candidate for v1.4).** v1.3.2 introduced the first asymmetric treatment of the Core Brief — Perplexity passes omit §5/§7/§8 to avoid a generation-collapse failure mode. This was necessary and correct but sets a precedent worth formalizing. Open question: should the Core Brief output spec be explicitly parameterized by platform (a `{{OMITTED_SECTIONS}}` variable, or a per-platform section profile), so that future platform-specific deviations have a structured place to land rather than accreting as wrapper-level overrides? Related: does ChatGPT-DR exhibit a similar output-budget problem under the full 8-section spec? (Not observed yet; no data.) Re-examine after the next triangulation that includes a ChatGPT-DR pass. [Session #10]
- **Cross-platform author-attribution hallucinations — prompt-level countermeasure (candidate for v1.4).** Retrospective quality audit 2026-04-17 across four projects surfaced a recurring failure mode: the same paper is credited to different author lists across platforms (e.g., a 2016 JGIM paper on election→suicide variously attributed to Yan/Hsia/Yeung/Sloan, Venkatamani, Yan/Hong/Xu/Tsai, and Chang across three reports; "Allure Immune Harry" credited to LiviaHyde7 in Gemini vs. the canonical Racke in the other three reports on the same fanfiction topic). The current rubric catches these in Tier 2 contradiction handling, but Tier 1 has no structural control to prevent them. Candidate intervention: extend the Evidence Standards section of the Core Brief to require that any cited paper with three or more authors have its author list cross-checked against at least one independent reference (publisher page, CrossRef, Google Scholar, AO3 canonical work page) before entering the Source Inventory — and if the cross-check cannot be performed, the author list is reduced to `[first-author] et al.` rather than fabricated. Trade-off worth measuring: small recall hit (fewer full author lists) in exchange for a meaningful precision gain on attribution. [retrospective-audit 2026-04-17]
- **D6 follow-up — eval the tightened citation format in practice.** Run real triangulations and observe how each platform handles the author + year + venue + DOI constraint. Which platforms comply? Which substitute plausible-sounding fabrications? Which report gaps honestly? → Drives D6 refinement.
- **D7 — platform wrapper symmetry.** Claude DR has a role opener; Perplexity, Gemini, ChatGPT don't. Either add tuned role openers to the other three wrappers, or remove it from Claude. Current asymmetry is arbitrary.
- **D10 — convergence-threshold awareness in Phase 1 prompts.** Add a line to Evidence Standards informing the model that downstream analysis applies a ±15% convergence threshold, so it produces point estimates with uncertainty ranges where possible.
- **D14 — source hierarchy injection contract.** `{{INJECTED_SOURCE_PROFILE}}` currently relies on the assembling agent pasting correctly. Define a structured export block in `source-profiles.md` that every profile produces identically.

## Nice-to-have — could roll into v1.2 if scope allows

- **D8 — mandatory Year column in Source Inventory.** Require every row to have a year or explicit "Undated" marker, never blank. Enables the Tier 1 "recency compliance" dimension to be audited reliably.
- **D11 — strengthen "Do not repeat" phrasing.** Rephrase "What We Already Know (Do Not Repeat)" with a positive frame that explains *why* restating basics wastes effort.
- **D13 — context-window truncation priority rules.** Specify which sections the model should complete first if length-limited (metadata header, Source Inventory, Executive Summary, recommendations) before less-critical sections.

## Minor — batch in any future cleanup pass

- **D16 — handoff magic-phrase dependence.** The handoff "Next Step" section names one specific trigger phrase. SKILL.md's Phase 2 triggers are broader. Align the handoff to list the broader trigger options.
- **D20 — path reference `/mnt/user-data/outputs/` staleness.** SKILL.md line 126 references a path that may no longer match the current Cowork workspace convention. Verify and either update or parameterize.

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

1. When starting a new version, read this file first and pick scope.
2. When an item ships, move its line to the SKILL.md changelog with the shipped version number and delete it from here.
3. Item IDs (D6, D7, ...) trace back to the skill's internal design notes; each line is self-contained enough to act on without them.
