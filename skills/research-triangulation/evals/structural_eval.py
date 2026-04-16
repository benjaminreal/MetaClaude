#!/usr/bin/env python3
"""Structural eval for the research-triangulation skill.

Runs deterministic checks on the skill's source files and fixture outputs.
Exit code 0 = all pass, 1 = one or more failures.

What this covers
----------------
- Parameter Dictionary completeness: every {{VAR}} referenced in phase1-templates.md
  is defined in the Parameter Dictionary, and every entry in the dictionary is
  used somewhere in the templates.
- Reference-file integrity: every file SKILL.md's "Reference Files" table points
  to actually exists and is non-empty.
- Pass-type consistency: the valid pass types listed in the File Naming Convention
  table are the ones used in all example filenames elsewhere in the templates.
- Fixture filename conformance: every .md file under fixtures/ matches either the
  prompt or report naming pattern defined in phase1-templates.md.
- Fixture metadata header: every fixture report file begins with a YAML front-matter
  block containing all required keys.

What this does NOT cover
------------------------
- Whether the skill produces good research (that's the Tier 1 / Tier 2 rubrics' job).
- Whether the skill triggers on realistic prompts (use skill-creator's description-
  optimization loop for that — it's non-deterministic and belongs in a different tool).
- Whether an actual model, invoked with this skill, produces outputs that conform to
  the structural conventions. That is a behavioral question and would require the full
  skill-creator eval loop with subagents. This script only verifies that the skill's
  own rules are internally consistent and that reference fixtures comply.

Run from the skill root:
    python evals/structural_eval.py

Or from anywhere:
    python path/to/skills/multi-platform-research/evals/structural_eval.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_ROOT / "SKILL.md"
PHASE1_TEMPLATES = SKILL_ROOT / "references" / "phase1-templates.md"
CONSOLIDATION_TEMPLATE = SKILL_ROOT / "references" / "consolidation-template.md"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Required keys in the YAML metadata header, per phase1-templates.md § "Metadata Header".
# Keep this in sync with the template definition. If these diverge, the
# check_metadata_schema_consistency check below fails and will tell you.
REQUIRED_METADATA_KEYS = {
    "topic",
    "platform",
    "pass",
    "date",
    "source_profile",
    "primary_question",
    "recency_window",
}

# Naming patterns. These are derived from phase1-templates.md § "File Naming Convention".
# Prompt files: prompt_{{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}.md
# Report files: {{PLATFORM_NAME}}-{{PASS_TYPE}}_{{TOPIC_SLUG}}_{{DATE_ISO}}.md (with
#               optional _PARTIAL suffix per the handoff template).
PROMPT_FILENAME_RE = re.compile(
    r"^prompt_(?P<platform>[A-Za-z]+)-(?P<pass>[A-Za-z]+)_(?P<slug>[a-z0-9][a-z0-9-]*)\.md$"
)
REPORT_FILENAME_RE = re.compile(
    r"^(?P<platform>[A-Za-z]+)-(?P<pass>[A-Za-z]+)_(?P<slug>[a-z0-9][a-z0-9-]*)_"
    r"(?P<date>\d{4}-\d{2}-\d{2})(?:_PARTIAL)?\.md$"
)

# Valid pass types per platform, per the File Naming Convention table.
# This check uses this dict as the expected truth and validates that the table
# in phase1-templates.md agrees. If you change the table, change this too.
EXPECTED_VALID_PASS_TYPES = {
    "Claude": {"DR"},
    "Perplexity": {"Web", "Academic"},
    "Gemini": {"DR"},
    "ChatGPT": {"DR"},
}


# ---------------------------------------------------------------------------
# Utility parsing
# ---------------------------------------------------------------------------

def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8")


def find_double_brace_vars(text: str) -> set[str]:
    """Return the set of {{VAR_NAME}} identifiers appearing in text."""
    return set(re.findall(r"\{\{\s*([A-Z][A-Z0-9_]*)\s*\}\}", text))


def extract_parameter_dictionary(templates_text: str) -> set[str]:
    """Extract parameter names from the Parameter Dictionary table in phase1-templates.md.

    The dictionary is the markdown table that starts after the '## Parameter Dictionary'
    heading. Each row has the variable in the first cell, formatted as `` `{{VAR}}` ``.
    """
    # Isolate the section from '## Parameter Dictionary' up to the next '## ' heading.
    m = re.search(
        r"##\s*Parameter Dictionary\s*\n(.*?)(?:\n##\s|\Z)",
        templates_text,
        re.DOTALL,
    )
    if not m:
        raise ValueError("Parameter Dictionary section not found in phase1-templates.md")
    section = m.group(1)
    # Match table rows that start with | `{{VAR}}` |
    return set(re.findall(r"\|\s*`\{\{\s*([A-Z][A-Z0-9_]*)\s*\}\}`\s*\|", section))


def extract_parameter_dictionary_text_region(templates_text: str) -> str:
    """Return the text *inside* the Parameter Dictionary section, used to exclude the
    dictionary's own citations of variables when computing template usage."""
    m = re.search(
        r"##\s*Parameter Dictionary\s*\n(.*?)(?:\n##\s|\Z)",
        templates_text,
        re.DOTALL,
    )
    return m.group(1) if m else ""


