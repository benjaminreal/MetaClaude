# Phase 1: Research Prompt Templates

These are parameterized templates for generating platform-specific research prompts. The skill produces one self-contained prompt file per platform-pass combination — each file contains only the prompt, ready to copy-paste into its target platform. No operator instructions or usage notes live inside the prompt files themselves.

All variables use the `{{VAR_NAME}}` double-brace convention. The Parameter Dictionary immediately below is the single source of truth for what each variable means and how to fill it in.

---

## Parameter Dictionary

Every placeholder in the templates below refers to one of these parameters. Resolve every `{{VAR_NAME}}` before delivering a prompt file — unresolved placeholders in generated prompts are a correctness bug.

| Variable | Required | Description | Default / How to get it |
|---|---|---|---|
| `{{TOPIC_TITLE}}` | Yes | The research topic in title form | User provides |
| `{{TOPIC_SLUG}}` | Yes | URL-safe slug form of the topic title | Derived: lowercase, hyphenated, short (e.g., "Small Bets Framework" → `small-bets`) |
| `{{DECISION_CONTEXT}}` | Yes | What decision the research supports; who will use the output | Ask user: "What decision does this research support?" |
| `{{PRIMARY_QUESTION}}` | Yes | The single most important research question | Ask user or derive from their request |
| `{{SECONDARY_QUESTIONS}}` | Yes | Numbered list of 3-6 supporting research questions | Co-develop with user |
| `{{RECENCY_WINDOW}}` | Yes | The time window for acceptable sources, stated as a sentence | Default: "Prioritize sources from the last 18 months. Accept older foundational work only when explicitly justified." |
| `{{GEO_SCOPE}}` | Yes | Geographic emphasis or constraint | Ask user or infer from context |
| `{{WHAT_TO_INCLUDE}}` | Optional | Specific domains, industries, or source types to prioritize | Set to "None specified" if not applicable |
| `{{WHAT_TO_EXCLUDE}}` | Optional | Topics, source types, or frameworks to skip | Set to "None specified" if not applicable |
| `{{KNOWN_CONTEXT}}` | Yes | What the user already knows — prevents restating basics | Ask user: "What do you already know about this?" |
| `{{INJECTED_SOURCE_PROFILE}}` | Yes | The source hierarchy block from the selected source profile | Paste the structured export block from `references/source-profiles.md` — contains the source hierarchy + the search instruction for THIS platform only. See the Structured Export Format section in that file. |
| `{{DOMAIN_SPECIFIC_SECTIONS}}` | Yes | Output sections specific to this topic type | See "Domain-Specific Section Defaults" below |
| `{{DATE_ISO}}` | Yes | ISO 8601 date (YYYY-MM-DD) the prompt was generated | Current date |
| `{{PLATFORM_NAME}}` | Yes | Target platform | One of: `Claude`, `Perplexity`, `Gemini`, `ChatGPT` |
| `{{PASS_TYPE}}` | Yes | Pass type for this platform | See "File Naming Convention" for valid values per platform |
| `{{PROFILE_NAME}}` | Yes | Human-readable name of the selected source profile | e.g., "Practitioner-first", "Academic-first" |
| `{{LIST_OF_PLATFORM_PASSES}}` | Yes | Comma-separated list of platform-pass combinations used | e.g., "Claude-DR, Perplexity-Web, Perplexity-Academic, Gemini-DR" |
| `{{CONTEXT_WINDOW_WARNING}}` | Optional | Ad-hoc note about context window risk for this topic | Leave empty if not applicable |

### Domain-Specific Section Defaults

If no domain-specific section is explicitly defined for a given topic, fall back to the default matched to the selected source profile:

