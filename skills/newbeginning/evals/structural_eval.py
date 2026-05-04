#!/usr/bin/env python3
"""Structural eval for the newbeginning skill.

Runs deterministic checks on the skill's source file.
Exit code 0 = all pass, 1 = one or more failures.

What this covers
----------------
- Frontmatter: name, description, version fields present and well-formed.
- 7-part section structure: all expected numbered sections present.
- Sibling skill reference: closingtime mentioned as the paired skill.
- Trigger phrases: the MUST-trigger list in the description matches documented
  triggers in the body text.
- Token target: the ≤2.5K token budget is documented.
- Cold-start branch: Step 1a exists and describes the bootstrap path.
- Permitted-edit carve-out: the write boundary is explicitly stated.
- Harness adaptations table: Required/Optional capability structure present.

What this does NOT cover
------------------------
- Whether the skill produces good briefs (that's the Eval Criteria section's job).
- Whether the skill triggers on realistic prompts (non-deterministic).
- Whether an actual model follows the workflow correctly (behavioral, not structural).

Run from the skill root:
    python evals/structural_eval.py

Or from anywhere:
    python path/to/skills/newbeginning/evals/structural_eval.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_ROOT / "SKILL.md"

EXPECTED_SECTIONS = [
    "1. Purpose & Scope",
    "2. Pre-flight Checklist",
    "3. Core Workflow",
    "4. Harness Adaptations",
    "5. Decision Rules",
    "6. Eval Criteria",
    "7. Version & Changelog",
]

EXPECTED_TRIGGERS = {
    "newbeginning",
    "new beginning",
    "where did we leave off",
    "what were we working on",
    "pick up where we left off",
    "catch me up",
    "start session",
    "open session",
    "resume work",
    "whats the status",
    "brief me on this project",
}


def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8")


def extract_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip("\n")
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip().strip('"')
    return result


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_frontmatter_completeness() -> list[str]:
    """Frontmatter must contain name, description, and version fields."""
    issues: list[str] = []
    text = read(SKILL_MD)
    fm = extract_frontmatter(text)

    if not fm:
        issues.append("No YAML frontmatter found (expected --- delimited block at top)")
        return issues

    for field in ("name", "description", "version"):
        if field not in fm:
            issues.append(f"Frontmatter missing required field: {field}")
        elif not fm[field]:
            issues.append(f"Frontmatter field '{field}' is empty")

    if "name" in fm and fm["name"] != "newbeginning":
        issues.append(
            f"Frontmatter 'name' should be 'newbeginning', got '{fm['name']}'"
        )

    if "version" in fm and fm["version"]:
        if not re.match(r"^\d+\.\d+\.\d+$", fm["version"]):
            issues.append(
                f"Version '{fm['version']}' is not valid semver (expected X.Y.Z)"
            )

    return issues


def check_section_structure() -> list[str]:
    """All 7 expected numbered sections must be present as ## headings."""
    issues: list[str] = []
    text = read(SKILL_MD)

    for section in EXPECTED_SECTIONS:
        pattern = rf"^##\s+{re.escape(section)}\s*$"
        if not re.search(pattern, text, re.MULTILINE):
            issues.append(f"Missing expected section: '## {section}'")

    return issues


def check_sibling_reference() -> list[str]:
    """The skill must reference closingtime as its sibling."""
    issues: list[str] = []
    text = read(SKILL_MD)

    if "closingtime" not in text.lower():
        issues.append("No reference to sibling skill 'closingtime' found in SKILL.md")
        return issues

    fm = extract_frontmatter(text)
    desc = fm.get("description", "")
    if "closingtime" not in desc:
        issues.append(
            "Description does not mention 'closingtime' — sibling pointer "
            "should be in the description for harness-level disambiguation"
        )

    return issues


