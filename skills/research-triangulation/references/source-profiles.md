# Source Priority Profiles

Select the profile that matches the research context. Each profile defines a ranked source hierarchy and platform-specific search instructions for embedding in research prompts.

## Structured Export Format

When assembling a research prompt, the `{{INJECTED_SOURCE_PROFILE}}` placeholder in the Core Brief's Source Requirements section is replaced with a **structured export block** — a deterministic slice of the selected profile for the target platform. The export block has this exact format for every profile:

```
### Source Priority: {Profile Name}

**Source hierarchy (highest → lowest trust):**
1. {source type}
2. {source type}
...

**Search focus for this platform:**
{The platform-specific instruction for THIS platform only — copy verbatim from the profile below}
```

**Assembly rule:** for profile X and platform Y, the export block is always: the profile's source hierarchy (same across all platforms) + that platform's search instruction (one entry from the platform search instructions below). Do not paste instructions for other platforms.

---

## Profile: Academic-First

**Use when**: Building evidence for academic work, validating frameworks with empirical data, thesis research, establishing causal claims, or when the user explicitly needs peer-reviewed sources.

**Source hierarchy (highest → lowest trust)**:
1. Peer-reviewed empirical studies (RCTs, quasi-experiments, meta-analyses)
2. Peer-reviewed theoretical/conceptual papers
3. Working papers from recognized institutions (NBER, SSRN with institutional affiliation)
4. Doctoral dissertations and theses
5. Practitioner documentation with quantified outcomes
6. Expert commentary and opinion pieces
7. Vendor/industry reports (flag as low-trust)

**Platform search instructions:**
- **Claude Deep Research:** "Ground every finding in the academic literature first. Use practitioner sources only to illustrate or contextualize academic findings. When citing practitioner evidence, explicitly note the evidence gap — what would a rigorous study need to test?"
- **Perplexity (Web):** "Search for grey literature, preprints, and practitioner content that extends or applies academic findings. For every non-academic claim, note whether supporting peer-reviewed evidence exists. Deprioritize SEO content and aggregator sites — link to primary sources."
- **Perplexity (Academic):** "Prioritize peer-reviewed journals, Google Scholar indexed papers, and institutional working papers. For every claim, provide: author(s), year, journal/publication, sample size where applicable, and DOI or URL. Exclude blog posts, Medium articles, and vendor white papers unless no academic source exists."
- **Gemini Deep Research:** "Survey the academic landscape broadly. Include citation counts and recency. Flag foundational papers (>500 citations) separately from recent work (<2 years). Note any systematic reviews or meta-analyses on the topic."
- **ChatGPT Deep Research:** "Ground every finding in the academic literature first. Use practitioner sources only to illustrate or contextualize academic findings. When citing practitioner evidence, explicitly note the evidence gap — what would a rigorous study need to test?"

---

## Profile: Practitioner-First

**Use when**: Researching how something is being done in practice, tool evaluations, workflow design, implementation evidence, training curriculum development, or competitive intelligence.

**Source hierarchy (highest → lowest trust)**:
1. Documented implementations with quantified outcomes (case studies, blog posts with metrics)
2. Independent tool reviews and comparisons (not vendor-produced)
3. Conference talks and workshop materials with demonstrated methods
4. Expert practitioner blogs and newsletters (named individuals with track records)
5. Community discussions with verifiable claims (specific examples, not opinions)
6. Academic papers validating practitioner patterns
7. Vendor case studies and marketing (flag as vendor-sourced)

**Platform search instructions:**
- **Claude Deep Research:** "Synthesize practitioner evidence into patterns. Look for convergence across multiple practitioners — a workflow documented by 3+ independent practitioners is stronger than one person's blog post. When a practitioner claim lacks metrics, note the evidence gap."
- **Perplexity (Web):** "Focus on practitioner blogs (Medium, Substack, Smashing Magazine, A List Apart, UX Collective), YouTube walkthroughs, conference talks (recordings and slides), and professional publications. For every workflow or method, require: who did it, what tools they used, what the before/after looked like, and a link to the original source."
- **Perplexity (Academic):** "Search for academic studies that validate practitioner patterns — empirical evaluations of tools, methods, or workflows. Prioritize studies that measure real-world outcomes rather than lab settings. Note where academic evidence supports or contradicts practitioner claims."
- **Gemini Deep Research:** "Cast a wide net across practitioner content. Include survey data on adoption patterns. Flag the distinction between 'people say they do X' (survey) vs. 'here's documented evidence of someone doing X' (case study)."
- **ChatGPT Deep Research:** "Synthesize practitioner evidence into patterns. Look for convergence across multiple practitioners — a workflow documented by 3+ independent practitioners is stronger than one person's blog post. When a practitioner claim lacks metrics, note the evidence gap."

---

## Profile: Legal/Regulatory

**Use when**: Researching legal frameworks, labor law, regulatory compliance, tax implications, or policy analysis.

**Source hierarchy (highest → lowest trust)**:
1. Primary legislation (statutes, codes, constitutional provisions)
2. Court decisions and jurisprudence (especially Supreme Court/highest court precedents)
3. Regulatory guidance (official bulletins, circulars, interpretive letters)
4. Legal scholarship (law review articles, treatises)
5. Legal practitioner analysis (law firm publications, bar association guides)
6. Government agency publications and FAQs
7. News reporting on legal developments (flag as secondary)