def extract_valid_pass_type_table(templates_text: str) -> dict[str, set[str]]:
    """Extract the valid-pass-types table from phase1-templates.md."""
    m = re.search(
        r"\*\*Valid pass types per platform:\*\*\s*\n\n(\|[^\n]+\|\n\|[-:|\s]+\|\n((?:\|[^\n]+\|\n?)+))",
        templates_text,
    )
    if not m:
        raise ValueError("Valid pass types table not found in phase1-templates.md")
    rows_block = m.group(2)
    result: dict[str, set[str]] = {}
    for line in rows_block.strip().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        platform = cells[0]
        # Each cell item may look like `DR` (Deep Research) — drop parenthetical
        # commentary first, then strip backticks and whitespace.
        pass_types = set()
        for raw in cells[1].split(","):
            cleaned = re.sub(r"\s*\(.*?\)", "", raw).strip()
            cleaned = cleaned.strip("`").strip()
            if cleaned:
                pass_types.add(cleaned)
        result[platform] = pass_types
    return result


def extract_reference_files_table(skill_md_text: str) -> list[str]:
    """Extract the list of reference file paths from SKILL.md's 'Reference Files' table."""
    m = re.search(
        r"##\s*Reference Files\s*\n(.*?)(?:\n##\s|\Z)",
        skill_md_text,
        re.DOTALL,
    )
    if not m:
        return []
    section = m.group(1)
    paths = re.findall(r"`(references/[^`]+)`", section)
    return paths


