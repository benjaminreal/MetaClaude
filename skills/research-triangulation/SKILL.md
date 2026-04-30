---
name: research-triangulation
description: Orchestrates research across AI platforms with Deep Research or equivalent autonomous research functionality (Claude, Perplexity, Gemini, ChatGPT, Grok, and others) to produce higher-confidence findings through convergence/divergence analysis. Use this skill whenever the user wants to triangulate research across platforms, cross-validate findings from multiple AI-generated reports, consolidate or synthesize multi-source research outputs, or design a multi-platform research process. Also trigger when the user mentions "research triangulation," "cross-platform research," "consolidation prompt," "research synthesis," "multi-model research," "deep research," or references running the same research question across different AI tools. This skill coordinates multi-platform research — for single-platform prompts, use other skills or write directly.
---

# Research Triangulation Methodology


## Purpose & Scope

### What this skill does
Orchestrates research across AI platforms with Deep Research or equivalent autonomous research functionality — Claude, Perplexity, Gemini, ChatGPT, and others (Grok DeepSearch, You.com Research, Kimi, Copilot Researcher, Manus) — to produce higher-confidence findings than any single platform delivers alone. The core mechanism: when independent systems with different training data, search access, and synthesis biases converge on a finding, confidence increases. When they diverge, the divergence itself is diagnostic.

Three phases: divergent research (parallel platform prompts) → convergent consolidation (cross-validation synthesis) → verification & scoring (quality rubric + claims tracing). Each phase can run independently.

### What this skill does NOT do
- **Single-platform prompt engineering.** Use other skills or write it directly.
- **Literature reviews or systematic reviews.** Can feed into one, not a substitute.
- **Real-time monitoring.** Point-in-time research only.
- **Primary data collection.** Synthesizes existing sources only.

### When to use this vs. something else
| Situation | Use this? | Alternative |
|---|---|---|
| High-stakes decision needing validated evidence | **Yes** | — |
| Exploring a domain where you don't know what you don't know | **Yes** | — |
| Separating vendor claims from demonstrated evidence | **Yes** | — |
| Quick fact-check or single question | No | Direct query to one platform |
| Need a research prompt for one platform | No | Other skills, direct prompting |
| Academic literature review with citation management | No | Dedicated lit review tools |
| Competitive intelligence with ongoing tracking | Phase 1 only | Pair with competitive analysis workflow |

## Pre-flight Checklist

Before starting any phase, answer these questions. Ask the user if not provided — don't infer.

1. **Objective**: What decision or action does this research support?
2. **Audience**: Who reads the output? (Affects register, depth, language)
3. **Domain confidence**: How much does the user already know about this topic? (Prevents restating basics; flags when the user may not recognize bad output)
4. **Known context**: What has the user already researched or decided? (Prevents redundant coverage)

## Entry Points

Each phase can be invoked independently. Identify which phase the user needs based on these triggers:

### → Phase 1: Divergent Research
**Triggers**: "help me research [topic] across platforms," "create research prompts for [topic]," "I need a multi-platform research on [topic]," "generate research prompts," "research prompt for Perplexity/Gemini/Claude," "deep research on [topic]"
**What happens**: Steps 1-4. Ask clarifying questions, select source profile, generate N separate prompt files (one per platform) + operator handoff file. Pause — user executes prompts externally.
**Deliverables**: One self-contained prompt file per platform + one operator handoff file. See "Phase 1 Output Format" below.

### → Phase 2: Convergent Consolidation
**Triggers**: "consolidate these reports," "I have N reports on [topic]," "synthesize these research outputs," "merge these findings," "cross-validate these reports," user uploads multiple research report files
**What happens**: Steps 5-6. Generate the consolidation prompt as a self-contained file, or run consolidation directly if reports are uploaded to this conversation.
**Deliverables**: One consolidation prompt file (if generating for external use) or the consolidated report itself (if running in-session).

### → Phase 3: Verification & Scoring
**Triggers**: "score this report," "evaluate this research," "run quality check," "grade these outputs," "how good is this report"
**What happens**: Steps 7-10. Generate scoring agent prompts (copy-paste into fresh AI sessions) or run scoring directly if the report is in context.
**Deliverables**: Tier 1 and/or Tier 2 scorecards, key claims verification results, platform tracker log entry.

