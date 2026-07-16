#!/usr/bin/env python3
"""Structural eval for the calibre skill.

Runs deterministic checks on the skill's source file.
Exit code 0 = all pass, 1 = one or more failures.

What this covers
----------------
- Frontmatter: name, description, version fields present and well-formed.
- 8-part section structure: all expected numbered sections present.
- Trigger phrases: the MUST-trigger list in the description matches the
  documented expected set.
- Core Workflow: the four labelled workflows (A-D) are present.
- Command Reference: the scoped CLI tools are all named.
- Read-only vs. mutating boundary: both classes named; library-write
  out-of-scope language present.
- Decision Rules table: table present with key situations (overwrite,
  in-place, DRM).
- Harness Adaptations: Required/Optional capability structure present.

What this does NOT cover
------------------------
- Whether Calibre is installed or the CLI actually runs.
- Whether a conversion or metadata edit produces correct output (behavioral).
- Whether the skill triggers on realistic prompts (non-deterministic).

Run from the skill root:
    python evals/structural_eval.py

Or from anywhere:
    python path/to/skills/calibre/evals/structural_eval.py
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
    "4. Command Reference",
    "5. Decision Rules",
    "6. Harness Adaptations",
    "7. Eval Criteria",
    "8. Version & Changelog",
]

EXPECTED_TRIGGERS = {
    "convert ebook",
    "convert this book",
    "convert to epub",
    "convert to mobi",
    "convert to azw3",
    "convert to pdf",
    "ebook metadata",
    "fix ebook metadata",
    "set ebook metadata",
    "fetch book metadata",
    "calibre convert",
}

EXPECTED_WORKFLOWS = [
    "Workflow A",
    "Workflow B",
    "Workflow C",
    "Workflow D",
]

EXPECTED_TOOLS = [
    "ebook-convert",
    "ebook-meta",
    "fetch-ebook-metadata",
    "calibredb",
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

    if "name" in fm and fm["name"] != "calibre":
        issues.append(f"Frontmatter 'name' should be 'calibre', got '{fm['name']}'")

    if "version" in fm and fm["version"]:
        if not re.match(r"^\d+\.\d+\.\d+$", fm["version"]):
            issues.append(
                f"Version '{fm['version']}' is not valid semver (expected X.Y.Z)"
            )

    return issues


def check_section_structure() -> list[str]:
    """All 8 expected numbered sections must be present as ## headings."""
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

    must_match = re.search(r"MUST trigger on:\s*(.+?)(?:\.\s*Do NOT)", desc)
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


def check_core_workflows() -> list[str]:
    """All four labelled workflows (A-D) must be documented in the Core Workflow."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 3\. Core Workflow\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 3. Core Workflow' not found or empty")
        return issues

    section = section_match.group(1)
    for wf in EXPECTED_WORKFLOWS:
        if wf not in section:
            issues.append(f"Core Workflow missing: {wf}")

    return issues


def check_command_reference() -> list[str]:
    """All scoped CLI tools must be named in the Command Reference section."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 4\. Command Reference\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 4. Command Reference' not found or empty")
        return issues

    section = section_match.group(1)
    for tool in EXPECTED_TOOLS:
        if tool not in section:
            issues.append(f"Command Reference missing tool: {tool}")

    return issues


def check_readonly_mutating_boundary() -> list[str]:
    """The skill must name both the read-only and mutating classes and keep
    library writes out of scope."""
    issues: list[str] = []
    text = read(SKILL_MD).lower()

    if "read-only" not in text:
        issues.append("Missing 'read-only' classification language")
    if "mutating" not in text:
        issues.append("Missing 'mutating' classification language")
    if "out of scope" not in text and "out-of-scope" not in text:
        issues.append(
            "Missing 'out of scope' boundary for mutating library operations"
        )
    # calibredb library-write subcommands should be explicitly named as gated
    if "set_metadata" not in text:
        issues.append(
            "Expected explicit mention of a gated calibredb write (e.g. set_metadata)"
        )

    return issues


def check_decision_rules_table() -> list[str]:
    """Section 5 must contain a decision rules table with key situations."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 5\. Decision Rules\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 5. Decision Rules' not found or empty")
        return issues

    section = section_match.group(1).lower()

    if "|" not in section:
        issues.append("Decision Rules missing table (expected markdown table)")
        return issues

    expected_situations = [
        "skip",
        "overwrite",
        "in-place",
        "drm",
    ]
    for situation in expected_situations:
        if situation.lower() not in section:
            issues.append(
                f"Decision Rules table may be missing situation involving: {situation}"
            )

    return issues


def check_harness_adaptations() -> list[str]:
    """Section 6 must contain a Required/Optional capabilities structure."""
    issues: list[str] = []
    text = read(SKILL_MD)

    section_match = re.search(
        r"## 6\. Harness Adaptations\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        issues.append("Section '## 6. Harness Adaptations' not found or empty")
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
    ("trigger_phrases", check_trigger_phrases),
    ("core_workflows", check_core_workflows),
    ("command_reference", check_command_reference),
    ("readonly_mutating_boundary", check_readonly_mutating_boundary),
    ("decision_rules_table", check_decision_rules_table),
    ("harness_adaptations", check_harness_adaptations),
]


def run() -> int:
    print(f"Structural eval: calibre skill at {SKILL_ROOT}\n")
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