| Source profile | Default domain section |
|---|---|
| Academic-first | Study Inventory (table: study, author/year, sample size, method, finding) |
| Practitioner-first | Tool/Method Cards (one card per tool or method, with use cases and evidence of adoption) |
| Market/competitive | Vendor Comparison Matrix (feature × vendor, with evidence source per cell) |
| Legal/regulatory | Jurisdiction Inventory (regulation, scope, effective date, status, implementing body) |
| Mixed/exploratory | Landscape Summary (named players, methodologies in use, active debates) |

Override the default when the topic warrants a different structure.

---

## File Naming Convention

Both prompt files and the resulting research report files follow a platform-pass hyphenated format. The pass type in the filename must agree with the `pass` field in the report's YAML metadata header (see Core Brief output format). Filename and metadata agreeing is how downstream consolidation distinguishes, for example, a Perplexity-Web pass from a Perplexity-Academic pass — two independent data points, not one doubled.

**Prompt files** (produced by this skill, one per platform-pass):
```
prompt_{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}.md
```

**Report files** (produced by the platform, named by the operator):
```
{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}_{{DATE_ISO}}.md
```

**Valid pass types per platform:**

| Platform | Valid pass types |
|---|---|
| Claude | `DR` (Deep Research) |
| Perplexity | `Web`, `Academic` |
| Gemini | `DR` |
| ChatGPT | `DR` |

**Examples:**
- `prompt_Claude-DR_small-bets.md`
- `Claude-DR_small-bets_2026-04-04.md`
- `Perplexity-Web_small-bets_2026-04-04.md`
- `Perplexity-Academic_small-bets_2026-04-04.md`
- `Gemini-DR_small-bets_2026-04-04.md`

---

## Assembly Process

For each platform-pass combination in the research plan:

1. Start with the Core Brief Template below
2. Resolve every `{{VAR_NAME}}` using the Parameter Dictionary
3. Select the section profile for this platform-depth combination from `references/section-profiles.md` (lookup by platform + depth mode — default is Full; use Light for mid-capability DR agents or when the user requests a lighter output spec)
4. If the profile is not `standard-full`, prepend the profile's section-selection preamble to the Output Format section of the Core Brief
5. Inject the source hierarchy by pasting the selected source profile's structured export block into `{{INJECTED_SOURCE_PROFILE}}` — the export block contains the source hierarchy plus the search instruction for THIS platform only (see `references/source-profiles.md`)
6. Wrap the completed core brief in the appropriate Platform Wrapper
7. Save as `prompt_{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}.md`

Produce one Operator Handoff File alongside the prompt files — see the Operator Handoff Template at the bottom of this document.

---

## Core Brief Template

This is the foundation shared across all platforms. Fill it in, then wrap it in platform-specific instructions.

