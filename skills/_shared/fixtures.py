#!/usr/bin/env python3
"""Deterministic envelope fixtures + one-defect mutants (Phase 1 deliverables 2-3).

Fixtures are generated from a base rather than hand-written, so a schema change
updates all of them at once and they cannot drift apart.

Scope, stated rather than silently truncated
--------------------------------------------
The contract's Part H catalogs 15 families / 44 variants. This module contains
the envelope/receipt subset introduced in Phase 1. Phase 2 filesystem and
concurrency variants live in ``helper_fixtures.py``; only behavioral traces that
require the rewritten skill bodies remain in DEFERRED.

Mutant rule (Part H.2): each mutant removes EXACTLY ONE of a receipt, an
approval, a readback, or a required warning, and declares the failure code it
must produce. A mutant that fails a different code is a scorer defect, not a pass.
"""

from __future__ import annotations

import copy

import schemas as S

INVOCATION_START = "2026-08-03T22:00:00Z"

TASK_ROWS = [  # synthetic; never real IDs (Session #36: assert by pattern)

    {"id": "task-aaaa", "title": "First synthetic task", "priority": 1, "status": "open"},
    {"id": "task-bbbb", "title": "Second synthetic task", "priority": 2, "status": "open"},
]

DEFERRED = {}


def base_profile(tasks_mcp="working", open_brain="absent") -> dict:
    return {
        "schema_version": S.SCHEMA_VERSION,
        "local": {"shell_available": True, "git_available": True,
                  "temporary_workspace_available": True,
                  "parallel_read_only_available": True},
        "external": {"tasks_mcp": tasks_mcp, "open_brain": open_brain},
        "external_detail": {"tasks_mcp": {"project_ref": "proj-ref-placeholder"},
                            "open_brain": {"reason": "no capture_thought in tool list"}},
    }


def working_receipt(rows=None) -> dict:
    rows = TASK_ROWS if rows is None else rows
    return {
        "schema_version": S.SCHEMA_VERSION,
        "capability": "tasks_mcp",
        "identity": {"project_ref": "proj-ref-placeholder", "view": "task_urgency"},
        "tool_result_id": "tr-0001",
        "observed_at": "2026-08-03T22:31:04Z",
        "operation_fingerprint": "sha256:query-task-urgency-open-project",
        "row_fingerprint": S.canonical_row_fingerprint(rows),
        "row_count": len(rows),
        "status": "current",
    }


def unavailable_receipt(state="present_unauthenticated") -> dict:
    return {
        "schema_version": S.SCHEMA_VERSION,
        "capability": "tasks_mcp",
        "identity": {"project_ref": None, "view": "task_urgency"},
        "tool_result_id": None,
        "observed_at": "2026-08-03T22:31:04Z",
        "operation_fingerprint": "sha256:query-task-urgency-open-project",
        "row_fingerprint": None,
        "row_count": 0,
        "status": "unavailable",
        "capability_state": state,
    }


def base_envelope(**over) -> dict:
    env = {
        "schema_version": S.SCHEMA_VERSION,
        "invocation_id": "inv-0001",
        "invocation_started_at": INVOCATION_START,
        "skill": "closingtime",
        "workspace_root": "/w",
        "capability_profile": base_profile(),
        "local_snapshot": {
            "index": {"path": "project_index.md", "sha256": "aaa", "mtime": "...", "words": 412},
            "session": {"path": "project_session.md", "tail_sha256": "bbb",
                        "latest_session_number": 38},
            "pending_learnings": {"present": False},
            "git": {"available": True, "head": "0000000", "dirty": True,
                    "diff_stat_sha256": "ccc"},
            "sync_conflicts": [],
            "projection_bytes_emitted": 3184,
        },
        "mcp_receipts": [working_receipt()],
        "mutation_scope": {"M2": ["project_session.md"], "M3": ["tasks:update:task-aaaa"], "M4": []},
        "approval": {"granted": True, "scope_string": "log session #N + update task task-aaaa",
                     "at": "2026-08-03T22:40:00Z"},
        "source_hashes_used_for_draft": {"index": "aaa", "session_tail": "bbb"},
    }
    env.update(over)
    return env


# --- valid fixtures: must all validate cleanly -----------------------------