def check_trigger_phrases() -> list[str]:
    """Trigger phrases in the description's MUST-trigger list should all appear
    somewhere in the body text to confirm they're documented behavior."""
    issues: list[str] = []
    text = read(SKILL_MD)
    fm = extract_frontmatter(text)
    desc = fm.get("description", "")

    must_match = re.search(r"MUST trigger on:\s*(.+?)(?:\.|Sibling)", desc)
    if not must_match:
        issues.append("Description missing 'MUST trigger on:' phrase list")
        return issues

    trigger_text = must_match.group(1)
    triggers_found = {t.strip().strip("'\"") for t in trigger_text.split(",")}
    triggers_found = {t for t in triggers_found if t}

    missing_from_desc = EXPECTED_TRIGGERS - triggers_found
    if missing_from_desc:
        issues.append(
            f"Expected triggers missing from description's MUST-trigger list: "
            f"{sorted(missing_from_desc)}"
        )

    extra_in_desc = triggers_found - EXPECTED_TRIGGERS
    if extra_in_desc:
        issues.append(
            f"Description lists triggers not in EXPECTED_TRIGGERS constant: "
            f"{sorted(extra_in_desc)}. If intentional, update the constant."
        )

    return issues


def check_token_target() -> list[str]:
    """The skill must document its token budget (≤2.5K)."""
    issues: list[str] = []
    text = read(SKILL_MD)

    if "2.5K" not in text and "2500" not in text and "2,500" not in text:
        issues.append(
            "Token target not found. Expected '2.5K' or equivalent in the skill body "
            "(Section 6 Eval Criteria or Section 3)."
        )

    return issues


def check_cold_start_branch() -> list[str]:
    """Step 1a must exist and describe the cold-start bootstrap."""
    issues: list[str] = []
    text = read(SKILL_MD)

    if "### Step 1a" not in text:
        issues.append("Cold-start branch '### Step 1a' heading not found")
        return issues

    step_1a_match = re.search(
        r"### Step 1a.*?\n(.*?)(?=\n### |\n## |\Z)", text, re.DOTALL
    )
    if step_1a_match:
        body = step_1a_match.group(1)
        if "project_index.md" not in body:
            issues.append(
                "Step 1a does not mention creating project_index.md — "
                "cold-start should bootstrap this file"
            )
        if "interview" not in body.lower() and "ask" not in body.lower():
            issues.append(
                "Step 1a does not mention user interview/confirmation — "
                "cold-start writes must be user-confirmed"
            )

    return issues


def check_permitted_edit_carveout() -> list[str]:
    """The skill must explicitly state its write boundaries."""
    issues: list[str] = []
    text = read(SKILL_MD)

    write_gate_patterns = [
        r"permitted.edit",
        r"only\s+write",
        r"only\s+edit",
        r"permitted\s+.*\s+edit",
    ]

    found = any(re.search(p, text, re.IGNORECASE) for p in write_gate_patterns)
    if not found:
        issues.append(
            "No explicit write-boundary statement found. The skill should declare "
            "when it's permitted to write files (cold-start and priority adjustment only)."
        )

    return issues


def check_harness_adaptations_table() -> list[str]:
    """Section 4 must contain a Required/Optional capabilities structure."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 4\. Harness Adaptations\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 4. Harness Adaptations' not found or empty")
        return issues

    section = section_match.group(1)

    if "**Required:**" not in section and "Required:" not in section:
        issues.append("Harness Adaptations missing 'Required:' capabilities block")

    if "Optional" not in section:
        issues.append("Harness Adaptations missing 'Optional' capabilities block")

    if "|" not in section:
        issues.append(
            "Harness Adaptations missing capability table (expected markdown table "
            "with | delimiters)"
        )

    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    ("frontmatter_completeness", check_frontmatter_completeness),
    ("section_structure", check_section_structure),
    ("sibling_reference", check_sibling_reference),
    ("trigger_phrases", check_trigger_phrases),
    ("token_target", check_token_target),
    ("cold_start_branch", check_cold_start_branch),
    ("permitted_edit_carveout", check_permitted_edit_carveout),
    ("harness_adaptations_table", check_harness_adaptations_table),
]


def run() -> int:
    print(f"Structural eval: newbeginning skill at {SKILL_ROOT}\n")
    total = len(CHECKS)
    failed: list[str] = []
    for name, fn in CHECKS:
        try:
            issues = fn()
        except Exception as e:
            issues = [f"check crashed: {type(e).__name__}: {e}"]
        if issues:
            print(f"FAIL  {name}")
            for issue in issues:
                print(f"        - {issue}")
            failed.append(name)
        else:
            print(f"PASS  {name}")
    print()
    if failed:
        print(f"{len(failed)}/{total} check(s) failed: {failed}")
        return 1
    print(f"{total}/{total} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
