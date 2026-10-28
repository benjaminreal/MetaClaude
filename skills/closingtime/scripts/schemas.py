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

import datetime as _dt
import hashlib
import json
import os

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
FUTURE_RECEIPT = "FUTURE_RECEIPT"
INVALID_TIME = "INVALID_TIME"
WORKSPACE_MISMATCH = "WORKSPACE_MISMATCH"
FOREIGN_ROWS = "FOREIGN_ROWS"

# Tolerance for clock skew between the local host and an MCP server.
RECEIPT_CLOCK_SKEW_SECONDS = 120


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

def _parse_instant(value: object) -> _dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        instant = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return instant if instant.tzinfo is not None and instant.utcoffset() is not None else None


def fingerprint_operation(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.replace("\r\n", "\n").rstrip().encode("utf-8")).hexdigest()


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

    observed = _parse_instant(receipt.get("observed_at"))
    started = _parse_instant(invocation_started_at)
    skew = _dt.timedelta(seconds=RECEIPT_CLOCK_SKEW_SECONDS)
    if observed is None or started is None:
        issues.append({"code": INVALID_TIME, "receipt": cap, "detail": "timezone-aware observed_at and start required"})
    else:
        if observed < started - skew:
            issues.append({"code": STALE_RECEIPT, "receipt": cap})
        if observed > _dt.datetime.now(_dt.timezone.utc) + skew:
            issues.append({"code": FUTURE_RECEIPT, "receipt": cap})

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

def _same_root(left: object, right: object) -> bool:
    """Roots agree after symlink resolution (e.g. macOS /var -> /private/var)."""
    if not isinstance(left, str) or not isinstance(right, str) or not left or not right:
        return False
    return os.path.realpath(os.path.expanduser(left)) == os.path.realpath(os.path.expanduser(right))


HISTORY_ERRORS = {"session_unparseable", "duplicate_session_number", "session_header_malformed", "session_date_impossible"}


def legacy_session_number(line: str) -> int | None:
    """Number of a legacy, never-written-by-helper entry heading, else None.

    Accepted: letter-suffixed supplements ("### Session #12A | ...",
    "#### Session #12A (supplement) | ..."), v1 headings at another level or
    without "#" ("## Session 5 — Title", "### Session 5 — Title"). A level-3
    "### Session #N" heading that is not the strict format stays malformed.
    """
    import re
    line = line.rstrip("\r")
    m = re.match(r"#{2,6}[ \t]+Session[ \t]+#([0-9]+)[A-Za-z]{1,2}\b", line)
    if m:
        return int(m[1])
    m = re.match(r"(#{2}|#{4,6})[ \t]+(?:Session|Sesi[oó]n)[ \t]+#?([0-9]+)\b", line) or re.match(r"(###)[ \t]+(?:Session|Sesi[oó]n)[ \t]+([0-9]+)\b", line)
    if m:
        return int(m[2])
    # A legacy multi-day entry: "### Session #N | 2026-04-15–16 | ..." (date range).
    m = re.match(r"###[ \t]+Session[ \t]+#([0-9]+)[ \t]*\|[ \t]*[0-9]{4}-[0-9]{2}-[0-9]{2}[–-][0-9]{2}(?:-[0-9]{2})?[ \t]*\|", line)
    return int(m[1]) if m else None


def legacy_session_numbers(text: str) -> list[int]:
    import re
    return [n for n in (legacy_session_number(m.group()) for m in re.finditer(r"(?m)^#{2,6}[ \t]+(?:Session|Sesi[oó]n)[ \t]+#?[0-9][^\n]*", text)) if n is not None]


def parse_history(text: str) -> tuple[list[dict], list[str]]:
    """Single grammar for projection, validation, audit and persistence.

    A legacy first header may follow the title directly. Writers emit separators;
    when present a separator belongs to the following entry's receipt bytes.
    """
    import re
    # Entry-like headings only: level-1 titles ("# Session Log — X") and
    # headings without a number ("## Session Context") are ordinary text.
    candidates = list(re.finditer(r"(?m)^(?:###[ \t]+Session[ \t]+#|#{2,6}[ \t]+Session[ \t]+#?[0-9])[^\n]*", text))
    header = re.compile(r"### Session #([0-9]+)[ \t]*\|[ \t]*([0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*\|[ \t]*[^\s|][^\n|]*")
    entries, warnings, numbers = [], [], []
    starts = []
    for m in candidates:
        prefix = text[:m.start()]
        separator = re.search(r"(?m)^---\n\n$", prefix)
        starts.append(separator.start() if separator else m.start())
    for i, m in enumerate(candidates):
        parsed = header.fullmatch(m.group().rstrip("\r"))
        if not parsed:
            if legacy_session_number(m.group()) is None:
                warnings.append("session_header_malformed")
            continue
        number = int(parsed[1]); numbers.append(number)
        try:
            _dt.date.fromisoformat(parsed[2])
        except ValueError:
            warnings.append("session_date_impossible")
        chunk = text[starts[i]:starts[i+1] if i+1 < len(starts) else len(text)].rstrip() + "\n"
        entries.append({"session_number": number, "date": parsed[2], "header_start": m.start(), "chunk": chunk})
    if "### Session" in text and not entries:
        warnings.append("session_unparseable")
    if len(numbers) != len(set(numbers)):
        warnings.append("duplicate_session_number")
    if any(b <= a for a, b in zip(numbers, numbers[1:])):
        warnings.append("session_non_monotonic")
    return entries, sorted(set(warnings))