### → Full Cycle
**Triggers**: "run the full research process on [topic]," "full research cycle," "end-to-end research"
**What happens**: Steps 1-4, then pause for external execution, then Steps 5-10 when reports arrive.
**Deliverables**: All of the above, sequentially.

## Phase 1: Divergent Research

### Step 1: Define the Research Brief

Pre-flight questions should already be answered. Now define the Phase-1-specific parameters:

1. **Research questions**: What specific questions must be answered? (Primary + secondary)
2. **Source profile**: Which source priority profile applies? → Read `references/source-profiles.md`
3. **Depth mode**: Full (default) or Light? Full produces the complete 8-section output spec. Light trims to 5 sections for mid-capability DR agents or when a lighter output is acceptable. The depth mode determines the section profile applied during prompt assembly — see `references/section-profiles.md`.
4. **Recency window**: How recent must sources be? (Default: 18 months, accept foundational older work)

### Step 2: Select and Configure Source Profiles

Read `references/source-profiles.md` to select the appropriate source priority profile. Available profiles:
- **Academic-first**: Peer-reviewed journals, empirical studies, then practitioner validation
- **Practitioner-first**: Documented implementations, case studies, then academic scaffolding
- **Legal/regulatory**: Statutes, jurisprudence, regulatory guidance, then practitioner interpretation
- **Market/competitive**: Industry reports, vendor analysis, then independent validation
- **Mixed/exploratory**: Equal weighting, used when you don't yet know where the best evidence lives

The source profile determines the source hierarchy instructions embedded in each platform's research prompt.

### Step 3: Select Platforms and Generate Research Prompts

**Before generating any prompts, ask the user which platforms they have access to and intend to run.** Generate prompts only for the confirmed set — do not emit prompts for platforms the user cannot or does not want to use. If the user doesn't specify, present the platform list below and ask them to pick.

Read `references/phase1-templates.md` for the parameterized prompt templates. Each template has:
- A model-agnostic core (research questions, scope, constraints, output format)
- A section profile that selects which output sections to include based on platform and depth mode — see `references/section-profiles.md`
- Platform-specific wrappers that exploit each platform's strengths
- Source profile instructions matched to the selected profile, in a deterministic structured export format — see `references/source-profiles.md`

**Platform assignment strategy** (default, adjust based on topic):
- **Claude Deep Research**: Best for synthesis-heavy topics. Assign when you need analytical depth and framework integration.
- **Perplexity Pro (Web focus)**: Best for recent practitioner content, blog posts, conference talks, social media signals. Assign for recency and breadth.
- **Perplexity Pro (Academic focus)**: Run as a separate pass with explicit academic source instructions. Best for peer-reviewed empirical evidence.
- **Gemini Deep Research**: Best for broad landscape surveys and quantitative data synthesis. Assign when coverage breadth matters.
- **ChatGPT Deep Research**: Best for diverse source types and exploratory searches. Good complementary pass.

Other platforms with Deep Research or equivalent functionality (Grok DeepSearch, You.com Research, Kimi, Copilot Researcher, Manus) can be used — the Core Brief template is model-agnostic. Generate a wrapper following the existing pattern if the user requests a platform not listed above.

**Minimum: 3 platform-passes. Recommended: 4 (including at least one academic-focused pass).**

### Phase 1 Output Format

Generate each deliverable as a **separate file**. The user needs to copy-paste each prompt into a different platform — mixing operator instructions with prompt content creates friction.

**Prompt files** (one per platform, contains ONLY the prompt — no operator notes, no "how to use" text):
```text
prompt_Claude-DR_{topic-slug}.md
prompt_Perplexity-Web_{topic-slug}.md
prompt_Perplexity-Academic_{topic-slug}.md
prompt_Gemini-DR_{topic-slug}.md
prompt_ChatGPT-DR_{topic-slug}.md
```

Each prompt file is self-contained: the user opens it, selects all, copies, and pastes into the target platform. Nothing else needed.

**Operator handoff file** (one file, contains checklist and instructions for the user):
```text
handoff_{topic-slug}.md
```

