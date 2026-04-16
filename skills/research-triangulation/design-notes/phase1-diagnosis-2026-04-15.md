# Phase 1 Templates — Diagnostic Analysis

**Target file:** `skills/multi-platform-research/references/phase1-templates.md`
**Context:** `research-triangulation` v1.1 — core prompt template work
**Date:** 2026-04-15
**Analytical lenses applied:** `skill-creator` (explain the why, keep lean, generalize across many runs, avoid heavy-handed MUSTs) + `skill-doc-generator` (imperative form, specificity, active voice, consistency)

---

## Scope note

One distinction matters throughout: **the documentation standards apply to SKILL.md and reference files as documentation**, not to the content of the prompts those files generate. A prompt written to instruct an external AI model legitimately uses second person ("you are a senior analyst..."). A reference file explaining that prompt does not. Where the two conflict in the same file, I apply the correct standard to each part.

---

# CRITICAL — Session #2 carry-over

## D1. Variable-marking convention is inconsistent

### Problem, expanded

The template uses three placeholder conventions in the same file:

- Bare name: `{TOPIC_TITLE}`
- Name + inline author description via em-dash: `{DECISION_CONTEXT — What decision does this research support? Who will use the output?}`
- Directive form: `{OPTIONAL: "Include a Spanish-language executive summary..."}` and `{INCLUDE_IF_RELEVANT: "..."}`

Two concrete failure modes:

1. **Leakage.** An AI assembling a prompt from this template may paste the em-dash description into the final prompt. The author's note ("What decision does this research support?") becomes part of the prompt the user sees. This is a known LLM failure mode — models under-distinguish between metadata and content when they share the same syntactic container.
2. **Maintainability.** A human editor touching the template cannot grep for a single pattern to find all variables. Every convention must be tracked separately, which erodes over time.

A subtler problem: the inline-description variant masks the need for a parameter specification. Because the description is packed into the placeholder, there's no separate "what does this variable mean" document. So when variables drift or multiply, nothing keeps them consistent.

### Alternatives

**Alt A — Double-brace convention + parameter dictionary.** Switch every placeholder to `{{VAR_NAME}}`. Move all descriptions, defaults, examples, and optionality flags to a parameter table at the top of the file.

**Alt B — Angle-bracket convention.** Switch to `<TOPIC_TITLE>` or `<<TOPIC_TITLE>>`. Same dictionary pattern as Alt A but different delimiter.

**Alt C — Structured data block.** Define variables in a YAML-like block at the top:
```yaml
variables:
  TOPIC_TITLE:
    required: true
    description: The research topic title
    example: "Small Bets Framework"
```
Then reference them inline with a distinct token (e.g., `$TOPIC_TITLE`).

### Proposal — Alt A

Double-brace (`{{VAR_NAME}}`) with a parameter dictionary table.

**Why:** Double braces are the de facto standard (Handlebars, Jinja, Mustache). Any operator — human or AI — recognizes them. Single braces fail because they also appear in natural prose ("Include relevant context here"). Angle brackets collide with HTML-ish syntax some platforms treat specially. The YAML approach (Alt C) is cleanest for machines but adds syntactic weight to a file that humans will also read and edit.

The parameter dictionary matters more than the delimiter choice. Without it, the next maintainer adds a new variable inline and the convention decays again. With it, every variable has exactly one documented home.

**Applying skill-doc-generator standards:** Imperative form in the dictionary entries ("Provide the research topic title" not "You should provide..."). No vague terms.

---

## D2. Phase 1 adversarial follow-up is missing — SKILL.md misrepresents the template

### Problem, expanded

SKILL.md line 259 states: *"Note: Phase 1 adversarial follow-up is embedded in the research prompt templates — see `references/phase1-templates.md`."*

The template contains no adversarial follow-up instructions. The Self-Critique section (3 bullets at the end of Output Format) is weak and reactive — it asks the model to reflect after writing, not to actively probe its own conclusions with new searches or counter-evidence.

