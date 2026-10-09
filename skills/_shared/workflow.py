#!/usr/bin/env python3
"""Deterministic Phase 3 policies that do not belong in model prose."""

from __future__ import annotations


ACTIVE_DECISION_LIMIT = 8
ARCHIVED_DECISION_LIMIT = 10

SKIP_ACKNOWLEDGEMENTS = {
    "tasks": "Task updates intentionally skipped; Tasks DB state was left unchanged.",
    "index": "Index narrative and mirror update intentionally skipped.",
    "learning": "Learning extraction intentionally skipped; no candidates were created.",
    "openbrain": "Open Brain capture intentionally skipped; pending candidates were retained.",
    "ritual": "Closing ritual line intentionally skipped; verification receipts remain listed.",
}

STAGES = (
    "observed",
    "drafted",
    "approved",
    "session_verified",
    "index_verified",
    "tasks_verified",
    "learning_pending",
    "closed",
)


def archive_decision_overflow(active: list[str], archived: list[str]) -> dict:
    """Apply the active-8/archive-10 policy without losing ordered history."""
    active_out = list(active)
    archived_out = list(archived)
    while len(active_out) > ACTIVE_DECISION_LIMIT:
        archived_out.append(active_out.pop(0))

    external_archive: list[str] = []
    while len(archived_out) > ARCHIVED_DECISION_LIMIT:
        external_archive.append(archived_out.pop(0))
    return {
        "active": active_out,
        "archived": archived_out,
        "external_archive": external_archive,
    }


def plan_skip_paths(skipped: set[str] | list[str] | tuple[str, ...]) -> dict:
    """Return explicit acknowledgements and the mutations still permitted."""
    selected = set(skipped)
    unknown = selected - set(SKIP_ACKNOWLEDGEMENTS)
    if unknown:
        raise ValueError(f"unknown skip paths: {sorted(unknown)}")

    return {
        "skipped": sorted(selected),
        "acknowledgements": [
            SKIP_ACKNOWLEDGEMENTS[name] for name in sorted(selected)
        ],
        "allow": {
            "session_entry": True,
            "task_updates": "tasks" not in selected,
            "index_update": "index" not in selected,
            "learning_extraction": "learning" not in selected,
            "openbrain_capture": (
                "learning" not in selected and "openbrain" not in selected
            ),
            "ritual_line": "ritual" not in selected,
        },
        "retain_pending_learnings": (
            "openbrain" in selected and "learning" not in selected
        ),
    }


def interruption_report(stage: str, verified: list[str], next_action: str) -> dict:
    """Describe an interrupted close without upgrading attempted work to done."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    if not next_action.strip():
        raise ValueError("next_action is required")
    reached = STAGES.index(stage)
    return {
        "stage": stage,
        "verified": list(verified),
        "not_completed": list(STAGES[reached + 1 :]),
        "claim_session_complete": stage == "closed",
        "mutation_permitted": reached >= STAGES.index("approved"),
        "next": next_action.strip(),
    }