Contains: the handoff checklist from Step 4, file naming conventions for collecting outputs, expected completion timelines, context window warnings, and any topic-specific notes.

Save all files to `/mnt/user-data/outputs/` and present them to the user.

### Step 4: Handoff Checklist

Before the user runs the prompts, provide this checklist:

- [ ] All prompts reviewed and customized for the specific topic
- [ ] Source profile confirmed and instructions embedded in each prompt
- [ ] Output format specified consistently across all prompts (markdown preferred)
- [ ] File naming convention agreed: `{Platform}-{Pass}_{topic-slug}_{YYYY-MM-DD}.md` (e.g., `Claude-DR_small-bets_2026-04-04.md`, `Perplexity-Academic_small-bets_2026-04-04.md`). Pass-type in filename is mandatory — see `references/phase1-templates.md` for valid pass types per platform.
- [ ] Expected completion timeline noted per platform
- [ ] Context window limits considered — flag if topic may require split sessions

**File collection protocol:**
- Save each platform's output as markdown or PDF immediately upon completion
- Do not edit or clean reports before consolidation — the consolidation prompt handles normalization
- If a platform produces partial output (context window limit), note which sections are incomplete
- Name files consistently so the consolidation prompt can reference them clearly

## Phase 2: Convergent Consolidation

### Step 5: Generate the Consolidation Prompt

Read `references/consolidation-template.md` for the parameterized consolidation prompt. Configure:

- **Number of input reports** (3-5, adjusts the comparison matrix dimensions)
- **Decision context** (carried forward from Phase 1)
- **Organizational context** (if recommendations need to be grounded in specific constraints)
- **Output language** (default: English; specify a secondary language only when explicitly needed for the audience)

**Two modes of operation:**

**Mode A — Generate prompt file for external use**: Produce a self-contained file `consolidation_{topic-slug}.md` containing only the prompt. The user uploads this file + all Phase 1 reports to Claude (Opus preferred) in a separate session. Use this mode when context window limits require a fresh session or when the user wants to run consolidation later.

**Mode B — Run consolidation in-session**: If the user has uploaded all Phase 1 reports to this conversation, run the consolidation directly using the template's analytical protocol. Produce the consolidated report as a markdown file `consolidated_{topic-slug}.md`. Use this mode when all reports fit in context.

The consolidation prompt mandates six analytical operations:
1. Individual report audit and quality assessment
2. Cross-report triangulation with convergence matrix
3. Unique discovery classification (novel insight / potential hallucination / vendor echo)
4. Contradiction resolution with documented tensions
5. Evidence hierarchy application with confidence levels
6. Strategic synthesis with actionable recommendations

### Step 6: Run Consolidation

- Upload all Phase 1 reports plus the consolidation prompt to Claude (Opus preferred for analytical depth)
- If total input exceeds context window: split into two sessions
  - Session A: Upload all reports + Phases 1-3 of consolidation (audit, triangulation, evidence hierarchy). Save output.
  - Session B: Upload Session A output + Phases 4-6 (synthesis, recommendations, self-critique). Complete.

### Analytical Standards (apply in every consolidation)

These are non-negotiable analytical lenses embedded in the consolidation prompt:

- **Aspiration vs. demonstration**: Organizations "talking about doing something" is categorically different from "demonstrating they have done it." Never conflate announced intentions with verified implementations.
- **Vendor bias correction**: Vendor-sponsored studies overstate gains. Independent RCTs show modest or negative results for experienced practitioners. Flag provenance of every major claim.
- **Source hierarchy enforcement**: Replicated experiments > single experiments > case studies with metrics > expert frameworks > industry reports > vendor claims > opinion/speculation.
- **±15% / 2-of-3 convergence threshold**: Quantitative claims that converge within ±15% across 2+ independent sources get confidence boost. Divergent claims get flagged, not averaged.
- **GRADE-inspired upgrade/downgrade**: Findings start at their evidence-hierarchy level, then get downgraded for inconsistency, indirectness, or imprecision — and upgraded for large effect size, dose-response, or 3+ source convergence.

## Phase 3: Verification & Scoring

### Step 7: Score Individual Reports (Tier 1)

