#!/usr/bin/env python3
"""Phase 2 deterministic fixtures for the local session-skill helpers.

Every filesystem mutation in this module is confined to ``TemporaryDirectory``.
The fixtures exercise the seven families that Phase 1 explicitly deferred:
F2, F3, F4, F5, F8, F10, and F15.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import fixtures
import helpers as H


INDEX_TEXT = """# Synthetic Project
**Updated:** 2026-08-03

## Summary
Synthetic state for deterministic helper testing.
"""

SESSION_TEXT = """# Session Log

---

### Session #1 | 2026-08-02 | Code (Test)
**Focus:** First synthetic session.
**Done:** Created the fixture.
**Next:** Continue testing.
**Blockers:** None.

---

### Session #2 | 2026-08-03 | Code (Test)
**Focus:** Second synthetic session.
**Done:** Prepared the observed tail.
**Next:** Exercise compare and swap.
**Blockers:** None.
"""

ENTRY_DRAFT = """### Session #[N] | 2026-08-04 | Code (Test)
**Focus:** Exercise the append helper.
**Done:** Wrote one synthetic entry through the validated path.
**Next:** Verify the journal.
**Blockers:** None."""


@contextmanager
def workspace(index_name="project_index.md", session_name="project_session.md",
              index_text=INDEX_TEXT, session_text=SESSION_TEXT):
    with tempfile.TemporaryDirectory(prefix="session-helper-fixture-") as raw:
        root = Path(raw)
        if index_name and index_text is not None:
            (root / index_name).write_text(index_text, encoding="utf-8")
        if session_name and session_text is not None:
            (root / session_name).write_text(session_text, encoding="utf-8")
        yield root


def _policy(root: Path, ceiling: int = 2) -> None:
    journal = root / "private-artifacts" / "session-journal"
    journal.mkdir(parents=True, exist_ok=True)
    (journal / H.GRANDFATHER_POLICY).write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "grandfather_session_ceiling": ceiling,
                "recorded_at": "2026-08-04T00:00:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _envelope(root: Path, invocation_id: str = "fixture-inv-1") -> dict:
    env = fixtures.base_envelope(
        invocation_id=invocation_id,
        workspace_root=str(root),
        local_snapshot=H.capture_local_snapshot(root),
    )
    env["skill_version"] = "closingtime@fixture"
    env["returned_rows_by_capability"] = {"tasks_mcp": fixtures.TASK_ROWS}
    return env


def _expect_error(code: str, call, issues: list[str], label: str) -> None:
    try:
        call()
    except H.HelperError as exc:
        if exc.code != code:
            issues.append(f"{label}: expected {code}, got {exc.code}: {exc.detail}")
    else:
        issues.append(f"{label}: expected {code}, but the call succeeded")


def check_f2_no_git() -> list[str]:
    issues: list[str] = []
    with workspace() as root:
        snap = H.capture_local_snapshot(root)
        if snap["git"] != {"available": False}:
            issues.append(f"F2-no-git: unexpected result {snap['git']}")

    with workspace() as root:
        (root / ".git").mkdir()
        _expect_error(
            "EGITFAIL",
            lambda: H.capture_local_snapshot(root),
            issues,
            "F2-git-present-failing",
        )
    return issues


def check_f3_filename_variants() -> list[str]:
    issues: list[str] = []
    cases = [
        ("Project_Index.md", "project_session.md", "Project_Index.md"),
        ("project.md", "project_session.md", "project.md"),
        ("project_index.md", "session_log.md", "session_log.md"),
    ]
    for index_name, session_name, expected in cases:
        with workspace(index_name=index_name, session_name=session_name) as root:
            snap = H.capture_local_snapshot(root)
            observed = {snap["index"]["path"], snap["session"]["path"]}
            if expected not in observed:
                issues.append(f"F3-{expected}: resolved {sorted(observed)}")
    return issues


def check_f4_missing_notes() -> list[str]:
    issues: list[str] = []
    cases = [
        ("index-only", "project_index.md", None, True, False),
        ("session-only", None, "project_session.md", False, True),
        ("neither", None, None, False, False),
    ]
    for label, index_name, session_name, index_present, session_present in cases:
        with workspace(index_name=index_name, session_name=session_name) as root:
            snap = H.capture_local_snapshot(root)
            got = (snap["index"]["present"], snap["session"]["present"])
            if got != (index_present, session_present):
                issues.append(f"F4-{label}: expected {(index_present, session_present)}, got {got}")
    return issues


def check_f5_corrupted_notes() -> list[str]:
    issues: list[str] = []
    malformed = "# Session Log\n\n### Session #x | no date | broken\n"
    with workspace(session_text=malformed) as root:
        snap = H.capture_local_snapshot(root)
        if "session_unparseable" not in snap["parse_warnings"]:
            issues.append(f"F5-unparseable: warnings={snap['parse_warnings']}")

    stale_index = INDEX_TEXT.replace("2026-08-03", "2026-08-01")
    with workspace(index_text=stale_index) as root:
        snap = H.capture_local_snapshot(root)
        if "index_updated_before_latest_session" not in snap["parse_warnings"]:
            issues.append(f"F5-contradiction: warnings={snap['parse_warnings']}")
    return issues


def check_f6_sync_conflict_observation() -> list[str]:
    issues: list[str] = []
    for name in (
        "project_index (Conflicted copy 2026-08-04).md",
        "project_session.sync-conflict-20260804.md",
    ):
        with workspace() as root:
            (root / name).write_text("conflict", encoding="utf-8")
            snap = H.capture_local_snapshot(root)
            if name not in snap["sync_conflicts"]:
                issues.append(f"F6-{name}: conflict not reported")
    return issues


def check_f8_projection_cap() -> list[str]:
    issues: list[str] = []
    large_index = INDEX_TEXT + ("indexword " * 4_000)
    large_session = SESSION_TEXT + ("sessionword " * 4_000)
    with workspace(index_text=large_index, session_text=large_session) as root:
        first = H.capture_local_snapshot(root)
        full = first["projection_bytes_full"]
        with mock.patch.object(H, "PROJECTION_BYTE_CAP", full):
            at_cap = H.capture_local_snapshot(root)
        if at_cap["projection_bytes_emitted"] != full or at_cap["projection"]["truncated"]:
            issues.append(
                f"F8-at-cap: emitted={at_cap['projection_bytes_emitted']} full={full} "
                f"truncated={at_cap['projection']['truncated']}"
            )

        with mock.patch.object(H, "PROJECTION_BYTE_CAP", 1_024):
            over = H.capture_local_snapshot(root)
        if over["projection_bytes_emitted"] > 1_024 or not over["projection"]["truncated"]:
            issues.append(
                f"F8-over-cap: emitted={over['projection_bytes_emitted']} "
                f"truncated={over['projection']['truncated']}"
            )
    return issues


def check_f9_invalid_envelope_refusal() -> list[str]:
    issues: list[str] = []
    _expect_error(
        fixtures.S.MISSING_RECEIPT,
        lambda: H.append_session_entry({}, ENTRY_DRAFT),
        issues,
        "F9-absent-envelope",
    )
    for name, original, rows, _expected in fixtures.mutants():
        env = copy.deepcopy(original)
        env["returned_rows_by_capability"] = rows
        _expect_error(
            "EINVALIDENVELOPE",
            lambda env=env: H.append_session_entry(env, ENTRY_DRAFT),
            issues,
            f"F9-{name}",
        )
    # Approval of another operation must never authorize a session append.
    for local_scope in ([], ["project_index.md"]):
        with workspace() as root:
            env = _envelope(root)
            env["mutation_scope"] = {
                "M2": local_scope, "M3": ["tasks:create:unrelated"], "M4": [],
            }
            env["approval"]["scope_string"] = "Approve only the listed operations"
            before = (root / "project_session.md").read_bytes()
            _expect_error(
                fixtures.S.SCOPE_UNAPPROVED,
                lambda: H.append_session_entry(env, ENTRY_DRAFT),
                issues,
                f"F9-unrelated-scope-{local_scope}",
            )
            if (root / "project_session.md").read_bytes() != before:
                issues.append("F9-unrelated-scope: session bytes changed")
            if (root / "private-artifacts").exists():
                issues.append("F9-unrelated-scope: journal created")
    return issues


def check_f10_concurrency_and_audit() -> list[str]:
    issues: list[str] = []

    # A first close needs no historical exemptions or policy-file mutation.
    with workspace(index_name=None, session_name=None) as root:
        result = H.append_session_entry(_envelope(root), ENTRY_DRAFT)
        audit = H.audit_session_log(root)
        if result["session_number"] != 1 or audit["journaled"] != 1:
            issues.append(f"F10-first-close: {result}, {audit}")
        if audit["errors"] or audit["unjournaled"] or audit["orphan_records"]:
            issues.append(f"F10-first-close-audit: {audit}")

    # Without a policy, existing entries never become grandfathered by default.
    with workspace() as root:
        missing = H.audit_session_log(root)
        if missing["grandfathered"] or len(missing["unjournaled"]) != 2:
            issues.append(f"F10-no-journal-no-exemptions: {missing}")
        H.append_session_entry(_envelope(root), ENTRY_DRAFT)
        audit = H.audit_session_log(root)
        if audit["grandfathered"] or len(audit["unjournaled"]) != 2 or audit["journaled"] != 1:
            issues.append(f"F10-no-policy-no-exemptions: {audit}")

    # A foreign write after observation must stop before any append or journal.
    with workspace() as root:
        _policy(root)
        env = _envelope(root)
        session = root / "project_session.md"
        session.write_text(
            session.read_text(encoding="utf-8") + "\nforeign write\n",
            encoding="utf-8",
        )
        _expect_error(
            "ESTALE",
            lambda: H.append_session_entry(env, ENTRY_DRAFT),
            issues,
            "F10-tail-changed",
        )
        if "Session #3" in session.read_text(encoding="utf-8"):
            issues.append("F10-tail-changed: stale append wrote session #3")

    # Two envelopes observed from one tail cannot both allocate the same number.
    with workspace() as root:
        _policy(root)
        first = _envelope(root, "fixture-duplicate-a")
        second = copy.deepcopy(first)
        second["invocation_id"] = "fixture-duplicate-b"
        result = H.append_session_entry(first, ENTRY_DRAFT)
        if result["session_number"] != 3 or not result["readback_ok"]:
            issues.append(f"F10-first-append: unexpected result {result}")
        _expect_error(
            "ESTALE",
            lambda: H.append_session_entry(second, ENTRY_DRAFT),
            issues,
            "F10-duplicate-number",
        )
        if (root / "project_session.md").read_text(encoding="utf-8").count("Session #3") != 1:
            issues.append("F10-duplicate-number: session #3 count is not exactly one")

        audit = H.audit_session_log(root)
        if audit["journaled"] != 1 or audit["unjournaled"]:
            issues.append(f"F10-audit-valid: {audit}")

        # Direct write bypasses the helper and must be detected post hoc.
        with (root / "project_session.md").open("a", encoding="utf-8") as stream:
            stream.write(
                "\n---\n\n### Session #4 | 2026-08-04 | Code (Test)\n"
                "**Focus:** Bypassed writer.\n**Done:** Direct append.\n"
                "**Next:** Audit.\n**Blockers:** None.\n"
            )
        bypass_audit = H.audit_session_log(root)
        if [entry["session_number"] for entry in bypass_audit["unjournaled"]] != [4]:
            issues.append(f"F10-bypassed-write: {bypass_audit}")

    # A stale local lock is recovered and reported; a fresh one would refuse.
    with workspace() as root:
        _policy(root)
        env = _envelope(root, "fixture-stale-lock")
        lock = H._lock_path(root)
        lock.write_text("dead-process", encoding="utf-8")
        old = time.time() - H.LOCK_STALE_SECONDS - 5
        os.utime(lock, (old, old))
        result = H.append_session_entry(env, ENTRY_DRAFT)
        if "ESTALE" not in result["warnings"]:
            issues.append(f"F10-stale-lock: warnings={result['warnings']}")

    # A readback mismatch refuses journal creation and remains auditable.
    with workspace() as root:
        _policy(root)
        env = _envelope(root, "fixture-readback")
        with mock.patch.object(H, "_readback_entry", return_value="corrupt\n"):
            _expect_error(
                "EREADBACK",
                lambda: H.append_session_entry(env, ENTRY_DRAFT),
                issues,
                "F10-readback-mismatch",
            )
        journal_records = list((root / "private-artifacts" / "session-journal").glob("*.json"))
        journal_records = [p for p in journal_records if p.name != H.GRANDFATHER_POLICY]
        if journal_records:
            issues.append("F10-readback-mismatch: journal was written after failed readback")
        audit = H.audit_session_log(root)
        if [entry["session_number"] for entry in audit["unjournaled"]] != [3]:
            issues.append(f"F10-readback-audit: {audit}")

    return issues


def check_f10_audit_matching_order() -> list[str]:
    issues: list[str] = []

    # An exact receipt wins even below the grandfather ceiling. Only a valid
    # receipt that matches no entry may remain as an orphan.
    with workspace() as root:
        _policy(root, ceiling=3)
        result = H.append_session_entry(_envelope(root, "fixture-below-ceiling"), ENTRY_DRAFT)
        H._write_journal_record(
            root,
            {
                "schema_version": H.S.SCHEMA_VERSION,
                "invocation_id": "fixture-genuine-orphan",
                "envelope_sha256": "sha256:fixture-orphan-envelope",
                "session_number": 99,
                "entry_sha256": "sha256:fixture-orphan-entry",
                "written_at": "2026-08-04T01:00:00Z",
                "skill_version": "closingtime@fixture",
            },
        )

        audit = H.audit_session_log(root)
        grandfathered = [entry["session_number"] for entry in audit["grandfathered"]]
        orphaned = [
            record.get("session_number")
            for record in audit["orphan_records"]
            if "session_number" in record
        ]
        expected = {
            "entries": 3,
            "journaled": 1,
            "grandfathered": [1, 2],
            "unjournaled": [],
            "orphaned": [99],
            "errors": [],
        }
        observed = {
            "entries": audit["entries"],
            "journaled": audit["journaled"],
            "grandfathered": grandfathered,
            "unjournaled": audit["unjournaled"],
            "orphaned": orphaned,
            "errors": audit["errors"],
        }
        if result["session_number"] != 3 or observed != expected:
            issues.append(
                "F10-match-before-grandfather: "
                f"append={result}, expected={expected}, observed={observed}"
            )

    return issues


def check_f10_documented_unverified_exception() -> list[str]:
    issues: list[str] = []
    with workspace() as root:
        _policy(root)
        session = root / "project_session.md"
        session.write_text(
            session.read_text(encoding="utf-8")
            + "\n---\n\n### Session #3 | 2026-08-04 | Code (Test)\n"
            + "**Focus:** Historical entry.\n**Done:** Original text.\n"
            + "**Next:** Audit.\n**Blockers:** Missing receipt.\n"
            + "\n---\n\n### Session #4 | 2026-08-04 | Code (Test)\n"
            + "**Focus:** Another entry.\n**Done:** Direct write.\n"
            + "**Next:** Audit.\n**Blockers:** Missing receipt.\n",
            encoding="utf-8",
        )
        entry_hash = H._parse_session_entries(session.read_text(encoding="utf-8"))[2]["entry_sha256"]
        note = root / "private-artifacts/session-journal/historical-exceptions/Session_3.md"
        note.parent.mkdir(parents=True)
        note.write_text("Original append unverified.\n", encoding="utf-8")
        policy_path = root / "private-artifacts/session-journal" / H.GRANDFATHER_POLICY
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["documented_unverified_exceptions"] = [{
            "session_number": 3,
            "entry_sha256": entry_hash,
            "evidence_path": "private-artifacts/session-journal/historical-exceptions/Session_3.md",
            "evidence_sha256": H._sha256_bytes(note.read_bytes()),
        }]
        policy_path.write_text(json.dumps(policy), encoding="utf-8")

        audit = H.audit_session_log(root)
        if (
            audit["journaled"] != 0
            or [item["session_number"] for item in audit["documented_unverified"]] != [3]
            or [item["session_number"] for item in audit["unjournaled"]] != [4]
            or audit["errors"]
        ):
            issues.append(f"F10-exact-exception: {audit}")

        session.write_text(
            session.read_text(encoding="utf-8").replace("Original text.", "Changed text."),
            encoding="utf-8",
        )
        changed = H.audit_session_log(root)
        if changed["documented_unverified"] or [item["session_number"] for item in changed["unjournaled"]] != [3, 4] or not any(error.startswith("EUNMATCHED_EXCEPTION") for error in changed["errors"]):
            issues.append(f"F10-changed-entry: {changed}")

        note.write_text("Tampered note.\n", encoding="utf-8")
        tampered = H.audit_session_log(root)
        if tampered["documented_unverified"] or not any(error.startswith("EBADPOLICY") for error in tampered["errors"]):
            issues.append(f"F10-tampered-note: {tampered}")
    return issues


def check_f15_deploy() -> list[str]:
    issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="session-sync-fixture-") as raw:
        root = Path(raw)
        canonical = root / "canonical"
        matched = root / "matched"
        mismatched = root / "mismatched"
        canonical.mkdir()
        (canonical / "SKILL.md").write_text("canonical\n", encoding="utf-8")
        (canonical / "nested").mkdir()
        (canonical / "nested" / "helper.py").write_text("pass\n", encoding="utf-8")
        shutil.copytree(canonical, matched)
        shutil.copytree(canonical, mismatched)
        (mismatched / "SKILL.md").write_text("drifted\n", encoding="utf-8")

        good = H.verify_skill_sync(canonical, [matched])
        if not good["matches_all"]:
            issues.append(f"F15-matched: {good}")
        partial = H.verify_skill_sync(canonical, [matched, mismatched])
        target_matches = [t["matches_canonical"] for t in partial["targets"]]
        if partial["matches_all"] or target_matches != [True, False]:
            issues.append(f"F15-partial: {partial}")
    return issues


def check_no_database_credentials() -> list[str]:
    source = Path(H.__file__).read_text(encoding="utf-8")
    forbidden = ("service_role", "SUPABASE_KEY", "DATABASE_URL", "postgresql://", "supabase.co")
    found = [token for token in forbidden if token in source]
    return [f"credential boundary: helpers.py contains {token!r}" for token in found]


CHECKS = [
    ("F2 no-git", check_f2_no_git),
    ("F3 filename-variant", check_f3_filename_variants),
    ("F4 missing-notes", check_f4_missing_notes),
    ("F5 corrupted-notes", check_f5_corrupted_notes),
    ("F6 sync-conflict", check_f6_sync_conflict_observation),
    ("F8 projection-cap", check_f8_projection_cap),
    ("F9 invalid-envelope refusal", check_f9_invalid_envelope_refusal),
    ("F10 concurrency + audit", check_f10_concurrency_and_audit),
    ("F10 audit matching order", check_f10_audit_matching_order),
    ("F10 documented exception", check_f10_documented_unverified_exception),
    ("F15 deploy", check_f15_deploy),
    ("credential boundary", check_no_database_credentials),
]


def run() -> list[str]:
    problems: list[str] = []
    for label, check in CHECKS:
        problems.extend(f"{label}: {problem}" for problem in check())
    return problems
