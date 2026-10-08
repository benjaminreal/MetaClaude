#!/usr/bin/env python3
"""Local evidence and persistence helpers for the session-skill lifecycle.

This module implements the local half of Phase 2.  It deliberately has no
network client and accepts no database credentials: MCP results enter only as
data in an evidence envelope, whose receipt fingerprints are recomputed by
``schemas.validate_envelope``.

The important concurrency invariant is compare-and-swap on the observed
session tail.  The temporary same-host lock only prevents two local processes
from entering the critical section together; it cannot see a Dropbox write
from another device.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Iterator

import schemas as S


PROJECTION_BYTE_CAP = 16_384
SESSION_ENTRY_WORD_CAP = 300
LOCK_STALE_SECONDS = 10 * 60
GRANDFATHER_POLICY = "_policy.json"

INDEX_NAMES = ("project_index.md", "Project_Index.md", "project.md", "index.md")
SESSION_NAMES = (
    "project_session.md",
    "Project_Session.md",
    "session_log.md",
    "sessions.md",
)
PENDING_NAMES = ("pending_learnings.md", "Pending_Learnings.md")
SYNC_PATTERNS = ("*(Conflicted copy*", "*.sync-conflict-*", "* (case conflict)*")

SESSION_HEADER_RE = re.compile(
    r"^### Session #(?P<number>\d+)\s*\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|",
    re.MULTILINE,
)
ENTRY_RE = re.compile(
    r"(?ms)(?:\A|\n)(---\n\n### Session #(?P<number>\d+).*?)"
    r"(?=\n---\n\n### Session #|\Z)"
)


class HelperError(RuntimeError):
    """A deterministic helper refusal with a stable contract error code."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_root(workspace_root: str | os.PathLike[str]) -> Path:
    if not isinstance(workspace_root, (str, os.PathLike)):
        raise HelperError("ENOROOT", "workspace_root must be a filesystem path")
    root = Path(workspace_root).expanduser()
    try:
        root = root.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise HelperError("ENOROOT", str(exc)) from exc
    if not root.is_dir():
        raise HelperError("ENOROOT", f"not a directory: {root}")
    return root