Read `references/quality-rubric.md` for the full scoring protocol and agent prompts.

**This step gates consolidation.** Score each Phase 1 report before starting Phase 2. Reports below threshold do not enter consolidation — flag them to the user for re-run or exclusion.

Each report is scored by an independent AI agent (a different instance, never the same model that produced the report) on 7 dimensions, each 1-5:

1. **Source traceability** — Can every major claim be traced to a named, linkable source?
2. **Source quality distribution** — What % of sources are high-trust vs. low-trust?
3. **Hallucination rate** — Spot-check 10 claims: how many are fabricated?
4. **Coverage breadth** — Did the report address all research questions?
5. **Coverage depth** — Beyond surface-level summaries?
6. **Recency compliance** — What % of sources fall within the specified window?
7. **Actionability** — Could you act on this report alone?

**Minimum threshold to enter consolidation: 3.0 average, no single dimension below 2.0.**

**Score persistence:** Save each scorecard as `scorecard_{platform}_{topic-slug}.json` alongside the report. Structure: `{ "platform": "", "topic": "", "date": "", "dimensions": { "source_traceability": N, ... }, "composite": N, "flags": [] }`. These files feed into Step 10 (platform tracking) and are referenced during consolidation.

### Step 8: Score Consolidation Report (Tier 2)

The consolidation output is scored on 6 dimensions, each 1-5:

1. **Triangulation rigor** — Systematic convergent/divergent mapping?
2. **Contradiction handling** — Disagreements investigated and resolved or documented?
3. **Unique discovery assessment** — Single-source findings classified with reasoning?
4. **Evidence hierarchy application** — Recommendations weighted by evidence quality?
5. **Synthesis vs. summary** — Genuinely integrated analysis with emergent findings?
6. **Decision readiness** — Audience can act without re-reading source reports?

**Minimum threshold for usable consolidation: 3.5 average.**

**Score persistence:** Save as `scorecard_consolidation_{topic-slug}.json` alongside the consolidated report. Same structure as Tier 1 scorecards but with the 6 consolidation dimensions.

### Step 9: Key Claims Verification

After scoring, the top 5-10 highest-impact findings from the consolidation are spot-checked:

- Trace each claim back to its cited source(s) in the Phase 1 reports
- Trace the Phase 1 citation back to the original external source (if possible)
- Classify verification result: **Confirmed** / **Partially confirmed** / **Unverifiable** / **Contradicted**
- Any claim rated "Unverifiable" or "Contradicted" gets flagged in the final output with a warning

### Step 10: Log Results for Platform Tracking

Read `references/platform-tracker.md` for the tracking format. After each complete research cycle, log:
- Topic, date, source profile used
- Tier 1 scores per platform (7 dimensions + composite)
- Tier 2 consolidation score (6 dimensions + composite)
- Notable platform strengths/weaknesses observed
- Any prompt modifications that improved results

Over time, this builds a dataset for optimizing which platforms to assign to which types of research questions and how to adjust prompt instructions per platform.

## Decision Rules

### When to cross-validate
- **Always** for quantitative claims that drive recommendations (revenue figures, adoption rates, effect sizes)
- **Always** for causal claims ("X causes Y," "X leads to Y")
- **Not required** for background context, definitions, or well-established historical facts

### When to use adversarial follow-up (Phase 2)
Trigger adversarial follow-up during consolidation when:
- A finding appears to converge across reports but may trace to a shared weak source (echo, not convergence)
- A single-source finding carries high decision weight
- Quantitative claims converge but lack independent methodologies

**How:** The consolidating model identifies findings that need adversarial testing and generates 5-7 specific probing questions per finding. An independent agent (different model instance) runs these questions on any available platform. Results are returned to the consolidating model, which adjusts confidence levels accordingly.

Note: Phase 1 adversarial follow-up is embedded in the research prompt templates — see `references/phase1-templates.md`.

