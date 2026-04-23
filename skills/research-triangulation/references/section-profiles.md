# Section Profiles

Section profiles parameterize the Core Brief's Output Format by declaring which sections a given platform-depth combination produces. The Core Brief template in `phase1-templates.md` defines all 8 sections as the canonical reference — profiles select from that set.

## How Profiles Work

1. The assembly process looks up the profile for the target platform-depth combination (see lookup table below)
2. If the profile includes all 8 sections (`standard-full`), the Core Brief's Output Format is used as-is
3. If the profile omits sections, the profile's **section-selection preamble** is prepended to the Output Format section — this tells the model which sections to produce and how to renumber them
4. Platform wrappers do NOT override section selection — that responsibility belongs entirely to the profile system

## Profile Lookup Table

| Platform | Full | Light |
|---|---|---|
| Claude-DR | `standard-full` | `light` |
| Perplexity-Web | `perplexity-optimized` | `light` |
| Perplexity-Academic | `perplexity-optimized` | `light` |
| Gemini-DR | `standard-full` | `light` |
| ChatGPT-DR | `standard-full` | `light` |

Default depth is **Full**. Select **Light** when the DR agent is a mid-capability model (e.g., Sonnet-class rather than Opus-class) or when the user explicitly requests a lighter output spec.

---

## Profile: `standard-full`

**Sections included:** §1 Executive Summary, §2 Findings by Research Question, §3 Domain-Specific Sections, §4 Source Inventory, §5 Adversarial Self-Check, §6 Gaps and Unanswered Questions, §7 Self-Assessment, §8 Open Self-Critique

**Section-selection preamble:** None — use the Core Brief's Output Format as-is.

**Applies to:** Claude-DR, Gemini-DR, ChatGPT-DR at Full depth.

**Rationale:** These platforms handle the full 8-section spec without generation issues. The Adversarial Self-Check (§5) and Self-Assessment (§7) provide diagnostic value for Phase 3 scoring.

---

## Profile: `perplexity-optimized`

**Sections included:** §1 Executive Summary, §2 Findings by Research Question, §3 Domain-Specific Sections, §4 Source Inventory, §6 Gaps and Unanswered Questions

**Sections omitted:** §5 (Adversarial Self-Check), §7 (Self-Assessment), §8 (Open Self-Critique)

**Section-selection preamble** (prepend to the Output Format section of the Core Brief):

```
**Section selection (profile: perplexity-optimized).** Produce only the following sections from the Output Format below, renumbered sequentially:
- §1 → Executive Summary (Core Brief §1)
- §2 → Findings by Research Question (Core Brief §2)
- §3 → Domain-Specific Sections (Core Brief §3)
- §4 → Source Inventory (Core Brief §4)
- §5 → Gaps and Unanswered Questions (Core Brief §6)

Omit Core Brief sections 5 (Adversarial Self-Check), 7 (Self-Assessment), and 8 (Open Self-Critique). These sections trigger a generation-collapse failure mode on Perplexity Deep Research where the model completes research but exits before producing the report body. Phase 2 consolidation does not depend on their presence in Perplexity reports.
```

**Applies to:** Perplexity-Web, Perplexity-Academic at Full depth.

**Rationale:** Documented generation-collapse failure mode (v1.3.2, topic `gt-suicide-crosslang`): Perplexity's per-turn output-generation budget is exhausted by the full 8-section spec before the report body begins. Verified 2026-04-19 — stripped prompt produced all 5 retained sections with proper YAML header.

---

## Profile: `light`

**Sections included:** §1 Executive Summary, §2 Findings by Research Question, §3 Domain-Specific Sections, §4 Source Inventory, §6 Gaps and Unanswered Questions

**Sections omitted:** §5 (Adversarial Self-Check), §7 (Self-Assessment), §8 (Open Self-Critique)

**Section-selection preamble** (prepend to the Output Format section of the Core Brief):

```
**Section selection (profile: light).** Produce only the following sections from the Output Format below, renumbered sequentially:
- §1 → Executive Summary (Core Brief §1)
- §2 → Findings by Research Question (Core Brief §2)
- §3 → Domain-Specific Sections (Core Brief §3)
- §4 → Source Inventory (Core Brief §4)
- §5 → Gaps and Unanswered Questions (Core Brief §6)

Omit Core Brief sections 5 (Adversarial Self-Check), 7 (Self-Assessment), and 8 (Open Self-Critique). Light mode trims the output spec for mid-capability DR agents that cannot reliably complete the full 8-section format.
```

**Applies to:** Any platform at Light depth.

**Rationale:** Mid-capability DR agents (e.g., Sonnet-class) crash or produce incomplete output when given the full spec. The omitted sections are the heaviest: §5 requires a mid-write search pass, §7 requires 7-dimension scored assessment, §8 requires open-ended critique. Removing them lets the agent focus on the substantive research sections.

---

## Adding a New Profile

To add a new platform or depth mode:

1. Define the profile in this file following the structure above: name, sections included/omitted, section-selection preamble, applicable platform-depth combinations, rationale
2. Add the platform-depth combination to the Profile Lookup Table
3. If the profile omits sections, write the section-selection preamble mapping Core Brief section numbers to renumbered output sections
4. No wrapper edit is needed — the assembly process in `phase1-templates.md` reads the profile and applies it automatically

This is the acceptance criterion: adding a new platform or depth mode is a profile definition, not a wrapper edit.