def parse_yaml_frontmatter(text: str) -> dict[str, str] | None:
    """Very small YAML front-matter parser: expects a `---`-delimited block at the top
    containing simple `key: value` lines. Returns a dict or None if not found."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end].strip("\n")
    result: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_parameter_dictionary_completeness() -> list[str]:
    """Every {{VAR}} referenced in phase1-templates.md is defined in the Parameter
    Dictionary, and every entry in the dictionary is used in at least one template
    block in the same file."""
    issues: list[str] = []
    text = read(PHASE1_TEMPLATES)
    defined = extract_parameter_dictionary(text)

    # Exclude the dictionary region itself when computing usage, so that variables
    # *defined* in the dictionary don't count as *used* just by being listed there.
    dict_region = extract_parameter_dictionary_text_region(text)
    usage_text = text.replace(dict_region, "")
    # Also exclude inline-backticked occurrences like `{{VAR_NAME}}`. Those are prose
    # mentions of the convention itself (e.g., "Resolve every `{{VAR_NAME}}`...")
    # rather than real template variables. Genuine template usages live in YAML blocks,
    # markdown table rows, and template bodies without inline backticks.
    usage_text = re.sub(r"`\{\{\s*[A-Z][A-Z0-9_]*\s*\}\}`", "", usage_text)
    used = find_double_brace_vars(usage_text)

    undefined = used - defined
    if undefined:
        issues.append(
            f"{len(undefined)} variable(s) used in templates but missing from Parameter "
            f"Dictionary: {sorted(undefined)}"
        )

    unused = defined - used
    if unused:
        issues.append(
            f"{len(unused)} variable(s) in Parameter Dictionary but never used in any "
            f"template block: {sorted(unused)}"
        )

    return issues


def check_reference_files_exist() -> list[str]:
    """Every `references/<path>` mentioned in SKILL.md's Reference Files table must
    exist on disk and be non-empty."""
    issues: list[str] = []
    paths = extract_reference_files_table(read(SKILL_MD))
    if not paths:
        issues.append(
            "SKILL.md 'Reference Files' table appears to be empty or malformed — expected "
            "at least one row referencing `references/<file>`."
        )
        return issues
    for rel in paths:
        full = SKILL_ROOT / rel
        if not full.exists():
            issues.append(f"Referenced file missing: {rel}")
        elif full.stat().st_size == 0:
            issues.append(f"Referenced file is empty: {rel}")
    return issues


def check_pass_type_consistency() -> list[str]:
    """The pass-type table in phase1-templates.md must match EXPECTED_VALID_PASS_TYPES,
    and every example filename elsewhere in the file must use only pass types the
    table declares valid for that platform."""
    issues: list[str] = []
    text = read(PHASE1_TEMPLATES)
    table = extract_valid_pass_type_table(text)

    # Structural agreement between table and the contract declared in this script.
    if table != EXPECTED_VALID_PASS_TYPES:
        issues.append(
            "Valid-pass-types table in phase1-templates.md does not match the expected "
            f"contract. Expected {EXPECTED_VALID_PASS_TYPES}, got {table}. If you "
            "intentionally changed the table, update EXPECTED_VALID_PASS_TYPES in this "
            "script to match."
        )
        # Can't usefully continue — bail out of this check.
        return issues

    # Scan example filenames in the file for non-conforming pass types.
    # Matches filenames like Claude-DR_foo_... or prompt_Perplexity-Web_foo...
    example_pattern = re.compile(
        r"\b(?:prompt_)?(?P<platform>Claude|Perplexity|Gemini|ChatGPT)-"
        r"(?P<pass>[A-Za-z]+)_[a-z0-9-]+"
    )
    for m in example_pattern.finditer(text):
        platform = m.group("platform")
        pass_type = m.group("pass")
        valid = table.get(platform, set())
        # Skip when the pass type is a template variable placeholder (e.g., {{PASS_TYPE}})
        # — that case is covered by the example after variable resolution.
        if pass_type in {"PASS", "PASSTYPE"}:
            continue
        if pass_type not in valid:
            issues.append(
                f"Example filename uses invalid pass type for platform: "
                f"{platform}-{pass_type} (valid for {platform}: {sorted(valid)})"
            )
    return issues


def check_metadata_schema_consistency() -> list[str]:
    """The metadata header spec in phase1-templates.md must declare exactly the keys
    this script considers required (REQUIRED_METADATA_KEYS). Catches drift between
    the template's schema and any fixtures/tools that depend on it."""
    issues: list[str] = []
    text = read(PHASE1_TEMPLATES)
    m = re.search(
        r"###\s*Metadata Header\s*\n(.*?)(?:\n###\s|\n##\s|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        issues.append("Metadata Header subsection not found in phase1-templates.md")
        return issues
    section = m.group(1)
    # Extract keys from the YAML-ish block: lines shaped like `key: {{VAR}}`.
    declared_keys = set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*:\s*\{\{", section, re.MULTILINE))
    missing = REQUIRED_METADATA_KEYS - declared_keys
    extra = declared_keys - REQUIRED_METADATA_KEYS
    if missing:
        issues.append(
            f"Metadata Header declares fewer keys than required: missing {sorted(missing)}"
        )
    if extra:
        issues.append(
            "Metadata Header declares extra keys not in REQUIRED_METADATA_KEYS: "
            f"{sorted(extra)}. If these are intentional additions, update "
            "REQUIRED_METADATA_KEYS."
        )
    return issues


def check_fixture_filenames() -> list[str]:
    """Every .md file under fixtures/ must match either the prompt or the report
    filename pattern, and the embedded platform + pass must be table-valid."""
    issues: list[str] = []
    if not FIXTURES_DIR.exists():
        issues.append(
            f"fixtures/ directory not found at {FIXTURES_DIR}. At least one golden "
            "prompt and one golden report should live here."
        )
        return issues
    fixtures = sorted(FIXTURES_DIR.glob("*.md"))
    if not fixtures:
        issues.append(
            "fixtures/ directory contains no .md files. Add at least one prompt-file "
            "fixture and one report-file fixture."
        )
        return issues
    for path in fixtures:
        name = path.name
        m_prompt = PROMPT_FILENAME_RE.match(name)
        m_report = REPORT_FILENAME_RE.match(name)
        if not (m_prompt or m_report):
            issues.append(
                f"Fixture filename does not match prompt or report pattern: {name}"
            )
            continue
        m = m_prompt or m_report
        platform = m.group("platform")
        pass_type = m.group("pass")
        valid = EXPECTED_VALID_PASS_TYPES.get(platform)
        if valid is None:
            issues.append(
                f"Fixture {name} uses unknown platform '{platform}'. "
                f"Known platforms: {sorted(EXPECTED_VALID_PASS_TYPES)}"
            )
        elif pass_type not in valid:
            issues.append(
                f"Fixture {name} uses invalid pass type '{pass_type}' for platform "
                f"{platform}. Valid: {sorted(valid)}"
            )
    return issues


def check_fixture_metadata_headers() -> list[str]:
    """Every report-style fixture must begin with a YAML front-matter block containing
    all REQUIRED_METADATA_KEYS. Prompt-style fixtures are exempt — prompts don't carry
    a metadata header; the *reports they produce* do."""
    issues: list[str] = []
    if not FIXTURES_DIR.exists():
        return issues  # already flagged by check_fixture_filenames
    for path in sorted(FIXTURES_DIR.glob("*.md")):
        if not REPORT_FILENAME_RE.match(path.name):
            continue  # prompt fixtures skip header check
        front = parse_yaml_frontmatter(read(path))
        if front is None:
            issues.append(
                f"Report fixture {path.name} is missing its YAML front-matter block "
                "(expected `---` delimited header at the very top)"
            )
            continue
        missing = REQUIRED_METADATA_KEYS - set(front.keys())
        if missing:
            issues.append(
                f"Report fixture {path.name} missing required metadata keys: "
                f"{sorted(missing)}"
            )
    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    ("parameter_dictionary_completeness", check_parameter_dictionary_completeness),
    ("reference_files_exist", check_reference_files_exist),
    ("pass_type_consistency", check_pass_type_consistency),
    ("metadata_schema_consistency", check_metadata_schema_consistency),
    ("fixture_filenames", check_fixture_filenames),
    ("fixture_metadata_headers", check_fixture_metadata_headers),
]


def run() -> int:
    print(f"Structural eval: research-triangulation skill at {SKILL_ROOT}\n")
    total = len(CHECKS)
    failed: list[str] = []
    for name, fn in CHECKS:
        try:
            issues = fn()
        except Exception as e:  # noqa: BLE001 — surface any unexpected crash
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