"Adversarial follow-up" as a research concept means: after producing initial findings, the model deliberately attacks them — searches for disconfirming evidence, questions whether its strongest sources are also its most biased, checks whether converging claims trace to a shared root source. This is fundamentally different from a retrospective "what might be wrong" bullet.

The gap between SKILL.md's claim and the template's reality is a correctness bug. Either the claim comes out, or the feature goes in.

### Alternatives

**Alt A — Embed adversarial instructions in the Core Brief output format.** Add a mandatory section (e.g., "Section 5.5: Adversarial Self-Check") requiring the model to identify its three weakest claims, attempt to disconfirm each via targeted search, and report the result before finalizing.

**Alt B — Two-phase prompt structure.** Restructure the prompt so the model explicitly produces a Phase A draft, then runs a Phase B adversarial pass that includes new searches, then produces the final output. Higher quality but brittle on platforms that don't support mid-run structure.

**Alt C — Minimal upgrade.** Expand the existing Self-Critique section from 3 bullets to a structured checklist covering: shared-source risk (are converging claims tracing to one origin?), vendor-echo risk, convenience-sampling risk, and missing-perspective risk. No new searches required.

### Proposal — Alt A with a cross-reference to Phase 2

Embed adversarial instructions in the Core Brief as a required output section. Claim target: *"Before finalizing, identify the three most important claims in this report whose reversal would most change the conclusions. For each: (1) state what evidence would disconfirm it, (2) run a targeted search for that evidence, (3) report what you found. If your three weakest claims survive the probe, state it. If they don't, revise the report."*

**Why:** Alt B is technically superior but assumes the platform supports a mid-run branch that all four target platforms handle consistently. They don't — Gemini DR runs a planned pipeline, Perplexity Pro has its own agentic loop, Claude DR supports extended thinking. Alt A works within any platform's normal output flow while still forcing adversarial search behavior.

Alt C (retrospective checklist) is what the current template tries and fails to do. More bullets don't produce more rigor — the model can satisfy a checklist without ever searching again.

The Phase 2 consolidation already has its own adversarial follow-up (SKILL.md Decision Rules section, lines 252-259). The Phase 1 version is lighter-weight, individually scoped. Add a sentence in the template that acknowledges the division of labor: Phase 1 adversarial check focuses on the report's own claims; Phase 2 adversarial follow-up addresses cross-report issues (shared-source echo, single-source decision weight).

**Applying skill-creator guidance:** Explain the why in the instruction itself. Don't just demand adversarial thinking — tell the model the reason ("because findings that don't survive probing aren't findings, they're guesses").

---

## D3. File naming convention doesn't encode pass type

### Problem, expanded

The Operator Handoff template specifies: `{Platform}_{topic-slug}_{YYYY-MM-DD}.md` with examples like `Perplexity-Web_{topic-slug}_2026-04-04.md` and `Perplexity-Academic_{topic-slug}_2026-04-04.md`. The hyphenation (Perplexity-Web vs. Perplexity-Academic) is convention by example, not specification.

Concrete failure: an operator running two Perplexity passes might save as `Perplexity_topic_date.md` for both, creating a filename collision that loses one output. Or they save them with slight variations (`Perplexity_web_...`, `perplexity-web-...`) that the consolidation prompt cannot parse reliably.

The convention exists implicitly in the current examples. It needs to be documented as a rule, with the valid pass types enumerated per platform.

### Alternatives

**Alt A — Formalize `{Platform}-{Pass}_{topic-slug}_{YYYY-MM-DD}.md`.** Document pass types per platform explicitly: Claude → DR; Perplexity → Web, Academic; Gemini → DR; ChatGPT → DR. If a platform has only one pass type, include it anyway for consistency.

**Alt B — Pass-suffix format.** `Perplexity_small-bets_2026-04-04_pass-academic.md` — keeps platform and pass as separate tokens for easier parsing but reads awkwardly.

**Alt C — Move pass identity to metadata header only.** Keep simple filenames, require pass identity in the structured header (D4 territory).

