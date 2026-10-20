# evidence-research

> Answer bounded desk-research questions for decisions with traceable, checked evidence.

## Why this skill?

Research answers tend to blend fresh observations, old recommendations, model summaries and assumptions into one confident paragraph. **evidence-research** makes the agent reuse prior work first, pick the smallest method that can answer the decision question, check decisive claims against the source passage, keep contradictions and unknowns visible, and stop at explicit bounds with concrete next checks.

It defers to specialist skills: multi-platform report consolidation goes to `research-triangulation`; hiring-contact dossiers go to `boss-hunt-research`.

**Version:** 0.1.1 — **candidate, not shipped**

---

## Status and evidence

- **Offline fixture test (2026-10-18):** nine frozen local cases, each run by a fresh native Codex executor and graded by one independent reviewer. All nine passed; one minor criterion miss (a construction-applicability answer did not name concrete professional/authority next checks). The candidate was not tuned to the answer key.
- **Not established:** live research usefulness, automatic skill discovery, cross-harness transferability, causal improvement over a baseline, or benchmark performance. Most fixture sources were synthetic.
- **Live pilot (2026-10-19):** two real desk-research tasks under fresh Codex executors, each graded by the parent session on reuse, claim support, separation, next checks and discipline, plus an owner usefulness verdict. v0.1.0 passed one and was partial on reuse in the other: it judged prior work sufficient without listing what existed and missed two local source sets. v0.1.1 adds one rule to section 1 (inventory local source sets and record each as read or skipped before judging prior work sufficient); the rerun passed, with 7 of 7 re-opened claims matching. Owner usefulness: yes, but limited, for both tasks.
- **Next:** a cross-harness transferability check before claiming the skill works outside Codex.

The test packets and grading evidence stay private because some fixtures derive from the owner's own project records. This published copy differs from the tested candidate trees only in one heading and two provenance lines of `references/framework-map.md`, where private local paths were replaced with generic descriptions or repository-relative links; no instruction text changed.

## Contents

| File | Purpose |
|---|---|
| `SKILL.md` | Workflow: reuse and frame, find and preserve evidence, check meaning and applicability, stop and hand off |
| `references/methods.md` | Extended or resumable research runs |
| `references/evidence-record.md` | Evidence record structure for extended work |
| `references/framework-map.md` | Design provenance: which public frameworks were adapted and their limits |
| `agents/openai.yaml` | Codex interface metadata |

## Install

Not recommended yet. To try it anyway:

```bash
cp -r skills/evidence-research ~/.claude/skills/evidence-research
```
