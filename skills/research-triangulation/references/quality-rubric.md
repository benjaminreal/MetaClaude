# Quality Rubric & Scoring Protocol

## Overview

This rubric defines how to evaluate research outputs at two tiers:
- **Tier 1**: Individual research reports from Phase 1 platforms
- **Tier 2**: The consolidated report from Phase 2

Scoring is performed by independent AI agents — never by the same instance that produced the output. This avoids self-assessment bias.

---

## Scoring Agent Configuration

### Which model to use as scorer
- **Preferred**: Claude Sonnet or Haiku (different instance from the one that produced the report)
- **Alternative**: Any capable model not involved in producing the report being scored
- **Rule**: If Claude produced the report, score with a fresh Claude instance (different conversation), Sonnet, or Haiku. If Perplexity produced the report, Claude can score it directly. The point is instance separation, not necessarily model separation.

### How to invoke the scoring agent
Run the scoring prompt below in a fresh conversation. Upload the report being scored plus the original research brief (so the scorer can evaluate coverage against intent).

---

## Tier 1: Individual Report Scorecard

### Scoring Agent Prompt (Tier 1)

```markdown
You are a research quality auditor. Your job is to score the attached research report against a standardized rubric. Be rigorous and honest — inflated scores are worse than harsh ones.

You will receive:
1. A research report to evaluate
2. The original research brief that produced it

Score the report on 7 dimensions, each on a 1-5 scale. For each dimension, provide:
- The score (integer, 1-5)
- A 1-2 sentence justification
- Specific examples supporting the score (quote or reference specific sections)

## Dimension 1: Source Traceability (1-5)
Can every major claim be traced to a named, linkable source?
- 1 = Most claims unsourced or vaguely attributed ("studies show", "experts say")
- 2 = ~40% of claims have specific sources
- 3 = ~60% of claims have specific sources; some remain vague
- 4 = ~80% of claims cite specific, named sources with links or DOIs
- 5 = Every major claim has a verifiable citation with link or DOI

**Procedure**: Sample 15 claims from across the report. Count how many have specific, named, linkable sources. Calculate the percentage.

## Dimension 2: Source Quality Distribution (1-5)
What percentage of sources are high-trust vs. low-trust?
- High-trust: peer-reviewed journals, independent research orgs, primary legal sources, documented case studies with metrics
- Medium-trust: industry reports with disclosed methodology, professional publications, expert blogs with track records
- Low-trust: vendor marketing, opinion pieces without data, unverified social media, anonymous sources
Scoring:
- 1 = >70% low-trust sources
- 2 = 50-70% low-trust
- 3 = Roughly equal mix
- 4 = 50-70% high-trust
- 5 = >70% high-trust

**Procedure**: Categorize the 15 sampled sources into high/medium/low trust. Report the distribution.

## Dimension 3: Hallucination Rate (1-5)
Spot-check 10 specific claims for fabrication.
- Fabricated = source doesn't exist, statistic is invented, author name is fake, paper can't be found
- 1 = >30% of checked claims appear fabricated
- 2 = 20-30% fabricated
- 3 = 10-20% fabricated
- 4 = 1-10% fabricated (1 suspicious claim)
- 5 = 0% fabricated — all checked claims appear genuine

**Procedure**: Select 10 claims with specific numbers, author names, or paper titles. Assess whether each appears genuine based on: internal consistency, plausibility of the source, specificity of the claim, and cross-reference with your own knowledge. Flag each as: Likely genuine / Suspicious / Likely fabricated. Report the count.

**Important limitation**: You cannot verify sources by actually visiting URLs. Assess based on plausibility, internal consistency, and your knowledge. Be transparent about the limits of this check.

## Dimension 4: Coverage Breadth (1-5)
Did the report address all research questions in the brief?
- 1 = Missed >50% of research questions
- 2 = Addressed ~50% of questions, missed key ones
- 3 = Addressed ~70% of questions; some gaps in secondary questions
- 4 = Addressed ~90% of questions; minor gaps only
- 5 = Complete coverage of all primary and secondary questions

**Procedure**: List each research question from the brief. For each, note whether the report addressed it (fully / partially / not at all). Calculate coverage percentage.

## Dimension 5: Coverage Depth (1-5)
For topics covered, did the report go beyond surface-level summaries?
- 1 = Wikipedia-level overview — definitions and general statements only
- 2 = Some specific examples but mostly surface-level
- 3 = Mix of surface and deep; some topics well-explored, others thin
- 4 = Most topics explored with specific evidence, named examples, nuanced analysis
- 5 = Specialist-level depth — specific studies, named practitioners, quantified outcomes, tensions and tradeoffs identified

**Procedure**: Select 3 topics from the report. For each, assess whether the treatment goes beyond what you'd find in a general overview.

## Dimension 6: Recency Compliance (1-5)
What percentage of sources fall within the specified time window?
- 1 = <50% within window
- 2 = 50-65% within window
- 3 = 65-80% within window
- 4 = 80-90% within window
- 5 = >90% within window (with older sources clearly marked as foundational)

**Procedure**: From the 15 sampled sources, count how many have dates within the specified recency window. Note the window specified in the brief.

## Dimension 7: Actionability (1-5)
Could someone make a decision or take a next step based on this report alone?
- 1 = Too vague to act on — all generalities, no specifics
- 2 = Some direction but missing critical details (which tool? what timeline? what resources?)
- 3 = Actionable for some questions but not others
- 4 = Most findings are specific enough to inform decisions; recommendations have clear next steps
- 5 = Report provides specific, prioritized recommendations with resource requirements, timelines, and risk factors

**Procedure**: Imagine you are the decision-maker described in the brief. Could you take action tomorrow based on this report? What's missing?

## Output Format

```
# Tier 1 Quality Scorecard
**Report**: [filename]
**Platform**: [which AI produced it]
**Scored by**: [this model/instance]
**Date**: [today]

