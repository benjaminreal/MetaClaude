#!/usr/bin/env python3
"""Phase 0 data contracts, executable (Phase 1 deliverable 2, part 1).

Implements Parts C.1-C.4 of `lifecycle_contract_v1.md` as validators. These are
the *contracts*, not the helpers -- no filesystem access, no MCP calls, no
credentials. Phase 2 helpers will produce structures these validate.

The one non-obvious rule: `row_fingerprint` is RECOMPUTED from the returned
rows rather than trusted as asserted (C.2). That is what makes drift between a
claim and its cited evidence detectable.
"""

from __future__ import annotations

import hashlib
import json

SCHEMA_VERSION = "1.0"

EXTERNAL_STATES = {"absent", "present_unauthenticated", "present_wrong_scope", "working"}
RECEIPT_STATUSES = {"current", "unavailable", "error", "conflicted"}
LOCAL_CAPS = {"shell_available", "git_available",
              "temporary_workspace_available", "parallel_read_only_available"}

# Failure codes -- Part D.3.
MISSING_RECEIPT = "MISSING_RECEIPT"
STALE_RECEIPT = "STALE_RECEIPT"
FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
CONTRADICTORY = "CONTRADICTORY"
UNRECOGNIZED_SCHEMA = "UNRECOGNIZED_SCHEMA"
SCOPE_UNAPPROVED = "SCOPE_UNAPPROVED"
SYNC_CONFLICT = "SYNC_CONFLICT"


def canonical_row_fingerprint(rows: list[dict], primary_key: str = "id") -> str:
    """Canonicalize then hash: rows sorted by primary key, keys sorted,
    whitespace normalized. Deterministic across dict ordering and formatting."""
    def norm(v):
        if isinstance(v, str):
            return " ".join(v.split())
        if isinstance(v, dict):
            return {k: norm(v[k]) for k in sorted(v)}
        if isinstance(v, list):
            return [norm(x) for x in v]
        return v

    ordered = sorted(rows, key=lambda r: str(r.get(primary_key, "")))
    payload = [{k: norm(r[k]) for k in sorted(r)} for r in ordered]
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# C.1 capability profile
# --------------------------------------------------------------------------

def validate_capability_profile(profile: dict) -> list[dict]:
    issues: list[dict] = []
    if profile.get("schema_version") != SCHEMA_VERSION:
        return [{"code": UNRECOGNIZED_SCHEMA, "detail": profile.get("schema_version")}]

    local = profile.get("local", {})
    for cap in LOCAL_CAPS:
        if cap not in local:
            issues.append({"code": "MISSING_LOCAL_CAP", "detail": cap})
        elif not isinstance(local[cap], bool):
            issues.append({"code": "LOCAL_CAP_NOT_BOOL", "detail": cap})

    external = profile.get("external", {})
    for cap in ("tasks_mcp", "open_brain"):
        if cap not in external:
            issues.append({"code": "MISSING_EXTERNAL_CAP", "detail": cap})
        elif external[cap] not in EXTERNAL_STATES:
            # A boolean here is the specific defect the four-state model exists
            # to prevent -- it cannot distinguish unauthenticated from wrong-scope.
            issues.append({"code": "EXTERNAL_CAP_NOT_FOUR_STATE",
                           "detail": f"{cap}={external[cap]!r}"})
    return issues


# --------------------------------------------------------------------------
# C.2 MCP receipt
# --------------------------------------------------------------------------