### Restart vs. iterate
- **Restart the platform pass** when: the report scored below threshold on coverage breadth or depth. The prompt missed the target — rewrite with tighter scope or different framing.
- **Drop the platform** when: the report scored below threshold on source traceability or hallucination rate, and at least 3 other reports passed threshold. Proceed without it.
- **Replace the platform** when: the report scored below threshold on source traceability or hallucination rate, and dropping it would leave fewer than 3 reports. Run an additional pass on a different platform.
- **Iterate on consolidation** when: Tier 2 scores are below threshold but Tier 1 inputs were solid. The problem is synthesis — adjust the consolidation prompt and re-run.
- **Restart the full cycle** when: all Tier 1 reports score below 3.0. The research brief or source profile was wrong — return to Pre-flight.

### When to split consolidation
- **Split** when total input reports exceed the context window of the consolidation platform
- **Split** when more than 5 reports are being consolidated — analytical quality degrades with too many simultaneous inputs
- **How:** Session A handles audit + triangulation + evidence hierarchy. Session B takes Session A's output and completes synthesis + recommendations.

## Reference Files

| File | When to read |
|---|---|
| `references/phase1-templates.md` | Always read when generating Phase 1 research prompts |
| `references/consolidation-template.md` | Always read when generating the consolidation prompt |
| `references/quality-rubric.md` | Always read when scoring (contains agent prompts and rubric details) |
| `references/source-profiles.md` | Read during Step 2 to select and configure source priorities. Contains the structured export format for `{{INJECTED_SOURCE_PROFILE}}` injection. |
| `references/section-profiles.md` | Read during Step 3 to select the section profile for each platform-depth combination. Determines which Core Brief output sections appear in each prompt. |
| `references/platform-tracker.md` | Read during Step 10 to log results; consult before Step 3 for historical platform performance |

## Test Cases for This Skill

Use these to verify the skill produces correct outputs:

1. **"Help me research [new topic] across multiple platforms"** → Should trigger full Phase 1 workflow: ask clarifying questions, select source profile, generate platform-specific prompts, provide handoff checklist
2. **"I have 4 research reports on [topic], help me consolidate them"** → Should trigger Phase 2: generate parameterized consolidation prompt, provide context window guidance
3. **"Score this research report"** → Should trigger Phase 3 Tier 1: generate scoring agent prompt with the 7-dimension rubric
4. **"Create a research prompt about [topic] for Perplexity/Gemini/Claude"** → Should trigger Phase 1 Steps 1-3 with platform-specific customization

## Version & Changelog

**Current version:** 1.5.1
**Author:** Benjamín Calderón

### 1.5.1 (2026-04-29) — Benjamín Calderón

Gemini-DR YAML header: confirmed as architectural constraint, removed dead prompt instruction.

- **Removed YAML-header instruction from Gemini wrapper.** The v1.3.1 fix (elevated YAML requirement to first wrapper bullet) never worked — Gemini Deep Research's synthesis pipeline does not support structured outputs per Google's own API documentation. Tested 2026-04-29 with three alternative prompt strategies (pre-prompt positional anchor, output continuation seed, visual box-drawing copy-action framing) on topic `flowerpot-top50`; all three failed identically. Root cause: the DR synthesis stage applies its own formatting model and performs self-critique passes that restructure content — YAML frontmatter is outside its output vocabulary. This is not fixable via prompt engineering.
- **Updated Known failure modes for Gemini DR** in `references/phase1-templates.md` to document the architectural constraint with evidence trail (3 topics, 5 prompt variants, 0 successes) and recommended workaround (manual YAML prepend post-export or Phase 2 metadata inference).
- **No methodology or consolidation-template changes.** Phase 2 consolidation already handles Gemini reports without YAML — confirmed 2026-04-28 on the flowerpot v1.5 acceptance run.

### 1.5 (2026-04-22) — Benjamín Calderón

Parameterize the Core Brief contract: platform x depth section profiles + source-injection contract. Two bundled items that share the same Core Brief variable-contract surface.