```markdown
# Research Brief: {{TOPIC_TITLE}}

## Context
{{DECISION_CONTEXT}}

## Primary Research Question
{{PRIMARY_QUESTION}}

## Secondary Research Questions
{{SECONDARY_QUESTIONS}}

## Scope Boundaries
- **Time window**: {{RECENCY_WINDOW}}
- **Geography**: {{GEO_SCOPE}}
- **Inclusions**: {{WHAT_TO_INCLUDE}}
- **Exclusions**: {{WHAT_TO_EXCLUDE}}

## What We Already Know (Do Not Repeat)
{{KNOWN_CONTEXT}}

## Source Requirements
{{INJECTED_SOURCE_PROFILE}}

## Evidence Standards

- Every cited source must include **author(s)**, **year**, **venue/publisher**, and **DOI or stable URL**. If you cannot provide all four, do not cite the source — state the gap explicitly instead. A cited source missing any of these four fields is treated as a fabrication signal during downstream audit, so the legitimate move when evidence is thin is to report the gap, not to manufacture a plausible citation.
- Distinguish evidence types for every finding: (a) Documented practice — someone did this and reported results; (b) Expert recommendation — practitioner or researcher advises, no specific outcome reported; (c) Plausible inference — based on capabilities, not yet documented.
- For quantitative claims, report: the number, the source, the sample size (if applicable), and the methodology (if available). Downstream analysis applies a ±15% convergence threshold to numeric estimates; where possible, report point estimates with uncertainty ranges (e.g., "8.3% ± 1.2%" or "8.3% (95% CI: 7.1–9.5%)") rather than bare numbers.
- Apply the aspiration vs. demonstration distinction: announcing intent is categorically different from demonstrating implementation is categorically different from measuring outcomes. Every claim about adoption or results belongs to exactly one of these three buckets and must be labeled accordingly.
- For any cited work with three or more authors, cross-check the author list against at least one independent reference (publisher page, CrossRef, Google Scholar, or the canonical work page) before including it in the Source Inventory. If the cross-check cannot be performed, reduce the author list to `[first-author] et al.` rather than reproducing an unverified list. Fabricated or misattributed author lists are a recurring cross-platform failure mode — the honest fallback is abbreviation, not guessing.

## Output Format

Produce your output as a single, self-contained markdown document. Begin with the YAML metadata header, then follow the section order below exactly.

### Metadata Header

Begin the output with exactly this YAML block, with every field filled in:

\`\`\`yaml
---
topic: {{TOPIC_TITLE}}
platform: {{PLATFORM_NAME}}
pass: {{PASS_TYPE}}
date: {{DATE_ISO}}
source_profile: {{PROFILE_NAME}}
primary_question: {{PRIMARY_QUESTION}}
recency_window: {{RECENCY_WINDOW}}
---
\`\`\`

This header is how downstream consolidation identifies what this report is and how it was produced. Do not omit fields or rename them.

### 1. Executive Summary
- Five most important findings with confidence levels (High / Medium / Low)
- Three key recommendations
- Biggest knowledge gap identified

### 2. Findings by Research Question
For each research question:
- **State of evidence**: What do we know with confidence?
- **Key findings**: Specific, sourced findings (cite every claim)
- **Evidence quality**: Rate the evidence base for this question (Strong / Mixed / Weak) — this is a roll-up of the Trust Levels of the sources cited for this question
- **Gaps**: What couldn't be found or remains unresolved?

### 3. {{DOMAIN_SPECIFIC_SECTIONS}}

### 4. Source Inventory

Organize all sources in a single table:

| Source | Type | Year | Trust Level | Key Finding |
|---|---|---|---|---|

### 5. Adversarial Self-Check

Before finalizing this report, identify the three claims whose reversal would most change the conclusions. These are your high-stakes claims.

For each:
1. State the claim precisely
2. State what evidence would disconfirm it
3. Run a targeted search for that disconfirming evidence
4. Report what you found. If you found disconfirming evidence, revise the report body and note the revision here.

The purpose of this section is not cosmetic self-reflection. It is to force an actual search pass against your own conclusions before finalizing. Findings that don't survive a disconfirmation probe are not findings — they are guesses.

Note: Phase 2 consolidation runs its own adversarial follow-up on cross-report issues (shared-source echo, single-source decision weight). Your job here is the narrower one: probe this report's own internal claims.

### 6. Gaps and Unanswered Questions
- What important questions could not be answered?
- Where is the evidence weakest?
- What would need to happen to close these gaps?

### 7. Self-Assessment

Rate this report on each of the seven dimensions below on a 1-5 scale. Provide a one-to-two sentence justification per rating. Honest self-rating is more useful than defensive self-rating — downstream audit compares these scores against an independent rating, and any mismatch is itself a signal.

- **Source traceability** [1-5] — Can every major claim be traced to a named, linkable source?
- **Source quality distribution** [1-5] — What proportion of sources are high-trust vs. low-trust?
- **Hallucination risk (self-estimated)** [1-5] — How confident are you that no cited source is fabricated? (5 = fully verifiable; 1 = several sources could not be independently verified)
- **Coverage breadth** [1-5] — Did the report address every research question?
- **Coverage depth** [1-5] — Beyond surface-level summaries on the central questions?
- **Recency compliance** [1-5] — What proportion of sources fall within the specified recency window?
- **Actionability** [1-5] — Could a reader act on this report alone, without the source reports?

### 8. Open Self-Critique

Beyond the scored dimensions above:
- Where might this report be wrong in ways the dimensions don't capture?
- What biases might be present in the sources found (vendor bias, English-language bias, recency bias, techno-optimism)?
- What would change these conclusions?
```

