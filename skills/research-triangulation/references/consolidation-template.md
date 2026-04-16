# Phase 2: Consolidation Prompt Template

This is a parameterized template for generating the consolidation prompt that synthesizes multiple Phase 1 research reports into a single, integrated analysis.

## Parameters

| Parameter | Description | Example |
|---|---|---|
| `{TOPIC_TITLE}` | Research topic | "Small Bets Framework and Portfolio Entrepreneurship" |
| `{NUM_REPORTS}` | Number of input reports (3-5) | 4 |
| `{REPORT_LIST}` | Description of each report with platform and focus | See below |
| `{DECISION_CONTEXT}` | Carried from Phase 1 | "Inform my post-employment income strategy" |
| `{ORG_CONTEXT}` | Optional organizational context for grounded recommendations | Multiplica description, constraints, etc. |
| `{OUTPUT_LANGUAGE}` | Primary output language; specify a secondary language only when the audience requires it | "English" (default). For bilingual audiences, specify explicitly (e.g., "English body, Spanish executive summary") |
| `{SOURCE_PROFILE_USED}` | Which source profile was used in Phase 1 | "Practitioner-first" |
| `{CONVERGENCE_THRESHOLD}` | Default ±15% / 2-of-3 | Can adjust for domain |

---

## Consolidation Prompt Template

```markdown
# Consolidation Brief: Meta-Analysis of {TOPIC_TITLE}

## Your Role
You are a senior research director conducting a rigorous meta-analysis across {NUM_REPORTS} independent research reports on the same topic. Your job is not to merge or summarize — it is to perform cross-validation, extract unique discoveries, resolve contradictions, and produce a synthesis more valuable than any individual input.

## Input Reports

{REPORT_LIST — Fill in the inventory table below with one row per report:}

| # | Filename | Platform | Pass Type | Stated Focus |
|---|---|---|---|---|
| 1 | `Claude-DR_small-bets_2026-04-04.md` | Claude | DR | Synthesized practitioner + academic with analytical depth. Expected strength: framework integration and tension identification. |
| 2 | `Perplexity-Web_small-bets_2026-04-04.md` | Perplexity | Web | Recent practitioner content. Expected strength: current implementations and community patterns. |
| 3 | `Perplexity-Academic_small-bets_2026-04-04.md` | Perplexity | Academic | Peer-reviewed sources only. Expected strength: empirical validation and theoretical scaffolding. |
| 4 | `Gemini-DR_small-bets_2026-04-04.md` | Gemini | DR | Broad landscape survey. Expected strength: coverage breadth and quantitative data. |

The `Platform` and `Pass Type` columns together uniquely identify each report. Both columns must be populated for every row — do not collapse them into a single "Platform" label.

## Source Diversity Design

These reports were produced by different AI platforms (and in some cases, different passes of the same platform) using the same research brief but with different search access, training data, search profiles, and synthesis biases. Where reports converge, confidence is highest. Where they diverge, the divergence itself is informative.

**Same-platform passes are independent data points.** Two passes from the same platform with different focus profiles (e.g., Perplexity-Web and Perplexity-Academic) count as independent sources for convergence analysis. Do not collapse, de-duplicate, or merge their findings under a single "Perplexity" label. The Web pass exercises practitioner and recency-biased search; the Academic pass exercises peer-reviewed evidence — these are distinct source surfaces, and a finding that appears in both is stronger evidence than one that appears in either alone.

Apply this rule everywhere in this analysis — the Convergence Matrix, the Unique Discovery Classification, and the Contradiction Matrix all treat each row of the Input Reports inventory as an independent unit.

## Analytical Mandate

Read all reports fully before starting. Use extended thinking to plan the integration before writing.

### Phase A: Individual Report Audit

For each report, assess:

| Dimension | Report 1 | Report 2 | Report 3 | Report 4 |
|---|---|---|---|---|
| Source count | | | | |
| % sources with links/DOIs | | | | |
| % high-trust sources | | | | |
| Coverage of primary question | | | | |
| Coverage of secondary questions | | | | |
| Unique sources (not in other reports) | | | | |
| Overall quality grade (A-D) | | | | |

### Phase B: Cross-Report Triangulation

**B.1 Convergence Matrix**
For each major finding documented across reports:

| Finding | R1 | R2 | R3 | R4 | Evidence Type | Confidence |
|---|---|---|---|---|---|---|
| [finding] | ✓/✗ | ✓/✗ | ✓/✗ | ✓/✗ | (a)/(b)/(c) | High/Med/Low |

Evidence typing:
- (a) Documented practice: someone did this, reported experience, evidence of real use
- (b) Expert recommendation: practitioner/researcher advises, no specific outcome reported
- (c) Plausible inference: based on capabilities, not yet documented

**B.2 Quantitative Claims Reconciliation**
Cross-reference all numerical claims. Apply ±{CONVERGENCE_THRESHOLD} convergence threshold.

| Claim | R1 | R2 | R3 | R4 | Convergent? | Best Estimate |
|---|---|---|---|---|---|---|
| [claim] | [value + source] | [value + source] | [value + source] | [value + source] | Yes/No | [value or range] |

**B.3 Unique Discovery Classification**
What did each report find that no other found? For each:
- Name the finding
- Identify the original source
- Classify as: **Novel insight** (plausible, verifiable, adds value) / **Potential hallucination** (unverifiable, suspiciously specific) / **Vendor echo** (marketing claim without independent validation)
- Assess: is it actionable even without cross-validation?

**B.4 Contradiction Matrix**
Where reports disagree:

| Topic | Report A says | Report B says | Root cause | Resolution or documented tension |
|---|---|---|---|---|

**B.5 Hallucination Audit**
Spot-check 10 claims across reports for:
- Fabricated sources (author names that don't exist, papers that can't be found)
- Invented statistics (precise numbers with no traceable origin)
- Misattributed findings (real source, wrong claim)

### Phase C: Evidence Hierarchy Construction

Rank all validated findings:
1. **Replicated experiment** (multiple controlled studies agree) → Highest confidence
2. **Single experiment** (one controlled study, clear methodology) → High confidence
3. **Case study with metrics** (real implementation, quantified outcomes) → Medium-high
4. **Expert framework** (credible authority, no empirical validation) → Medium
5. **Industry report claim** (Gartner, Forrester, McKinsey — methodology often opaque) → Medium-low
6. **Vendor claim** (tool company's own case study or marketing) → Low
7. **Opinion/speculation** (blog posts, conference talks without data) → Lowest

**GRADE-inspired adjustment rules:**
- **Downgrade** for: inconsistency across sources, indirectness to the research question, imprecision in measurement
- **Upgrade** for: large effect size, dose-response relationship, convergence across 3+ independent sources

Assign a final confidence level (High / Medium / Low / Unknown) to every major finding.

### Phase D: Synthesis by Domain

{CUSTOMIZE THIS SECTION BASED ON TOPIC — provide the domain categories relevant to the research}

For each domain area:
- **Consolidated state of the art**: What do we know with confidence?
- **Emerging patterns**: What's appearing but not yet validated?
- **Open questions**: What remains unresolved?
- **Practical implications**: What can be acted on now?

### Phase E: Recommendations

{IF ORG_CONTEXT PROVIDED:}
Ground all recommendations in this organizational context:
{ORG_CONTEXT}

For each recommendation:
- What the recommendation is (specific, actionable)
- Evidence basis (which findings support it, at what confidence level)
- What it requires (resources, time, dependencies)
- What could go wrong (risks, assumptions that must hold)
- Priority (sequence relative to other recommendations)

**Include an anti-recommendations section**: Things that look appealing but should NOT be done, with explanation of why the evidence doesn't support them.

**Include a recommendation dependency map**: Which recommendations must succeed before others become viable?

### Phase F: Self-Critique

Address:
- Where all source reports failed to provide adequate evidence
- What biases might be present (AI models tend toward techno-optimism; vendor promotion in training data; English-language bias; recency bias)
- What critical questions remain unanswered
- What would need to happen in the next 6 months to change these conclusions
- What additional research would be worth investing in

## Analytical Standards (Non-Negotiable)

- **Aspiration vs. demonstration**: "Talking about doing something" is categorically different from "demonstrating having done it." Apply this distinction to every claim about adoption, implementation, or outcomes.
- **Vendor bias correction**: Vendor-sponsored studies overstate gains. Independent RCTs show modest or negative results for experienced practitioners. Flag the provenance chain of every major claim.
- **Do not privilege your own output**: Apply the same quality standards to your own analysis as to the input reports.
- **Absence ≠ evidence of absence**: If no report covers a topic, that's a gap worth documenting, not proof it doesn't exist.

## Output Format

Produce your output as a single, self-contained markdown document that can be saved as a `.md` file. Structure it as follows:

```
# {TOPIC_TITLE}: Consolidated Research Report
## Meta-Analysis of {NUM_REPORTS} Independent Research Outputs