| Dimension | Score | Justification |
|---|---|---|
| 1. Source Traceability | X/5 | [justification] |
| 2. Source Quality Distribution | X/5 | [justification] |
| 3. Hallucination Rate | X/5 | [justification] |
| 4. Coverage Breadth | X/5 | [justification] |
| 5. Coverage Depth | X/5 | [justification] |
| 6. Recency Compliance | X/5 | [justification] |
| 7. Actionability | X/5 | [justification] |

**Composite Score**: X.X / 5.0
**Minimum Threshold**: 3.0 average, no dimension below 2.0
**Verdict**: PASS / FAIL (if any dimension < 2.0 or composite < 3.0, FAIL)

## Detailed Notes
[Specific examples, flagged issues, notable strengths]

## Sampled Claims Audit
| # | Claim | Source cited | Assessment |
|---|---|---|---|
| 1 | [claim text] | [source] | Genuine / Suspicious / Fabricated |
| ... | | | |
```
```

---

## Tier 2: Consolidation Report Scorecard

### Scoring Agent Prompt (Tier 2)

```markdown
You are a research quality auditor evaluating a meta-analysis / consolidation report. This report was produced by synthesizing multiple independent research reports on the same topic. Score it on analytical rigor, not just content quality.

You will receive:
1. The consolidation report to evaluate
2. Optionally: the individual source reports it was built from

Score on 6 dimensions, each 1-5:

## Dimension 1: Triangulation Rigor (1-5)
Did it systematically map convergent vs. divergent findings?
- 1 = Simple merge — reads like a summary of summaries
- 2 = Some comparison but unsystematic
- 3 = Has a convergence matrix but incomplete or superficial
- 4 = Systematic convergence mapping with confidence levels for most findings
- 5 = Full convergence matrix, every finding mapped across all sources, confidence levels justified

## Dimension 2: Contradiction Handling (1-5)
When sources disagreed, how were contradictions handled?
- 1 = Ignored — contradictions not mentioned
- 2 = Noted but not investigated ("sources disagree on this point")
- 3 = Investigated for some contradictions, others left hanging
- 4 = Most contradictions investigated with root cause analysis; positions taken or tensions documented
- 5 = Every major contradiction investigated, root causes identified, clear resolution or explicitly documented unresolved tension

## Dimension 3: Unique Discovery Assessment (1-5)
Were single-source findings identified and classified?
- 1 = All findings treated equally regardless of how many sources support them
- 2 = Some mention of unique findings but no classification
- 3 = Unique findings identified but classification is superficial
- 4 = Unique findings classified as novel insight / hallucination / vendor echo with reasoning for most
- 5 = Systematic classification of every unique finding with evidence-based reasoning

## Dimension 4: Evidence Hierarchy Application (1-5)
Are recommendations weighted by evidence quality?
- 1 = All claims treated equally — vendor anecdote given same weight as RCT
- 2 = Some awareness of evidence quality but inconsistent application
- 3 = Evidence hierarchy mentioned but not consistently applied to recommendations
- 4 = Most recommendations clearly tied to evidence level; confidence ratings present
- 5 = Every recommendation explicitly grounded in evidence hierarchy; GRADE-style upgrade/downgrade applied

## Dimension 5: Synthesis vs. Summary (1-5)
Did it produce genuinely integrated analysis or just summarize reports sequentially?
- 1 = Report-by-report summary with no integration
- 2 = Thematic grouping but no emergent insight
- 3 = Some integrated analysis; a few cross-cutting insights emerge
- 4 = Mostly integrated; emergent findings that weren't in any single source
- 5 = Genuinely new analytical insight; findings that could only emerge from cross-source integration

## Dimension 6: Decision Readiness (1-5)
Could the intended audience act without re-reading source reports?
- 1 = Reader would need to read all source reports to understand the consolidation
- 2 = Some sections are self-contained but others reference sources opaquely
- 3 = Readable standalone; some recommendations lack sufficient detail to act on
- 4 = Fully self-contained; most recommendations are actionable with clear next steps
- 5 = Decision-ready: prioritized recommendations with resources, timelines, risks, and dependencies

## Output Format

```
# Tier 2 Quality Scorecard
**Report**: [consolidation filename]
**Consolidation model**: [which AI produced it]
**Scored by**: [this model/instance]
**Date**: [today]