---

## Platform Wrappers

Each wrapper goes AROUND the completed Core Brief. The final prompt file has this structure:

```
[Platform-specific role and instructions — from wrapper]
[Complete Core Brief — all variables resolved]
[Platform-specific additional instructions — from wrapper]
```

### Claude Deep Research Wrapper

**File**: `prompt_Claude-DR_{{TOPIC_SLUG}}.md`

Open with:
```markdown
You are a senior research analyst conducting deep research on {{TOPIC_TITLE}}.
```

Then insert the complete, parameterized Core Brief.

Then close with:
```markdown
## Additional Instructions for This Platform
- Use extended thinking to plan your research strategy before starting
- Synthesize across source types — don't just list findings, identify patterns and tensions
- When you find conflicting evidence, investigate the root cause rather than just reporting both sides
- For each major finding, assess: what would need to be true for this to be wrong?
- If you identify a high-quality anchor source (rigorous study, foundational framework), call it out explicitly
- This report will be cross-referenced against reports from other AI platforms on the same topic. Prioritize depth and analytical rigor over breadth.
```

### Perplexity Pro Wrapper (Web Focus)

**File**: `prompt_Perplexity-Web_{{TOPIC_SLUG}}.md`

Insert the complete Core Brief (with any section-selection preamble already applied per `references/section-profiles.md`), then append:
```markdown
## Additional Instructions for This Platform
- Focus on recent, practitioner-oriented sources: blog posts, YouTube walkthroughs, conference talks, professional publications, social media threads with substantive content
- For every workflow, method, or tool claim: who documented it? When? What was the outcome?
- Include links to every source
- **Numbered bibliography required.** If your output uses inline citation markers (e.g., `[cite:1]`, `[1]`, or similar), every marker must resolve to a numbered entry in a final "Sources" section listing: number, author/site, title, URL, and year. If you cannot produce a matching numbered bibliography, switch to inline parenthetical citations (Author, Year) instead — unresolvable markers make the report unauditable downstream.
- Prioritize sources from the last 6 months for rapidly evolving topics
- Search in both English and Spanish where relevant
- This report will be cross-referenced against reports from other AI platforms. Prioritize unique sources that other platforms might miss — community discussions, niche blogs, recent conference talks.
```

### Perplexity Pro Wrapper (Academic Focus)

**File**: `prompt_Perplexity-Academic_{{TOPIC_SLUG}}.md`

Insert the complete Core Brief (with any section-selection preamble already applied per `references/section-profiles.md`), then append:
```markdown
## Additional Instructions for This Platform
- Focus exclusively on peer-reviewed academic sources, working papers from recognized institutions, and doctoral research
- For every study: cite author(s), year, journal, sample size, methodology, key finding
- Include DOI or stable URL for every source
- Distinguish between: empirical studies (data-driven), theoretical papers (framework-building), and literature reviews (synthesis)
- Note citation counts and journal impact factors where available
- Flag any systematic reviews or meta-analyses — these are the highest-value sources
- This report will be cross-referenced against practitioner-focused reports. Your job is to provide the empirical backbone.
```

### Gemini Deep Research Wrapper

**File**: `prompt_Gemini-DR_{{TOPIC_SLUG}}.md`