### Proposal — Alt A

Formalize the `{Platform}-{Pass}_{topic-slug}_{YYYY-MM-DD}.md` pattern. Document the valid pass types. Enforce it in both the Operator Handoff template and in each platform's wrapper instruction.

**Why:** Alt A matches existing informal usage, so it's a documentation fix more than a behavior change. Filename self-describes without the operator opening the file. Alt C is wrong because filenames are the primary sort key in any filesystem — burying the distinction inside the file forces consolidation to open every file just to orient itself. Alt B is technically fine but the hyphen convention (Platform-Pass) is already in use and reads more naturally.

Pair this with a small table in the handoff template listing valid pass types per platform, so the operator has a lookup.

---

## D4. No structured metadata header at the top of each report

### Problem, expanded

When the consolidation prompt reads four separate reports, it needs to know, without ambiguity: topic, platform, pass type, date run, source profile used, primary question, recency window. Currently the only signal is the filename (which D3 fixes) and whatever the body prose happens to include.

This creates two failure modes:

1. **Silent mismatch.** A Perplexity-Academic pass that accidentally received a Perplexity-Web prompt produces a report that looks like one but was run against the other. Without a metadata header, the inconsistency is undetectable.
2. **Degraded triangulation.** The consolidation's Evidence Hierarchy section ranks findings by source type. If one report is academic-profile and another is practitioner-profile, they should be weighted differently. Without the profile marker in the report itself, the consolidator has to infer — or get it wrong.

The metadata header is cheap insurance against these mismatches and enables programmatic parsing if someone later automates parts of consolidation.

### Alternatives

**Alt A — YAML frontmatter block at the top of every report.** Machine-parseable, standard markdown extension. Fields: `topic`, `platform`, `pass`, `date`, `source_profile`, `primary_question`, `recency_window`.

**Alt B — Markdown metadata section.** A "## Report Metadata" section with labeled lines. Human-readable, but not structured data — parsers must regex.

**Alt C — Both: YAML for machines + markdown section for humans.** Redundant but covers both audiences.

### Proposal — Alt A