- **Parameterized Core Brief with platform x depth section profiles.** New file `references/section-profiles.md` defines three profiles (`standard-full`, `perplexity-optimized`, `light`) that declare which Core Brief output sections a given platform-depth combination produces. Replaces the ad-hoc Perplexity wrapper overrides (which omitted §5/§7/§8 inline) with a structural profile system. The v1.3.2 Perplexity behavior is now reproduced through the `perplexity-optimized` profile with no wrapper-level override. Light mode (new) trims the output spec for mid-capability DR agents — motivated by an external cold-user test (2026-04-20) where a Sonnet-class agent crashed on the full 8-section spec. Adding a new platform or depth mode is now a profile definition, not a wrapper edit.
- **Depth mode in Step 1.** Step 1 now asks the user to select Full (default, 8-section output) or Light (5-section output for mid-capability agents). The depth mode feeds into the section profile lookup during prompt assembly.
- **D14 — source-hierarchy injection contract.** `{{INJECTED_SOURCE_PROFILE}}` now has a defined target shape. Every source profile in `references/source-profiles.md` lists platform search instructions under identical headers (Claude Deep Research, Perplexity Web, Perplexity Academic, Gemini Deep Research, ChatGPT Deep Research) so the substitution is deterministic. A Structured Export Format section at the top of the file defines exactly what gets pasted and how. Previously, profiles had inconsistent formatting — some grouped platforms, some listed "Same as Claude," some omitted ChatGPT entirely — making paste behavior vibes-based.
- **Assembly process updated.** The prompt assembly process in `references/phase1-templates.md` gains two new steps: (3) look up the section profile for this platform-depth combination, (4) prepend the section-selection preamble if the profile omits sections. Source injection step updated to reference the structured export format.
- **Structural eval extended.** Four new checks in `evals/structural_eval.py`: section profile schema validation, profile-wrapper-no-override enforcement, source profile export format consistency, and section coverage completeness. Total: 10 checks (6 existing + 4 new).

### 1.4 (2026-04-22) — Benjamín Calderón

Lean quality and UX pass driven by an external cold-user test (2026-04-20) and retrospective quality audits across Sessions #8–9. Eight items, each independently shippable.

- **Platform-selection gate at Phase 1 entry.** Step 3 now requires asking the user which platforms they have access to before generating prompts. Eliminates unreachable prompt files (e.g., ChatGPT-DR prompts for users without Plus/Pro). The skill also now acknowledges platforms beyond the core four — Grok DeepSearch, You.com Research, Kimi, Copilot Researcher, Manus — as valid targets using the model-agnostic Core Brief.
- **Skill description updated to "AI platforms with Deep Research or equivalent functionality."** Replaces the ambiguous "across platforms" phrasing. Added "deep research" as a trigger phrase.
- **Perplexity-Web numbered bibliography requirement.** Wrapper now mandates that every `[cite:N]` marker resolve to a numbered entry in a final "Sources" section (number, author/site, title, URL, year). Fallback: switch to inline parenthetical citations if bibliography can't be produced. Restores Tier 2 source-verification auditability for Perplexity-Web passes.
- **Gemini-DR DOI-required + specificity-without-verification counter.** Two new structural controls in the Gemini-DR wrapper: (a) every cited paper must carry a DOI or direct URL, with "DOI not found" flagging for sources that lack one; (b) any precise figure (>3 significant digits), specific date, or named author list must carry a citation — otherwise downgraded to "approximately" or flagged as estimate. Targets Gemini's documented pattern of confident but under-cited specifics (Sessions #8–9).
- **Cross-platform author-attribution countermeasure in Evidence Standards.** Core Brief now requires cross-checking author lists for 3+ author works against an independent reference (publisher page, CrossRef, Google Scholar). If cross-check can't be performed, author list reduces to `[first-author] et al.` rather than reproducing an unverified list. Trade-off: small recall hit on full author lists in exchange for precision gain on attribution accuracy.
- **Convergence-threshold awareness in Phase 1 prompts (D10).** Evidence Standards now informs research agents that downstream consolidation applies a ±15% convergence threshold, requesting point estimates with uncertainty ranges where possible.
- **Deep-Research mode pre-flight checklist in handoff.** Replaced the generic "Before You Run" section with per-platform pre-paste checklists (Claude-DR, Perplexity, Gemini-DR, ChatGPT-DR) specifying exact mode toggles to enable before pasting. Prevents silently invalidated runs from missing mode toggles.
- **D6 — citation-compliance observation discipline.** Not a code change. As v1.4 items get exercised on real triangulations, per-platform citation-compliance behavior should be systematically recorded in platform-tracker entries.