Insert the complete Core Brief, then append:
```markdown
## Additional Instructions for This Platform
- **Begin your output with the YAML metadata header specified in the Core Brief, reproduced verbatim with every field filled in.** Gemini Deep Research has a documented tendency to drop this header even when the Core Brief mandates it; reproducing the YAML block exactly is non-negotiable. Downstream consolidation identifies reports structurally via this header — a report without it is treated as non-compliant.
- **DOI or direct URL required for every cited paper.** If a DOI or direct URL cannot be found, flag the source as "DOI not found" rather than silently retaining it as fully cited. Gemini Deep Research has a documented tendency to produce confident-sounding but under-cited specifics — this control surfaces gaps rather than burying them.
- **Specificity-without-verification counter.** If you state a precise figure (>3 significant digits), a specific date, or a named author list, it must carry a citation to a verifiable source. If the citation cannot be provided, downgrade the claim to "approximately" or flag it as an estimate. Unsourced precision is a hallucination signal, not a quality signal.
- Cast a wide net. Prioritize coverage breadth — survey the full landscape before going deep on any subtopic
- Include quantitative survey data and adoption statistics where available
- When reporting survey findings, note: who conducted it, sample size, methodology, and date
- Create comparison tables where multiple options/tools/frameworks exist
- This report will be cross-referenced against reports from other AI platforms. Prioritize comprehensive coverage and quantitative data that other platforms might not surface.
```

### ChatGPT Deep Research Wrapper

**File**: `prompt_ChatGPT-DR_{{TOPIC_SLUG}}.md`

Insert the complete Core Brief, then append:
```markdown
## Additional Instructions for This Platform
- Search across diverse source types — academic, practitioner, news, community
- For each finding, classify the source type and note typical reliability
- Where you find strong disagreement between sources, report both positions with evidence
- Include any relevant historical context that helps explain current state
- This report will be cross-referenced against reports from other AI platforms. Prioritize sources and perspectives that provide unique angles on the topic.
```

---

## Platform Tuning Notes

The Platform Wrappers above set the baseline for each platform. This section documents the per-platform tuning knowledge that *informs* those wrappers — why each one says what it says, what it's compensating for, and when to deviate. Read this when generating prompts for an unusual topic or when debugging a platform that's producing weak output.

### Tuning levers that actually move the needle

| Lever | Claude DR | Perplexity (Web) | Perplexity (Academic) | Gemini DR | ChatGPT DR |
|---|---|---|---|---|---|
| Role opener (e.g. "You are a senior research analyst…") | Improves analytical framing | Low signal — compresses | Low signal — compresses | Low signal | Low signal |
| Explicit per-claim citation demand | Default behavior | Required — else terse and uncited | Required — keeps it peer-reviewed | Required — under-cites by default | Required — drifts without it |
| Explicit length / depth target | Rarely needed | Helps — default is too short | Helps | Helps | Usually unneeded |
| Request extended thinking / planning pass | Available and useful | N/A | N/A | N/A | N/A |
| Table-first output structure | Accepts | Accepts | Accepts | Strong suit — lean in | Accepts |
| Bilingual search (Spanish + English) | Opt-in via instruction | Opt-in — already in wrapper | Opt-in | Opt-in | Opt-in |
| Ask for methodology + sample size per quantitative claim | High compliance | Mixed compliance | High compliance | Mixed — needs explicit ask | Mixed — needs explicit ask |

Current wrappers apply exactly one role opener (Claude DR). That asymmetry is deliberate, not oversight — adding role openers to the other three did not improve output quality in informal testing and sometimes degraded it. This is tracked in `BACKLOG.md` (D7) as an open question pending empirical validation.

### Known failure modes, per platform

**Claude DR.** Produces rigorous analysis but can under-source — arrives at a framework faster than it arrives at citations. The Source Inventory table in the Core Brief is the structural counter. If outputs are still thin on sources, add an explicit minimum source count in the Additional Instructions block.