YAML frontmatter. Every deep research platform can produce a YAML block (it's just text). It doesn't rely on the platform supporting markdown renders with frontmatter stripping — it survives as plain text either way.

**Why:** Alt A wins on every axis except "extremely human-friendly rendering." Alt C's redundancy violates skill-creator's "keep lean" principle — the same information in two places drifts over time. Alt B loses structured-data benefits for no clear win.

Specific field list:
```yaml
---
topic: {{TOPIC_TITLE}}
platform: {{PLATFORM_NAME}}
pass: {{PASS_TYPE}}
date: {{ISO_DATE}}
source_profile: {{PROFILE_NAME}}
primary_question: {{PRIMARY_QUESTION}}
recency_window: {{RECENCY_WINDOW}}
---
```

The prompt template instructs the model to emit this block verbatim as the first content in its output. This works on every platform tested — they all reproduce leading structured text when instructed to.

---

## D5. Same-platform consolidation collapse (lives in consolidation-template.md)

### Problem, expanded

The consolidation template's Input Reports section shows how to describe each report but does not contain an instruction protecting against collapse. Two Perplexity passes (Web and Academic) with different focus profiles are different data points — they exercise different source biases and produce partly disjoint evidence bases. Treating them as "Perplexity's answer" instead of two independent sources halves the triangulation signal on any finding they touch.

The failure is harder to detect than it sounds. A consolidating model reading "Perplexity-Web report" and "Perplexity-Academic report" may naturally de-duplicate findings that appear in both, thinking "Perplexity said this." In reality, two independent passes with different search surfaces converging on a finding is stronger evidence than one would be.

### Alternatives

**Alt A — Explicit instruction in the Analytical Mandate.** One paragraph stating: "Passes from the same platform with different focus profiles are independent data points. Do not collapse or de-duplicate them in the Convergence Matrix."

**Alt B — Restructure the Input Reports inventory.** Require pass identity as a mandatory column, not embedded in prose.

**Alt C — Both.**

### Proposal — Alt C

Both instruction and structural enforcement. The instruction addresses the conceptual error; the structural field makes collapse difficult at the data level.

**Why:** Cheap. Two-paragraph change. High leverage on consolidation quality for the one case (same-platform, multi-pass) where collapse risk is acute.

This is a modification to `consolidation-template.md`, not `phase1-templates.md`. Worth fixing in the same pass because it closes the loop on D3 (filename pass-encoding) and D4 (metadata header pass field).

---

# IMPORTANT — high-value additions not in Session #2's scope

## D6. "Do not hallucinate sources" is a plea, not a constraint

### Problem, expanded

Line 51: *"Do not hallucinate sources. If evidence is insufficient, state the gap explicitly."*

This is a social instruction, not a constraint. LLMs hallucinate sources precisely when the prompt doesn't make fabrication harder than admission. A model under pressure to answer the research question will generate a plausible-sounding paper ("Smith & Chen, 2023, *Journal of Organizational Behavior*") rather than say "I couldn't find a source for this."

The strongest anti-fabrication pattern is not social pressure but format rigor. If the cited format requires author + year + venue + stable identifier, and the prompt permits the model to skip the citation and state a gap, then fabricating a citation costs the model more than admitting absence. This flips the calculus.

### Alternatives

**Alt A — Required citation format with legitimate out.** "Every cited source must include author(s), year, venue/publisher, and DOI or stable URL. If you cannot provide all four, do not cite the source — state the gap explicitly."

**Alt B — Self-verification checklist.** After each major claim, require the model to answer: "Did I verify this URL resolves? Did I verify this paper exists?" (Y/N). Unverified claims flagged.

**Alt C — Pre-commit source list.** Require the model to list its sources at the start of the research pass and commit to them. Makes mid-flow fabrication harder.

### Proposal — Alt A

Required citation format with legitimate out.

**Why:** Alt A is a format constraint that operates within normal output flow. It gives the model a face-saving exit ("state the gap") that's easier than fabrication. Alt B asks the model to self-report honestly about its own hallucination — not a reliable lie-detector. Alt C is interesting but disrupts how deep research tools naturally operate (they search iteratively).

This is the single highest-leverage anti-fabrication change in the template. Every platform report currently includes sources where one or more of author/year/venue/DOI are missing. After this change, those gaps become visible.

Pair with an instruction that the Source Inventory table must include all four columns as required fields.

---

## D7. Platform wrapper asymmetry — Claude gets a role opener, others don't

### Problem, expanded

Claude DR wrapper opens with: *"You are a senior research analyst conducting deep research on {TOPIC_TITLE}."*

Perplexity, Gemini, and ChatGPT wrappers have no opening role statement. They go straight from the Core Brief to additional instructions. This is arbitrary asymmetry. Either role priming helps (in which case it should be present everywhere) or it doesn't (in which case it shouldn't be on Claude either).

Role priming does help, modestly and consistently, across all modern LLMs. The effect is largest when the role is specific and task-aligned. Removing it from Claude would be a regression. Adding it to the others is a small, positive intervention.

### Alternatives

**Alt A — Add platform-tuned role openers to all four wrappers.** Each platform gets a role statement that references its strengths.

**Alt B — Move the role statement into the Core Brief.** Role becomes shared; wrappers only add platform-specific appendices.

**Alt C — Remove all role openers.** Standardize by subtraction.

### Proposal — Alt A

Platform-tuned role openers in each wrapper.

**Why:** The wrappers exist to exploit platform differences. A generic shared role (Alt B) defeats the purpose. Alt C throws out a known-positive intervention. Alt A preserves the wrapper pattern's logic while restoring symmetry at the level that matters: every platform starts with a role prime.

Example tunings:
- Claude DR: "senior research analyst conducting deep synthesis..."
- Perplexity Web: "investigative researcher tracking recent practitioner work..."
- Perplexity Academic: "research librarian compiling empirical evidence..."
- Gemini DR: "survey researcher mapping the full landscape..."
- ChatGPT DR: "cross-disciplinary analyst synthesizing diverse sources..."

