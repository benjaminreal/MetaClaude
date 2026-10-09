#!/usr/bin/env python3
"""Structural and packaging eval for the closingtime vNext candidate."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
EXPECTED_TRIGGERS = {
    "closingtime", "closing time", "close session", "wrap up",
    "we are done for now", "end session", "log this session",
    "save the session", "lets close this out", "time to wrap",
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
    if fm.get("name") != "closingtime":
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
    if "newbeginning" not in fm.get("description", ""):
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


def check_named_gates() -> list[str]:
    source = text()
    required = (
        "OBSERVATION_GATE", "DRAFT_GATE", "APPROVAL_GATE", "CONCURRENCY_GATE",
        "VERIFICATION_GATE", "LEARNING_GATE", "CLOSING_GATE",
        "PENDING_LEARNING_LIFECYCLE", "INSTRUCTION_RESOLUTION",
    )
    return [f"missing {item}" for item in required if item not in source]


def check_recovery_skip_interruption() -> list[str]:
    source = text()
    required = (
        "SKIP-tasks", "SKIP-index", "SKIP-learning", "SKIP-openbrain",
        "SKIP-ritual", "On interruption", "Pre-draft interruption",
        "Post-approval interruption", "first session",
    )
    return [f"missing {item}" for item in required if item not in source]


def check_instruction_and_capability() -> list[str]:
    source = text()
    issues: list[str] = []
    for phrase in (
        "project-root", "ancestor", "instructions_absent", "absent",
        "present_unauthenticated", "present_wrong_scope", "working",
    ):
        if phrase not in source:
            issues.append(f"missing {phrase}")
    if re.search(r"(?:root|project-root)\s+`(?:CLAUDE|AGENTS)\.md`", source):
        issues.append("unconditional root instruction pointer")
    if re.search(r"(?:closingtime|newbeginning)\s+Step\s+\d+", source):
        issues.append("cross-skill step-number reference")
    return issues


def check_templates_and_boundaries() -> list[str]:
    source = text()
    required = (
        "Focus:", "Done:", "Decisions:", "Next:", "Blockers:",
        "## Summary", "## Key Decisions", "## Active TODOs", "## Key Files",
        "Read-only mirror", "scripts/runtime_cli.py", "append",
        "separate request in this invocation",
    )
    return [f"missing {item}" for item in required if item not in source]


def check_ritual_compatibility_size() -> list[str]:
    source = text()
    body = source[source.find("\n---", 3) + 4 :]
    issues: list[str] = []
    required = (
        "Session #N logged", "Tasks DB updated",
        "Project index narrative + task mirror updated",
        "You don't have to go home, but you can't stay here",
        "v1-compatible", "instruction_bytes_loaded",
    )
    issues.extend(f"missing {item}" for item in required if item not in source)
    if len(body.splitlines()) > 500:
        issues.append(f"body exceeds 500 lines: {len(body.splitlines())}")
    if re.search(r"\$\d", source):
        issues.append("dollar-number placeholder present")
    if "```sql" in source:
        issues.append("SQL template remained in runtime body")
    return issues


def check_candidate_quality() -> list[str]:
    source = " ".join(text().split())
    required = (
        "references/candidate_quality_contract.md",
        "plain, standalone",
        "one central insight",
        "explicit user preference",
        "dominant session language",
        "English or Spanish",
        "internal IDs/codes",
        "after owner edits",
        "fresh approval",
    )
    return [f"candidate quality rule absent: {item}" for item in required if item not in source]


CHECKS = (
    ("frontmatter", check_frontmatter),
    ("structure", check_structure),
    ("runtime_package", check_runtime_package),
    ("named_gates", check_named_gates),
    ("recovery_skip_interruption", check_recovery_skip_interruption),
    ("instruction_and_capability", check_instruction_and_capability),
    ("templates_and_boundaries", check_templates_and_boundaries),
    ("ritual_compatibility_size", check_ritual_compatibility_size),
    ("candidate_quality", check_candidate_quality),
)


def run() -> int:
    failed: list[str] = []
    print(f"Structural eval: closingtime at {ROOT}\n")
    for name, check in CHECKS:
        try:
            issues = check()
        except Exception as exc:
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