**Platform search instructions:**
- **Claude Deep Research:** "When analyzing legal frameworks, identify: (a) the applicable statute, (b) relevant judicial interpretations, (c) any regulatory guidance that modifies or clarifies the statute. Flag where the law is ambiguous or where circuit/jurisdictional splits exist."
- **Perplexity (Web):** "Search for primary legal sources, official regulatory texts, and legal practitioner commentary. For every legal claim, cite the specific statute, article, section, or case. Note jurisdiction explicitly. Distinguish between binding law and legal commentary."
- **Perplexity (Academic):** "Search for legal scholarship — law review articles, treatises, and doctrinal analysis. For every legal claim, cite the specific article, section, or case and link to SSRN, HeinOnline, or equivalent. Prioritize comparative analyses and systematic doctrinal reviews."
- **Gemini Deep Research:** "Survey the legal landscape broadly. When analyzing legal frameworks, identify: (a) the applicable statute, (b) relevant judicial interpretations, (c) any regulatory guidance. Flag jurisdictional variations and note where the law is evolving."
- **ChatGPT Deep Research:** "Search across diverse legal source types — statutes, case law, regulatory guidance, legal commentary, and news reporting. For each finding, classify the source type (primary law, judicial interpretation, legal commentary) and note the jurisdiction. Flag where the law is ambiguous or where jurisdictional splits exist."

---

## Profile: Market/Competitive

**Use when**: Evaluating competitive positioning, market trends, vendor capabilities, pricing analysis, or technology landscape mapping.

**Source hierarchy (highest → lowest trust)**:
1. Independent analyst reports with disclosed methodology (Gartner, Forrester, IDC — note: methodology often opaque)
2. SEC filings, earnings calls, annual reports (publicly verifiable)
3. Independent benchmarks and comparisons (METR, DORA, academic evaluations)
4. Credible journalism (named reporters at established outlets)
5. Customer reviews and community sentiment (aggregate patterns, not individual reviews)
6. Vendor marketing materials (flag explicitly, use only for feature claims)
7. Social media speculation (lowest trust, use only for signal detection)

**Platform search instructions:**
- **Claude Deep Research:** "Apply the aspiration vs. demonstration test to every competitive claim. 'Company X announced Y' ≠ 'Company X shipped Y' ≠ 'Company X's Y is used by customers.' Track the provenance chain."
- **Perplexity (Web):** "Find recent competitive intelligence. For vendor claims about their own products, always cross-reference with independent reviews. For market size claims, require the methodology source. Note when an 'industry report' is actually vendor-sponsored."
- **Perplexity (Academic):** "Search for academic studies on market dynamics, industry analysis, and competitive strategy. Prioritize empirical research over opinion. For market size and growth claims, require methodology and sample source."
- **Gemini Deep Research:** "Cast a wide net across market intelligence sources. Apply the aspiration vs. demonstration test to every claim. Create comparison tables where multiple vendors or products exist. Track provenance — note whether evidence comes from vendor marketing, independent review, or empirical study."
- **ChatGPT Deep Research:** "Search across diverse source types for competitive intelligence. Apply the aspiration vs. demonstration test to every claim. For vendor marketing, always note that the source is vendor-produced. Classify each finding by source type and typical reliability."

---

## Profile: Mixed/Exploratory

**Use when**: You don't yet know where the best evidence lives, exploring a new domain, or the topic spans academic, practitioner, and market evidence.

**Source hierarchy**: Equal weighting across all source types initially. The consolidation phase will reveal which evidence classes are strongest.

**Platform search instructions:**
- **Claude Deep Research:** "Search across all source types — academic, practitioner, market, legal, community. For each finding, classify the source type and note its typical trust level. We will determine the appropriate evidence weighting during synthesis."
- **Perplexity (Web):** "Search across all source types — academic, practitioner, market, legal, community. For each finding, classify the source type and note its typical trust level. We will determine the appropriate evidence weighting during synthesis."
- **Perplexity (Academic):** "Search across all source types — academic, practitioner, market, legal, community. For each finding, classify the source type and note its typical trust level. We will determine the appropriate evidence weighting during synthesis."
- **Gemini Deep Research:** "Search across all source types — academic, practitioner, market, legal, community. For each finding, classify the source type and note its typical trust level. We will determine the appropriate evidence weighting during synthesis."
- **ChatGPT Deep Research:** "Search across all source types — academic, practitioner, market, legal, community. For each finding, classify the source type and note its typical trust level. We will determine the appropriate evidence weighting during synthesis."

**Note**: Mixed/Exploratory is the default when the user hasn't specified a preference. After the first research cycle on a topic, switch to a more specific profile based on where the strongest evidence was found.

---

## Custom Profile Construction

If none of the above profiles fit, construct a custom profile following the same structure:

1. Name the profile and write a "Use when" description
2. List the source types relevant to this topic, ranked by expected trust level
3. Write platform-specific search instructions for all five platform groups, using the same headers as above:
   - Claude Deep Research
   - Perplexity (Web)
   - Perplexity (Academic)
   - Gemini Deep Research
   - ChatGPT Deep Research
4. Note any sources to explicitly exclude (e.g., "Exclude vendor white papers entirely" or "Exclude pre-2024 sources")

The structured export block for a custom profile follows the same format as standard profiles — hierarchy + the target platform's search instruction.