Each primes a stance aligned with the platform's strength. Total addition: ~5 lines of text.

---

## D8. Recency requirement not exposed in output

### Problem, expanded

The Core Brief demands a recency window ("Prioritize Jan 2025–present..."). The Source Inventory table includes a Year column. But nothing in the prompt requires the model to fill Year for every source or to report a recency distribution. So the Tier 1 scoring agent, evaluating "Recency compliance" (Step 7 dimension 6), has to estimate — often from nothing.

### Alternatives

**Alt A — Make the Year column mandatory.** Every row in the Source Inventory must have a year or explicit "Undated" marker.

**Alt B — Add a Recency Distribution summary.** A one-paragraph block reporting: % of sources within preferred window, % outside, % undated.

**Alt C — Both.**

### Proposal — Alt A

Make Year mandatory, with "Undated" as an allowed value.

**Why:** Minimal addition, maximum effect. The Recency Distribution (Alt B) is derivable from the table once Year is required. Forcing "Undated" as explicit rather than implicit blank makes missing dates visible instead of hidden.

---

## D9. Self-Critique section is unaligned with the Tier 1 scoring rubric

### Problem, expanded

The template's Self-Critique section has 3 open-ended bullets: "Where might this report be wrong?", "What biases might be present?", "What would change these conclusions?". The Tier 1 rubric (SKILL.md Step 7) scores reports on 7 dimensions. The two instruments do not communicate.

If the self-critique used the same 7 dimensions, two benefits emerge. First, the report surfaces the exact information the Tier 1 agent needs to audit (and can flag cases where the model scored itself high on a dimension the agent rates low — a useful red flag). Second, the model is forced to think about the report's quality on axes that matter structurally, not just axes that happened to come to mind.

### Alternatives

**Alt A — Replace Self-Critique with a scored 7-dimension self-assessment.** Pure numeric self-rating.

**Alt B — Expand Self-Critique into a scored + prose hybrid.** Self-rate on 7 dimensions with 1-2 sentences of justification per rating.

**Alt C — Keep Self-Critique as-is, add a separate "Self-Assessment" scoring block above it.**

### Proposal — Alt B

Scored + prose hybrid. Self-rate on the 7 dimensions, 1-2 sentences each.

**Why:** Pure scoring (Alt A) misses unknown failure modes — things the model notices but can't fit into a dimension. Pure prose (current state) misses known structural issues. The hybrid catches both. Alt C duplicates concern without integrating them.

Concrete form:
```markdown
### Self-Assessment
For each dimension, rate 1-5 and justify in 1-2 sentences:
- Source traceability: [rating] — [justification]
- Source quality distribution: [rating] — [justification]
- Hallucination risk (self-estimated): [rating] — [justification]
- Coverage breadth: [rating] — [justification]
- Coverage depth: [rating] — [justification]
- Recency compliance: [rating] — [justification]
- Actionability: [rating] — [justification]

### Open Self-Critique
[Beyond the dimensions above: what else might be wrong? What would change these conclusions?]
```

This gives the Tier 1 agent a baseline to compare against and keeps the open-ended critique for things the dimensions miss.

---

## D10. No convergence-threshold awareness in Phase 1 prompts

### Problem, expanded

Phase 2 consolidation applies a ±15% convergence threshold to quantitative claims. Phase 1 reports don't know this. A report saying "~30%" will be compared to one saying "28.4%" and should count as convergent. But a report saying "between 20 and 40%" is harder to reconcile. If Phase 1 prompts asked for point estimates with uncertainty ranges where possible, Phase 2's quantitative reconciliation gets cleaner inputs.

### Alternatives

**Alt A — One-line addition to Evidence Standards.** "For quantitative claims, provide a point estimate with uncertainty range where available. Downstream analysis applies a ±15% convergence threshold across independent reports."