### 1.3.2 (2026-04-19) — Benjamín Calderón

Targeted Perplexity-DR generation-collapse fix surfaced by a real-world run on topic `gt-suicide-crosslang` (SCM donor-pool validation for a Master's thesis). Perplexity Deep Research completed 46 internal research steps, indexed 273 sources, emitted the phrase *"I now have sufficient evidence to compile the comprehensive report. Let me build it now."*, appended its bibliography, and terminated without producing the report body. Re-prompting restarted the research loop and hit the same wall. Root cause: the full Core Brief output spec (8 sections — including §5 Adversarial Self-Check with its mid-write new-search requirement, §7 seven-dimension Self-Assessment with per-dimension justification, and §8 Open Self-Critique) exhausts Perplexity's per-turn output-generation budget before the report body begins. Claude DR and Gemini DR have cleaner research/write phase separation and are unaffected. Patch:

- Both Perplexity wrappers (`Perplexity-Web` and `Perplexity-Academic`) in `references/phase1-templates.md` now open with an **Output format override** bullet instructing the model to omit Core Brief sections 5, 7, and 8 and produce only the 5 retained sections (Executive Summary, Findings by RQ, Domain-Specific Sections, Source Inventory, Gaps), renumbered §1–§5.
- Added **Perplexity DR (both Web and Academic)** entry to *Known failure modes, per platform* documenting the echo-and-exit pattern with dated observation, root-cause reasoning, and structural counter.
- Tradeoff explicitly documented: no Perplexity self-scored Tier 1 metadata reaches Phase 2. Acceptable because Phase 3 scoring runs independently against the report body — the loss is diagnostic-only (can't compare self-score to independent score for Perplexity passes), not substantive.

Verified by re-running the same topic with a hand-stripped prompt: Perplexity produced all 5 retained sections with proper YAML header, the full Locale-Fitness Matrix with admissibility verdicts, and a 19-source Source Inventory. No methodology, rubric, or consolidation-template changes.

### 1.3.1 (2026-04-17) — Benjamín Calderón

Targeted Gemini-DR YAML compliance fix surfaced by a retrospective quality audit across four projects (LitReview_v1, Small_bets_v1, flowerpot_v1, mexico-city_v1.3). The audit found that Gemini-DR silently drops the YAML metadata header mandated by the Core Brief even in v1.3 — the only platform to do so. All three other platforms on the same topic produced correct headers. Patch:

- Elevated the YAML-header requirement to the first bullet of the Gemini wrapper in `references/phase1-templates.md`, with an explicit note that Gemini has a documented tendency to drop it.
- Expanded the **Gemini DR** entry in *Known failure modes, per platform* to document the drop pattern with topic + date, and flagged an escalation path (in-Core-Brief pre-header reminder) if the next Gemini-DR passes still drop the header.

No changes to methodology, rubric, or consolidation template. The audit also surfaced cross-platform author-attribution hallucinations (the same paper credited to different author lists across reports) as a candidate for a v1.4 prompt-level control — captured in `BACKLOG.md` for the next feature cycle.

### 1.3 (2026-04-15) — Benjamín Calderón

Documentation and tooling polish pass. No methodology changes.

- Added a human-facing **`README.md`** at the skill root. Written by regenerating via the `skill-doc-generator` after patching four bugs in that generator (broken reference-file links, truncated trigger extraction, weak example selection, missing non-standard directories). The patched generator lives at `../tooling/skill-doc-generator-patched/` with `PATCH_NOTES.md` documenting each fix — consider upstreaming after a few more skills have exercised it.
- Added a tagged `text` language on the two previously-bare code blocks in "Phase 1 Output Format". Surfaced a related validator bug (collapsed "no tag" and explicit `text`) which is fixed in the patched copy.
- **`examples/` directory** scaffolded with a README differentiating it from `evals/fixtures/`. Intended for real archived triangulations (Phase 1 prompts + reports + consolidations) as quality anchors; empty pending first archival-worthy run.
- Closed the **"Overview vs. Purpose & Scope"** INFO flag in `BACKLOG.md` as a documented decision rather than a deferred item. Purpose & Scope serves the Overview role; renaming would trade accurate framing for validator compliance.
- Ran skill-description optimization via `skill-creator`'s `run_loop.py` for 5 iterations with a 20-query eval set at `evals/trigger-eval-set.json` (10 should-trigger, 10 should-not-trigger). Result: flat trigger rate (6/12 train, 4/8 test) across every proposed variant, including three rewrites that explicitly named all four platforms. The loop correctly kept the original description as "best" since nothing improved on it. Closed the description-optimization BACKLOG item with the empirical finding: the ~50% trigger ceiling is structural (Claude's skill-selection logic for research-methodology queries), not fixable through wording changes. Also closes the two related validator INFOs (description length, vague term "multiple") as unresolvable-by-rewording. Full artifacts in `evals/description-optimization/2026-04-15_174301/`.

### 1.2 (2026-04-15) — Benjamín Calderón

Closing out two Session #2 residual items that had been deferred to BACKLOG.md:

- Added **Platform Tuning Notes** section to `references/phase1-templates.md`, documenting per-platform tuning levers (role openers, citation demand, length, extended thinking, table-first output, bilingual search, methodology asks), known failure modes per platform with structural counters, when to deviate from the default wrapper, and observed anti-patterns. The section is deliberately a living document — new platform-specific observations get added with topic + date stamps as triangulations accumulate.
- Added **structural eval suite** at `evals/` with six deterministic checks (parameter dictionary completeness, reference-file integrity, pass-type consistency, metadata schema consistency, fixture filename conformance, fixture metadata header completeness). Runs in seconds, no dependencies beyond Python stdlib, exits non-zero on any failure. Fixtures under `evals/fixtures/` double as golden structural examples of a prompt file and a report file. README documents scope — the eval covers the skill's internal consistency and fixture conformance, not research quality (Tier 1/2 rubrics' job) and not skill triggering (skill-creator's description-optimization loop's job).