def valid_fixtures() -> dict[str, tuple[dict, dict]]:
    """name -> (envelope, returned_rows_by_capability)"""
    rows = {"tasks_mcp": TASK_ROWS}

    f1 = base_envelope()

    # F7: DB unavailable in each non-working state, no mutations claimed.
    f7 = {}
    for state in ("absent", "present_unauthenticated", "present_wrong_scope"):
        env = base_envelope(
            capability_profile=base_profile(tasks_mcp=state),
            mcp_receipts=[unavailable_receipt(state)],
            mutation_scope={"M2": [], "M3": [], "M4": []},
            approval={"granted": False, "scope_string": "", "at": None},
        )
        f7[f"F7-db-{state}"] = (env, {})

    # F7: empty result set is a legitimate current reading.
    f7["F7-db-empty"] = (base_envelope(mcp_receipts=[working_receipt([])]), {"tasks_mcp": []})

    # F14: Open Brain in each four-state value.
    f14 = {f"F14-ob-{s}": (base_envelope(capability_profile=base_profile(open_brain=s)), rows)
           for s in sorted(S.EXTERNAL_STATES)}

    # F1 read-only opening: no mutations, so no approval required.
    f1_open = base_envelope(skill="newbeginning",
                            mutation_scope={"M2": [], "M3": [], "M4": []},
                            approval={"granted": False, "scope_string": "", "at": None})

    return {"F1-normal-close": (f1, rows), "F1-normal-open": (f1_open, rows), **f7, **f14}


# --- mutants: each removes exactly one thing, and must fail with its code ---

def _drop(env, path):
    env = copy.deepcopy(env)
    node = env
    for k in path[:-1]:
        node = node[k]
    node.pop(path[-1], None)
    return env


def mutants() -> list[tuple[str, dict, dict, str]]:
    """(name, envelope, returned_rows, expected_failure_code)"""
    rows = {"tasks_mcp": TASK_ROWS}
    out: list[tuple[str, dict, dict, str]] = []

    # M-receipt: the receipt is gone but the profile still claims working.
    out.append(("M-receipt-removed",
                base_envelope(mcp_receipts=[]), rows, S.MISSING_RECEIPT))

    # M-fingerprint: rows changed after the receipt was issued (claim/citation drift).
    drifted = [dict(TASK_ROWS[0], title="Something else"), TASK_ROWS[1]]
    out.append(("M-fingerprint-drift",
                base_envelope(), {"tasks_mcp": drifted}, S.FINGERPRINT_MISMATCH))

    # M-rowcount: fingerprint right, count wrong.
    bad = base_envelope()
    bad["mcp_receipts"][0]["row_count"] = 99
    out.append(("M-rowcount-mismatch", bad, rows, S.FINGERPRINT_MISMATCH))

    # M-approval: mutations claimed, approval withdrawn.
    out.append(("M-approval-removed",
                base_envelope(approval={"granted": False, "scope_string": "", "at": None}),
                rows, S.SCOPE_UNAPPROVED))

    # M-scope-string: approved, but no record of what was approved.
    out.append(("M-approval-scope-string-removed",
                base_envelope(approval={"granted": True, "scope_string": "", "at": "x"}),
                rows, S.SCOPE_UNAPPROVED))

    # M-warning: unavailable receipt that omits its required named state.
    r = unavailable_receipt()
    r.pop("capability_state")
    out.append(("M-degraded-warning-removed",
                base_envelope(capability_profile=base_profile(tasks_mcp="absent"),
                              mcp_receipts=[r],
                              mutation_scope={"M2": [], "M3": [], "M4": []},
                              approval={"granted": False, "scope_string": "", "at": None}),
                {}, S.MISSING_RECEIPT))

    # M-stale: receipt predates the invocation -- ambient context reused as evidence.
    stale = base_envelope()
    stale["mcp_receipts"][0]["observed_at"] = "2026-08-01T09:00:00Z"
    out.append(("M-stale-receipt", stale, rows, S.STALE_RECEIPT))

    # M-sync-conflict: a conflicted copy exists for a project-truth file.
    conflicted = base_envelope()
    conflicted["local_snapshot"]["sync_conflicts"] = [
        "project_session (Conflicted copy 2026-08-03).md"]
    out.append(("M-sync-conflict-present", conflicted, rows, S.SYNC_CONFLICT))

    # M-schema: unrecognized version must refuse, not best-effort parse.
    out.append(("M-unrecognized-schema",
                base_envelope(schema_version="0.9"), rows, S.UNRECOGNIZED_SCHEMA))

    # M-boolean-capability: the exact defect four-state exists to prevent.
    prof = base_profile()
    prof["external"]["tasks_mcp"] = True
    out.append(("M-capability-boolean",
                base_envelope(capability_profile=prof), rows,
                "EXTERNAL_CAP_NOT_FOUR_STATE"))

    # M-contradictory: two receipts for one capability disagreeing on status.
    out.append(("M-contradictory-receipts",
                base_envelope(mcp_receipts=[working_receipt(), unavailable_receipt()]),
                rows, S.CONTRADICTORY))

    # M-snapshot: local evidence absent entirely.
    out.append(("M-local-snapshot-removed",
                _drop(base_envelope(), ["local_snapshot"]), rows, S.MISSING_RECEIPT))

    return out