**Alt B — Require a separate Quantitative Claims Table.** Dedicated output section.

**Alt C — Both.**

### Proposal — Alt A

Single line addition.

**Why:** 80% of the benefit for 5% of the overhead. A dedicated table (Alt B) adds prompt complexity and may distort how the model reports findings. The goal is to shape behavior during research, not to create a new artifact. One sentence does it.

---

# NICE-TO-HAVE — worth considering but lower-priority

## D11. "Do not repeat" phrasing is brittle

### Problem, expanded

Line 42: "What We Already Know (Do Not Repeat)". Models restate basics anyway — the instruction is negatively phrased and easy to satisfice ("I'll just briefly recap..."). Positive framing with a cost attached works better.

### Alternatives

- **Alt A:** Rephrase as: "The user has prior domain knowledge. Restating common definitions wastes their time and your output budget. Skip foundational material."
- **Alt B:** Cost-attached version: "Do not restate material already listed below. Any output under 'What We Already Know' that appears in your findings will be considered wasted."

### Proposal — Alt A

Alt A. Explains the why, imperative voice, no artificial penalties. Alt B tries to threaten the model, which doesn't reliably work and sounds silly.

---

## D12. `{DOMAIN_SPECIFIC_SECTIONS}` has no defaults

### Problem, expanded

Line 72: "Section 3: `{DOMAIN_SPECIFIC_SECTIONS — customize based on topic}`". Operator-facing variables with no defaults get skipped. An AI filling the template in may leave the section empty or fill it poorly.

### Alternatives

- **Alt A:** Provide per-source-profile defaults. Academic-first → Study Inventory. Practitioner-first → Tool/Method Cards. Market/competitive → Vendor Comparison Matrix. Mixed → offer all three, pick one.
- **Alt B:** Make the section optional and document when to use it.

### Proposal — Alt A

Per-profile defaults with an "override if your topic needs different" note.

**Why:** Defaults reduce variance across runs. The source-profile connection makes the defaults intellectually honest — academic research warrants a study inventory; practitioner research warrants tool cards. Alt B abdicates design.

---

## D13. No instruction on context-window truncation

### Problem, expanded

Gemini and ChatGPT can hit length limits on long deep research outputs. When they do, they truncate arbitrarily. The prompt doesn't specify a priority order.

### Alternatives

- **Alt A:** Specify priority: "If length-limited, complete sections 1, 2, 4 before 3, 5, 6. Never skip the metadata header or the Source Inventory."
- **Alt B:** Require a Priority Mode: if the model senses length pressure, it should compress rather than truncate, and state explicitly that it did so.

### Proposal — Alt A

Priority ordering.

**Why:** Alt B asks the model to self-diagnose length pressure, which is unreliable. Alt A is a deterministic rule that works regardless of the model's self-awareness. Keeps the critical sections (metadata, source inventory, executive summary, recommendations) intact at the expense of the less-critical ones (domain-specific sections, self-critique).

---

## D14. Source hierarchy injection is ad-hoc

### Problem, expanded

Line 46: `{INJECTED_FROM_SOURCE_PROFILE — paste the relevant source hierarchy and evidence standards from source-profiles.md}`

The assembling agent decides what to paste and how much. Different agents produce different-sized, differently-structured injections. No contract.

### Alternatives

- **Alt A:** Define the injection contract in `source-profiles.md` — every profile exports a fixed structure (hierarchy list, evidence standards block, red flags list) and the template pastes the structured block verbatim.
- **Alt B:** Inline all profiles in the template with a `{SELECTED_PROFILE}` toggle.

### Proposal — Alt A

Structured export contract from source-profiles.md.

**Why:** Alt B bloats phase1-templates.md and duplicates what source-profiles.md exists to provide. Alt A keeps separation of concerns — source-profiles.md owns the profile content, phase1-templates.md owns the prompt structure, and the contract between them is explicit.

---

## D15. Parameterization Quick Reference table is incomplete

### Problem, expanded

