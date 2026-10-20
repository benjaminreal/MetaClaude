# Framework-to-practice map

Checked 2026-10-18. Adoption below means a design adaptation, not certification
or a claim to have run the named benchmark.

## F1 — Plan–Execute–Verify–Replan / VMAO

Source: https://arxiv.org/abs/2603.11445 (2026-03-15, arXiv v2).

Adopted practice: Question decomposition, coverage verification, bounded replanning and explicit stop conditions.

Limits: Adapted manual workflow; no dependency-DAG scheduler or complete VMAO implementation. The paper reports 25 market-research queries, not universal validation.

Candidate checks: T2, T6, T7, T8.

## F2 — Orchestrator–workers; evaluator–optimizer; simplicity

Source: https://www.anthropic.com/engineering/building-effective-agents (2024-12-19; current tooling caveat present).

Adopted practice: Choose simple methods first; split independent work only when useful; use bounded review with explicit criteria.

Limits: Delegation remains conditional on need, availability and user authority. This candidate does not require multiple agents or implement a new harness.

Candidate checks: T6, T7, T9.

## F3 — DeepResearch Bench / RACE and FACT

Source: https://arxiv.org/abs/2506.11763 (2025-06-13, arXiv v1).

Adopted practice: Evaluate usefulness/report quality separately from citation support and retrieval quality.

Limits: Evaluation principles adapted; official tasks, reference reports, judges and numerical benchmark scores are not run or reproduced.

Candidate checks: T1, T3, T4, T5, T6.

## F4 — RAVine

Source: https://arxiv.org/abs/2507.16725 (2025-07-22 initial submission).

Adopted practice: Inspect the process and efficiency alongside realistic answer requirements; retain action/failure/coverage evidence.

Limits: No official RAVine dataset, sandbox or metric implementation. Fixture receipts and observed outputs are a narrower evaluation.

Candidate checks: T7, T8, T9.

## F5 — Private source-grounded verification prototype

Source: the owner's private research-harness prototype for a property project (2026-09-23 prototype, subsequent A3/A5 runs and corrections); not published.

Adopted practice: Underlying sources, claim-level support, separate verification, explicit applicability gaps and failure states.

Limits: Generalize the prototype rather than import fixed Spanish-first/18-month/six-fetch/property rules. Stale untested header is not a finding that later runs never occurred.

Candidate checks: T2, T3, T4, T7.

## F6 — Local research-triangulation methodology

Source: [`skills/research-triangulation/SKILL.md`](../../research-triangulation/SKILL.md) in this repository (existing canonical skill; hash in provenance).

Adopted practice: Preserve contradictions and deduplicate underlying sources. Explicit multi-platform report work stays with that skill.

Limits: No automatic platform fan-out. GRADE-inspired confidence wording in the existing skill is not formal GRADE. Model diversity does not by itself establish source independence.

Candidate checks: T1, T3, T5.