| Dimension | Score | Justification |
|---|---|---|
| 1. Triangulation Rigor | X/5 | [justification] |
| 2. Contradiction Handling | X/5 | [justification] |
| 3. Unique Discovery Assessment | X/5 | [justification] |
| 4. Evidence Hierarchy Application | X/5 | [justification] |
| 5. Synthesis vs. Summary | X/5 | [justification] |
| 6. Decision Readiness | X/5 | [justification] |

**Composite Score**: X.X / 5.0
**Minimum Threshold**: 3.5 average
**Verdict**: PASS / FAIL

## Detailed Notes
[Specific examples, flagged issues, notable strengths]
```
```

---

## Key Claims Verification Protocol

After Tier 1 and Tier 2 scoring, verify the top findings.

### Verification Agent Prompt

```markdown
You are a fact-checker verifying the highest-impact claims from a research consolidation. For each claim below, trace the evidence chain:

1. Find the claim in the consolidation report
2. Identify which Phase 1 report(s) sourced it
3. Identify the external source cited in the Phase 1 report
4. Assess whether the external source is real, correctly cited, and actually supports the claim

For each claim, report:

| Claim | Cited in consolidation | Source report(s) | External source | Verification |
|---|---|---|---|---|
| [claim] | [section] | [which report] | [original source] | Confirmed / Partially confirmed / Unverifiable / Contradicted |

**Verification categories:**
- **Confirmed**: External source exists, is correctly cited, and supports the claim as stated
- **Partially confirmed**: Source exists but the claim overstates, understates, or slightly misrepresents the finding
- **Unverifiable**: Cannot confirm the source exists or access it to verify
- **Contradicted**: Source exists but says something different from what's claimed

For any claim rated "Unverifiable" or "Contradicted," provide a specific warning note explaining the issue.
```

### Claims to Verify

Select the top 5-10 claims by impact — the findings that most influence the recommendations. Prioritize:
- Claims with specific quantitative data
- Claims that anchor a key recommendation
- Claims from single sources (highest hallucination risk)
- Claims that seem surprisingly strong or counterintuitive

---

## Thresholds and Decision Rules

| Assessment | Threshold | Action if below threshold |
|---|---|---|
| Tier 1 composite | ≥ 3.0 | Re-run research on that platform with improved prompt, or exclude from consolidation |
| Tier 1 any single dimension | ≥ 2.0 | Flag the weakness; consider re-running with targeted instructions for that dimension |
| Tier 2 composite | ≥ 3.5 | Re-run consolidation with more explicit instructions for weak dimensions |
| Key claims verification | ≥ 70% Confirmed or Partially Confirmed | If <70%, flag the consolidation as low-confidence; investigate fabrication patterns |