The reference table (line 186) is missing `{WHAT_TO_INCLUDE}`, `{WHAT_TO_EXCLUDE}`. Minor but real.

### Proposal

Fix by listing every parameter. Rolls into D1's parameter dictionary — fixed once, for all parameters, with a single source of truth.

---

# MINOR — cleanup only

## D16. Handoff "Next Step" depends on a magic phrase

Line 276 of `phase1-templates.md`: the handoff instructs the user to say "I have {N} reports on {TOPIC_TITLE}, help me consolidate them." SKILL.md's Phase 2 triggers (line 52) are broader. **Fix:** update the handoff to list broader trigger options or point to SKILL.md's triggers.

## D17. `{INCLUDE_IF_RELEVANT: "..."}` is yet another variable convention

Rolls into D1. Convert to `{{CONTEXT_WINDOW_WARNING}}` with description in the dictionary, default empty.

## D18. Bilingual handling is a footnote

Line 62's optional Spanish summary is an exception pattern. **Fix:** promote to a top-level `{{OUTPUT_LANGUAGES}}` parameter with options (English-only, English+Spanish summary, Spanish primary). Default: English-only.

## D19. "Evidence Quality" vs. "Trust Level" unreconciled

Line 68 asks for Strong/Mixed/Weak per question. Line 77 asks for Trust Level per source. **Fix:** clarify in template comments — per-question Evidence Quality is a roll-up derived from the Trust Levels of sources cited for that question. One sentence.

## D20. Path reference `/mnt/user-data/outputs/` may be stale

SKILL.md line 126. Current Cowork workspace is `/sessions/cool-blissful-carson/mnt/31_MetaClaude`. **Verification needed.** If the skill still operates inside a session sandbox where `/mnt/user-data/outputs/` is valid, leave it. If not, replace with a variable or a cross-reference to the current output convention.

---

# Applying skill-creator and skill-doc-generator lenses — what shaped the proposals

**From skill-creator:**
- Several proposals (D2, D6, D11) explicitly explain the *why* in the instruction itself — the model acts better when it understands why a rule exists rather than obeying it blindly.
- Proposals avoid heavy-handed MUSTs in favor of explained structure (D2's reason-giving on adversarial pass; D11's cost-framing on repetition).
- D14's separation of concerns reflects "keep SKILL.md lean" — don't pull content into the template that lives correctly elsewhere.
- Every proposal considers generalization: the skill runs across many topics, so fixes must not overfit to research types.

**From skill-doc-generator:**
- D1's parameter dictionary uses imperative descriptions, avoids vague terms like "multiple" (the current description is flagged for using this word).
- D4's metadata header uses consistent field naming.
- The minor-fixes (D18–D20) apply the same consistency discipline the validator does.
- I deliberately do not apply "avoid second person" to the content of generated prompts — a prompt speaking to an AI model legitimately uses "you."

**Validator baseline:** 0 errors, 0 warnings, 5 INFOs on the current skill. The changes proposed won't degrade this. The vague-term flag ("multiple") is in the skill's frontmatter description, not the template — separate fix, comes up during description optimization after v1.1 ships.

---

# Scope recommendations

Three reasonable scopes:

**Minimum viable (Session #2 scope):** D1, D2, D3, D4, D5. Finishes v1.1 as defined. Risk: D2 is the heaviest item and expanding the template's Self-Critique into proper adversarial structure is not trivial.

**Recommended scope:** D1, D2, D3, D4, D5, D6, D9. Adds two high-leverage items (anti-fabrication + rubric-aligned self-assessment) that are cheap once you're in the file. Puts the skill in materially better shape for v1.1 without sliding into v1.2.

**Full scope:** D1–D10. Ships a substantially stronger template. Widens the pass meaningfully. Probably worth reframing as v1.2 if we go here, since it's beyond Session #2's scope.

**Not recommended:** trying to ship D11–D20 in this pass. The minor fixes are real but they don't require Session #3's attention — most can be resolved in a cleanup pass after v1.1 is tested in real use.

Pick a scope.