def validate_receipt(receipt: dict, returned_rows: list[dict] | None,
                     invocation_started_at: str) -> list[dict]:
    issues: list[dict] = []
    if receipt.get("schema_version") != SCHEMA_VERSION:
        return [{"code": UNRECOGNIZED_SCHEMA, "receipt": receipt.get("capability"),
                 "detail": receipt.get("schema_version")}]

    cap = receipt.get("capability")
    status = receipt.get("status")
    if status not in RECEIPT_STATUSES:
        issues.append({"code": "BAD_STATUS", "receipt": cap, "detail": status})

    for field in ("capability", "observed_at", "operation_fingerprint"):
        if not receipt.get(field):
            issues.append({"code": MISSING_RECEIPT, "receipt": cap, "detail": field})

    observed = receipt.get("observed_at", "")
    if observed and observed < invocation_started_at:
        issues.append({"code": STALE_RECEIPT, "receipt": cap,
                       "detail": f"observed_at {observed} precedes invocation "
                                 f"start {invocation_started_at}"})

    if status == "current":
        if returned_rows is None:
            issues.append({"code": MISSING_RECEIPT, "receipt": cap,
                           "detail": "status=current with no returned rows to verify"})
        else:
            recomputed = canonical_row_fingerprint(returned_rows)
            if receipt.get("row_fingerprint") != recomputed:
                issues.append({"code": FINGERPRINT_MISMATCH, "receipt": cap,
                               "detail": f"asserted {receipt.get('row_fingerprint')} "
                                         f"!= recomputed {recomputed}"})
            if receipt.get("row_count") != len(returned_rows):
                issues.append({"code": FINGERPRINT_MISMATCH, "receipt": cap,
                               "detail": f"row_count {receipt.get('row_count')} "
                                         f"!= {len(returned_rows)}"})
    else:
        if receipt.get("row_fingerprint") is not None:
            issues.append({"code": CONTRADICTORY, "receipt": cap,
                           "detail": f"status={status} carries a row_fingerprint"})
        if receipt.get("capability_state") not in EXTERNAL_STATES - {"working"}:
            issues.append({"code": MISSING_RECEIPT, "receipt": cap,
                           "detail": "non-current receipt must name its capability_state"})
    return issues


# --------------------------------------------------------------------------
# C.3 envelope
# --------------------------------------------------------------------------

def validate_envelope(envelope: dict, returned_rows_by_capability: dict | None = None) -> dict:
    """Returns {'valid': bool, 'failures': [...]}. No partial validity."""
    returned_rows_by_capability = returned_rows_by_capability or {}
    failures: list[dict] = []

    if envelope.get("schema_version") != SCHEMA_VERSION:
        return {"valid": False, "failures": [
            {"code": UNRECOGNIZED_SCHEMA, "detail": envelope.get("schema_version")}]}

    failures += validate_capability_profile(envelope.get("capability_profile", {}))

    snap = envelope.get("local_snapshot") or {}
    if not snap:
        failures.append({"code": MISSING_RECEIPT, "detail": "local_snapshot absent"})
    if snap.get("sync_conflicts"):
        failures.append({"code": SYNC_CONFLICT,
                         "detail": ", ".join(snap["sync_conflicts"])})

    started = envelope.get("invocation_started_at", "")
    receipts = envelope.get("mcp_receipts", [])
    seen: dict[str, str] = {}
    for r in receipts:
        cap = r.get("capability")
        failures += validate_receipt(r, returned_rows_by_capability.get(cap), started)
        if cap in seen and seen[cap] != r.get("status"):
            failures.append({"code": CONTRADICTORY, "receipt": cap,
                             "detail": f"{seen[cap]} vs {r.get('status')}"})
        seen[cap] = r.get("status")

    # An authoritative task claim needs a working tasks_mcp receipt.
    external = (envelope.get("capability_profile") or {}).get("external", {})
    if external.get("tasks_mcp") == "working" and "tasks_mcp" not in seen:
        failures.append({"code": MISSING_RECEIPT,
                         "detail": "tasks_mcp reported working with no receipt"})

    scope = envelope.get("mutation_scope") or {}
    has_mutations = any(scope.get(cls) for cls in ("M2", "M3", "M4"))
    approval = envelope.get("approval") or {}
    if has_mutations and not approval.get("granted"):
        failures.append({"code": SCOPE_UNAPPROVED,
                         "detail": "mutation_scope non-empty without granted approval"})
    if has_mutations and approval.get("granted") and not approval.get("scope_string"):
        failures.append({"code": SCOPE_UNAPPROVED,
                         "detail": "approval granted without a recorded scope_string"})

    return {"valid": not failures, "failures": failures}


# --------------------------------------------------------------------------
# C.4 journal record
# --------------------------------------------------------------------------

def validate_journal_record(record: dict) -> list[dict]:
    issues: list[dict] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        return [{"code": UNRECOGNIZED_SCHEMA, "detail": record.get("schema_version")}]
    for field in ("invocation_id", "envelope_sha256", "session_number",
                  "entry_sha256", "written_at", "skill_version"):
        if record.get(field) in (None, ""):
            issues.append({"code": MISSING_RECEIPT, "detail": field})
    if isinstance(record.get("session_number"), bool) or \
            not isinstance(record.get("session_number"), int):
        issues.append({"code": "BAD_SESSION_NUMBER", "detail": record.get("session_number")})
    return issues