def _inside(root: Path, path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HelperError("EPERM", f"path escapes or is unreadable: {path}") from exc
    return resolved


def _resolve_named_file(root: Path, names: tuple[str, ...]) -> Path | None:
    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise HelperError("EPERM", f"cannot list {root}: {exc}") from exc
    by_exact = {child.name: child for child in children if child.is_file()}
    for name in names:
        if name in by_exact:
            return _inside(root, by_exact[name])

    by_casefold: dict[str, list[Path]] = {}
    for child in children:
        if child.is_file():
            by_casefold.setdefault(child.name.casefold(), []).append(child)
    for name in names:
        matches = by_casefold.get(name.casefold(), [])
        if len(matches) == 1:
            return _inside(root, matches[0])
    return None


def _read_text(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    path = _inside(root, path)
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise HelperError("EPERM", f"cannot read {path}: {exc}") from exc


def _last_session_entries(text: str, count: int = 2) -> tuple[str, int]:
    matches = list(SESSION_HEADER_RE.finditer(text))
    if not matches:
        return "", 0
    selected = matches[-count:]
    start = selected[0].start()
    tail = text[start:].strip()
    latest = max(int(match.group("number")) for match in matches)
    return tail, latest


def _sync_conflicts(root: Path) -> list[str]:
    conflicts: list[str] = []
    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise HelperError("EPERM", f"cannot scan {root}: {exc}") from exc
    for child in children:
        if not child.is_file():
            continue
        folded = child.name.casefold()
        if any(fnmatch.fnmatch(folded, pattern.casefold()) for pattern in SYNC_PATTERNS):
            conflicts.append(child.name)
    return sorted(conflicts)


def _git_snapshot(root: Path) -> dict:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
        except FileNotFoundError:
            return subprocess.CompletedProcess(args, 127, "", "git not installed")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HelperError("EGITFAIL", str(exc)) from exc

    probe = run("rev-parse", "--is-inside-work-tree")
    if probe.returncode == 127:
        return {"available": False}
    if probe.returncode != 0:
        if (root / ".git").exists():
            raise HelperError("EGITFAIL", probe.stderr.strip() or "git probe failed")
        return {"available": False}

    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain=v1", "--untracked-files=all")
    diff = run("diff", "--stat", "HEAD", "--")
    for result in (head, status, diff):
        if result.returncode != 0:
            raise HelperError("EGITFAIL", result.stderr.strip() or "git command failed")

    return {
        "available": True,
        "head": head.stdout.strip(),
        "dirty": bool(status.stdout.strip()),
        "diff_stat_sha256": _sha256_text(diff.stdout),
        "status_sha256": _sha256_text(status.stdout),
    }


def _parse_warnings(index_text: str, session_text: str) -> list[str]:
    warnings: list[str] = []
    if index_text and not re.search(r"(?m)^## Summary\s*$", index_text):
        warnings.append("index_missing_summary")
    if session_text:
        headers = list(SESSION_HEADER_RE.finditer(session_text))
        if "### Session" in session_text and not headers:
            warnings.append("session_unparseable")
        numbers = [int(m.group("number")) for m in headers]
        if len(numbers) != len(set(numbers)):
            warnings.append("duplicate_session_number")

        updated = re.search(r"(?m)^\*\*Updated:\*\*\s*(\d{4}-\d{2}-\d{2})", index_text)
        dated = [m.group("date") for m in headers]
        if updated and dated and updated.group(1) < max(dated):
            warnings.append("index_updated_before_latest_session")
    return warnings


def _projection_payload(index_path: Path | None, index_text: str,
                        session_path: Path | None, session_tail: str,
                        pending_present: bool) -> dict:
    return {
        "index": {
            "path": index_path.name if index_path else None,
            "text": index_text,
        },
        "session": {
            "path": session_path.name if session_path else None,
            "tail": session_tail,
        },
        "pending_learnings": {"present": pending_present},
        "truncated": False,
    }


def _truncate_projection(projection: dict, cap: int) -> tuple[dict, int, int]:
    full_bytes = len(_canonical_json(projection))
    if full_bytes <= cap:
        return projection, full_bytes, full_bytes

    source_index = projection["index"]["text"]
    source_session = projection["session"]["tail"]

    def candidate(fraction: float) -> dict:
        out = json.loads(json.dumps(projection))
        index_chars = int(len(source_index) * fraction)
        session_chars = int(len(source_session) * fraction)
        out["index"]["text"] = source_index[:index_chars]
        # Keep the most recent end of the session projection, where Next and
        # Blockers normally live.
        out["session"]["tail"] = (
            source_session[-session_chars:] if session_chars else ""
        )
        out["truncated"] = True
        return out

    empty = candidate(0.0)
    if len(_canonical_json(empty)) > cap:
        raise HelperError("EPROJECTIONCAP", "cap is smaller than projection metadata")

    low, high = 0.0, 1.0
    best = empty
    for _ in range(32):
        mid = (low + high) / 2
        trial = candidate(mid)
        if len(_canonical_json(trial)) <= cap:
            best, low = trial, mid
        else:
            high = mid
    emitted = len(_canonical_json(best))
    return best, emitted, full_bytes


def capture_local_snapshot(workspace_root: str | os.PathLike[str]) -> dict:
    """Return the bounded local snapshot defined by lifecycle contract D.1."""
    root = _resolve_root(workspace_root)
    index_path = _resolve_named_file(root, INDEX_NAMES)
    session_path = _resolve_named_file(root, SESSION_NAMES)
    pending_path = _resolve_named_file(root, PENDING_NAMES)

    index_text = _read_text(root, index_path)
    session_text = _read_text(root, session_path)
    session_tail, latest_number = _last_session_entries(session_text, count=2)

    projection = _projection_payload(
        index_path, index_text, session_path, session_tail, pending_path is not None
    )
    projection, emitted, full = _truncate_projection(projection, PROJECTION_BYTE_CAP)

    def file_observation(path: Path | None, text: str) -> dict:
        if path is None:
            return {"path": None, "present": False, "sha256": _sha256_text("")}
        stat = path.stat()
        return {
            "path": path.name,
            "present": True,
            "sha256": _sha256_text(text),
            "mtime": dt.datetime.fromtimestamp(
                stat.st_mtime, dt.timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "words": len(text.split()),
        }

    return {
        "index": file_observation(index_path, index_text),
        "session": {
            **file_observation(session_path, session_text),
            "tail_sha256": _sha256_text(session_tail),
            "latest_session_number": latest_number,
        },
        "pending_learnings": {
            "present": pending_path is not None,
            "path": pending_path.name if pending_path else None,
        },
        "git": _git_snapshot(root),
        "sync_conflicts": _sync_conflicts(root),
        "parse_warnings": _parse_warnings(index_text, session_text),
        "projection": projection,
        "projection_bytes_emitted": emitted,
        "projection_bytes_full": full,
        "projection_cap": PROJECTION_BYTE_CAP,
        "workspace_root": str(root),
        "observed_at": _utc_now(),
    }


def _session_path_from_envelope(root: Path, envelope: dict) -> Path:
    observed = ((envelope.get("local_snapshot") or {}).get("session") or {}).get("path")
    if observed:
        candidate = root / observed
        if candidate.exists():
            return _inside(root, candidate)
        raise HelperError("ESTALE", f"observed session file disappeared: {observed}")
    existing = _resolve_named_file(root, SESSION_NAMES)
    if existing is not None:
        raise HelperError("ESTALE", f"session file appeared after observation: {existing.name}")
    return root / "project_session.md"


def _lock_path(root: Path) -> Path:
    root = root.resolve()
    lock_root = Path(tempfile.gettempdir()) / "session-skill-locks"
    lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    return lock_root / f"{digest}.lock"


@contextlib.contextmanager
def _advisory_lock(root: Path, invocation_id: str) -> Iterator[bool]:
    path = _lock_path(root)
    token = f"{invocation_id}:{os.getpid()}:{time.time()}"
    stale_recovered = False
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(token)
            break
        except FileExistsError as exc:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age <= LOCK_STALE_SECONDS:
                raise HelperError("ELOCK", f"same-host lock is active: {path}") from exc
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            stale_recovered = True
    else:
        raise HelperError("ELOCK", f"could not acquire {path}")

    try:
        yield stale_recovered
    finally:
        try:
            if path.read_text(encoding="utf-8") == token:
                path.unlink()
        except FileNotFoundError:
            pass


def _render_entry(entry_text: str, session_number: int) -> str:
    normalized = entry_text.replace("\r\n", "\n").strip()
    if len(normalized.split()) > SESSION_ENTRY_WORD_CAP:
        raise HelperError(
            "EWORDCAP",
            f"entry has {len(normalized.split())} words; cap is {SESSION_ENTRY_WORD_CAP}",
        )
    if "Session #[N]" in normalized:
        normalized = normalized.replace("Session #[N]", f"Session #{session_number}", 1)
    else:
        match = SESSION_HEADER_RE.search(normalized)
        if not match:
            raise HelperError("EENTRYFORMAT", "entry needs a '### Session #[N]' header")
        if int(match.group("number")) != session_number:
            raise HelperError(
                "ESTALE",
                f"draft names session {match.group('number')}; next is {session_number}",
            )
    if not normalized.startswith("### Session #"):
        raise HelperError("EENTRYFORMAT", "session header must be the first line")
    return "---\n\n" + normalized + "\n"


def _readback_entry(session_path: Path, session_number: int) -> str | None:
    text = session_path.read_text(encoding="utf-8")
    for match in ENTRY_RE.finditer(text):
        if int(match.group("number")) == session_number:
            return match.group(1).rstrip() + "\n"
    return None


def _journal_record_path(root: Path, invocation_id: str, written_at: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", invocation_id)
    stamp = written_at.replace(":", "").replace("-", "")
    return root / "private-artifacts" / "session-journal" / f"{stamp}-{safe_id}.json"


def _write_journal_record(root: Path, record: dict) -> Path:
    issues = S.validate_journal_record(record)
    if issues:
        raise HelperError("EJOURNAL", json.dumps(issues, sort_keys=True))
    path = _journal_record_path(root, record["invocation_id"], record["written_at"])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    except FileExistsError as exc:
        raise HelperError("EJOURNAL", f"journal record already exists: {path}") from exc
    return path


def append_session_entry(envelope: dict, entry_text: str) -> dict:
    """Validate, compare-and-swap append, read back, and journal one entry."""
    if not envelope:
        raise HelperError(S.MISSING_RECEIPT, "evidence envelope is absent")
    returned_rows = envelope.get("returned_rows_by_capability") or {}
    verdict = S.validate_envelope(envelope, returned_rows)
    if not verdict["valid"]:
        codes = sorted({failure["code"] for failure in verdict["failures"]})
        raise HelperError("EINVALIDENVELOPE", ",".join(codes))
    if not (envelope.get("approval") or {}).get("granted"):
        raise HelperError(S.SCOPE_UNAPPROVED, "session append lacks approval")

    invocation_id = envelope.get("invocation_id")
    if not invocation_id:
        raise HelperError(S.MISSING_RECEIPT, "invocation_id")
    skill_version = envelope.get("skill_version")
    if not skill_version:
        raise HelperError("EMISSINGVERSION", "skill_version is required for the journal")

    root = _resolve_root(envelope.get("workspace_root", ""))
    session_path = _session_path_from_envelope(root, envelope)
    session_relative = session_path.relative_to(root).as_posix()
    approved_local = (envelope.get("mutation_scope") or {}).get("M2", [])
    if not isinstance(approved_local, list) or session_relative not in approved_local:
        raise HelperError(
            S.SCOPE_UNAPPROVED,
            f"session append requires {session_relative} in the approved M2 scope",
        )
    warnings: list[str] = []

    with _advisory_lock(root, invocation_id) as stale_recovered:
        if stale_recovered:
            warnings.append("ESTALE")

        conflicts = _sync_conflicts(root)
        if conflicts:
            raise HelperError(S.SYNC_CONFLICT, ", ".join(conflicts))

        current_text = _read_text(root, session_path if session_path.exists() else None)
        current_tail, current_latest = _last_session_entries(current_text, count=2)
        observed_session = (envelope.get("local_snapshot") or {}).get("session") or {}
        observed_tail_hash = observed_session.get("tail_sha256")
        if observed_tail_hash != _sha256_text(current_tail):
            raise HelperError("ESTALE", "session tail changed after observation")

        next_number = current_latest + 1
        chunk = _render_entry(entry_text, next_number)
        prefix = ""
        if not session_path.exists():
            prefix = "# Session Log\n\n"
        elif current_text and not current_text.endswith("\n\n"):
            prefix = "\n" if current_text.endswith("\n") else "\n\n"

        try:
            with session_path.open("a", encoding="utf-8", newline="") as stream:
                stream.write(prefix + chunk)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise HelperError("EPERM", f"cannot append {session_path}: {exc}") from exc

        expected_hash = _sha256_text(chunk)
        readback = _readback_entry(session_path, next_number)
        if readback is None or _sha256_text(readback) != expected_hash:
            raise HelperError("EREADBACK", "appended entry hash did not read back")

        written_at = _utc_now()
        record = {
            "schema_version": S.SCHEMA_VERSION,
            "invocation_id": invocation_id,
            "envelope_sha256": _sha256_bytes(_canonical_json(envelope)),
            "session_number": next_number,
            "entry_sha256": expected_hash,
            "written_at": written_at,
            "skill_version": skill_version,
        }
        journal_path = _write_journal_record(root, record)

    return {
        "session_number": next_number,
        "entry_sha256": expected_hash,
        "journal_record_path": str(journal_path),
        "readback_ok": True,
        "warnings": warnings,
    }


def _parse_session_entries(text: str) -> list[dict]:
    entries: list[dict] = []
    for match in ENTRY_RE.finditer(text):
        chunk = match.group(1).rstrip() + "\n"
        entries.append(
            {
                "session_number": int(match.group("number")),
                "entry_sha256": _sha256_text(chunk),
            }
        )
    return entries


def _read_audit_policy(
    root: Path, journal_dir: Path
) -> tuple[int, dict[tuple[int, str], str], list[str]]:
    policy = journal_dir / GRANDFATHER_POLICY
    if not policy.exists():
        # No policy grants no historical exemptions. A fresh project with
        # complete journal receipts can still verify its first close.
        return 0, {}, []
    ceiling = 0
    try:
        value = json.loads(policy.read_text(encoding="utf-8"))
        candidate = value["grandfather_session_ceiling"]
        if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 0:
            raise ValueError("ceiling must be a non-negative integer")
        ceiling = candidate
        exceptions = value.get("documented_unverified_exceptions", [])
        if not isinstance(exceptions, list):
            raise ValueError("documented_unverified_exceptions must be a list")
        accepted: dict[tuple[int, str], str] = {}
        for item in exceptions:
            if not isinstance(item, dict) or set(item) != {
                "session_number", "entry_sha256", "evidence_path", "evidence_sha256"
            }:
                raise ValueError("exception must contain four exact fields")
            number, entry_hash = item["session_number"], item["entry_sha256"]
            if isinstance(number, bool) or not isinstance(number, int) or number <= ceiling:
                raise ValueError("exception session must be an integer above ceiling")
            if not isinstance(entry_hash, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", entry_hash):
                raise ValueError("exception entry hash must be SHA-256")
            evidence_path, evidence_hash = item["evidence_path"], item["evidence_sha256"]
            if not isinstance(evidence_path, str) or not isinstance(evidence_hash, str):
                raise ValueError("exception evidence path and hash must be strings")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence_hash):
                raise ValueError("exception evidence hash must be SHA-256")
            relative = Path(evidence_path)
            if relative.is_absolute() or ".." in relative.parts or relative.parts[:3] != (
                "private-artifacts", "session-journal", "historical-exceptions"
            ) or relative.suffix != ".md":
                raise ValueError("exception evidence must be a local historical note")
            evidence = _inside(root, root / relative)
            if _sha256_bytes(evidence.read_bytes()) != evidence_hash:
                raise ValueError(f"exception evidence hash differs: {evidence_path}")
            key = (number, entry_hash)
            if key in accepted:
                raise ValueError("duplicate documented exception")
            accepted[key] = evidence_path
        return ceiling, accepted, []
    except (OSError, json.JSONDecodeError, KeyError, ValueError, HelperError) as exc:
        return ceiling, {}, [f"EBADPOLICY:{exc}"]


def audit_session_log(workspace_root: str | os.PathLike[str]) -> dict:
    """Match receipts first; expose approved historical gaps as unverified."""
    root = _resolve_root(workspace_root)
    session_path = _resolve_named_file(root, SESSION_NAMES)
    session_text = _read_text(root, session_path)
    entries = _parse_session_entries(session_text)
    journal_dir = root / "private-artifacts" / "session-journal"

    if not journal_dir.is_dir():
        return {
            "entries": len(entries),
            "journaled": 0,
            "grandfathered": [],
            "documented_unverified": [],
            "unjournaled": entries,
            "orphan_records": [],
            "errors": ["ENOJOURNAL"],
        }

    ceiling, exceptions, errors = _read_audit_policy(root, journal_dir)
    records: list[tuple[Path, dict]] = []
    orphan_records: list[dict] = []
    for path in sorted(journal_dir.glob("*.json")):
        if path.name == GRANDFATHER_POLICY:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            orphan_records.append({"path": str(path), "reason": f"unreadable:{exc}"})
            continue
        issues = S.validate_journal_record(record)
        if issues:
            orphan_records.append({"path": str(path), "reason": issues})
            continue
        records.append((path, record))

    unmatched_records = set(range(len(records)))
    journaled = 0
    grandfathered: list[dict] = []
    documented_unverified: list[dict] = []
    unjournaled: list[dict] = []
    for entry in entries:
        match_index = next(
            (
                index
                for index, (_path, record) in enumerate(records)
                if index in unmatched_records
                and record["session_number"] == entry["session_number"]
                and record["entry_sha256"] == entry["entry_sha256"]
            ),
            None,
        )
        if match_index is not None:
            unmatched_records.remove(match_index)
            journaled += 1
        elif entry["session_number"] <= ceiling:
            grandfathered.append(entry)
        elif (entry["session_number"], entry["entry_sha256"]) in exceptions:
            key = (entry["session_number"], entry["entry_sha256"])
            documented_unverified.append({**entry, "evidence_path": exceptions.pop(key)})
        else:
            unjournaled.append(entry)

    for number, entry_hash in sorted(exceptions):
        errors.append(f"EUNMATCHED_EXCEPTION:{number}:{entry_hash}")

    for index in sorted(unmatched_records):
        path, record = records[index]
        orphan_records.append(
            {
                "path": str(path),
                "session_number": record["session_number"],
                "entry_sha256": record["entry_sha256"],
            }
        )

    return {
        "entries": len(entries),
        "journaled": journaled,
        "grandfathered": grandfathered,
        "documented_unverified": documented_unverified,
        "unjournaled": unjournaled,
        "orphan_records": orphan_records,
        "grandfather_session_ceiling": ceiling,
        "errors": errors,
    }


def _tree_hash(path: Path) -> str | None:
    if not path.is_dir():
        return None
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*"), key=lambda value: value.as_posix()):
        relative = child.relative_to(path)
        if any(part == "__pycache__" for part in relative.parts):
            continue
        if child.name == ".DS_Store":
            continue
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        if child.is_symlink():
            digest.update(b"L" + os.readlink(child).encode("utf-8") + b"\0")
        elif child.is_file():
            digest.update(b"F" + child.read_bytes() + b"\0")
        elif child.is_dir():
            digest.update(b"D\0")
    return "sha256:" + digest.hexdigest()


def verify_skill_sync(canonical_dir: str | os.PathLike[str],
                      target_dirs: list[str | os.PathLike[str]]) -> dict:
    """Hash canonical and installed skill trees; partial deployment is failure."""
    canonical = Path(canonical_dir).expanduser().resolve()
    canonical_hash = _tree_hash(canonical)
    if canonical_hash is None:
        raise HelperError("ENOROOT", f"canonical directory not found: {canonical}")

    targets: list[dict] = []
    for raw_target in target_dirs:
        target = Path(raw_target).expanduser().resolve()
        target_hash = _tree_hash(target)
        targets.append(
            {
                "path": str(target),
                "sha256": target_hash,
                "matches_canonical": target_hash == canonical_hash,
            }
        )
    return {
        "canonical": {"path": str(canonical), "sha256": canonical_hash},
        "targets": targets,
        "matches_all": bool(targets) and all(t["matches_canonical"] for t in targets),
    }
