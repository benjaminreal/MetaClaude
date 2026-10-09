#!/usr/bin/env python3
"""Phase 3 trace fixtures for archive, skip, and interruption behavior."""

from __future__ import annotations

import hashlib
import tempfile
import subprocess
import sys
from pathlib import Path

import workflow
import sync_runtime_copies


HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent


def check_f11_archive_overflow() -> list[str]:
    issues: list[str] = []
    active = [f"decision-{number}" for number in range(1, 10)]
    result = workflow.archive_decision_overflow(active, [])
    if result["active"] != active[1:]:
        issues.append(f"ninth decision did not retain newest eight: {result}")
    if result["archived"] != ["decision-1"] or result["external_archive"]:
        issues.append(f"ninth decision archive result wrong: {result}")

    archived = [f"archived-{number}" for number in range(1, 11)]
    result = workflow.archive_decision_overflow(active, archived)
    if len(result["archived"]) != 10:
        issues.append(f"archive ceiling not enforced: {result}")
    if result["external_archive"] != ["archived-1"]:
        issues.append(f"oldest archive item not externalized: {result}")
    return issues


def check_f12_skip_paths() -> list[str]:
    issues: list[str] = []
    expectations = {
        "tasks": ("task_updates", False),
        "index": ("index_update", False),
        "learning": ("learning_extraction", False),
        "openbrain": ("openbrain_capture", False),
        "ritual": ("ritual_line", False),
    }
    for skip, (field, expected) in expectations.items():
        result = workflow.plan_skip_paths({skip})
        if len(result["acknowledgements"]) != 1:
            issues.append(f"{skip}: missing acknowledgement: {result}")
        if result["allow"][field] is not expected:
            issues.append(f"{skip}: {field}={result['allow'][field]}")
        if not result["allow"]["session_entry"]:
            issues.append(f"{skip}: incorrectly disabled session entry")

    openbrain = workflow.plan_skip_paths({"openbrain"})
    if not openbrain["retain_pending_learnings"]:
        issues.append("openbrain skip did not retain pending candidates")
    learning = workflow.plan_skip_paths({"learning"})
    if learning["retain_pending_learnings"]:
        issues.append("learning skip incorrectly created pending candidates")
    return issues


def check_f13_interrupted() -> list[str]:
    issues: list[str] = []
    pre = workflow.interruption_report(
        "observed", ["local_snapshot"], "Draft the closeout before any mutation."
    )
    if pre["mutation_permitted"] or pre["claim_session_complete"]:
        issues.append(f"pre-draft interruption overclaimed: {pre}")
    if "drafted" not in pre["not_completed"] or not pre["next"]:
        issues.append(f"pre-draft interruption omitted handoff: {pre}")

    post = workflow.interruption_report(
        "approved", ["local_snapshot", "approved_scope"],
        "Resume at compare-and-swap and verify every attempted write.",
    )
    if not post["mutation_permitted"] or post["claim_session_complete"]:
        issues.append(f"post-approval interruption state wrong: {post}")
    if "session_verified" not in post["not_completed"]:
        issues.append(f"post-approval interruption upgraded an attempted write: {post}")
    return issues


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_packaged_runtime_matches_shared() -> list[str]:
    issues: list[str] = []
    runtime = ("helpers.py", "schemas.py", "runtime_cli.py", "workflow.py")
    references = (
        "runtime_contract.md",
        "task_operations.md",
        "candidate_quality_contract.md",
    )
    for skill in ("newbeginning", "closingtime"):
        for name in runtime:
            source = HERE / name
            target = SKILLS / skill / "scripts" / name
            if not target.is_file() or _digest(target) != _digest(source):
                issues.append(f"{skill}/scripts/{name} differs from shared source")
        for name in references:
            source = sync_runtime_copies.reference_source(skill, name)
            target = SKILLS / skill / "references" / name
            if not target.is_file() or _digest(target) != _digest(source):
                issues.append(f"{skill}/references/{name} differs from shared source")
    return issues


def check_sync_preserves_opening_scope() -> list[str]:
    """Regeneration must retain creation-only, retry-safe opening guidance."""
    import shutil

    issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="session-skill-sync-") as directory:
        root = Path(directory)
        shutil.copytree(HERE, root / "_shared", ignore=shutil.ignore_patterns("__pycache__"))
        sync_runtime_copies.sync(root)
        opening = root / "newbeginning/references/task_operations.md"
        closing = root / "closingtime/references/task_operations.md"
        first = opening.read_bytes()
        source = first.decode("utf-8")
        if "update tasks" in source.lower():
            issues.append("regeneration expanded opening guidance to task updates")
        if "<reserved-task-uuid>" not in source or "read that" not in source:
            issues.append("regeneration lost reserved-ID retry protection")
        if "update tasks" not in closing.read_text().lower():
            issues.append("regeneration removed closeout task operations")
        sync_runtime_copies.sync(root)
        if opening.read_bytes() != first:
            issues.append("reference regeneration is not idempotent")
    return issues


def check_packaged_cli_smoke() -> list[str]:
    issues: list[str] = []
    for skill in ("newbeginning", "closingtime"):
        cli = SKILLS / skill / "scripts" / "runtime_cli.py"
        result = subprocess.run(
            [sys.executable, str(cli), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0 or "fingerprint-rows" not in result.stdout:
            issues.append(
                f"{skill}: runtime CLI smoke failed rc={result.returncode} "
                f"stderr={result.stderr.strip()!r}"
            )
    return issues


CHECKS = (
    ("F11 archive-overflow", check_f11_archive_overflow),
    ("F12 skip-paths", check_f12_skip_paths),
    ("F13 interrupted", check_f13_interrupted),
    ("packaged runtime hashes", check_packaged_runtime_matches_shared),
    ("regeneration preserves opening task scope", check_sync_preserves_opening_scope),
    ("packaged CLI smoke", check_packaged_cli_smoke),
)


def run() -> list[str]:
    problems: list[str] = []
    for label, check in CHECKS:
        problems.extend(f"{label}: {problem}" for problem in check())
    return problems
