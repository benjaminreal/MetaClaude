# Platform Performance Tracker

## Purpose

Track how each AI research platform performs across research cycles. Over time, this data informs:
- Which platforms to assign to which types of research questions
- How to adjust prompt instructions per platform to compensate for known weaknesses
- Whether skill/prompt improvements are actually improving output quality

## Logging Format

After each complete research cycle (Phase 1 + Phase 2 + Phase 3), log a new entry using this structure:

```markdown
## Cycle: [YYYY-MM-DD] — [Topic Slug]

**Topic**: [Full topic title]
**Source Profile**: [Academic-first / Practitioner-first / Legal / Market / Mixed]
**Platforms Used**: [List]
**Prompt Version**: [Skill version or "pre-skill" for cycles before this skill existed]

### Tier 1 Scores

| Dimension | Claude DR | Perplexity Web | Perplexity Academic | Gemini DR | ChatGPT DR |
|---|---|---|---|---|---|
| Source Traceability | | | | | |
| Source Quality Dist. | | | | | |
| Hallucination Rate | | | | | |
| Coverage Breadth | | | | | |
| Coverage Depth | | | | | |
| Recency Compliance | | | | | |
| Actionability | | | | | |
| **Composite** | | | | | |

### Tier 2 Score

| Dimension | Score |
|---|---|
| Triangulation Rigor | |
| Contradiction Handling | |
| Unique Discovery Assessment | |
| Evidence Hierarchy Application | |
| Synthesis vs. Summary | |
| Decision Readiness | |
| **Composite** | |

### Key Claims Verification
- Claims checked: [N]
- Confirmed: [N]
- Partially confirmed: [N]
- Unverifiable: [N]
- Contradicted: [N]
- Verification rate: [%]

### Platform-Specific Observations
- **Claude DR**: [What it did well, what it missed, notable behaviors]
- **Perplexity Web**: [...]
- **Perplexity Academic**: [...]
- **Gemini DR**: [...]
- **ChatGPT DR**: [...]

### Prompt Modifications That Helped
[Any prompt adjustments made during this cycle that improved results]

### Notes
[Anything else worth tracking for future cycles]
```

---

## Cumulative Platform Profiles

Update these profiles as data accumulates. After 3+ cycles, patterns should emerge.

### Claude Deep Research
- **Typical strengths**: [Update after cycles — e.g., "analytical depth, framework integration, tension identification"]
- **Typical weaknesses**: [Update — e.g., "sometimes fabricates specific statistics, can overfit to a single narrative"]
- **Best assigned to**: [Update — e.g., "synthesis-heavy topics, framework analysis"]
- **Average composite score**: [Calculate after 3+ cycles]
- **Prompt adjustments that help**: [Accumulate what works]

### Perplexity Pro (Web Focus)
- **Typical strengths**: [Update]
- **Typical weaknesses**: [Update]
- **Best assigned to**: [Update]
- **Average composite score**: [Calculate]
- **Prompt adjustments that help**: [Accumulate]

### Perplexity Pro (Academic Focus)
- **Typical strengths**: [Update]
- **Typical weaknesses**: [Update]
- **Best assigned to**: [Update]
- **Average composite score**: [Calculate]
- **Prompt adjustments that help**: [Accumulate]

### Gemini Deep Research
- **Typical strengths**: [Update]
- **Typical weaknesses**: [Update]
- **Best assigned to**: [Update]
- **Average composite score**: [Calculate]
- **Prompt adjustments that help**: [Accumulate]

### ChatGPT Deep Research
- **Typical strengths**: [Update]
- **Typical weaknesses**: [Update]
- **Best assigned to**: [Update]
- **Average composite score**: [Calculate]
- **Prompt adjustments that help**: [Accumulate]

---

## Pre-Skill Baseline Data

These observations come from research cycles conducted before this skill was formalized. They are qualitative and based on memory — treat as provisional until confirmed by scored cycles.

### AI-UX Design Research (Feb 2026)
- **Platforms**: Claude, Perplexity Web, Perplexity Academic, Gemini
- **Source profile**: Practitioner-first
- **Observations**:
  - Claude: Strong on jagged frontier framework integration, good task-level mapping. Strength in synthesizing practitioner + academic sources.
  - Perplexity Web: Best for recent practitioner content — blogs, Config 2025 talks, LinkedIn experiments, Georgia Tech research. Found "hidden labor" study.
  - Perplexity Academic: Strongest on empirical accuracy data and controlled studies. Found hallucination rate studies.
  - Gemini: Broadest coverage — survey data synthesis (UXTools 2024, Figma State of Design 2025). "Text-first revolution" framing.
  - Consolidation finding: Where all four converged, confidence was high. 84% collaborator mental model finding was single-source — correctly flagged.

### AI Literacy / Training Curriculum Research (Mar 2026)
- **Platforms**: Claude, Perplexity Web, Perplexity Academic, Gemini
- **Source profile**: Mixed (academic + practitioner)
- **Observations**:
  - All evidence had a LATAM-shaped hole — zero documented cases of AI-assisted UX in Latin American markets
  - CARE-V framework recommendation emerged from synthesis (not in any single report)
  - Heuristic evaluation had the widest gap between naive and trained use (20% → 75%)
  - Error accumulation finding (3-20% incorrect references in multi-turn) surfaced from Perplexity Academic
  - Georgia Tech hidden labor study was highest-value unique find (Perplexity Web)

### Small Bets Framework Research (Apr 2026)
- **Platforms**: Claude, Perplexity, Gemini (planned)
- **Source profile**: Academic-first (validate practitioner claims)
- **Observations**: [Pending — cycle may be in progress]

---

## Trend Analysis Template

After 5+ cycles, run this analysis:

1. **Per-platform dimension averages**: Which platforms consistently score highest on which dimensions?
2. **Source profile × platform fit**: Do certain platforms perform better on certain source profiles?
3. **Prompt improvement tracking**: Are composite scores trending upward as prompts are refined?
4. **Consolidation quality trend**: Is the Tier 2 score improving as the methodology matures?
5. **Verification rate trend**: Is the hallucination/fabrication rate decreasing over time?

Present as a comparison table and flag any platform whose composite has dropped below 3.0 for 2+ consecutive cycles — consider adjusting its role in the research workflow.