**Date**: [current date]
**Research platforms**: {list platforms}
**Consolidation model**: Claude
**Source profile**: {SOURCE_PROFILE_USED}

---

## Executive Summary
[1-2 pages: 5 key findings with confidence levels, 3 top recommendations, biggest gap, direct relevance to decision context]

{IF OUTPUT_LANGUAGE specifies a secondary language: include a parallel executive summary in that language immediately after.}

## 1. Methodology
### 1.1 Source Reports and Quality Assessment
### 1.2 Analytical Approach
### 1.3 Limitations

## 2. Cross-Report Analysis
### 2.1 Convergence Matrix
### 2.2 Unique Discoveries
### 2.3 Contradiction Resolution
### 2.4 Hallucination Audit Results

## 3. Consolidated Findings by Domain
{Domain-specific sections}

## 4. Evidence-Weighted Recommendations
### 4.1 Recommended Actions (prioritized)
### 4.2 Anti-Recommendations
### 4.3 Dependency Map

## 5. Research Gaps and Next Steps

## 6. Self-Critique

## Appendix A: Master Source Inventory
## Appendix B: Full Convergence Data
```
```

---

## Context Window Management

If the total input (all reports + this prompt) exceeds context limits:

**Split-session protocol:**
- **Session A**: Upload all reports. Run Phases A-C (audit, triangulation, evidence hierarchy). Save the complete output.
- **Session B**: Upload Session A output + the Phase D-F section of this prompt + any organizational context. Complete synthesis, recommendations, and self-critique.

When splitting, Session A's output must include the full convergence matrix, contradiction matrix, hallucination audit, and evidence-ranked findings list — Session B depends on these as inputs.
