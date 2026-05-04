#!/usr/bin/env python3
"""Structural eval for the closingtime skill.

Runs deterministic checks on the skill's source file.
Exit code 0 = all pass, 1 = one or more failures.

What this covers
----------------
- Frontmatter: name, description, version fields present and well-formed.
- 7-part section structure: all expected numbered sections present.
- Sibling skill reference: newbeginning mentioned as the paired skill.
- Trigger phrases: the MUST-trigger list in the description matches documented
  triggers in the body text.
- Session entry template: the entry template contains all required fields.
- Project index template: the index format contains all required sections.
- Closing ritual: the Semisonic line and checkmark format are present.
- Harness adaptations table: Required/Optional capability structure present.

What this does NOT cover
------------------------
- Whether the skill produces good session entries (that's the Eval Criteria's job).
- Whether the skill triggers on realistic prompts (non-deterministic).
- Whether an actual model follows the workflow correctly (behavioral, not structural).

Run from the skill root:
    python evals/structural_eval.py

Or from anywhere:
    python path/to/skills/closingtime/evals/structural_eval.py
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
    "closingtime",
    "closing time",
    "close session",
    "wrap up",
    "we are done for now",
    "end session",
    "log this session",
    "save the session",
    "lets close this out",
    "time to wrap",
}

REQUIRED_ENTRY_FIELDS = [
    "Focus:",
    "Done:",
    "Decisions:",
    "Next:",
    "Blockers:",
]

REQUIRED_INDEX_SECTIONS = [
    "Summary",
    "Key Decisions",
    "Active TODOs",
    "Key Files",
]


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

    if "name" in fm and fm["name"] != "closingtime":
        issues.append(
            f"Frontmatter 'name' should be 'closingtime', got '{fm['name']}'"
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
    """The skill must reference newbeginning as its sibling."""
    issues: list[str] = []
    text = read(SKILL_MD)

    if "newbeginning" not in text.lower():
        issues.append("No reference to sibling skill 'newbeginning' found in SKILL.md")
        return issues

    fm = extract_frontmatter(text)
    desc = fm.get("description", "")
    if "newbeginning" not in desc:
        issues.append(
            "Description does not mention 'newbeginning' — sibling pointer "
            "should be in the description for harness-level disambiguation"
        )

    return issues


def check_trigger_phrases() -> list[str]:
    """Trigger phrases in the description's MUST-trigger list should match expected set."""
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


def check_session_entry_template() -> list[str]:
    """The session entry template must contain all required fields."""
    issues: list[str] = []
    text = read(SKILL_MD)

    template_match = re.search(
        r"Entry template.*?\n```markdown\n(.*?)```", text, re.DOTALL
    )
    if not template_match:
        issues.append("Session entry template code block not found")
        return issues

    template = template_match.group(1)
    for field in REQUIRED_ENTRY_FIELDS:
        if field not in template:
            issues.append(f"Session entry template missing required field: {field}")

    return issues


def check_project_index_template() -> list[str]:
    """The project index format must contain all required sections."""
    issues: list[str] = []
    text = read(SKILL_MD)

    index_match = re.search(
        r"Step 3: Update project_index.*?\n```markdown\n(.*?)```", text, re.DOTALL
    )
    if not index_match:
        issues.append("Project index template code block not found")
        return issues

    template = index_match.group(1)
    for section in REQUIRED_INDEX_SECTIONS:
        if section not in template:
            issues.append(f"Project index template missing required section: {section}")

    return issues


def check_closing_ritual() -> list[str]:
    """The closing ritual must include the Semisonic line and checkmark format."""
    issues: list[str] = []
    text = read(SKILL_MD)

    if "You don't have to go home, but you can't stay here" not in text:
        issues.append("Closing ritual Semisonic line not found")

    if "Session #N logged" not in text:
        issues.append("Closing ritual checkmark format not found ('Session #N logged')")

    if "Project index updated" not in text:
        issues.append(
            "Closing ritual checkmark format not found ('Project index updated')"
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
    ("session_entry_template", check_session_entry_template),
    ("project_index_template", check_project_index_template),
    ("closing_ritual", check_closing_ritual),
    ("harness_adaptations_table", check_harness_adaptations_table),
]


def run() -> int:
    print(f"Structural eval: closingtime skill at {SKILL_ROOT}\n")
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