**Perplexity (Web).** Prone to aggregator sources (SEO-optimized summaries of other sources) and to under-sourcing niche topics. The wrapper's ask for "blog posts, YouTube walkthroughs, conference talks" is meant to push toward primary sources. If aggregators still dominate, add an explicit "do not cite content aggregator sites (Medium listicles, SEO roundups) — link to the primary source they reference" instruction. Additionally, Perplexity-Web uses inline `[cite:N]` markers that often lack a matching numbered bibliography, making source verification impossible. The v1.4 wrapper now requires a numbered "Sources" section resolving every marker, with a fallback to inline parenthetical citations if a bibliography can't be produced.

**Perplexity (Academic).** When a plausible-sounding citation is expected but not findable, the model can fabricate DOIs. The D6 tightening (author + year + venue + DOI required, or report the gap) is the structural counter — a missing field converts what would have been a fabrication into a gap statement, which is honest. Watch for a rise in "gap statement" frequency after v1.1 on academic passes; that's the intended substitution, not a regression.

**Perplexity DR (both Web and Academic).** Generation-collapse failure mode: the model completes its research pass (tens of internal research steps, hundreds of sources indexed), outputs the phrase *"I now have sufficient evidence to compile the comprehensive report. Let me build it now."*, appends the source bibliography, and exits without producing the report body. The prompt is echoed back verbatim as the "output." Observed 2026-04-19 on topic `gt-suicide-crosslang` (v1.3.1, Academic pass): 46 research steps, 273 sources, zero report body; re-prompting restarted the research loop and hit the same wall with fewer sources. Root cause: the full Core Brief output spec (8 sections including Adversarial Self-Check with its new-search requirement, 7-dimension Self-Assessment with per-dimension justification, and Open Self-Critique) exhausts Perplexity's per-turn output-generation budget before the report body begins. Perplexity's research/write phases are not cleanly separated the way Claude DR and Gemini DR are. **Structural counter (v1.3.2):** both Perplexity wrappers now override the Core Brief output format to omit §5, §7, §8 on Perplexity passes only. Verified 2026-04-19 on the same topic with a hand-stripped prompt — Perplexity produced all 5 retained sections with proper YAML header, filled Locale-Fitness Matrix, and 19-source Source Inventory. Tradeoff: no Perplexity self-scored Tier 1 metadata in Phase 2. Acceptable because Phase 3 scoring runs independently against the report body, so the loss is diagnostic-only (can't compare self-score to independent score for Perplexity), not substantive.

**Gemini DR.** Breadth bias. Will enumerate many sources shallowly rather than fewer sources deeply. Counter: require per-finding depth (methodology, sample size, effect size where applicable) alongside coverage. Gemini-DR also produces confident-sounding but under-cited specifics — exact figures, dates, and author lists stated without verifiable sources. Observed across Sessions #8–9 (IBA ">95% survival" conflation, multiple attribution hallucinations). The v1.4 wrapper adds two structural controls: (a) DOI or direct URL required for every cited paper, with "DOI not found" flagging for sources that lack one; (b) a specificity-without-verification counter requiring citations for any precise figure, specific date, or named author list, with downgrade to "approximately" if unverifiable.

Gemini DR also silently drops the YAML metadata header specified in the Core Brief. Observed 2026-04-17 on topic `mexico-city-urban-reforestation` (v1.3): Gemini jumped straight to a prose title, skipping the entire YAML block, while Claude-DR, Perplexity-Academic, and Perplexity-Web on the same topic produced correct headers. The v1.3.1 wrapper now re-states the YAML requirement as its first bullet. Watch subsequent Gemini-DR passes to confirm compliance lifts; if drops continue, escalate to an in-Core-Brief Gemini-specific pre-header reminder.

**ChatGPT DR.** Tone drift toward executive-summary register even when the topic is academic. The wrapper's "source type classification" instruction partly counters this, but if register matters (e.g., thesis research), specify audience explicitly in `{{DECISION_CONTEXT}}` — e.g., "Audience: doctoral committee; register: formal academic prose with methodological specificity."

### When to deviate from the default wrapper

- **Topic is quantitative/empirical-heavy.** Consider running a second academic-style pass on a different platform (e.g., ChatGPT with an explicit "peer-reviewed only" instruction added) alongside Perplexity-Academic, rather than a single academic pass. This gives two independent empirical surfaces for convergence analysis.
- **Topic is early-stage or emerging practice** (new tool, recent methodology). Lean harder on Perplexity-Web; tighten `{{RECENCY_WINDOW}}` to 6 months; reduce expectations on Perplexity-Academic (peer review lags by 12–24 months, so this surface will be thin and that thinness is itself the finding).
- **Topic is cross-jurisdictional or regulatory.** Switch source profile to Legal/Regulatory, and add jurisdiction-specific framing to `{{GEO_SCOPE}}` and `{{DECISION_CONTEXT}}` — not to the Additional Instructions block, where it gets dominated by the existing platform-specific guidance.
- **Topic is adversarial** (evaluating vendor claims, competitive intelligence). Strengthen the aspiration-vs-demonstration language in Evidence Standards by adding a line like "Treat any claim sourced from vendor marketing, vendor-sponsored studies, or vendor blog posts as a *claim about what the vendor says they do*, not as evidence that they do it. Label accordingly."

### Anti-patterns

- **Stacking role openers.** One role framing helps Claude DR. Piling on ("you are also a critical reviewer / fact-checker / peer-reviewer") splits attention and degrades output. Pick one frame.
- **Over-specifying output structure.** The Core Brief already defines 8 sections. Adding more sections via the Additional Instructions block fragments attention and weakens each section. If a topic genuinely needs an extra section, add it to `{{DOMAIN_SPECIFIC_SECTIONS}}` rather than to the wrapper.
- **Translating the whole prompt for non-English research.** Keep the prompt in English. Use `{{WHAT_TO_INCLUDE}}` or the wrapper's bilingual-search line to direct the *search scope* and *citation language*. A prompt translated into Spanish tends to narrow source coverage without improving quality.
- **Adding "be thorough" or "be comprehensive" to the wrapper.** These phrases do not change behavior — the research-mode models are already trying to be thorough. Replace with specific structural asks (minimum N sources, required fields per finding, explicit section coverage).

### Updating this section

This is a living section. When a triangulation surfaces a platform-specific behavior worth remembering — a new failure mode, a tuning lever that mattered, a deviation that worked — add it here with the topic and date (e.g., *"Observed 2026-05-XX on topic Y: Gemini DR under-cited even with explicit ask; adding table-first structure recovered coverage."*). Over time this converges on empirical per-platform guidance rather than a priori guessing, which is the point.

---

## Prompt Generation Workflow

1. Collect parameters from the user (questions live in Step 1 of SKILL.md)
2. Select source profile from `references/source-profiles.md`
3. Resolve every `{{VAR_NAME}}` in the Core Brief using the Parameter Dictionary
4. For each target platform-pass combination:
   a. Take the completed Core Brief
   b. Wrap it in the platform's wrapper (role + additional instructions)
   c. Save as `prompt_{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}.md`
5. Generate the Operator Handoff File
6. Save all files to the session's output directory and present them to the user
7. User reviews, then copies each prompt into its target platform

---

## Operator Handoff Template

**File**: `handoff_{{TOPIC_SLUG}}.md`

This file is for the user — it contains everything needed to run the research externally and collect results.

```markdown
# Research Handoff: {{TOPIC_TITLE}}

**Date generated**: {{DATE_ISO}}
**Source profile**: {{PROFILE_NAME}}
**Platform-passes**: {{LIST_OF_PLATFORM_PASSES}}

## Prompt Files

| Platform-Pass | File | Where to paste |
|---|---|---|
| Claude-DR | `prompt_Claude-DR_{{TOPIC_SLUG}}.md` | claude.ai → Deep Research mode |
| Perplexity-Web | `prompt_Perplexity-Web_{{TOPIC_SLUG}}.md` | perplexity.ai → Pro Search |
| Perplexity-Academic | `prompt_Perplexity-Academic_{{TOPIC_SLUG}}.md` | perplexity.ai → Pro Search (new session) |
| Gemini-DR | `prompt_Gemini-DR_{{TOPIC_SLUG}}.md` | gemini.google.com → Deep Research |
| ChatGPT-DR | `prompt_ChatGPT-DR_{{TOPIC_SLUG}}.md` | chatgpt.com → Deep Research |

Include only the rows corresponding to the platform-passes actually used.

## Pre-Paste Checklist (per platform)

Complete the checklist for each platform **before** pasting the prompt. Skipping a mode toggle silently invalidates the entire run.

**Claude-DR:**
- [ ] Open claude.ai → start a new conversation
- [ ] Enable Research mode (look for the Research toggle or select "Research" from the model/mode picker)
- [ ] Paste the full prompt from `prompt_Claude-DR_{{TOPIC_SLUG}}.md`

**Perplexity-Web / Perplexity-Academic:**
- [ ] Open perplexity.ai → start a new thread (separate thread per pass)
- [ ] Confirm Pro Search is enabled (toggle at bottom of input box)
- [ ] Paste the full prompt from the corresponding prompt file

**Gemini-DR:**
- [ ] Open gemini.google.com → start a new conversation
- [ ] Enable Deep Research mode (select from the model/mode dropdown — it is NOT the default)
- [ ] Confirm the model is set to Gemini with Deep Research, not standard Gemini
- [ ] Paste the full prompt from `prompt_Gemini-DR_{{TOPIC_SLUG}}.md`

**ChatGPT-DR:**
- [ ] Open chatgpt.com → start a new conversation
- [ ] Enable Deep Research mode (select from the model picker — requires Plus/Pro)
- [ ] Paste the full prompt from `prompt_ChatGPT-DR_{{TOPIC_SLUG}}.md`

Include only the checklists for platforms actually used in this run.

## General Checks

- [ ] Review each prompt file — confirm the research questions and scope match your intent
- [ ] Confirm source profile is correct: **{{PROFILE_NAME}}**
- [ ] Each prompt file is self-contained. Open, select all, copy, paste.

## Collecting Results

Save each platform's output using this naming convention:

```
{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}_{{DATE_ISO}}.md
```

Examples:
- `Claude-DR_{{TOPIC_SLUG}}_{{DATE_ISO}}.md`
- `Perplexity-Web_{{TOPIC_SLUG}}_{{DATE_ISO}}.md`
- `Perplexity-Academic_{{TOPIC_SLUG}}_{{DATE_ISO}}.md`
- `Gemini-DR_{{TOPIC_SLUG}}_{{DATE_ISO}}.md`

The platform-pass hyphen format is not optional. Two passes from the same platform (e.g., Perplexity-Web and Perplexity-Academic) are independent data points during consolidation — filename and metadata header must agree on which is which.

**Important:**
- Save as markdown (.md) when possible. If a platform only exports PDF, save as PDF.
- Do not edit or clean reports before consolidation — the consolidation prompt handles normalization.
- If a platform produces partial output (context window limit), append `_PARTIAL` to the filename: `Claude-DR_{{TOPIC_SLUG}}_{{DATE_ISO}}_PARTIAL.md`.

## Expected Timelines

| Platform | Typical completion time |
|---|---|
| Claude Deep Research | 5-15 minutes |
| Perplexity Pro Search | 2-5 minutes |
| Gemini Deep Research | 5-20 minutes |
| ChatGPT Deep Research | 5-15 minutes |

## Context Window Warnings

{{CONTEXT_WINDOW_WARNING}}

## Next Step

Once all reports are collected, return to Claude. Phase 2 triggers on any of: "consolidate these reports," "I have N reports on {{TOPIC_TITLE}}," "synthesize these research outputs," "merge these findings," or equivalent phrasings. Upload all report files with the request.
```
