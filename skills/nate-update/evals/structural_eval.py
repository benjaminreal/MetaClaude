#!/usr/bin/env python3
"""Structural eval for the nate-update skill.

Runs deterministic checks on the skill's source file.
Exit code 0 = all pass, 1 = one or more failures.

What this covers
----------------
- Frontmatter: name, description, version fields present and well-formed.
- 10-part section structure: all expected numbered sections present.
- Trigger phrases: the MUST-trigger list in the description matches documented
  triggers in the body text.
- State file schema: the JSON state file template is present with required keys.
- Pipeline stages: all 7 stages documented in the Core Workflow.
- Script reference table: all expected scripts are referenced.
- Harness adaptations table: Required/Optional capability structure present.
- Decision rules table: table present with expected situation entries.

What this does NOT cover
------------------------
- Whether the pipeline actually runs (requires live Substack, Chrome MCP, etc.).
- Whether the skill triggers on realistic prompts (non-deterministic).
- Whether an actual model follows the workflow correctly (behavioral, not structural).

Run from the skill root:
    python evals/structural_eval.py

Or from anywhere:
    python path/to/skills/nate-update/evals/structural_eval.py
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
    "4. State Management",
    "5. Chrome MCP Health Strategy",
    "6. Decision Rules",
    "7. Harness Adaptations",
    "8. Script Reference",
    "9. Eval Criteria",
    "10. Version & Changelog",
]

EXPECTED_TRIGGERS = {
    "update nate archive",
    "nate update",
    "sync nate content",
    "update nate",
    "nate archive update",
    "sync nate",
    "nate sync",
}

EXPECTED_STAGES = [
    "Stage 1",
    "Stage 2",
    "Stage 3",
    "Stage 4",
    "Stage 5",
    "Stage 6",
    "Stage 7",
]

EXPECTED_SCRIPTS = [
    "ingest_nate_content.py",
    "tag_nate_articles.py",
    "download_paywalled_transcripts.py",
    "regenerate_indexes.py",
    "verify_nate_ingest.py",
    "build_inventory.py",
    "check_env.py",
]

STATE_FILE_KEYS = [
    "schema_version",
    "run_id",
    "started",
    "window",
    "baseline",
    "delta_slugs",
    "completed_stages",
    "errors",
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

    if "name" in fm and fm["name"] != "nate-update":
        issues.append(
            f"Frontmatter 'name' should be 'nate-update', got '{fm['name']}'"
        )

    if "version" in fm and fm["version"]:
        if not re.match(r"^\d+\.\d+\.\d+$", fm["version"]):
            issues.append(
                f"Version '{fm['version']}' is not valid semver (expected X.Y.Z)"
            )

    return issues


def check_section_structure() -> list[str]:
    """All 10 expected numbered sections must be present as ## headings."""
    issues: list[str] = []
    text = read(SKILL_MD)

    for section in EXPECTED_SECTIONS:
        pattern = rf"^##\s+{re.escape(section)}\s*$"
        if not re.search(pattern, text, re.MULTILINE):
            issues.append(f"Missing expected section: '## {section}'")

    return issues


def check_trigger_phrases() -> list[str]:
    """Trigger phrases in the description's MUST-trigger list should match expected set."""
    issues: list[str] = []
    text = read(SKILL_MD)
    fm = extract_frontmatter(text)
    desc = fm.get("description", "")

    must_match = re.search(r"MUST trigger on:\s*(.+?)(?:\.\s*Do)", desc)
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


def check_state_file_schema() -> list[str]:
    """The state file JSON template must contain all required keys."""
    issues: list[str] = []
    text = read(SKILL_MD)

    json_match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if not json_match:
        issues.append("State file JSON schema template not found")
        return issues

    schema_text = json_match.group(1)
    for key in STATE_FILE_KEYS:
        if f'"{key}"' not in schema_text:
            issues.append(f"State file schema missing required key: {key}")

    return issues


def check_pipeline_stages() -> list[str]:
    """All 7 pipeline stages must be documented in the Core Workflow."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 3\. Core Workflow\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 3. Core Workflow' not found or empty")
        return issues

    section = section_match.group(1)
    for stage in EXPECTED_STAGES:
        if stage not in section:
            issues.append(f"Core Workflow missing: {stage}")

    return issues


def check_script_reference() -> list[str]:
    """All expected scripts must be referenced in the Script Reference section."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 8\. Script Reference\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 8. Script Reference' not found or empty")
        return issues

    section = section_match.group(1)
    for script in EXPECTED_SCRIPTS:
        if script not in section:
            issues.append(f"Script Reference missing: {script}")

    return issues


def check_harness_adaptations_table() -> list[str]:
    """Section 7 must contain a Required/Optional capabilities structure."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 7\. Harness Adaptations\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 7. Harness Adaptations' not found or empty")
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


def check_decision_rules_table() -> list[str]:
    """Section 6 must contain a decision rules table with key situations."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 6\. Decision Rules\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 6. Decision Rules' not found or empty")
        return issues

    section = section_match.group(1)

    if "|" not in section:
        issues.append("Decision Rules missing table (expected markdown table)")
        return issues

    expected_situations = [
        "skip",
        "empty",
        "cost",
    ]
    for situation in expected_situations:
        if situation.lower() not in section.lower():
            issues.append(
                f"Decision Rules table may be missing situation involving: {situation}"
            )

    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    ("frontmatter_completeness", check_frontmatter_completeness),
    ("section_structure", check_section_structure),
    ("trigger_phrases", check_trigger_phrases),
    ("state_file_schema", check_state_file_schema),
    ("pipeline_stages", check_pipeline_stages),
    ("script_reference", check_script_reference),
    ("harness_adaptations_table", check_harness_adaptations_table),
    ("decision_rules_table", check_decision_rules_table),
]


def run() -> int:
    print(f"Structural eval: nate-update skill at {SKILL_ROOT}\n")
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