### 1.1 (2026-04-15) — Benjamín Calderón

SKILL.md structural upgrade:
- Renamed skill from `multi-platform-research` to `research-triangulation`
- Added Purpose & Scope section with explicit boundaries (does / does not do / decision table)
- Added Pre-flight Checklist for intent clarification before research starts
- Added Decision Rules for cross-validation, adversarial follow-up, restart vs. iterate
- Removed hard-coded platform list — skill is now platform-agnostic by default
- Updated triggering description to coexist with other research skills

Core prompt template upgrade (`references/phase1-templates.md`):
- Standardized variable convention: all placeholders use `{{VAR_NAME}}` double-brace format
- Added Parameter Dictionary at the top of the template as single source of truth for every variable (purpose, default, how to obtain)
- Formalized platform-pass file naming convention: `{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}_{{DATE_ISO}}.md`, with valid pass types per platform documented explicitly
- Added required YAML metadata header for every report (topic, platform, pass, date, source_profile, primary_question, recency_window) — enables structural identification of reports during consolidation
- Embedded Adversarial Self-Check section in the Core Brief output format (Section 5): model must identify three high-stakes claims, search for disconfirming evidence, and revise before finalizing. Cross-references Phase 2 consolidation's own adversarial follow-up so the division of labor is clear.
- Tightened Evidence Standards citation format: every cited source must include author(s), year, venue/publisher, and DOI/stable URL. If any field is missing, the source cannot be cited — report the gap instead.
- Replaced open-ended Self-Critique with scored Self-Assessment aligned to the Tier 1 scoring rubric (7 dimensions, 1-5 scale with per-dimension justification), plus an Open Self-Critique section for failure modes outside the dimensions
- Removed optional Spanish executive summary instruction

Consolidation template upgrade (`references/consolidation-template.md`):
- Added explicit same-platform independence instruction: passes from the same platform with different focus profiles count as independent data points in the Convergence Matrix
- Restructured Input Reports inventory to require Platform and Pass Type as separate columns

### 1.0 (2026-04-04) — Benjamín Calderón
- Initial MVP: three-phase methodology (divergent → convergent → verification)
- Five reference files: phase1-templates, consolidation-template, quality-rubric, source-profiles, platform-tracker
- Tested with Claude DR, Perplexity Pro, Gemini DR, ChatGPT
