#!/usr/bin/env python3
"""Structural and packaging eval for the newbeginning vNext candidate."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
EXPECTED_TRIGGERS = {
    "newbeginning", "new beginning", "where did we leave off",
    "what were we working on", "pick up where we left off", "catch me up",
    "start session", "open session", "resume work", "whats the status",
    "brief me on this project",
}
SECTIONS = (
    "1. Purpose & Scope", "2. Pre-flight Checklist", "3. Core Workflow",
    "4. Harness Adaptations", "5. Decision Rules", "6. Eval Criteria",
    "7. Version & Changelog",
)


def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def frontmatter(source: str) -> dict[str, str]:
    end = source.find("\n---", 3)
    if not source.startswith("---") or end < 0:
        return {}
    out: dict[str, str] = {}
    for line in source[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip('"')
    return out


def check_frontmatter() -> list[str]:
    source = text()
    fm = frontmatter(source)
    issues: list[str] = []
    if fm.get("name") != "newbeginning":
        issues.append(f"name={fm.get('name')!r}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", fm.get("version", "")):
        issues.append(f"invalid version={fm.get('version')!r}")
    match = re.search(r"MUST trigger on:\s*(.+?)(?:\. Sibling|\. Sibling)", fm.get("description", ""))
    if not match:
        issues.append("missing MUST trigger list")
    else:
        got = {item.strip().strip("'\"") for item in match.group(1).split(",")}
        if got != EXPECTED_TRIGGERS:
            issues.append(f"trigger drift: missing={sorted(EXPECTED_TRIGGERS-got)} extra={sorted(got-EXPECTED_TRIGGERS)}")
    if "closingtime" not in fm.get("description", ""):
        issues.append("sibling absent from description")
    return issues


def check_structure() -> list[str]:
    source = text()
    return [name for name in SECTIONS if f"## {name}" not in source]


def check_runtime_package() -> list[str]:
    required = (
        "scripts/runtime_cli.py", "scripts/helpers.py", "scripts/schemas.py",
        "scripts/workflow.py", "references/runtime_contract.md",
        "references/task_operations.md", "references/candidate_quality_contract.md",
    )
    return [f"missing {path}" for path in required if not (ROOT / path).is_file()]


def check_named_contract() -> list[str]:
    source = text()
    required = (
        "OBSERVATION_GATE", "INSTRUCTION_RESOLUTION", "RECOVERY_BOOTSTRAP",
        "RECOVERY_RECONSTRUCT", "N-conflicted", "PENDING_LEARNING_LIFECYCLE",
        "scripts/runtime_cli.py", "references/runtime_contract.md",
    )
    return [f"missing {item}" for item in required if item not in source]


def check_instruction_resolution() -> list[str]:
    source = text()
    issues: list[str] = []
    for phrase in ("project root", "ancestor", "instructions_absent"):
        if phrase not in source:
            issues.append(f"instruction case absent: {phrase}")
    if re.search(r"(?:root|project-root)\s+`(?:CLAUDE|AGENTS)\.md`", source):
        issues.append("unconditional root instruction pointer")
    if re.search(r"(?:closingtime|newbeginning)\s+Step\s+\d+", source):
        issues.append("cross-skill step-number reference")
    return issues


def check_capability_and_budget() -> list[str]:
    source = text()
    required = (
        "absent", "present_unauthenticated", "present_wrong_scope", "working",
        "instruction_bytes_loaded", "projection_bytes_emitted", "brief_words",
        "16,384", "250 words",
    )
    return [f"missing {item}" for item in required if item not in source]


def check_write_and_task_boundaries() -> list[str]:
    source = text()
    required = (
        "Permitted writes are limited", "explicit approval", "current receipt",
        "frozen markdown TODOs", "references/task_operations.md",
        "Do not edit the Markdown task mirror",
    )
    return [f"missing {item}" for item in required if item not in source]


def check_compatibility_and_size() -> list[str]:
    source = text()
    body = source[source.find("\n---", 3) + 4 :]
    issues: list[str] = []
    for field in ("project_index.md", "project_session.md", "pending_learnings.md", "v1 readers"):
        if field not in source:
            issues.append(f"compatibility field absent: {field}")
    if len(body.splitlines()) > 500:
        issues.append(f"body exceeds 500 lines: {len(body.splitlines())}")
    if re.search(r"\$\d", source):
        issues.append("dollar-number placeholder present")
    return issues


def check_candidate_quality() -> list[str]:
    source = " ".join(text().split())
    required = (
        "references/candidate_quality_contract.md",
        "before presenting or revising",
        "after owner edits",
        "fresh approval",
        "explicit user preference",
        "dominant session language",
        "English or Spanish",
    )
    return [f"candidate quality rule absent: {item}" for item in required if item not in source]


CHECKS = (
    ("frontmatter", check_frontmatter),
    ("structure", check_structure),
    ("runtime_package", check_runtime_package),
    ("named_contract", check_named_contract),
    ("instruction_resolution", check_instruction_resolution),
    ("capability_and_budget", check_capability_and_budget),
    ("write_and_task_boundaries", check_write_and_task_boundaries),
    ("compatibility_and_size", check_compatibility_and_size),
    ("candidate_quality", check_candidate_quality),
)


def run() -> int:
    failed: list[str] = []
    print(f"Structural eval: newbeginning at {ROOT}\n")
    for name, check in CHECKS:
        try:
            issues = check()
        except Exception as exc:  # test runner must report, not crash silently
            issues = [f"crashed: {type(exc).__name__}: {exc}"]
        print(f"{'PASS' if not issues else 'FAIL'}  {name}")
        for issue in issues:
            print(f"        - {issue}")
        if issues:
            failed.append(name)
    print(f"\n{len(CHECKS)-len(failed)}/{len(CHECKS)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
