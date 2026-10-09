#!/usr/bin/env python3
"""Contract test suite for the session skills (`newbeginning`, `closingtime`).

Runs the deterministic half of the vNext test architecture — everything that
needs no private corpus or external service:

  1. checklist mapping table self-check (83 exit-gate rows)
  2. valid envelope fixtures validate cleanly
  3. one-defect mutants each fail with their declared code
  4. trigger activation: all 21 phrases declared, negatives excluded
  5. cross-skill step-number references (reported, not blocking)
  6. Phase 2 local-helper fixtures (temporary workspaces only)

The historical-corpus scorer self-test is NOT here — it depends on a private
evaluation ledger and lives alongside it. Its absence is reported below rather
than passed over, so a green run here is never mistaken for a full Phase 1 pass.

Usage:
    python skills/_shared/run_contract_tests.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixtures  # noqa: E402
import helper_fixtures  # noqa: E402
import mapping  # noqa: E402
import schemas as S  # noqa: E402
import workflow_fixtures  # noqa: E402
import candidate_quality_fixtures  # noqa: E402

SKILLS = Path(__file__).resolve().parent.parent

TRIGGERS = {
    "newbeginning": ["newbeginning", "new beginning", "where did we leave off",
                     "what were we working on", "pick up where we left off",
                     "catch me up", "start session", "open session", "resume work",
                     "whats the status", "brief me on this project"],
    "closingtime": ["closingtime", "closing time", "close session", "wrap up",
                    "we are done for now", "end session", "log this session",
                    "save the session", "lets close this out", "time to wrap"],
}
NEGATIVES = ["wrap this function", "close this file", "start the server",
             "resume the download", "whats the status of the build"]


def _frontmatter(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    return text[: text.index("\n---", 3)]


def check_activation() -> list[str]:
    issues, total = [], 0
    for skill, phrases in TRIGGERS.items():
        m = re.search(r"MUST trigger on:\s*(.+?)(?:\.\s*Sibling|$)",
                      _frontmatter(skill), re.DOTALL)
        if not m:
            issues.append(f"{skill}: no MUST-trigger list in frontmatter")
            continue
        declared = {t.strip().strip("'\"") for t in m.group(1).split(",")}
        for p in phrases:
            total += 1
            if p not in declared:
                issues.append(f"{skill}: trigger not declared: {p!r}")
        for neg in NEGATIVES:
            if neg in declared:
                issues.append(f"{skill}: negative phrase declared as trigger: {neg!r}")
    if total != 21:
        issues.append(f"expected 21 trigger phrases, checked {total}")
    return issues


def check_no_dollar_placeholders() -> list[str]:
    """`$N` in a SKILL.md body is claimed by slash-command argument substitution.

    Discovered 2026-08-03: invoking `/closingtime <args>` rewrote every `$1`..`$6`
    in the skill's SQL templates with the caller's words, producing
    `where id = we` and `values (we, will, not, push, to, origin)`. A model
    following those templates writes nonsense to the Tasks DB.

    Use angle-bracket placeholders (`'<task-uuid>'`, `<priority>`) instead.
    """
    issues = []
    for skill in TRIGGERS:
        text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r"\$\d", line):
                issues.append(f"{skill}/SKILL.md:{n}: {m.group(0)!r} in {line.strip()!r}")
    return issues


def check_no_step_refs() -> list[str]:
    found = []
    for skill in TRIGGERS:
        text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
        sibling = "closingtime" if skill == "newbeginning" else "newbeginning"
        for m in re.finditer(rf"`?{sibling}`?\s+Step\s+\d+", text):
            found.append(f"{skill}: {m.group(0)!r}")
    return found


def run() -> int:
    print("=" * 66)
    print("Session-skill contract tests")
    print("=" * 66)
    failures: list[str] = []

    probs = mapping.self_check()
    for skill in ("newbeginning", "closingtime"):
        c = mapping.counts(skill)
        print(f"  mapping {skill:14} {c['total']:3} rows  retained={c['retained']} "
              f"mapped={c['mapped']} retired={c['retired']}")
    failures += [f"mapping: {p}" for p in probs]
    print(f"  [{'PASS' if not probs else 'FAIL'}] checklist mapping table\n")

    vf = fixtures.valid_fixtures()
    bad = [f"{n}: {v['failures']}" for n, (e, r) in sorted(vf.items())
           if not (v := S.validate_envelope(e, r))["valid"]]
    failures += [f"fixture: {b}" for b in bad]
    print(f"  [{'PASS' if not bad else 'FAIL'}] {len(vf)} valid fixtures validate cleanly")
    for b in bad:
        print(f"        └─ {b}")

    ms = fixtures.mutants()
    survived, wrong = [], []
    for name, env, rows, expected in ms:
        v = S.validate_envelope(env, rows)
        if v["valid"]:
            survived.append(name)
        elif expected not in {f["code"] for f in v["failures"]}:
            wrong.append(f"{name}: expected {expected}, got "
                         f"{sorted({f['code'] for f in v['failures']})}")
    failures += [f"mutant survived: {m}" for m in survived] + \
                [f"mutant wrong code: {m}" for m in wrong]
    print(f"  [{'PASS' if not survived and not wrong else 'FAIL'}] {len(ms)} mutants — "
          f"each fails with its declared code")
    for m in survived + wrong:
        print(f"        └─ {m}")

    act = check_activation()
    failures += [f"activation: {a}" for a in act]
    print(f"  [{'PASS' if not act else 'FAIL'}] 21 trigger phrases declared, "
          f"{len(NEGATIVES)} negatives excluded")
    for a in act:
        print(f"        └─ {a}")

    dollars = check_no_dollar_placeholders()
    failures += [f"placeholder: {d}" for d in dollars]
    print(f"  [{'PASS' if not dollars else 'FAIL'}] no `$N` placeholders "
          f"(slash-command args would overwrite them)")
    for d in dollars:
        print(f"        └─ {d}")

    refs = check_no_step_refs()
    print(f"  [{'WARN' if refs else 'PASS'}] cross-skill step-number references")
    for r in refs:
        print(f"        └─ {r} (known; scheduled for the vNext rewrite)")

    helper_bad = helper_fixtures.run()
    failures += [f"helper: {problem}" for problem in helper_bad]
    print(f"  [{'PASS' if not helper_bad else 'FAIL'}] "
          f"{len(helper_fixtures.CHECKS)} Phase 2 helper fixture groups")
    for problem in helper_bad:
        print(f"        └─ {problem}")

    workflow_bad = workflow_fixtures.run()
    failures += [f"workflow: {problem}" for problem in workflow_bad]
    print(f"  [{'PASS' if not workflow_bad else 'FAIL'}] "
          f"{len(workflow_fixtures.CHECKS)} Phase 3 workflow/package groups")
    for problem in workflow_bad:
        print(f"        └─ {problem}")

    if candidate_quality_fixtures.run() != 0:
        failures.append("bilingual candidate-quality fixture catalog failed")

    print(f"\n  Not covered here ({len(fixtures.DEFERRED)} fixture families + the "
          f"historical-corpus scorer self-test):")
    for fam, why in fixtures.DEFERRED.items():
        print(f"        - {fam}: {why}")
    print("        - scorer self-test: requires the private evaluation ledger")

    print("\n" + "=" * 66)
    if failures:
        print(f"CONTRACT TESTS: FAILED ({len(failures)})")
        for f in failures:
            print("  -", f)
        return 1
    print("CONTRACT TESTS: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