def freshness_failures(snapshot: dict, invocation_started_at: object = None) -> list[dict]:
    captured = _parse_instant(snapshot.get("captured_at", snapshot.get("observed_at")))
    now = _dt.datetime.now(_dt.timezone.utc)
    if captured is None or now - captured > _dt.timedelta(hours=6) or captured - now > _dt.timedelta(seconds=120):
        return [{"code": "ESTALEEVIDENCE", "detail": "snapshot must be at most six hours old and at most 120 seconds ahead of wall clock"}]
    started = _parse_instant(invocation_started_at)
    if started is not None and captured - started > _dt.timedelta(minutes=15):
        return [{"code": "ESTALEEVIDENCE", "detail": "snapshot captured more than fifteen minutes after invocation start; use new-envelope"}]
    return []


def validate_envelope(envelope: dict, returned_rows_by_capability: dict | None = None, *, resume_bound: bool = False) -> dict:
    """Returns {'valid': bool, 'failures': [...]}. No partial validity."""
    returned_rows_by_capability = returned_rows_by_capability or {}
    failures: list[dict] = []

    if envelope.get("schema_version") != SCHEMA_VERSION:
        return {"valid": False, "failures": [
            {"code": UNRECOGNIZED_SCHEMA, "detail": envelope.get("schema_version")}]}

    failures += validate_capability_profile(envelope.get("capability_profile", {}))

    snap = envelope.get("local_snapshot") or {}
    if not resume_bound:
        failures += freshness_failures(snap, envelope.get("invocation_started_at"))
    projected_tail = ((snap.get("projection") or {}).get("session") or {}).get("tail", "")
    _, projected_warnings = parse_history(projected_tail)
    history_warnings = set(snap.get("parse_warnings", [])) | set(projected_warnings)
    if history_warnings & HISTORY_ERRORS or (snap.get("session") or {}).get("alternates"):
        failures.append({"code": "EHISTORY", "detail": "ambiguous or malformed history"})
    if not snap:
        failures.append({"code": MISSING_RECEIPT, "detail": "local_snapshot absent"})
    if snap.get("sync_conflicts"):
        failures.append({"code": SYNC_CONFLICT,
                         "detail": ", ".join(snap["sync_conflicts"])})

    if not snap.get("workspace_id") and not _same_root(envelope.get("workspace_root"), snap.get("workspace_root")):
        failures.append({"code": WORKSPACE_MISMATCH, "detail": "snapshot and envelope roots must agree"})
    started = envelope.get("invocation_started_at")
    start_time = _parse_instant(started)
    snap_time = _parse_instant(snap.get("observed_at"))
    skew = _dt.timedelta(seconds=RECEIPT_CLOCK_SKEW_SECONDS)
    now = _dt.datetime.now(_dt.timezone.utc)
    if start_time is None or snap_time is None or (start_time and snap_time and start_time > snap_time + skew):
        failures.append({"code": INVALID_TIME, "detail": "valid start and snapshot times required; start <= snapshot + 120s"})
    if (start_time and start_time > now + skew) or (snap_time and snap_time > now + skew):
        failures.append({"code": FUTURE_RECEIPT, "detail": "start/snapshot later than helper clock + 120s"})
    external = (envelope.get("capability_profile") or {}).get("external", {})
    details = (envelope.get("capability_profile") or {}).get("external_detail", {})
    seen = {}
    current = set()
    for r in envelope.get("mcp_receipts", []):
        cap = r.get("capability")
        rows = returned_rows_by_capability.get(cap)
        failures += validate_receipt(r, rows, started)
        identity = r.get("identity") or {}
        signature = (r.get("status"), json.dumps(identity, sort_keys=True))
        if cap in seen and seen[cap] != signature:
            failures.append({"code": CONTRADICTORY, "receipt": cap, "detail": "conflicting status or identity"})
        seen[cap] = signature
        profile_identity = details.get(cap) or {}
        for key in ("project_ref", "service", "account"):
            if profile_identity.get(key) is not None and identity.get(key) != profile_identity[key]:
                failures.append({"code": CONTRADICTORY, "receipt": cap, "detail": "profile/receipt identity mismatch: " + key})
        if r.get("status") == "current":
            current.add(cap)
            if external.get(cap) != "working":
                failures.append({"code": CONTRADICTORY, "receipt": cap, "detail": "current requires working capability"})
            if cap == "tasks_mcp":
                if identity.get("scope") == "portfolio":
                    if envelope.get("project") != "portfolio":
                        failures.append({"code": FOREIGN_ROWS, "detail": "portfolio identity needs portfolio intent"})
                    if rows is not None and any(not row.get("project") for row in rows):
                        failures.append({"code": FOREIGN_ROWS, "detail": "row project missing"})
                elif not envelope.get("project") or not identity.get("project"):
                    failures.append({"code": MISSING_RECEIPT, "detail": "explicit intended project and receipt project required"})
                elif identity["project"] != envelope["project"] or (rows is not None and any(row.get("project") != envelope["project"] for row in rows)):
                    failures.append({"code": FOREIGN_ROWS, "detail": "task project identity/rows differ from intent"})
        elif external.get(cap) == "working" or r.get("capability_state") != external.get(cap):
            failures.append({"code": CONTRADICTORY, "receipt": cap, "detail": "profile and unavailable receipt disagree"})
    for cap in ("tasks_mcp", "open_brain"):
        if external.get(cap) == "working" and cap not in current:
            failures.append({"code": MISSING_RECEIPT, "detail": cap + " working without current receipt"})

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
