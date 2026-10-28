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
import schemas as S


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


def _append(envelope, entry_text):
    """Freeze, approve, then append: the sanctioned closeout sequence (F-04)."""
    receipt = H.freeze_draft(envelope, entry_text)
    scope = ((envelope or {}).get("approval") or {}).get("scope_string") or "fixture-scope"
    return H.append_session_entry(envelope, entry_text, H.approve_draft(receipt, scope))


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
        lambda: _append({}, ENTRY_DRAFT),
        issues,
        "F9-absent-envelope",
    )
    for name, original, rows, _expected in fixtures.mutants():
        env = copy.deepcopy(original)
        env["returned_rows_by_capability"] = rows
        _expect_error(
            "EINVALIDENVELOPE",
            lambda env=env: _append(env, ENTRY_DRAFT),
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
                lambda: _append(env, ENTRY_DRAFT),
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
        result = _append(_envelope(root), ENTRY_DRAFT)
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
        _append(_envelope(root), ENTRY_DRAFT)
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
            lambda: _append(env, ENTRY_DRAFT),
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
        result = _append(first, ENTRY_DRAFT)
        if result["session_number"] != 3 or not result["readback_ok"]:
            issues.append(f"F10-first-append: unexpected result {result}")
        _expect_error(
            "ESTALE",
            lambda: _append(second, ENTRY_DRAFT),
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
        result = _append(env, ENTRY_DRAFT)
        if "ESTALE" not in result["warnings"]:
            issues.append(f"F10-stale-lock: warnings={result['warnings']}")

    # A readback mismatch refuses journal creation and remains auditable.
    with workspace() as root:
        _policy(root)
        env = _envelope(root, "fixture-readback")
        with mock.patch.object(H, "_readback_entry", return_value="corrupt\n"):
            _expect_error(
                "EREADBACK",
                lambda: _append(env, ENTRY_DRAFT),
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
        result = _append(_envelope(root, "fixture-below-ceiling"), ENTRY_DRAFT)
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


def check_instruction_resolution() -> list[str]:
    """CAP-8: root files win; else ancestors are walked; else instructions_absent."""
    issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="session-helper-instr-") as raw:
        parent = Path(raw) / "portfolio"
        project = parent / "project"
        project.mkdir(parents=True)
        (project / "project_index.md").write_text(INDEX_TEXT, encoding="utf-8")
        absent = H.capture_local_snapshot(project)["instructions"]
        if absent["state"] != "instructions_absent" or absent["files"]:
            issues.append(f"absent case: {absent}")
        (parent / "CLAUDE.md").write_text("ancestor rules\n", encoding="utf-8")
        ancestor = H.capture_local_snapshot(project)["instructions"]
        if ancestor["state"] != "ancestor" or not any(
            f["path"].endswith("portfolio/CLAUDE.md") and f["bytes"] == 15 for f in ancestor["files"]
        ):
            issues.append(f"ancestor case: {ancestor}")
        (project / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
        rooted = H.capture_local_snapshot(project)["instructions"]
        if rooted["state"] != "project_root" or [Path(f["path"]).name for f in rooted["files"]] != ["AGENTS.md"]:
            issues.append(f"root case: {rooted}")
        if not any(f["path"].endswith("portfolio/CLAUDE.md") for f in rooted["ancestor_files"]):
            issues.append(f"root case hides ancestor files: {rooted}")
    budget = H.capture_local_snapshot(Path(__file__).resolve().parent)["instruction_budget"]
    if set(budget) != {"skill_md_bytes", "reference_bytes"}:
        issues.append(f"instruction budget shape: {budget}")
    return issues


def check_cli_stdin_inputs() -> list[str]:
    """fingerprint-rows and validate accept JSON on stdin via '-'."""
    issues: list[str] = []
    cli = Path(__file__).resolve().parent / "runtime_cli.py"
    rows = [{"id": "a", "project": "p"}]
    expected = S.canonical_row_fingerprint(rows)
    done = subprocess.run(["python3", str(cli), "fingerprint-rows", "-"], input=json.dumps(rows),
                          text=True, capture_output=True, check=False)
    if done.returncode or json.loads(done.stdout or "{}").get("row_fingerprint") != expected:
        issues.append(f"fingerprint-rows stdin: rc={done.returncode} out={done.stdout[:200]} err={done.stderr[:200]}")
    done = subprocess.run(["python3", str(cli), "validate", "-"], input="{}",
                          text=True, capture_output=True, check=False)
    if "valid" not in (done.stdout or ""):
        issues.append(f"validate stdin: rc={done.returncode} out={done.stdout[:200]} err={done.stderr[:200]}")
    return issues


def check_f04_frozen_draft() -> list[str]:
    """A later snapshot, edited entry, missing or tampered receipt, or bad chronology refuses."""
    issues: list[str] = []

    def expect(code, call, label):
        _expect_error(code, call, issues, label)

    # Rebase: a foreign append between draft and approval, then a fresh snapshot.
    with workspace() as root:
        _policy(root)
        draft_env = _envelope(root)
        receipt = H.freeze_draft(draft_env, ENTRY_DRAFT)
        with (root / "project_session.md").open("a", encoding="utf-8") as stream:
            stream.write("\n---\n\n### Session #9 | 2026-08-04 | Foreign\n**Next:** x\n")
        rebased = _envelope(root)
        before = (root / "project_session.md").read_text(encoding="utf-8")
        approved = H.approve_draft(receipt, rebased["approval"]["scope_string"])
        expect("EDRAFTMISMATCH", lambda: H.append_session_entry(rebased, ENTRY_DRAFT, approved), "F04-rebased")
        expect("ESTALE", lambda: H.append_session_entry(draft_env, ENTRY_DRAFT, approved), "F04-foreign-write")
        if (root / "project_session.md").read_text(encoding="utf-8") != before:
            issues.append("F04: refused append still mutated the session log")
        journal = root / "private-artifacts" / "session-journal"
        records = [p for p in journal.glob("*.json") if p.name != "_policy.json"] if journal.is_dir() else []
        if records:
            issues.append(f"F04: refused append journaled {records}")

    with workspace() as root:
        _policy(root)
        env = _envelope(root)
        scope = env["approval"]["scope_string"]
        receipt = H.freeze_draft(env, ENTRY_DRAFT)
        approved = H.approve_draft(receipt, scope)
        expect("EDRAFTRECEIPT", lambda: H.append_session_entry(env, ENTRY_DRAFT, None), "F04-missing")
        expect("EDRAFTRECEIPT", lambda: H.append_session_entry(env, ENTRY_DRAFT, receipt), "F04-unapproved-tampered")
        expect("EDRAFTMISMATCH", lambda: H.append_session_entry(env, ENTRY_DRAFT + " edited", approved), "F04-entry")
        tampered = dict(approved, approved_at="2026-10-28T00:20:00Z")
        expect("EDRAFTRECEIPT", lambda: H.append_session_entry(env, ENTRY_DRAFT, tampered), "F04-tampered")
        future = dict(approved, approved_at="2999-01-01T00:00:00Z")
        future["receipt_sha256"] = H._receipt_digest(future)
        expect("ECHRONOLOGY", lambda: H.append_session_entry(env, ENTRY_DRAFT, future), "F04-future")
        early = dict(approved, approved_at="2000-01-01T00:00:00Z")
        early["receipt_sha256"] = H._receipt_digest(early)
        expect("ECHRONOLOGY", lambda: H.append_session_entry(env, ENTRY_DRAFT, early), "F04-before-draft")
        expect("EDRAFTRECEIPT", lambda: H.approve_draft(approved, scope), "F04-double-approve")
        result = H.append_session_entry(env, ENTRY_DRAFT, approved)
        if not result.get("readback_ok"):
            issues.append(f"F04-happy: {result}")
    return issues


def check_f01_local_date() -> list[str]:
    """The snapshot carries the host's local calendar date and offset."""
    issues: list[str] = []
    with workspace() as root:
        snap = H.capture_local_snapshot(root)
    import datetime as _dt
    expected = _dt.datetime.now(_dt.timezone.utc).astimezone().date().isoformat()
    if snap.get("local_date") != expected or not str(snap.get("local_utc_offset", "")).count(":") == 1:
        issues.append(f"local calendar fields: {snap.get('local_date')} {snap.get('local_utc_offset')}")
    return issues


def check_g_helper_computed_values() -> list[str]:
    """Counts, receipt times, git branch and the task mirror come from the helper."""
    issues: list[str] = []
    cli = Path(__file__).resolve().parent / "runtime_cli.py"

    def run(*args, stdin=""):
        done = subprocess.run(["python3", str(cli), *args], input=stdin, text=True,
                              capture_output=True, check=False)
        return done.returncode, json.loads(done.stdout or "{}")

    text = "Uno dos  tres\ncuatro\tcinco — seis"
    rc, out = run("count-words", "-", stdin=text)
    if rc or out.get("words") != len(text.split()) or out.get("words") != 7:
        issues.append(f"count-words: rc={rc} out={out}")

    rc, out = run("fingerprint-rows", "-", stdin=json.dumps([{"id": "a"}]))
    stamped = H._parse_utc(out.get("fingerprinted_at"))
    if rc or stamped is None:
        issues.append(f"fingerprint-rows lacks fingerprinted_at: {out}")

    future = copy.deepcopy(fixtures.base_envelope())
    future["mcp_receipts"][0]["observed_at"] = "2999-01-01T00:00:00Z"
    codes = {f["code"] for f in S.validate_envelope(future, future.get("returned_rows_by_capability") or
                                                    {"tasks_mcp": fixtures.TASK_ROWS})["failures"]}
    if S.FUTURE_RECEIPT not in codes:
        issues.append(f"future receipt time not refused: {sorted(codes)}")
    present = copy.deepcopy(fixtures.base_envelope())
    codes = {f["code"] for f in S.validate_envelope(present, {"tasks_mcp": fixtures.TASK_ROWS})["failures"]}
    if S.FUTURE_RECEIPT in codes:
        issues.append("a past receipt time was refused as future")

    rows = [{"id": "u1", "title": "First  task", "priority": 1, "due": "2026-11-01", "flagged": True},
            {"id": "u2", "title": "Second", "priority": None, "review_on": "2026-10-30"}]
    rc, out = run("render-mirror", "-", "2026-10-27", stdin=json.dumps(rows))
    expected = ("_Read-only mirror regenerated from Supabase `task_urgency` on 2026-10-27. "
                "Top 2 open tasks; bounded view. Do not hand-edit; DB wins._\n"
                "- [P1] First task (id: `u1` ; due 2026-11-01 ; flagged)\n"
                "- [P-] Second (id: `u2` ; review 2026-10-30)\n")
    if rc or out.get("markdown") != expected:
        issues.append(f"render-mirror: rc={rc} out={out}")
    rc, out = run("render-mirror", "-", "2026-10-27", stdin=json.dumps([{"title": "no id"}]))
    if rc == 0:
        issues.append("render-mirror accepted a row without id")

    with workspace() as root:
        env = _envelope(root)
        receipt = H.freeze_draft(env, ENTRY_DRAFT)
        if receipt.get("entry_words") != len(ENTRY_DRAFT.split()):
            issues.append(f"freeze-draft entry_words: {receipt.get('entry_words')}")

    if shutil.which("git"):
        with workspace() as root:
            subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "fixture-branch"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=f", "-c", "user.email=f@example.invalid",
                            "commit", "-q", "-m", "fixture"], check=True)
            (root / "project_index.md").write_text(INDEX_TEXT + "changed\n", encoding="utf-8")
            git = H.capture_local_snapshot(root)["git"]
            if git.get("branch") != "fixture-branch" or git.get("changed_paths") != ["project_index.md"] \
                    or git.get("changed_path_count") != 1:
                issues.append(f"git branch/changed paths: {git}")
    return issues


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
    ("CAP-8 instruction resolution", check_instruction_resolution),
    ("CLI stdin inputs", check_cli_stdin_inputs),
    ("F04 frozen draft", check_f04_frozen_draft),
    ("F01 local date", check_f01_local_date),
    ("G helper-computed values", check_g_helper_computed_values),
]


def run() -> list[str]:
    problems: list[str] = []
    for label, check in CHECKS:
        problems.extend(f"{label}: {problem}" for problem in check())
    return problems
