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

import base64
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import socket
import copy
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
POLICY_PATH = "private-artifacts/session-journal/_policy.json"

INDEX_NAMES = ("project_index.md", "Project_Index.md", "project.md", "index.md")
SESSION_NAMES = (
    "project_session.md",
    "Project_Session.md",
    "session_log.md",
    "sessions.md",
)
PENDING_NAMES = ("pending_learnings.md", "Pending_Learnings.md")
INSTRUCTION_NAMES = ("AGENTS.md", "CLAUDE.md")
GIT_CHANGED_PATHS_CAP = 20
SYNC_PATTERNS = ("*conflicted copy*", "*.sync-conflict-*", "*(case conflict*")
ARCHIVE_NAMES = ("project_decisions_archive.md",)

SESSION_HEADER_RE = re.compile(
    r"^### Session #(?P<number>[0-9]+)[ \t]*\|[ \t]*(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*\|[ \t]*[^\s|][^\n|]*$",
    re.MULTILINE,
)


class HelperError(RuntimeError):
    """A deterministic helper refusal with a stable contract error code."""

    def __init__(self, code: str, detail: str, **context):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.context = context


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


def _observation_clock() -> dict:
    """UTC observation time plus the host's local calendar date and offset.

    Relative dates in briefs ("today", "yesterday", gaps) must be resolved
    against `local_date`, never against the UTC date.
    """
    now = dt.datetime.now(dt.timezone.utc)
    local = now.astimezone()
    offset = local.strftime("%z")
    return {
        "observed_at": now.isoformat().replace("+00:00", "Z"),
        "captured_at": now.isoformat().replace("+00:00", "Z"),
        "local_date": local.date().isoformat(),
        "local_utc_offset": f"{offset[:3]}:{offset[3:]}" if offset else None,
    }


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


def _named_observation(root: Path, names: tuple[str, ...]) -> tuple[Path | None, list[str]]:
    children = list(root.iterdir())
    matches = sorted((p for p in children if p.name.casefold() in {n.casefold() for n in names}), key=lambda p: p.name)
    for p in matches:
        if not p.is_file():
            raise HelperError("EPERM", f"continuity path is not a file: {p}")
        _inside(root, p)
    if not matches:
        return None, []
    # Only the canonical spelling is unambiguous precedence. Multiple aliases
    # without that spelling are not a license to choose a history.
    exact = next((p for p in matches if p.name == names[0]), None)
    if exact is None and len(matches) > 1:
        raise HelperError("EAMBIGUOUSNAME", ", ".join(p.name for p in matches))
    chosen = exact or matches[0]
    return _inside(root, chosen), [p.name for p in matches if p != chosen]


def _resolve_named_file(root: Path, names: tuple[str, ...]) -> Path | None:
    return _named_observation(root, names)[0]


def _read_text(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    path = _inside(root, path)
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise HelperError("EPERM", f"cannot read {path}: {exc}") from exc


def _last_session_entries(text: str, count: int = 2) -> tuple[str, int]:
    entries, _ = S.parse_history(text)
    legacy = [(m.start(), S.legacy_session_number(m.group()))
              for m in re.finditer(r"(?m)^#{2,6}[ \t]+[^\n]*", text)
              if S.legacy_session_number(m.group()) is not None]
    selected = [e["header_start"] for e in entries[-count:]]
    if len(selected) < count:
        first = entries[0]["header_start"] if entries else len(text)
        selected = [pos for pos, _ in legacy if pos < first][-(count - len(selected)):] + selected
    latest = max([e["session_number"] for e in entries] + [n for _, n in legacy], default=0)
    return (text[min(selected):].strip() if selected else ""), latest


def _next_session_number(root: Path, text: str) -> tuple[int, list[int]]:
    """Current append intents reserve their numbers even after hand removal."""
    reserved = {r["session_number"] for p, r in _load_intents(root)
                if r["kind"] == "append_intent" and p.suffix != ".abandoned"}
    entries, _ = S.parse_history(text)
    present = {e["session_number"] for e in entries} | set(S.legacy_session_numbers(text))
    return max(_last_session_entries(text)[1], max(reserved, default=0)) + 1, sorted(reserved - present)


def _contained(root: Path, path: Path) -> Path:
    try:
        resolved = path.resolve()
        resolved.relative_to(Path(root).resolve())
    except (ValueError, OSError) as exc:
        raise HelperError("EPERM", f"path escapes workspace: {path}") from exc
    return resolved


def _sync_conflicts(root: Path) -> list[str]:
    conflicts = []
    journal = _contained(root, root / "private-artifacts/session-journal")
    directories = [root] + ([journal] if journal.is_dir() else [])
    stems = {Path(n).stem.casefold() for n in INDEX_NAMES + SESSION_NAMES + PENDING_NAMES + ARCHIVE_NAMES}
    for directory in directories:
        for child in directory.iterdir():
            if child.name == ".lock":
                continue
            folded = child.name.casefold()
            generic = any(fnmatch.fnmatch(folded, pattern) for pattern in SYNC_PATTERNS)
            specific = any(re.fullmatch(re.escape(stem) + r"(?: [0-9]+| copy(?: [0-9]+)?| \([0-9]+\))\.md", folded) for stem in stems)
            if generic or specific:
                conflicts.append(child.relative_to(root).as_posix())
    return sorted(conflicts)


def _git_snapshot(root: Path) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        except FileNotFoundError:
            return subprocess.CompletedProcess(args, 127, b"", b"git not installed")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return subprocess.CompletedProcess(args, 126, b"", str(exc).encode())

    def degraded(result):
        return {"available": False, "state": "corrupt", "error": result.stderr.decode("utf-8", "replace").strip() or "git evidence failed"}

    probe = run("rev-parse", "--is-inside-work-tree")
    if probe.returncode:
        if probe.returncode == 127 or (not (root / ".git").exists() and not (root / ".git").is_symlink() and b"not a git repository" in probe.stderr):
            return {"available": False}
        return degraded(probe)
    top = run("rev-parse", "--show-toplevel")
    if top.returncode:
        return degraded(top)
    toplevel = Path(os.fsdecode(top.stdout).strip()).resolve()
    branch = run("symbolic-ref", "--short", "-q", "HEAD")
    if branch.returncode not in (0, 1):
        return degraded(branch)
    head = run("rev-parse", "--verify", "-q", "HEAD")
    unborn = False
    if head.returncode:
        # A symbolic branch is unborn only if its ref genuinely does not exist.
        if branch.returncode:
            return degraded(head)
        ref = run("show-ref", "--verify", "--quiet", "refs/heads/" + os.fsdecode(branch.stdout).strip())
        if ref.returncode != 1:
            return degraded(ref)
        unborn = True
    else:
        obj = run("cat-file", "-e", "HEAD^{commit}")
        if obj.returncode:
            return degraded(obj)
    status = run("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", str(root))
    diff = run("diff", "--stat", *( [] if unborn else ["HEAD"] ), "--", str(root))
    for result in (status, diff):
        if result.returncode:
            return degraded(result)
    tokens = status.stdout.split(b"\0")
    changed = []
    i = 0
    while i < len(tokens):
        token = tokens[i]; i += 1
        if not token:
            continue
        paths = [token[3:]]
        if b"R" in token[:2] or b"C" in token[:2]:
            if i < len(tokens):
                paths.append(tokens[i]); i += 1
        for raw in paths:
            try:
                rel = (toplevel / os.fsdecode(raw)).relative_to(root).as_posix()
            except ValueError:
                continue
            if rel not in changed:
                changed.append(rel)
    return {"available": True, "head": None if unborn else os.fsdecode(head.stdout).strip(),
            "unborn": unborn, "branch": os.fsdecode(branch.stdout).strip() if not branch.returncode else None,
            "toplevel": str(toplevel), "dirty": bool(changed), "changed_paths": changed[:GIT_CHANGED_PATHS_CAP],
            "changed_path_count": len(changed), "diff_stat_sha256": _sha256_bytes(diff.stdout),
            "status_sha256": _sha256_bytes(status.stdout)}


def _parse_warnings(index_text: str, session_text: str) -> list[str]:
    warnings: list[str] = []
    if index_text and not re.search(r"(?m)^## Summary\s*$", index_text):
        warnings.append("index_missing_summary")
    if session_text:
        entries, history_warnings = S.parse_history(session_text)
        warnings.extend(history_warnings)
        updated = re.search(r"(?m)^\*\*Updated:\*\*\s*(\d{4}-\d{2}-\d{2})", index_text)
        dated = [entry["date"] for entry in entries]
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
    out = json.loads(json.dumps(projection))
    if full_bytes <= cap:
        return out, full_bytes, full_bytes
    out["truncated"] = True
    # Drop whole older entries first. Keep the latest header at the start.
    while len(_canonical_json(out)) > cap:
        headers, _ = S.parse_history(out["session"]["tail"])
        if len(headers) < 2:
            break
        out["session"]["tail"] = out["session"]["tail"][headers[1]["header_start"]:]
    while len(_canonical_json(out)) > cap and out["index"]["text"]:
        out["index"]["text"] = out["index"]["text"][:max(0, len(out["index"]["text"]) - max(1, (len(_canonical_json(out))-cap)//2))]
    if len(_canonical_json(out)) > cap:
        out["session"]["latest_entry_truncated"] = True
        while len(_canonical_json(out)) > cap and out["session"]["tail"]:
            out["session"]["tail"] = out["session"]["tail"][:-max(1, (len(_canonical_json(out))-cap)//2)]
    emitted = len(_canonical_json(out))
    if emitted > cap:
        raise HelperError("EPROJECTIONCAP", "cap smaller than metadata")
    return out, emitted, full_bytes


def _instruction_resolution(root: Path) -> dict:
    """Locate instruction files at the root, else in ancestors (contract INSTRUCTION_RESOLUTION).

    Reports paths and sizes only; the model must still read each listed file
    and decide whether task-tracking rules conflict.
    """
    def found(directory: Path) -> list[dict]:
        out = []
        for name in INSTRUCTION_NAMES:
            path = directory / name
            try:
                if path.is_file():
                    out.append({"path": str(path), "bytes": path.stat().st_size})
            except OSError:
                out.append({"path": str(path), "bytes": None, "unreadable": True})
        return out

    files = found(root)
    ancestors: list[dict] = []
    for directory in root.parents:
        ancestors += found(directory)
    if files:
        # Root files take precedence, but ancestors are still listed so the
        # model can read them and detect conflicting task-tracking rules.
        return {"state": "project_root", "files": files, "ancestor_files": ancestors}
    if ancestors:
        return {"state": "ancestor", "files": ancestors, "ancestor_files": ancestors}
    return {"state": "instructions_absent", "files": [], "ancestor_files": []}


def _instruction_budget() -> dict:
    """Byte sizes of the packaged skill instructions this runtime ships with."""
    skill_dir = Path(__file__).resolve().parent.parent
    skill_md = skill_dir / "SKILL.md"
    references = skill_dir / "references"
    return {
        "skill_md_bytes": skill_md.stat().st_size if skill_md.is_file() else None,
        "reference_bytes": {
            path.name: path.stat().st_size for path in sorted(references.glob("*.md"))
        } if references.is_dir() else {},
    }


def _is_intent_file(path: Path) -> bool:
    try:
        return json.loads(path.read_text()).get("kind") in {"append_intent", "write_intent", "remaining_intent"}
    except (OSError, ValueError, AttributeError):
        return True  # malformed recovery evidence is unfinished, never ignored


def capture_local_snapshot(workspace_root: str | os.PathLike[str], entries: int = 2) -> dict:
    """Return the bounded local snapshot defined by lifecycle contract D.1."""
    root = _resolve_root(workspace_root)
    if not isinstance(entries, int) or not 1 <= entries <= 10:
        raise HelperError("EINPUT", "entries must be 1..10")
    index_path, index_alts = _named_observation(root, INDEX_NAMES)
    session_path, session_alts = _named_observation(root, SESSION_NAMES)
    pending_path, pending_alts = _named_observation(root, PENDING_NAMES)
    archive_path, archive_alts = _named_observation(root, ARCHIVE_NAMES)

    index_text = _read_text(root, index_path)
    session_text = _read_text(root, session_path)
    session_tail, latest_number = _last_session_entries(session_text, count=2)
    projected_tail, _ = _last_session_entries(session_text, count=entries)

    projection = _projection_payload(
        index_path, index_text, session_path, projected_tail, pending_path is not None
    )
    projection, emitted, full = _truncate_projection(projection, PROJECTION_BYTE_CAP)

    def file_observation(path: Path | None, text: str) -> dict:
        if path is None:
            return {"path": None, "present": False, "sha256": _sha256_text("")}
        stat = path.stat()
        return {
            "path": path.name,
            "present": True,
            "sha256": _sha256_bytes(path.read_bytes()),
            "mtime": dt.datetime.fromtimestamp(
                stat.st_mtime, dt.timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "words": len(text.split()),
        }

    git = _git_snapshot(root)
    warnings = _parse_warnings(index_text, session_text)
    for label, alts in (("index", index_alts), ("session", session_alts), ("pending", pending_alts), ("archive", archive_alts)):
        if alts:
            warnings.append(label + "_alternates_present")
    if git.get("state") == "corrupt":
        warnings.append("git_unreadable")
    journal = _contained(root, root / "private-artifacts/session-journal")
    unfinished = sorted(str(p.relative_to(root)) for p in journal.iterdir()
                        if p.suffix == ".pending" or (p.suffix == ".json" and p.name not in {GRANDFATHER_POLICY, "workspace.json"} and _is_intent_file(p))) if journal.is_dir() else []
    return {
        "index": {**file_observation(index_path, index_text), "alternates": index_alts},
        "session": {
            **file_observation(session_path, session_text), "alternates": session_alts,
            "tail_sha256": _sha256_text(session_tail),
            "latest_session_number": latest_number,
        },
        "pending_learnings": {**file_observation(pending_path, _read_text(root, pending_path)), "alternates": pending_alts},
        "decisions_archive": {**file_observation(archive_path, _read_text(root, archive_path)), "alternates": archive_alts},
        "audit_policy": {"path": POLICY_PATH, "present": (journal / GRANDFATHER_POLICY).is_file(), "sha256": _file_state(journal / GRANDFATHER_POLICY)["sha256"]},
        "unfinished_operations": unfinished,
        "subprojects": sorted(p.name for p in root.iterdir() if p.is_dir() and not p.is_symlink() and any((p / name).is_file() for name in INDEX_NAMES + SESSION_NAMES))[:20],
        "git": git,
        "instructions": _instruction_resolution(root),
        "instruction_budget": _instruction_budget(),
        "sync_conflicts": _sync_conflicts(root),
        "parse_warnings": warnings,
        "projection": projection,
        "projection_bytes_emitted": emitted,
        "projection_bytes_full": full,
        "projection_cap": PROJECTION_BYTE_CAP,
        "workspace_root": str(root),
        "workspace_id": _workspace_id(root),
        **_observation_clock(),
    }


def _session_path_from_envelope(root: Path, envelope: dict) -> Path:
    observed = ((envelope.get("local_snapshot") or {}).get("session") or {}).get("path")
    if observed:
        candidate = _contained(root, root / observed)
        if candidate.exists():
            return _inside(root, candidate)
        raise HelperError("ESTALE", f"observed session file disappeared: {observed}")
    existing = _resolve_named_file(root, SESSION_NAMES)
    if existing is not None:
        raise HelperError("ESTALE", f"session file appeared after observation: {existing.name}")
    return root / "project_session.md"


def _workspace_id(root: Path, create: bool = False) -> str | None:
    path = _contained(root, root / "private-artifacts/session-journal/workspace.json")
    if path.exists():
        try:
            value = json.loads(path.read_text())["workspace_id"]
            uuid.UUID(value)
            return value
        except (ValueError, KeyError, TypeError) as exc:
            raise HelperError("ERECOVERY", "invalid workspace identity") from exc
    if create:
        value = str(uuid.uuid4())
        _atomic_record(_journal_dir(root) / "workspace.json", {"workspace_root": str(root), "workspace_id": value})
        return value
    return None


def _lock_path(root: Path) -> Path:
    return _journal_dir(root) / ".lock"


@contextlib.contextmanager
def _advisory_lock(root: Path, invocation_id: str) -> Iterator[bool]:
    path = _contained(root, _lock_path(root))
    token = json.dumps({"host": socket.gethostname(), "pid": os.getpid(), "started_at": time.time(), "invocation_id": invocation_id})
    stale_recovered = False
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(token)
            break
        except FileExistsError as exc:
            try:
                original = path.read_bytes()
                info = json.loads(original)
                if info["host"] == socket.gethostname():
                    try:
                        os.kill(int(info["pid"]), 0)
                        stale = False
                    except ProcessLookupError:
                        stale = True
                    except PermissionError:
                        stale = False
                else:
                    stale = time.time() - float(info["started_at"]) > LOCK_STALE_SECONDS
            except FileNotFoundError:
                continue
            except (ValueError, KeyError, TypeError) as error:
                raise HelperError("ELOCK", "unreadable lock; preserve and inspect") from error
            if not stale:
                raise HelperError("ELOCK", f"writer lock is active: {path}") from exc
            if path.read_bytes() != original:
                raise HelperError("ELOCK", "lock changed during stale recovery")
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
        raise HelperError("EWORDCAP", f"entry exceeds {SESSION_ENTRY_WORD_CAP} words")
    normalized = normalized.replace("Session #[N]", f"Session #{session_number}", 1)
    headers = [line for line in normalized.splitlines() if line.startswith("### Session")]
    if len(headers) != 1 or not normalized.startswith(headers[0]) or re.search(r"(?m)^---\s*$", normalized):
        raise HelperError("EENTRYFORMAT", "exactly one entry header; no embedded separators")
    header = SESSION_HEADER_RE.fullmatch(headers[0])
    mode = headers[0].rsplit("|", 1)[-1].strip()
    if not header or not re.fullmatch(r"[^\s()[\]]+[^()[\]]* \([^()[\]]+\)", mode):
        raise HelperError("EENTRYFORMAT", "complete number | real date | mode/tool header required")
    try:
        dt.date.fromisoformat(header.group("date"))
    except ValueError as exc:
        raise HelperError("EENTRYFORMAT", "impossible entry date") from exc
    if int(header.group("number")) != session_number:
        raise HelperError("ESTALE", "entry number differs from allocated number")
    for field in ("Focus", "Done", "Next", "Blockers"):
        values = re.findall(r"(?m)^\*\*" + field + r":\*\*[ \t]*(.*)$", normalized)
        if len(values) != 1 or not values[0].strip() or re.fullmatch(r"\[[^]]*\]", values[0].strip()):
            raise HelperError("EENTRYFORMAT", f"one populated {field}: field required")
    return "---\n\n" + normalized + "\n"


def _readback_entry(session_path: Path, session_number: int) -> str | None:
    text = session_path.read_text(encoding="utf-8")
    entries, _ = S.parse_history(text)
    for entry in entries:
        if entry["session_number"] == session_number:
            return entry["chunk"]
    return None


def _journal_dir(root: Path) -> Path:
    path = _contained(root, root / "private-artifacts/session-journal")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HelperError("EJOURNAL", f"journal directory unavailable: {exc}") from exc
    return path


def _write_journal_record(root: Path, record: dict) -> Path:
    """Legacy fixture/import writer; append uses durable intents instead."""
    issues = S.validate_journal_record(record)
    if issues:
        raise HelperError("EJOURNAL", json.dumps(issues))
    path = _journal_dir(root) / (uuid.uuid4().hex + ".json")
    _atomic_record(path, dict(record, workspace_root=str(root)))
    return path


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_record(path: Path, record: dict) -> None:
    # Temporary evidence is preserved on failure, never mistaken for an intent.
    path = _contained(Path(record["workspace_root"]), path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(_canonical_json(record) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_dir(path.parent)


def _move_record(path: Path, suffix: str) -> Path:
    destination = path.with_suffix(suffix)
    if destination != path:
        if destination.exists():
            raise HelperError("ERECOVERY", f"recovery destination exists: {destination}")
        os.replace(path, destination)
        _fsync_dir(destination.parent)
    return destination


def _file_state(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "length": 0, "sha256": "absent"}
    if not path.is_file():
        raise HelperError("EPERM", f"not a regular file: {path}")
    data = path.read_bytes()
    return {"exists": True, "length": len(data), "sha256": _sha256_bytes(data)}


def _state_matches(path: Path, expected: dict) -> bool:
    return _file_state(path) == expected


DRAFT_RECEIPT_KIND = "closingtime_draft_receipt"


def count_words(text: str) -> int:
    """Whitespace-delimited word count, the same rule as `wc -w`."""
    return len(text.split())


def render_task_mirror(rows: list[dict], local_date: str) -> str:
    """Render the read-only `## Active TODOs` body from current receipt rows.

    Row order is preserved (the query already ranks rows); the caller replaces
    the section body with this text and never edits task lines by hand.
    """
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise HelperError("EBADROWS", "rows JSON must contain a list of objects")
    lines = [
        f"_Read-only mirror regenerated from Supabase `task_urgency` on {local_date}. "
        f"Top {len(rows)} open tasks; bounded view. Do not hand-edit; DB wins._"
    ]
    for row in rows:
        if not row.get("id") or not row.get("title"):
            raise HelperError("EBADROWS", "each row needs id and title")
        for field in ("id", "due", "review_on", "priority"):
            if re.search(r"[\x00-\x1f\x7f]", str(row.get(field, ""))):
                raise HelperError("EBADROWS", "control character in task field: " + field)
        if re.search(r"[\x00-\x08\x0e-\x1f\x7f]", str(row["title"])):
            raise HelperError("EBADROWS", "control character in task title")
        priority = row.get("priority")
        label = f"P{priority}" if isinstance(priority, int) else "P-"
        details = [f"id: `{row['id']}`"]
        if row.get("due"):
            details.append(f"due {row['due']}")
        if row.get("review_on"):
            details.append(f"review {row['review_on']}")
        if row.get("flagged"):
            details.append("flagged")
        title = " ".join(str(row["title"]).split())
        lines.append(f"- [{label}] {title} ({' ; '.join(details)})")
    return "\n".join(lines) + "\n"


def _parse_utc(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _receipt_digest(receipt: dict) -> str:
    return _sha256_bytes(_canonical_json({k: v for k, v in receipt.items() if k != "receipt_sha256"}))


def _package_skill() -> str | None:
    skill = Path(__file__).resolve().parent.parent / "SKILL.md"
    if not skill.is_file():
        return None  # canonical shared library / standalone fixture import
    match = re.search(r"(?m)^name:\s*(newbeginning|closingtime)\s*$", skill.read_text().split("---", 2)[1])
    return match[1] if match else None


def _enforce_package_skill(envelope: dict) -> None:
    package = _package_skill()
    if package and envelope.get("skill") != package:
        raise HelperError("ESKILL", "envelope skill differs from this package")


def _workspace_binding(envelope: dict) -> Path:
    _enforce_package_skill(envelope)
    root = _resolve_root(envelope.get("workspace_root", ""))
    snapshot = envelope.get("local_snapshot") or {}
    identity = snapshot.get("workspace_id")
    if identity and identity != _workspace_id(root):
        raise HelperError("EWORKSPACEMISMATCH", "snapshot belongs to another journal identity")
    if not identity and not S._same_root(snapshot.get("workspace_root"), str(root)):
        raise HelperError("EWORKSPACEMISMATCH", "legacy snapshot needs a fresh observation at this root")
    return root


def _snapshot_digest(snapshot: dict) -> str:
    value = copy.deepcopy(snapshot)
    value.pop("workspace_root", None)  # informational location, not identity
    return _sha256_bytes(_canonical_json(value))


def _fresh(snapshot: dict, invocation_started_at: object = None) -> None:
    failures = S.freshness_failures(snapshot, invocation_started_at)
    if failures:
        raise HelperError("ESTALEEVIDENCE", failures[0]["detail"])


def _check_identity(root: Path, value: dict) -> None:
    identity = value.get("workspace_id")
    if identity and identity != _workspace_id(root):
        raise HelperError("EWORKSPACEMISMATCH", "journal workspace identities differ")


def _approval_path(root: Path, invocation: str) -> Path:
    return _journal_dir(root) / (hashlib.sha256(invocation.encode()).hexdigest() + ".approval")


def _check_invocation(root: Path, receipt: dict) -> None:
    path = _approval_path(root, receipt["invocation_id"])
    if path.exists() and json.loads(path.read_text()).get("receipt_sha256") != receipt["receipt_sha256"]:
        raise HelperError("EINVOCATIONUSED", "invocation already has a different approved draft")


def _history_detail(warnings: list[str], fallback: str) -> str:
    if "session_number_non_ascii" in warnings:
        return "non-ASCII digits in a session heading number; rewrite it with ASCII digits"
    return fallback


def _preflight(root: Path, envelope: dict, operations: list[dict], expected: dict | None = None) -> None:
    snapshot = envelope["local_snapshot"]
    current = capture_local_snapshot(root)
    if any(w in S.HISTORY_ERRORS for w in current["parse_warnings"]) or current["session"]["alternates"]:
        raise HelperError("EHISTORY", _history_detail(current["parse_warnings"], "ambiguous or malformed session history"))
    for op in operations:
        if op["class"] != "M2":
            if envelope.get("skill") == "newbeginning":
                raise HelperError("ESKILL", "opening only writes the approved index")
            continue
        name = op["path"]
        if envelope.get("skill") == "newbeginning" and (name not in INDEX_NAMES or op["operation"] != "replace"):
            raise HelperError("ESKILL", "opening only writes the approved index")
        if op["operation"] == "append":
            if envelope.get("skill") != "closingtime" or name not in SESSION_NAMES:
                raise HelperError("ESKILL", "only closingtime appends a session")
            _refuse_links(root, name)
            _session_path_from_envelope(root, envelope)
            obs = snapshot.get("session") or {}
            actual = _file_state(_contained(root, root / name))["sha256"]
            if actual != (obs.get("sha256") if obs.get("present") else "absent"):
                raise HelperError("ESTALE", "session changed since observation")
        else:
            target, field = _writer_target(root, envelope, name)
            if envelope.get("skill") == "newbeginning" and (field != "index" or op["operation"] != "replace"):
                raise HelperError("ESKILL", "opening only writes the approved index")
            obs = snapshot.get(field) or {}
            preimage = (expected or {}).get(name, obs.get("sha256") if obs.get("present") else "absent")
            if _file_state(target)["sha256"] != preimage:
                raise HelperError("ESOURCECHANGED", "approved preimage changed: " + name)


def _scope_operations(envelope: dict, legacy: bool = False) -> list[dict]:
    result = []
    for cls in ("M2", "M3", "M4"):
        items = (envelope.get("mutation_scope") or {}).get(cls, [])
        if not isinstance(items, list):
            raise HelperError("EINPUT", "scope must contain lists")
        for item in items:
            if cls == "M2":
                name = item.get("path") if isinstance(item, dict) else item
                if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts or "\n" in name or "\r" in name:
                    raise HelperError("EPERM", "scope needs contained relative paths")
                name = Path(name).as_posix()
                snap = envelope.get("local_snapshot") or {}
                session = (snap.get("session") or {}).get("path") or SESSION_NAMES[0]
                parent_close = any((v.get("path") == session and v.get("operation", "append") == "append") if isinstance(v, dict) else v == session for v in items)
                default = ["append"] if name == session else (["stage"] if name == "pending_learnings.md" and parent_close else ["replace"])
                if legacy:
                    # Match already-bound pre-round-3 receipts during recovery;
                    # new freezes never request this historical scope expansion.
                    pending = (snap.get("pending_learnings") or {}).get("path") or PENDING_NAMES[0]
                    default = ["append"] if name == session else (["replace", "delete"] if name == pending else ["replace"])
                kinds = [item["operation"]] if isinstance(item, dict) and "operation" in item else default
                for kind in kinds:
                    if kind not in {"append", "replace", "delete", "stage", "resolve"}:
                        raise HelperError("EINPUT", "unknown local operation kind")
                    if kind in {"stage", "resolve"} and name != "pending_learnings.md":
                        raise HelperError("ESTAGE", "stage is limited to pending_learnings.md")
                    result.append({"class": cls, "operation": kind, "path": name})
            else:
                if not isinstance(item, str) or not item.strip() or "\n" in item or "\r" in item:
                    raise HelperError("EINPUT", "external/repository scope needs exact operation identifier")
                result.append({"class": cls, "operation": item})
    return sorted(result, key=lambda v: _canonical_json(v))


def _scope_text(operations: list[dict], legacy: bool = False, session_number: int | None = None, historical_count: int | None = None) -> str:
    return "\n".join(op["class"] + " " + op["operation"] + (" " + op["path"] if "path" in op else "") +
                     (f" (adopt {historical_count} historical entries)" if historical_count is not None and op.get("path") == POLICY_PATH else "") +
                     (f" (Session #{session_number})" if session_number is not None and op["operation"] == "append" else "") +
                     (" (optional; new candidate blocks only)" if op["operation"] == "stage" else "") +
                     (" (conditional; exact disposed blocks only)" if op["operation"] == "resolve" else "") +
                     (" (+ journal receipt under private-artifacts/session-journal/)" if op["class"] == "M2" and (not legacy or op["operation"] == "append") else "") for op in operations)


def _observed_targets(envelope: dict) -> dict:
    snap = envelope["local_snapshot"]
    return {field: ((snap.get(field) or {}).get("path") or names[0]) for field, names in
            (("index", INDEX_NAMES), ("pending_learnings", PENDING_NAMES), ("decisions_archive", ARCHIVE_NAMES), ("audit_policy", (POLICY_PATH,)))}


def _unfinished(root: Path) -> list[str]:
    journal = _contained(root, root / "private-artifacts/session-journal")
    if not journal.is_dir():
        return []
    return [str(p.relative_to(root)) for p in sorted(journal.iterdir()) if p.suffix == ".pending" or
            (p.suffix == ".json" and p.name not in {GRANDFATHER_POLICY, "workspace.json"} and _is_intent_file(p))]


def freeze_draft(envelope: dict, entry_text: str | None = None, index_text: str | None = None, continue_parent: str | None = None, refreshable: bool = False) -> dict:
    if not envelope:
        raise HelperError(S.MISSING_RECEIPT, "envelope absent")
    if refreshable and (envelope.get("skill") == "newbeginning" or _package_skill() == "newbeginning"):
        raise HelperError("ESKILL", "opening cannot write a pre-approval freeze witness")
    if envelope.get("skill") == "newbeginning" and continue_parent is not None:
        raise HelperError("ESKILL", "continuation finishes a closing operation; run closingtime")
    _fresh(envelope.get("local_snapshot") or {}, envelope.get("invocation_started_at"))
    root = _workspace_binding(envelope)
    verdict = S.validate_envelope(envelope, envelope.get("returned_rows_by_capability") or {})
    codes = {f["code"] for f in verdict["failures"]} - {S.SCOPE_UNAPPROVED}
    if "EHISTORY" in codes:
        raise HelperError("EHISTORY", _history_detail(envelope["local_snapshot"].get("parse_warnings", []), "ambiguous or malformed session history"))
    if codes:
        raise HelperError("EINVALIDENVELOPE", ",".join(sorted(codes)))
    root = _workspace_binding(envelope)
    if _unfinished(root) and not continue_parent:
        raise HelperError("EUNFINISHED", "run resume: " + ", ".join(_unfinished(root)))
    operations = _scope_operations(envelope)
    targets = _observed_targets(envelope)
    _preflight(root, envelope, operations)
    historical_count = None
    if any(op.get("path") == POLICY_PATH for op in operations):
        proposal = adopt_history(root)
        observed = envelope["local_snapshot"].get("audit_policy") or {}
        preimage = observed.get("sha256") if observed.get("present") else "absent"
        if (envelope.get("local_payload_hashes") or {}).get(POLICY_PATH) != proposal["policy_sha256"] or preimage != proposal["preimage"]:
            raise HelperError("EDRAFTMISMATCH", "policy payload is not the current adopt-history proposal")
        historical_count = int(re.search(r"\(adopt ([0-9]+) historical entries\)", proposal["scope_line"])[1])
    if entry_text is not None and any(op["class"] == "M2" and op["operation"] != "append" and op["path"] != targets["index"] and op not in ({"class": "M2", "operation": "stage", "path": "pending_learnings.md"}, {"class": "M2", "operation": "resolve", "path": "pending_learnings.md"}) for op in operations):
        raise HelperError("EINPUT", "parent close permits session, index and optional pending stage only")
    if any(op["operation"] == "stage" for op in operations) and not any(op["operation"] == "append" for op in operations):
        raise HelperError("ESTAGE", "stage requires the same close's parent append")
    if len([op for op in operations if op["operation"] == "stage"]) > 1:
        raise HelperError("ESTAGE", "only one optional stage line per close")
    if continue_parent:
        parents = [(p, r) for p, r in _load_intents(root) if p == _contained(root, root / continue_parent) and r["kind"] == "append_intent" and p.suffix == ".done"]
        if len(parents) != 1 or entry_text is not None:
            raise HelperError("ERECOVERY", "continuation requires one verified parent and no entry")
        continue_parent = parents[0][0].relative_to(root).as_posix()
        if _append_classification(parents[0][1], final=True, root=root) != "appended":
            raise HelperError("ERECOVERY", "continuation parent append changed")
        remaining = _remaining_paths(root, parents[0][1], _load_intents(root))
        if len(operations) != 1 or operations[0] != {"class": "M2", "operation": "replace", "path": targets["index"]} or targets["index"] not in {op["path"] for op in remaining}:
            raise HelperError("ERECOVERY", "continuation covers only the remaining index")
    if envelope.get("skill") == "newbeginning" and any(op["operation"] == "append" for op in operations):
        raise HelperError("ESKILL", "newbeginning never appends")
    if targets["index"] in [op.get("path") for op in operations] and index_text is None:
        raise HelperError("EDRAFTMISMATCH", "index in scope requires exact index draft")
    archive = targets["decisions_archive"]
    if any(op.get("path") == archive and op["operation"] == "replace" for op in operations):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", (envelope.get("local_payload_hashes") or {}).get(archive, "")):
            raise HelperError("EDRAFTMISMATCH", "archive scope requires local_payload_hashes binding")
    pending = targets["pending_learnings"]
    for op in operations:
        if op.get("path") == pending and op["operation"] in {"replace", "delete"}:
            binding = (envelope.get("local_payload_hashes") or {}).get(pending, "")
            if not (binding == "absent" if op["operation"] == "delete" else re.fullmatch(r"sha256:[a-f0-9]{64}", binding)):
                raise HelperError("EDRAFTMISMATCH", "pending replacement/delete requires local_payload_hashes binding")
    if any(op.get("path") == POLICY_PATH for op in operations):
        if any(op.get("path") == POLICY_PATH and op["operation"] != "replace" for op in operations) or not re.fullmatch(r"sha256:[a-f0-9]{64}", (envelope.get("local_payload_hashes") or {}).get(POLICY_PATH, "")):
            raise HelperError("EDRAFTMISMATCH", "policy replacement requires exact payload hash")
    session_number = None
    if any(op["operation"] == "append" for op in operations):
        path = _session_path_from_envelope(root, envelope)
        text = _read_text(root, path if path.exists() else None)
        tail, latest = _last_session_entries(text, 2)
        observed = envelope["local_snapshot"].get("session") or {}
        if latest != observed.get("latest_session_number") or _sha256_text(tail) != observed.get("tail_sha256"):
            raise HelperError("ESTALE", "snapshot session number or tail differs from the live log")
        session_number, _ = _next_session_number(root, text)
    if entry_text is not None:
        _render_entry(entry_text, session_number or (envelope["local_snapshot"].get("session") or {}).get("latest_session_number", 0) + 1)
    elif any(op["operation"] == "append" for op in operations):
        raise HelperError("EENTRYFORMAT", "append scope requires entry")
    preimages = {}
    for field, name in targets.items():
        obs = envelope["local_snapshot"].get(field) or {}
        preimages[name] = obs.get("sha256") if obs.get("present") else "absent"
    receipt = {
        "schema_version": S.SCHEMA_VERSION, "kind": DRAFT_RECEIPT_KIND, "recovery_version": 2,
        "invocation_id": envelope.get("invocation_id"), "skill": envelope.get("skill"), "workspace_root": str(root),
        "workspace_id": _workspace_id(root), "continue_parent": continue_parent,
        "snapshot_sha256": _snapshot_digest(envelope["local_snapshot"]),
        "snapshot_observed_at": envelope["local_snapshot"].get("observed_at"),
        "snapshot_captured_at": envelope["local_snapshot"].get("captured_at", envelope["local_snapshot"].get("observed_at")),
        "invocation_started_at": envelope.get("invocation_started_at"),
        "observed_tail_sha256": (envelope["local_snapshot"].get("session") or {}).get("tail_sha256"),
        "entry_sha256": _sha256_text(entry_text) if entry_text is not None else None,
        "entry_words": count_words(entry_text or ""),
        "index_draft_sha256": _sha256_text(index_text) if index_text is not None else None,
        "index_draft": index_text,
        "m2_preimages": preimages, "scope_operations": operations,
        "local_payload_hashes": envelope.get("local_payload_hashes") or {},
        "scope_lines": _scope_text(operations, session_number=session_number, historical_count=historical_count),
        "scope_sha256": _sha256_text(_scope_text(operations, session_number=session_number, historical_count=historical_count)),
        "drafted_at": _utc_now(), "approved_at": None, "scope_string": None, "owner_reply": None,
    }
    if refreshable:
        receipt["refresh_binding"] = _refresh_binding(envelope)
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    if refreshable:
        with _advisory_lock(root, receipt["invocation_id"]):
            witness = _approval_path(root, receipt["invocation_id"]).with_suffix(".draft")
            if witness.exists() or _approval_path(root, receipt["invocation_id"]).exists():
                raise HelperError("EINVOCATIONUSED", "refreshable invocation already frozen")
            _atomic_record(witness, receipt)
    return receipt


def approve_draft(receipt: dict, scope_string: str | None = None, owner_reply: str = "") -> dict:
    if not isinstance(receipt, dict) or receipt.get("kind") != DRAFT_RECEIPT_KIND or receipt.get("recovery_version") != 2:
        raise HelperError("EDRAFTRECEIPT", "not a current draft receipt; freeze again")
    if receipt.get("skill") == "newbeginning" and receipt.get("continue_parent") is not None:
        raise HelperError("ESKILL", "continuation finishes a closing operation; run closingtime")
    if receipt.get("receipt_sha256") != _receipt_digest(receipt):
        raise HelperError("EDRAFTRECEIPT", "modified receipt")
    if receipt.get("approved_at"):
        raise HelperError("EINVOCATIONUSED", "invocation already approved")
    original_digest = receipt.get("receipt_sha256")
    if scope_string is not None and scope_string != receipt.get("scope_lines"):
        raise HelperError(S.SCOPE_UNAPPROVED, "approval must equal exact rendered scope")
    if scope_string is None or re.search(r"\b(?:skip|except)\b", owner_reply, re.I):
        receipt = _approval_selection(receipt, owner_reply)
        scope_string = receipt["scope_lines"]
    if not scope_string or scope_string != receipt.get("scope_lines"):
        raise HelperError(S.SCOPE_UNAPPROVED, "approval must equal exact rendered scope; exclusions require a new freeze")
    if not isinstance(owner_reply, str) or not owner_reply.strip():
        raise HelperError(S.SCOPE_UNAPPROVED, "approval requires non-empty owner words")
    package = _package_skill()
    if package and (receipt.get("skill") != package or package == "newbeginning" and any(op.get("path") not in INDEX_NAMES or op.get("operation") != "replace" for op in receipt.get("scope_operations", []))):
        raise HelperError("ESKILL", "draft is outside this package scope")
    _fresh({"captured_at": receipt.get("snapshot_captured_at", receipt.get("snapshot_observed_at"))}, receipt.get("invocation_started_at"))
    root = _resolve_root(receipt["workspace_root"])
    _check_identity(root, receipt)
    now = dt.datetime.now(dt.timezone.utc)
    drafted = _parse_utc(receipt.get("drafted_at"))
    if drafted is None or drafted >= now:
        raise HelperError("ECHRONOLOGY", "draft time must precede helper approval time")
    with _advisory_lock(root, receipt["invocation_id"]) as recovered:
        path = _approval_path(root, receipt["invocation_id"])
        if path.exists():
            raise HelperError("EINVOCATIONUSED", "one approved draft per invocation")
        approved = dict(receipt, warnings=["ELOCK_STALE_RECOVERED"] if recovered else [], workspace_id=_workspace_id(root, create=True), approved_at=now.isoformat().replace("+00:00", "Z"), scope_string=scope_string, owner_reply=owner_reply)
        approved["receipt_sha256"] = _receipt_digest(approved)
        _atomic_record(path, {"workspace_root": str(root), "receipt_sha256": approved["receipt_sha256"], "approved_draft": approved, "frozen_sha256": original_digest})
    return approved


def _check_approved_draft(envelope: dict, entry_text: str | None, receipt: dict | None) -> None:
    if not isinstance(receipt, dict) or receipt.get("kind") != DRAFT_RECEIPT_KIND or receipt.get("recovery_version") != 2:
        raise HelperError("EDRAFTRECEIPT", "requires current approved draft receipt")
    if receipt.get("receipt_sha256") != _receipt_digest(receipt) or not receipt.get("approved_at"):
        raise HelperError("EDRAFTRECEIPT", "modified or unapproved draft receipt")
    if receipt.get("carry_origin_at"):
        _check_carry_age(receipt["carry_origin_at"])
    legacy = "snapshot_captured_at" not in receipt
    scope = _scope_text(_scope_operations(envelope, legacy=legacy), legacy=legacy,
                        session_number=int(re.search(r" \(Session #([0-9]+)\)", receipt["scope_lines"])[1]) if re.search(r" \(Session #[0-9]+\)", receipt.get("scope_lines", "")) else None,
                        historical_count=int(re.search(r"\(adopt ([0-9]+) historical entries\)", receipt["scope_lines"])[1]) if re.search(r"\(adopt ([0-9]+) historical entries\)", receipt.get("scope_lines", "")) else None)
    snapshot_matches = receipt.get("snapshot_sha256") == _snapshot_digest(envelope.get("local_snapshot"))
    if legacy:
        snapshot_matches |= receipt.get("snapshot_sha256") == _sha256_bytes(_canonical_json(envelope.get("local_snapshot")))
        if envelope.get("resume_intent"):
            for path, record in _load_intents(_resolve_root(envelope["workspace_root"])):
                original = record["approved_envelope"]["local_snapshot"]
                if str(path) == envelope["resume_intent"] and receipt["receipt_sha256"] == record["draft_receipt_sha256"]:
                    snapshot_matches |= receipt.get("snapshot_sha256") == _sha256_bytes(_canonical_json(original)) and _snapshot_digest(original) == _snapshot_digest(envelope["local_snapshot"])
    if receipt.get("invocation_id") != envelope.get("invocation_id") or not snapshot_matches or receipt.get("scope_lines") != scope or receipt.get("scope_sha256") != _sha256_text(scope):
        raise HelperError("EDRAFTMISMATCH", "invocation, root, snapshot or scope differs from frozen draft")
    if "invocation_started_at" in receipt and receipt["invocation_started_at"] != envelope.get("invocation_started_at"):
        raise HelperError("EDRAFTMISMATCH", "invocation start differs from frozen draft")
    if entry_text is not None and receipt.get("entry_sha256") != _sha256_text(entry_text):
        raise HelperError("EDRAFTMISMATCH", "entry differs from frozen draft")
    if receipt.get("scope_string") != (envelope.get("approval") or {}).get("scope_string"):
        raise HelperError("EDRAFTMISMATCH", "envelope approval differs from frozen scope")
    observed, drafted, approved = [_parse_utc(receipt.get(k)) for k in ("snapshot_observed_at", "drafted_at", "approved_at")]
    if not (observed and drafted and approved and observed <= drafted < approved <= dt.datetime.now(dt.timezone.utc)):
        raise HelperError("ECHRONOLOGY", "require snapshot <= drafted < approved <= now")


def _approved_context(envelope: dict, receipt: dict, entry_text: str | None = None) -> Path:
    if not envelope:
        raise HelperError(S.MISSING_RECEIPT, "envelope absent")
    root = _workspace_binding(envelope)
    _check_approved_draft(envelope, entry_text, receipt)
    _check_identity(root, receipt)
    _check_invocation(root, receipt)
    recovering = False
    if envelope.get("resume_intent"):
        for path, record in _load_intents(root):
            if str(path) == envelope["resume_intent"] and record["draft_receipt_sha256"] == receipt["receipt_sha256"] and record["kind"] == "remaining_intent" and path.suffix == ".pending":
                parents = [(p, r) for p, r in _load_intents(root) if p == _contained(root, root / record["parent_intent"]) and p.suffix == ".done" and r["kind"] == "append_intent"]
                recovering = len(parents) == 1 and _append_classification(parents[0][1], final=True, root=root) == "appended"
        if not recovering:
            raise HelperError("ERECOVERY", "resume exemption needs a bound unfinished child")
    if not recovering:
        _fresh(envelope["local_snapshot"], envelope.get("invocation_started_at"))
    result = S.validate_envelope(envelope, envelope.get("returned_rows_by_capability") or {}, resume_bound=recovering)
    if not result["valid"]:
        raise HelperError("EINVALIDENVELOPE", ",".join(sorted({f["code"] for f in result["failures"]})))
    if not (envelope.get("approval") or {}).get("granted"):
        raise HelperError(S.SCOPE_UNAPPROVED, "explicit approval required")
    return root


def _check_conflicts(root: Path) -> None:
    conflicts = _sync_conflicts(root)
    if conflicts:
        raise HelperError(S.SYNC_CONFLICT, ", ".join(conflicts))


def _load_intents(root: Path) -> list[tuple[Path, dict]]:
    journal = _contained(root, root / "private-artifacts/session-journal")
    if not journal.is_dir():
        return []
    records = []
    for path in sorted(journal.iterdir()):
        if path.name in {GRANDFATHER_POLICY, "workspace.json", ".lock"} or path.is_dir():
            continue
        _contained(root, path)
        if path.suffix not in {".pending", ".json", ".done", ".abandoned"}:
            continue
        try:
            record = json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            raise HelperError("ERECOVERY", f"malformed record: {path}") from exc
        if not isinstance(record, dict):
            raise HelperError("ERECOVERY", f"record is not an object: {path}")
        if record.get("kind") not in {"append_intent", "write_intent", "remaining_intent"}:
            if path.suffix != ".json" or S.validate_journal_record(record):
                raise HelperError("ERECOVERY", f"foreign record: {path}")
            continue  # legacy journals are audit-only, never rewritten
        _check_identity(root, record)
        if record.get("record_sha256") != _intent_digest(record):
            raise HelperError("ERECOVERY", f"modified intent: {path}")
        required = {"workspace_root", "target", "preimage", "draft_receipt_sha256", "invocation_id", "approved_scope", "written_at", "approved_envelope", "approved_draft"}
        required |= ({"append_bytes", "append_length", "append_sha256", "session_number", "entry_sha256", "m2_operations"} if record["kind"] == "append_intent" else {"relative_path", "operation", "postimage", "transition_id"} if record["kind"] == "write_intent" else {"relative_path", "parent_intent"})
        if not required <= record.keys() or not isinstance(record["target"], str):
            raise HelperError("ERECOVERY", f"incomplete intent: {path}")
        draft = record["approved_draft"]
        saved_envelope = record["approved_envelope"]
        if not isinstance(draft, dict) or not isinstance(saved_envelope, dict) or draft.get("receipt_sha256") != record["draft_receipt_sha256"] or draft.get("receipt_sha256") != _receipt_digest(draft):
            raise HelperError("ERECOVERY", f"recovery inputs differ from intent: {path}")
        for state in [record["preimage"]] + ([record["postimage"]] if record["kind"] == "write_intent" else []):
            if not isinstance(state, dict) or set(state) != {"exists", "length", "sha256"} or not isinstance(state["exists"], bool) or type(state["length"]) is not int or state["length"] < 0 or not isinstance(state["sha256"], str):
                raise HelperError("ERECOVERY", f"invalid byte state: {path}")
        _record_target(root, record)
        records.append((path, record))
    keys = [(r["draft_receipt_sha256"], r["kind"], r.get("transition_id", "append")) for p, r in records if p.suffix != ".abandoned"]
    allocations = [(r["target"], r["session_number"]) for p, r in records if r["kind"] == "append_intent" and p.suffix != ".abandoned"]
    if len(keys) != len(set(keys)) or len(allocations) != len(set(allocations)):
        raise HelperError("ERECOVERY", "multiple conflicting intent matches")
    return records


def _intent_digest(record: dict) -> str:
    return _sha256_bytes(_canonical_json({k: v for k, v in record.items() if k != "record_sha256"}))


def _persist_intent(root: Path, record: dict) -> Path:
    record["workspace_root"] = str(root)
    record["workspace_id"] = _workspace_id(root, create=True)
    record["record_sha256"] = _intent_digest(record)
    path = _journal_dir(root) / (uuid.uuid4().hex + ".pending")
    _atomic_record(path, record)
    return path


def _record_target(root: Path, record: dict) -> Path:
    target = Path(record["target"])
    if target.is_absolute():  # legacy v2 intent, retain bytes and relocate by its recorded root
        try:
            target = target.relative_to(record["workspace_root"])
        except ValueError as exc:
            raise HelperError("EPERM", "legacy target outside recorded root") from exc
    if ".." in target.parts:
        raise HelperError("EPERM", "intent traversal")
    return _contained(root, root / target)


def _append_classification(record: dict, final: bool = False, root: Path | None = None) -> str:
    path = _record_target(root or Path(record["workspace_root"]), record)
    if _state_matches(path, record["preimage"]):
        return "not_appended"
    data = path.read_bytes() if path.exists() else b""
    pre = record["preimage"]
    appended = base64.b64decode(record["append_bytes"], validate=True)
    expected_length = pre["length"] + len(appended)
    if len(appended) != record["append_length"] or _sha256_bytes(appended) != record["append_sha256"]:
        raise HelperError("ERECOVERY", "intent append hash/length mismatch")
    prefix_ok = (not pre["exists"] and pre["length"] == 0) or _sha256_bytes(data[:pre["length"]]) == pre["sha256"]
    if final:
        # Finished receipts bind their own entry, independent of later edits to
        # earlier entries. Pending appends still require the full byte prefix.
        entries = _parse_session_entries(data.decode("utf-8"))
        matches = [e for e in entries if e["session_number"] == record["session_number"]]
        if len(matches) == 1 and matches[0]["entry_sha256"] == record["entry_sha256"]:
            return "appended"
    if prefix_ok and data[pre["length"]:expected_length] == appended and (len(data) == expected_length or (final and len(data) > expected_length)):
        return "appended"
    return "partial_or_conflicted"


def _append_bytes(path: Path, data: bytes) -> None:
    with path.open("ab" if os.path.lexists(path) else "xb") as stream:
        if stream.write(data) != len(data):
            raise OSError("short append")
        stream.flush()
        os.fsync(stream.fileno())


def _conditional_rollback(record: dict, pending: Path, root: Path) -> bool:
    if _append_classification(record, root=root) != "appended":
        return False
    path = _record_target(root or Path(record["workspace_root"]), record)
    if record["preimage"]["exists"]:
        with path.open("r+b") as stream:
            stream.truncate(record["preimage"]["length"])
            stream.flush(); os.fsync(stream.fileno())
    else:
        path.unlink()
        _fsync_dir(path.parent)
    if not _state_matches(path, record["preimage"]):
        return False
    _move_record(pending, ".abandoned")
    for path, child in _load_intents(root):
        if child["kind"] == "remaining_intent" and child["draft_receipt_sha256"] == record["draft_receipt_sha256"] and path.suffix == ".pending":
            _move_record(path, ".abandoned")
    return True


def _remaining_paths(root: Path, record: dict, records: list[tuple[Path, dict]]) -> list[dict]:
    remaining = []
    for name, operation in record.get("m2_operations", {}).items():
        if name not in INDEX_NAMES:
            continue  # legacy learning scopes no longer hold a parent close open
        children = [(p, r) for p, r in records if r["kind"] == "remaining_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and r["relative_path"] == name]
        writes = [(p, r) for p, r in records if r["kind"] == "write_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and r["relative_path"] == name and p.suffix == ".done"]
        if writes or (children and all(p.suffix in {".done", ".abandoned"} for p, r in children)):
            continue
        actual = _file_state(_contained(root, root / name))
        remaining.append({"path": name, **operation, "state": "remaining_stale" if actual["sha256"] != operation["preimage"] else "remaining", "current_sha256": actual["sha256"]})
    return remaining


def _create_children(root: Path, parent_path: Path, record: dict, records: list[tuple[Path, dict]]) -> None:
    for item in _remaining_paths(root, record, records):
        if any(r["kind"] == "remaining_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and r["relative_path"] == item["path"] for p, r in records):
            continue
        name = item["path"]
        child = {k: record[k] for k in ("workspace_root", "invocation_id", "draft_receipt_sha256", "approved_scope", "written_at", "approved_envelope", "approved_draft")}
        child.update(kind="remaining_intent", target=name, relative_path=name, parent_intent=parent_path.relative_to(root).with_suffix(".done").as_posix(), preimage={"exists": item["preimage"] != "absent", "length": 0, "sha256": item["preimage"]})
        _persist_intent(root, child)


def append_session_entry(envelope: dict, entry_text: str, approved_draft: dict | None = None) -> dict:
    if envelope and envelope.get("skill") != "closingtime":
        raise HelperError("ESKILL", "only closingtime appends")
    root = _approved_context(envelope, approved_draft, entry_text)
    if not envelope.get("skill_version"):
        raise HelperError("EMISSINGVERSION", "skill_version required")
    warnings = list(approved_draft.get("warnings", []))
    try:
        with _advisory_lock(root, envelope["invocation_id"]) as recovered:
            if recovered:
                warnings.append("ELOCK_STALE_RECOVERED")
            _check_conflicts(root)
            records = _load_intents(root)
            for path, record in records:
                if record["kind"] == "append_intent" and record["draft_receipt_sha256"] == approved_draft["receipt_sha256"] and path.suffix != ".abandoned":
                    state = _resume_append_state(root, path, record)
                    if state == "appended":
                        if path.suffix == ".pending":
                            path = _move_record(path, ".done")
                        return {"session_number": record["session_number"], "entry_sha256": record["entry_sha256"], "journal_record_path": str(path), "already_appended": True, "readback_ok": True, "warnings": warnings}
                    raise HelperError("EUNFINISHED", "existing intent; run resume")
            if _unfinished(root):
                raise HelperError("EUNFINISHED", "run resume before another close")
            _preflight(root, envelope, approved_draft["scope_operations"], approved_draft["m2_preimages"])
            session_path = _session_path_from_envelope(root, envelope)
            relative = session_path.relative_to(root).as_posix()
            if {"class": "M2", "operation": "append", "path": relative} not in approved_draft["scope_operations"]:
                raise HelperError(S.SCOPE_UNAPPROVED, "session append not in scope")
            _, alternates = _named_observation(root, SESSION_NAMES)
            current_text = _read_text(root, session_path if session_path.exists() else None)
            history = _parse_warnings("", current_text)
            if alternates or any(w in S.HISTORY_ERRORS for w in history):
                raise HelperError("EHISTORY", _history_detail(history, "ambiguous or malformed session history"))
            tail, latest = _last_session_entries(current_text, 2)
            if _sha256_text(tail) != approved_draft["observed_tail_sha256"]:
                raise HelperError("ESTALE", "session tail changed after draft")
            number, reserved_missing = _next_session_number(root, current_text)
            approved_number = re.search(r" \(Session #([0-9]+)\)", approved_draft["scope_lines"])
            if approved_number and int(approved_number[1]) != number:
                raise HelperError("ESTALE", f"approved Session #{approved_number[1]}, next unreserved is #{number}; freeze again")
            if reserved_missing:
                warnings.append("ALLOCATION_GAP")
            chunk = _render_entry(entry_text, number)
            date = dt.date.fromisoformat(SESSION_HEADER_RE.search(chunk).group("date"))
            local_date = dt.date.fromisoformat(envelope["local_snapshot"]["local_date"])
            if abs((date-local_date).days) > 1:
                warnings.append("ENTRY_DATE_SKEW")
            preimage = _file_state(session_path)
            prefix = "# Session Log\n\n" if not preimage["exists"] else ("" if current_text.endswith("\n\n") else "\n" if current_text.endswith("\n") else "\n\n")
            data = (prefix + chunk).encode("utf-8")
            m2 = {name: {"preimage": expected, "payload_sha256": approved_draft["index_draft_sha256"] if name == _observed_targets(envelope)["index"] else (approved_draft.get("local_payload_hashes") or {}).get(name)} for name, expected in approved_draft["m2_preimages"].items() if any(op.get("path") == name for op in approved_draft["scope_operations"])}
            record = {"schema_version": S.SCHEMA_VERSION, "kind": "append_intent", "workspace_root": str(root),
                      "target": relative, "preimage": preimage, "session_number": number,
                      "entry_sha256": _sha256_text(chunk), "append_sha256": _sha256_bytes(data), "append_length": len(data),
                      "append_bytes": base64.b64encode(data).decode(), "invocation_id": envelope["invocation_id"],
                      "draft_receipt_sha256": approved_draft["receipt_sha256"], "approved_scope": approved_draft["scope_lines"],
                      "m2_operations": m2, "envelope_sha256": _sha256_bytes(_canonical_json(envelope)),
                      "written_at": _utc_now(), "skill_version": envelope["skill_version"], "approved_at": approved_draft["approved_at"],
                      "approved_envelope": envelope, "approved_draft": approved_draft}
            try:
                pending = _persist_intent(root, record)
                _create_children(root, pending, record, records)
            except OSError as exc:
                raise HelperError("EJOURNAL", f"intent not durable; log untouched: {exc}") from exc
            try:
                # Recheck after intent I/O as well as under the shared lock.
                if not _state_matches(session_path, preimage):
                    raise HelperError("EPARTIAL_APPEND", f"preimage changed after intent: {pending}")
                _refuse_links(root, relative)
                _append_bytes(session_path, data)
                readback = _readback_entry(session_path, number)
                if readback is None or _sha256_text(readback) != record["entry_sha256"] or _append_classification(record, root=root) != "appended":
                    raise OSError("appended bytes did not read back")
            except (OSError, UnicodeError) as exc:
                try:
                    rolled_back = _conditional_rollback(record, pending, root)
                except (OSError, HelperError):
                    rolled_back = False
                raise HelperError("EREADBACK" if rolled_back else "EPARTIAL_APPEND", str(exc), rolled_back=rolled_back, pending_record=str(pending), session_number=number, entry_sha256=record["entry_sha256"], state="not_appended" if rolled_back else "partial_or_conflicted") from exc
            try:
                final = _move_record(pending, ".done")
            except OSError as exc:
                raise HelperError("EPARTIAL_APPEND", str(exc), pending_record=str(pending), session_number=number, entry_sha256=record["entry_sha256"], state="appended") from exc
            result = {"session_number": number, "entry_sha256": record["entry_sha256"], "journal_record_path": str(final), "readback_ok": True, "warnings": warnings}
            if reserved_missing:
                result["reserved_missing"] = reserved_missing
        return result
    except OSError as exc:
        raise HelperError("EPARTIAL_APPEND", f"inspect retained intent via resume: {exc}") from exc


def _refuse_links(root: Path, relative: str) -> None:
    """Refuse links below a resolved root, including the final component."""
    path = root.resolve()
    for component in Path(relative).parts:
        path = path / component
        if path.is_symlink():
            raise HelperError("EPERM", "symlinked continuity path: " + relative)


def _writer_target(root: Path, envelope: dict, relative_path: str) -> tuple[Path, str]:
    if envelope.get("skill") == "newbeginning" and relative_path not in INDEX_NAMES:
        raise HelperError("ESKILL", "opening only writes the approved index")
    if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise HelperError("EPERM", "relative contained target required")
    _refuse_links(root, relative_path)
    if relative_path == POLICY_PATH:
        if envelope.get("skill") != "closingtime":
            raise HelperError("ESKILL", "only closingtime writes audit policy")
        target = _contained(root, root / POLICY_PATH)
        if target.exists() and not target.is_file():
            raise HelperError("EPERM", "policy target is not a file")
        return target, "audit_policy"
    groups = {"index": INDEX_NAMES, "pending_learnings": ("pending_learnings.md",), "decisions_archive": ARCHIVE_NAMES}
    field = next((key for key, names in groups.items() if relative_path in names), None)
    if field is None:
        raise HelperError("EPERM", "writer allows fixed index aliases, pending_learnings.md and project_decisions_archive.md only")
    if envelope.get("skill") == "newbeginning" and field != "index":
        raise HelperError("ESKILL", "opening only writes its index")
    names = groups[field]
    observed = _observed_targets(envelope)[field]
    if observed not in names or observed != relative_path:
        raise HelperError("EPERM", "snapshot labels cannot expand fixed target names")
    resolved, alternates = _named_observation(root, names)
    if alternates:
        raise HelperError("EAMBIGUOUSNAME", "target has alternate continuity names")
    target = _contained(root, root / relative_path)
    if resolved is not None and resolved != target:
        raise HelperError("ESOURCECHANGED", "observed target name changed")
    if target.exists() and not target.is_file():
        raise HelperError("EPERM", "target is not a file")
    return target, field


def _replace_mirror(index: str, rows: list[dict], local_date: str) -> str:
    pattern = r"(?ms)(^## Active TODOs[^\n]*\n).*?(?=^## |\Z)"
    if not re.search(pattern, index):
        raise HelperError("EDRAFTMISMATCH", "index requires Active TODOs section for mirror")
    return re.sub(pattern, lambda m: m.group(1) + render_task_mirror(rows, local_date) + "\n", index, count=1)


def _stage_parent(root: Path, receipt_sha256: str, records: list[tuple[Path, dict]]) -> Path:
    parents = [(p, r) for p, r in records if r["kind"] == "append_intent" and r["draft_receipt_sha256"] == receipt_sha256 and p.suffix == ".done"]
    if len(parents) != 1 or _append_classification(parents[0][1], final=True, root=root) != "appended":
        raise HelperError("EUNFINISHED", "verify the parent append before staging")
    return parents[0][0]


def _stage_payload(current: bytes, payload: bytes) -> None:
    """Check only new block structure; existing v1 bytes are opaque and immutable."""
    if not payload.startswith(current):
        raise HelperError("ESTAGE", "stage cannot change any existing byte")
    try:
        suffix = payload[len(current):].decode("utf-8")
    except UnicodeError as exc:
        raise HelperError("ESTAGE", "new candidate blocks must be UTF-8") from exc
    if current and not current.endswith(b"\n") and not suffix.startswith("\n"):
        raise HelperError("ESTAGE", "new blocks must start on a new line")
    blocks = re.split(r"(?m)^## Candidate [0-9]+[^\S\n]*\r?$", suffix)
    if len(blocks) < 2 or blocks[0].strip():
        raise HelperError("ESTAGE", "append one or more ## Candidate <number> blocks only")
    for block in blocks[1:]:
        if re.search(r"(?m)^#{1,6} ", block) or not all(re.search(pattern, block) for pattern in (
                r"(?m)^\*\*Type:\*\*[^\S\n]*\S", r"(?m)^\*\*Insight:\*\*[^\S\n]*\S",
                r"(?m)^\*\*(?:Connection|Connects to):\*\*[^\S\n]*\S")):
            raise HelperError("ESTAGE", "new blocks need Type, Insight and Connection/Connects to")
        statuses = re.findall(r"(?m)^\*\*Status:\*\*[^\S\n]*(.*?)\s*$", block)
        if any(status != "pending" for status in statuses):
            raise HelperError("ESTAGE", "stage cannot apply a disposition")


def _resume_stage(root: Path, path: Path, record: dict, records: list[tuple[Path, dict]]) -> Path:
    """Retry the exact durable stage child, without a second staging transition."""
    parent = _stage_parent(root, record["draft_receipt_sha256"], records)
    if parent.relative_to(root).as_posix() != record.get("parent_intent"):
        raise HelperError("ERECOVERY", "stage parent binding differs")
    target, _ = _writer_target(root, record["approved_envelope"], record["relative_path"])
    payload = base64.b64decode(record["payload_bytes"], validate=True)
    current = target.read_bytes() if target.exists() else b""
    _stage_payload(current, payload)
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    _check_conflicts(root)
    _writer_target(root, record["approved_envelope"], record["relative_path"])
    if not _state_matches(target, record["preimage"]):
        raise HelperError("EPARTIAL_WRITE", "stage preimage changed; preserve child and foreign bytes")
    os.replace(temporary, target)
    _fsync_dir(target.parent)
    if not _state_matches(target, record["postimage"]):
        raise HelperError("EPARTIAL_WRITE", "stage readback failed; preserve child")
    return _move_record(path, ".done")


def write_approved_file(envelope: dict, receipt: dict, relative_path: str, content: str | None = None,
                        operation: str = "replace", expect: str | None = None,
                        mirror_rows: list[dict] | None = None, owner_reply: str = "", dispositions: list[dict] | None = None) -> dict:
    root = _approved_context(envelope, receipt)
    if (envelope.get("skill") == "newbeginning" or receipt.get("skill") == "newbeginning") and receipt.get("continue_parent") is not None:
        raise HelperError("ESKILL", "continuation finishes a closing operation; run closingtime")
    if operation not in {"replace", "delete", "stage", "resolve"} or expect is None or (expect != "absent" and not re.fullmatch(r"sha256:[a-f0-9]{64}", expect)):
        raise HelperError("EINPUT", "replace/delete/stage and explicit --expect sha256|absent required")
    if {"class": "M2", "operation": operation, "path": relative_path} not in receipt["scope_operations"]:
        raise HelperError(S.SCOPE_UNAPPROVED, "target/operation not in approved scope")
    if operation in {"replace", "stage"} and content is None or operation in {"delete", "resolve"} and content is not None:
        raise HelperError("EINPUT", "replace/stage needs payload; delete has none")
    try:
        with _advisory_lock(root, envelope["invocation_id"]) as recovered:
            _check_conflicts(root)
            current = capture_local_snapshot(root)
            if any(w in S.HISTORY_ERRORS for w in current["parse_warnings"]):
                raise HelperError("EHISTORY", _history_detail(current["parse_warnings"], "history changed or malformed"))
            target, field = _writer_target(root, envelope, relative_path)
            if field == "audit_policy":
                proposal = adopt_history(root)
                if _sha256_text(content or "") != proposal["policy_sha256"] or proposal["policy_sha256"] != receipt.get("local_payload_hashes", {}).get(relative_path) or expect != proposal["preimage"]:
                    raise HelperError("EDRAFTMISMATCH", "adopt-history proposal changed; run adopt-history and freeze again")
            records = _load_intents(root)
            stage_parent = None
            if operation == "stage":
                if relative_path != "pending_learnings.md" or envelope.get("skill") != "closingtime":
                    raise HelperError("ESTAGE", "only closingtime stages pending_learnings.md")
                stage_parent = _stage_parent(root, receipt["receipt_sha256"], records)
                if any(r["kind"] == "write_intent" and r["draft_receipt_sha256"] == receipt["receipt_sha256"] and r["operation"] == "stage" for p, r in records):
                    raise HelperError("ESTAGE", "one staging transition per close; resume or abandon its child")
            previous = [(p, r) for p, r in records if r["kind"] == "write_intent" and r["draft_receipt_sha256"] == receipt["receipt_sha256"] and r["relative_path"] == relative_path]
            if any(p.suffix == ".pending" and r["kind"] != "remaining_intent" for p, r in records):
                raise HelperError("EUNFINISHED", "resume pending intent before writing")
            if previous and operation not in {"stage", "resolve"}:
                raise HelperError("EDRAFTMISMATCH", "one transition per path per approved draft")
            if operation == "resolve":
                if field != "pending_learnings" or envelope.get("skill") != "closingtime":
                    raise HelperError("ESKILL", "only closingtime resolves pending learnings")
                if any(r["operation"] == "resolve" for _, r in previous):
                    raise HelperError("EDRAFTMISMATCH", "one resolution per approval")
                if any(op["operation"] == "append" for op in receipt["scope_operations"]):
                    _stage_parent(root, receipt["receipt_sha256"], records)
                if _file_state(target)["sha256"] != expect:
                    raise HelperError("ESOURCECHANGED", "resolution preimage changed")
                resolved = resolved_pending_payload(target.read_bytes() if target.exists() else b"", dispositions or [])
                content = resolved.decode("utf-8") if resolved is not None else None
                owner_reply = receipt["owner_reply"]
            if field == "pending_learnings":
                if operation not in {"stage", "resolve"} and receipt.get("local_payload_hashes", {}).get(relative_path) != (_sha256_text(content) if operation == "replace" else "absent"):
                    raise HelperError("EDRAFTMISMATCH", "pending payload differs from approved hash")
                if operation not in {"stage", "resolve"} and not owner_reply.strip():
                    raise HelperError(S.SCOPE_UNAPPROVED, "every pending revision needs --owner-reply")
                if dt.datetime.now(dt.timezone.utc) - _parse_utc(receipt["approved_at"]) > dt.timedelta(hours=6):
                    raise HelperError("ESTALEEVIDENCE", "pending approval older than six hours")
            if field == "index":
                if any(op["operation"] == "append" for op in receipt["scope_operations"]):
                    parents = [(p, r) for p, r in records if r["kind"] == "append_intent" and r["draft_receipt_sha256"] == receipt["receipt_sha256"] and p.suffix in {".done", ".json"}]
                    if len(parents) != 1 or _append_classification(parents[0][1], final=True, root=root) != "appended":
                        raise HelperError("EUNFINISHED", "verify the parent append before its index transition")
                if previous:
                    raise HelperError("EDRAFTMISMATCH", "index allows one transition per approved draft")
                if operation != "replace" or receipt["index_draft_sha256"] != _sha256_text(content):
                    raise HelperError("EDRAFTMISMATCH", "index payload differs from approved draft")
                if mirror_rows is not None:
                    if (envelope.get("capability_profile") or {}).get("external", {}).get("tasks_mcp") != "working":
                        raise HelperError(S.MISSING_RECEIPT, "mirror rows require current Tasks evidence")
                    # These are post-write rows; caller must supply the freshly
                    # re-read validated envelope receipt, separately from frozen snapshot.
                    mirror_receipt = envelope.get("mirror_receipt")
                    if not mirror_receipt:
                        raise HelperError(S.MISSING_RECEIPT, "post-Tasks mirror_receipt required")
                    check = dict(envelope, mcp_receipts=[mirror_receipt], returned_rows_by_capability={"tasks_mcp": mirror_rows})
                    external = dict(envelope["capability_profile"]["external"], open_brain="absent")
                    check["capability_profile"] = dict(envelope["capability_profile"], external=external)
                    verdict = S.validate_envelope(check, {"tasks_mcp": mirror_rows})
                    if not verdict["valid"]:
                        raise HelperError("EINVALIDENVELOPE", json.dumps(verdict["failures"]))
                    content = _replace_mirror(content, mirror_rows, envelope["local_snapshot"]["local_date"])
            elif mirror_rows is not None:
                raise HelperError("EINPUT", "mirror rows are index-only")
            if field in {"decisions_archive", "audit_policy"} and operation == "replace" and receipt["local_payload_hashes"].get(relative_path) != _sha256_text(content):
                raise HelperError("EDRAFTMISMATCH", "archive payload differs from approved hash")
            if operation != "stage" and not previous and expect != receipt["m2_preimages"][relative_path]:
                raise HelperError("ESOURCECHANGED", "first transition must use observed preimage")
            if previous:
                latest = max(previous, key=lambda pair: pair[1]["written_at"])[1]
                if expect != latest["postimage"]["sha256"]:
                    raise HelperError("ESOURCECHANGED", "revision must follow last verified transition")
            preimage = _file_state(target)
            if preimage["sha256"] != expect:
                raise HelperError("ESOURCECHANGED", "current bytes differ from expected preimage")
            payload = content.encode("utf-8") if content is not None else None
            if operation == "stage":
                _stage_payload(target.read_bytes() if target.exists() else b"", payload)
            postimage = {"exists": True, "length": len(payload), "sha256": _sha256_bytes(payload)} if payload is not None else {"exists": False, "length": 0, "sha256": "absent"}
            record = {"schema_version": S.SCHEMA_VERSION, "kind": "write_intent", "workspace_root": str(root),
                      "target": relative_path, "relative_path": relative_path, "operation": operation,
                      "preimage": preimage, "postimage": postimage, "payload_sha256": postimage["sha256"],
                      "draft_receipt_sha256": receipt["receipt_sha256"], "invocation_id": envelope["invocation_id"],
                      "approved_scope": receipt["scope_lines"], "owner_reply": owner_reply or (receipt.get("owner_reply", "") if operation == "stage" else ""),
                      "dispositions": dispositions if operation == "resolve" else None,
                      "transition_id": uuid.uuid4().hex, "written_at": _utc_now(),
                      "payload_bytes": base64.b64encode(payload).decode() if payload is not None else None,
                      "approved_envelope": envelope, "approved_draft": receipt}
            if stage_parent is not None:
                record["parent_intent"] = stage_parent.relative_to(root).as_posix()
            pending = _persist_intent(root, record)
            temporary = None
            if payload is not None:
                temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
                with temporary.open("xb") as stream:
                    stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            _check_conflicts(root)
            _writer_target(root, envelope, relative_path)
            if not _state_matches(target, preimage):
                raise HelperError("EPARTIAL_WRITE", "preimage changed before replacement; preserve intent and foreign file")
            if temporary is not None:
                os.replace(temporary, target)
            elif target.exists():
                target.unlink()
            _fsync_dir(target.parent)
            if not _state_matches(target, postimage):
                raise HelperError("EPARTIAL_WRITE", "postimage did not read back; resume")
            final = _move_record(pending, ".done")
            for child_path, child in _load_intents(root):
                if child["kind"] == "remaining_intent" and child_path.suffix == ".pending" and child["relative_path"] == relative_path:
                    if child["draft_receipt_sha256"] == receipt["receipt_sha256"] or child["parent_intent"] == receipt.get("continue_parent"):
                        _move_record(child_path, ".done")
            return {"path": relative_path, "operation": operation, "readback_sha256": postimage["sha256"], "bytes": postimage["length"], "readback_ok": True, "journal_record_path": str(final), "warnings": ["ELOCK_STALE_RECOVERED"] if recovered else []}

    except OSError as exc:
        raise HelperError("EPARTIAL_WRITE", f"inspect intent via resume: {exc}") from exc


def _recovery_inputs(root: Path, path: Path, record: dict) -> dict:
    envelope = copy.deepcopy(record["approved_envelope"])
    envelope["workspace_root"] = str(root)
    envelope["local_snapshot"]["workspace_root"] = str(root)
    envelope["resume_intent"] = str(path)
    return {"envelope": envelope, "approved_draft": record["approved_draft"],
            "index_draft": record["approved_draft"].get("index_draft")}


def _resume_append_state(root: Path, path: Path, record: dict) -> str:
    state = _append_classification(record, final=path.suffix != ".pending", root=root)
    if path.suffix == ".done" and state != "appended":
        target = _record_target(root, record)
        entries = _parse_session_entries(_read_text(root, target) if target.exists() else "")
        return "edited_after_close" if any(e["session_number"] == record["session_number"] for e in entries) else "missing_after_close"
    return state


def _inspect_recovery(root: Path, records: list[tuple[Path, dict]], receipt: dict | None = None) -> dict:
    """Opening's read-only view: no lock, record migration or child creation."""
    results = []
    for path, record in records:
        if path.suffix == ".abandoned" or receipt and record["draft_receipt_sha256"] != receipt["receipt_sha256"]:
            continue
        if record["kind"] == "append_intent":
            state = _resume_append_state(root, path, record)
            remaining = _remaining_paths(root, record, records)
            result = {"intent": str(path), "state": state, "session_number": record["session_number"], "remaining_paths": remaining}
            if remaining and state == "appended":
                child = next((p for p, r in records if r["kind"] == "remaining_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and p.suffix == ".pending"), path)
                result["recovery_inputs"] = _recovery_inputs(root, child, record)
        elif record["kind"] == "remaining_intent":
            if path.suffix != ".pending" or any(r["kind"] == "write_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and r["relative_path"] == record["relative_path"] and p.suffix == ".done" for p, r in records):
                continue
            parent = next((r for p, r in records if p.with_suffix(".done") == _contained(root, root / record["parent_intent"]) and r["kind"] == "append_intent" and p.suffix != ".abandoned"), None)
            if parent is None or _append_classification(parent, final=True, root=root) != "appended":
                result = {"intent": str(path), "state": "waiting_for_append", "path": record["relative_path"]}
            else:
                actual = _file_state(_record_target(root, record))
                result = {"intent": str(path), "state": "remaining" if actual["sha256"] == record["preimage"]["sha256"] else "remaining_stale", "path": record["relative_path"], "current_sha256": actual["sha256"], "recovery_inputs": _recovery_inputs(root, path, record)}
        else:
            actual = _file_state(_record_target(root, record))
            newer = any(r["kind"] == "write_intent" and r["relative_path"] == record["relative_path"] and r["written_at"] > record["written_at"] and p.suffix != ".abandoned" for p, r in records)
            state = "superseded" if newer else "applied" if actual == record["postimage"] else "not_applied" if actual == record["preimage"] and path.suffix == ".pending" else "partial_or_conflicted"
            result = {"intent": str(path), "state": state, "path": record["relative_path"]}
        results.append(result)
    return {"state": "partial_or_conflicted" if any(r["state"] == "partial_or_conflicted" for r in results) else results[0]["state"] if len(results) == 1 else "inspected",
            "operations": results, "unfinished_operations": _unfinished(root), "warnings": [],
            "recovery_instruction": "Run closingtime resume ROOT to finish closing operations.",
            "external_retry": "fresh preconditions and approval required", "freshness_exemption": "bound interrupted operation; no new approval authorized"}


def _opening_resume(root: Path, receipt: dict | None, abandon: str | None, owner_reply: str) -> dict:
    records = _load_intents(root)
    own = lambda p, r: p.suffix == ".pending" and r["kind"] == "write_intent" and r["relative_path"] in INDEX_NAMES and r["approved_envelope"].get("skill") == "newbeginning" and not r["approved_draft"].get("continue_parent")
    if abandon and not any(str(p.relative_to(root)) == abandon and own(p, r) for p, r in records):
        raise HelperError("ESKILL", "opening only recovers its own approved index; use closingtime resume")
    warnings = []
    if any(own(p, r) and (not receipt or r["draft_receipt_sha256"] == receipt["receipt_sha256"]) for p, r in records):
        with _advisory_lock(root, "resume-opening-index") as recovered:
            for path, record in _load_intents(root):
                if not own(path, record) or receipt and record["draft_receipt_sha256"] != receipt["receipt_sha256"]:
                    continue
                if abandon:
                    if str(path.relative_to(root)) != abandon:
                        continue
                    if not owner_reply.strip():
                        raise HelperError(S.SCOPE_UNAPPROVED, "abandon needs recorded explicit owner approval")
                    _move_record(path, ".abandoned")
                    _atomic_record(path.with_name(path.name + ".abandon-note"), {"workspace_root": str(root), "intent": abandon, "owner_reply": owner_reply, "written_at": _utc_now()})
                else:
                    actual = _file_state(_record_target(root, record))
                    if actual == record["postimage"]:
                        _move_record(path, ".done")
                    elif actual == record["preimage"]:
                        _move_record(path, ".abandoned")
            if recovered:
                warnings.append("ELOCK_STALE_RECOVERED")
    result = _inspect_recovery(root, _load_intents(root), receipt)
    result["warnings"] = warnings
    return result


def resume_append(workspace_root: str | os.PathLike[str], receipt: dict | None = None,
                  abandon: str | None = None, owner_reply: str = "") -> dict:
    root = _resolve_root(workspace_root)
    _check_conflicts(root)
    journal = _contained(root, root / "private-artifacts/session-journal")
    if receipt is not None:
        _check_identity(root, receipt)
        if receipt.get("receipt_sha256") != _receipt_digest(receipt) or not any(r["draft_receipt_sha256"] == receipt["receipt_sha256"] for p, r in _load_intents(root)):
            raise HelperError("ERECOVERY", "modified receipt or no durable intent")
    if _package_skill() == "newbeginning":
        return _opening_resume(root, receipt, abandon, owner_reply)
    if not journal.is_dir():
        if abandon:
            raise HelperError("ERECOVERY", "no unfinished child to abandon")
        return {"state": "inspected", "operations": [], "unfinished_operations": [], "warnings": []}
    try:
        with _advisory_lock(root, "resume") as recovered:
            _check_conflicts(root)
            records = _load_intents(root)
            if receipt is not None:
                _check_identity(root, receipt)
                if receipt.get("receipt_sha256") != _receipt_digest(receipt):
                    raise HelperError("ERECOVERY", "modified receipt")
                if not any(r["draft_receipt_sha256"] == receipt["receipt_sha256"] for p, r in records):
                    raise HelperError("ERECOVERY", "receipt has no durable intent")
            if abandon:
                if not owner_reply.strip():
                    raise HelperError(S.SCOPE_UNAPPROVED, "abandon needs recorded explicit owner approval")
                selected = _contained(root, root / abandon)
                matches = [(p, r) for p, r in records if p == selected]
                if len(matches) != 1 or selected.suffix != ".pending" or matches[0][1]["kind"] == "append_intent":
                    raise HelperError("ERECOVERY", "only unfinished child intents can be abandoned; append receipts survive")
                _move_record(selected, ".abandoned")
                _atomic_record(selected.with_name(selected.name + ".abandon-note"), {"workspace_root": str(root), "intent": selected.relative_to(root).as_posix(), "owner_reply": owner_reply, "written_at": _utc_now()})
                return {"state": "abandoned", "intent": str(selected), "freshness_exemption": "bound interrupted operation", "warnings": ["ELOCK_STALE_RECOVERED"] if recovered else []}
            classified = {}
            # Classify appends first. A read-back append is always final, regardless
            # of unfinished index work. Legacy .json parents migrate by rename only.
            for path, record in records:
                if record["kind"] != "append_intent" or path.suffix == ".abandoned":
                    continue
                state = _resume_append_state(root, path, record)
                if path.suffix == ".json" and state != "appended":
                    raise HelperError("ERECOVERY", "legacy final entry missing or edited: " + str(path))
                if state == "appended":
                    _create_children(root, path, record, records)
                    if path.suffix != ".done":
                        _move_record(path, ".done")
                elif state == "not_appended":
                    classified[path.with_suffix(".abandoned")] = state
                    _move_record(path, ".abandoned")
                    for child, r in records:
                        if r["kind"] == "remaining_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and child.suffix == ".pending":
                            _move_record(child, ".abandoned")
            records = _load_intents(root)
            # A rollback may have finalized before retiring its unstarted child.
            for child, r in records:
                if r["kind"] == "remaining_intent" and child.suffix == ".pending":
                    abandoned = _contained(root, root / r["parent_intent"]).with_suffix(".abandoned")
                    if any(p == abandoned and parent["kind"] == "append_intent" for p, parent in records):
                        _move_record(child, ".abandoned")
            records = _load_intents(root)
            results = []
            for path, record in records:
                if (path.suffix == ".abandoned" and path not in classified) or receipt and record["draft_receipt_sha256"] != receipt["receipt_sha256"]:
                    continue
                if record["kind"] == "append_intent":
                    state = classified.get(path) or _resume_append_state(root, path, record)
                    remaining = _remaining_paths(root, record, records)
                    result = {"intent": str(path), "state": state, "session_number": record["session_number"], "remaining_paths": remaining}
                    if remaining and state == "appended":
                        child = next((p for p, r in records if r["kind"] == "remaining_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and p.suffix == ".pending"), None)
                        if child:
                            result["recovery_inputs"] = _recovery_inputs(root, child, record)
                    results.append(result)
                elif record["kind"] == "remaining_intent":
                    if path.suffix != ".pending":
                        continue
                    writes = [(p, r) for p, r in records if r["kind"] == "write_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and r["relative_path"] == record["relative_path"] and p.suffix == ".done"]
                    if writes:
                        _move_record(path, ".done")
                        continue
                    parent_path = _contained(root, root / record["parent_intent"])
                    if not any(p == parent_path and parent["kind"] == "append_intent" and p.suffix == ".done" for p, parent in records):
                        results.append({"intent": str(path), "state": "waiting_for_append", "path": record["relative_path"]})
                        continue
                    actual = _file_state(_record_target(root, record))
                    state = "remaining" if actual["sha256"] == record["preimage"]["sha256"] else "remaining_stale"
                    results.append({"intent": str(path), "state": state, "path": record["relative_path"], "current_sha256": actual["sha256"], "recovery_inputs": _recovery_inputs(root, path, record)})
                else:
                    actual = _file_state(_record_target(root, record))
                    newer = [r for p, r in records if r["kind"] == "write_intent" and r["relative_path"] == record["relative_path"] and r["written_at"] > record["written_at"] and p.suffix != ".abandoned"]
                    if newer:
                        state = "superseded"
                    elif actual == record["postimage"]:
                        state = "applied"
                        if path.suffix == ".pending":
                            path = _move_record(path, ".done")
                    elif actual == record["preimage"] and path.suffix == ".pending":
                        if record["operation"] == "stage":
                            path = _resume_stage(root, path, record, records)
                            state = "applied"
                        else:
                            state = "not_applied"
                            path = _move_record(path, ".abandoned")
                    else:
                        state = "partial_or_conflicted"
                    results.append({"intent": str(path), "state": state, "path": record["relative_path"]})
            partial = any(r["state"] == "partial_or_conflicted" for r in results)
            return {"state": "partial_or_conflicted" if partial else (results[0]["state"] if len(results) == 1 else "inspected"), "operations": results,
                    "unfinished_operations": _unfinished(root), "external_retry": "fresh preconditions and approval required",
                    "freshness_exemption": "bound interrupted operation; no new approval authorized",
                    "warnings": ["ELOCK_STALE_RECOVERED"] if recovered else []}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HelperError("ERECOVERY", f"preserve recovery evidence: {exc}") from exc


def new_envelope(workspace_root: str | os.PathLike[str], local_only: bool = False) -> dict:
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    if not skill_md.is_file():
        raise HelperError("ESKILL", "new-envelope must run from a packaged skill")
    frontmatter = skill_md.read_text().split("---", 2)[1]
    name = re.search(r"(?m)^name:\s*([^\n]+)", frontmatter)
    version = re.search(r'(?m)^\s*version:\s*["\']?([0-9.]+)', frontmatter)
    if not name or name.group(1) not in {"newbeginning", "closingtime"} or not version:
        raise HelperError("ESKILL", "unknown packaged skill identity")
    snapshot = capture_local_snapshot(workspace_root)
    try:
        with tempfile.TemporaryFile():
            temporary_available = True
    except OSError:
        temporary_available = False
    result = {"schema_version": S.SCHEMA_VERSION, "skill": name.group(1), "skill_version": version.group(1),
            "invocation_id": str(uuid.uuid4()), "invocation_started_at": snapshot["observed_at"],
            "workspace_root": snapshot["workspace_root"], "project": None, "local_snapshot": snapshot,
            "capability_profile": {"schema_version": S.SCHEMA_VERSION,
                "local": {"shell_available": True, "git_available": snapshot["git"]["available"],
                          "temporary_workspace_available": temporary_available, "parallel_read_only_available": False},
                "external": {"tasks_mcp": "unprobed", "open_brain": "unprobed"}},
            "mcp_receipts": [], "returned_rows_by_capability": {}, "mutation_scope": {"M2": [], "M3": [], "M4": []},
            "approval": {"granted": False, "scope_string": None}}
    if local_only and result["skill"] != "closingtime":
        raise HelperError("ESKILL", "local-only mode is closingtime pending resolution only")
    if local_only:
        result["evidence_mode"] = "local_only"
        result["capability_profile"]["external"] = {"tasks_mcp": "not_claimed", "open_brain": "not_claimed"}
    return result


def _parse_session_entries(text: str) -> list[dict]:
    entries, _ = S.parse_history(text)
    return [{"session_number": e["session_number"], "entry_sha256": _sha256_text(e["chunk"])} for e in entries]


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
        _adoption_fields(root, value)
        return ceiling, accepted, []
    except (OSError, json.JSONDecodeError, KeyError, ValueError, HelperError) as exc:
        return ceiling, {}, [f"EBADPOLICY:{exc}"]


def _adoption_fields(root: Path, value: dict) -> tuple[set, set]:
    historical, superseded = set(), set()
    for key, fields, result in (("historical_entries", {"session_number", "entry_sha256"}, historical),
                                 ("superseded_records", {"path", "session_number", "entry_sha256"}, superseded)):
        items = value.get(key, [])
        if not isinstance(items, list):
            raise ValueError(key + " must be a list")
        for item in items:
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError(key + " has invalid fields")
            number, digest = item["session_number"], item["entry_sha256"]
            if isinstance(number, bool) or not isinstance(number, int) or number < 1 or not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
                raise ValueError(key + " needs positive number and SHA-256")
            identity = (number, digest)
            if key == "superseded_records":
                path = item["path"]
                if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts or Path(path).parent.as_posix() != "private-artifacts/session-journal" or Path(path).suffix not in {".json", ".done"}:
                    raise ValueError("superseded path must be a relative journal record")
                _contained(root, root / path)
                identity = (path, number, digest)
            if identity in result:
                raise ValueError("duplicate " + key)
            result.add(identity)
    return historical, superseded


def adopt_history(workspace_root: str | os.PathLike[str]) -> dict:
    """Read-only proposal; the fixed writer still needs freeze, approval and CAS."""
    if _package_skill() not in {None, "closingtime"}:
        raise HelperError("ESKILL", "adopt-history belongs to closingtime")
    root = _resolve_root(workspace_root)
    _check_conflicts(root)
    if _unfinished(root):
        raise HelperError("EUNFINISHED", "finish or abandon interrupted operations before adoption")
    audit = audit_session_log(root)
    if any(error != "ENOJOURNAL" for error in audit["errors"]):
        raise HelperError("EBADPOLICY", "reconcile audit errors before adoption")
    target = _contained(root, root / POLICY_PATH)
    value = json.loads(target.read_text()) if target.exists() else {"grandfather_session_ceiling": 0}
    value["schema_version"] = "2.0"
    historical, superseded = _adoption_fields(root, value)
    entries = audit["unjournaled"]
    historical.update((e["session_number"], e["entry_sha256"]) for e in entries)
    numbers = {e["session_number"] for e in entries}
    superseded.update((Path(r["path"]).relative_to(root).as_posix(), r["session_number"], r["entry_sha256"]) for r in audit["orphan_records"] if r.get("session_number") in numbers and r.get("entry_sha256"))
    value["historical_entries"] = [{"session_number": n, "entry_sha256": h} for n, h in sorted(historical)]
    value["superseded_records"] = [{"path": p, "session_number": n, "entry_sha256": h} for p, n, h in sorted(superseded)]
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    return {"policy_text": text, "policy_sha256": _sha256_text(text), "preimage": _file_state(target)["sha256"],
            "scope_line": f"M2 replace {POLICY_PATH} (adopt {len(entries)} historical entries)"}


def audit_session_log(workspace_root: str | os.PathLike[str]) -> dict:
    """Match receipts first; expose approved historical gaps as unverified."""
    root = _resolve_root(workspace_root)
    session_path = _resolve_named_file(root, SESSION_NAMES)
    session_text = _read_text(root, session_path)
    entries = _parse_session_entries(session_text)
    journal_dir = _contained(root, root / "private-artifacts" / "session-journal")

    if not journal_dir.is_dir():
        return {
            "entries": len(entries),
            "journaled": 0,
            "grandfathered": [],
            "documented_unverified": [], "historical": [], "superseded_records": [],
            "unjournaled": entries,
            "orphan_records": [],
            "errors": ["ENOJOURNAL"] + (["EHISTORY"] if any(w in S.HISTORY_ERRORS for w in S.parse_history(session_text)[1]) else []), "pending_records": [], "pending_journal": [], "foreign_files": [], "legacy_records": [],
        }

    ceiling, exceptions, errors = _read_audit_policy(root, journal_dir)
    historical_keys, superseded_keys = set(), set()
    if not errors and (journal_dir / GRANDFATHER_POLICY).exists():
        historical_keys, superseded_keys = _adoption_fields(root, json.loads((journal_dir / GRANDFATHER_POLICY).read_text()))
    if any(w in S.HISTORY_ERRORS for w in S.parse_history(session_text)[1]):
        errors.append("EHISTORY")
    records: list[tuple[Path, dict]] = []
    orphan_records: list[dict] = []
    for path in sorted(list(journal_dir.glob("*.json")) + list(journal_dir.glob("*.done"))):
        if path.name in {GRANDFATHER_POLICY, "workspace.json"}:
            continue
        try:
            _inside(root, path)
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, HelperError) as exc:
            orphan_records.append({"path": str(path), "reason": f"unreadable:{exc}"})
            continue
        if not isinstance(record, dict):
            orphan_records.append({"path": str(path), "reason": "record_not_object"})
            continue
        if record.get("kind") in {"write_intent", "remaining_intent"}:
            if (record.get("workspace_id") and record.get("workspace_id") != _workspace_id(root)) or record.get("record_sha256") != _intent_digest(record):
                orphan_records.append({"path": str(path), "reason": "foreign_or_modified_intent"})
            continue
        if record.get("kind") == "append_intent" and ((record.get("workspace_id") and record.get("workspace_id") != _workspace_id(root)) or record.get("record_sha256") != _intent_digest(record)):
            orphan_records.append({"path": str(path), "reason": "foreign_or_modified_intent"})
            continue
        issues = S.validate_journal_record(record)
        if issues:
            orphan_records.append({"path": str(path), "reason": issues})
            continue
        records.append((path, record))

    unmatched_records = set(range(len(records)))
    journaled = 0
    grandfathered: list[dict] = []
    historical: list[dict] = []
    superseded_records: list[dict] = []
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
        elif (entry["session_number"], entry["entry_sha256"]) in historical_keys:
            historical.append(entry)
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
        destination = superseded_records if (path.relative_to(root).as_posix(), record["session_number"], record["entry_sha256"]) in superseded_keys else orphan_records
        destination.append(
            {
                "path": str(path),
                "session_number": record["session_number"],
                "entry_sha256": record["entry_sha256"],
            }
        )

    pending_records = []
    pending_journal = []
    for path in sorted(journal_dir.glob("*.pending")):
        try:
            _inside(root, path)
            r = json.loads(path.read_text())
            pending_records.append({"path": str(path), "kind": r.get("kind")})
            if r.get("kind") == "append_intent" and (not r.get("workspace_id") or r.get("workspace_id") == _workspace_id(root)) and r.get("record_sha256") == _intent_digest(r):
                for entry in unjournaled[:]:
                    if entry["session_number"] == r.get("session_number") and entry["entry_sha256"] == r.get("entry_sha256"):
                        pending_journal.append(entry); unjournaled.remove(entry)
        except (OSError, ValueError, HelperError):
            errors.append("ERECOVERY:" + str(path))
    if _sync_conflicts(root):
        errors.append(S.SYNC_CONFLICT)
    known_suffixes = {".json", ".done", ".pending", ".abandoned", ".abandon-note"}
    foreign_files = [str(p) for p in journal_dir.iterdir() if p.is_file() and p.name != ".lock" and p.suffix not in known_suffixes | {".approval", ".draft"}]
    legacy_records = [str(p) for p, r in records if r.get("kind") != "append_intent"]
    return {
        "pending_records": pending_records, "pending_journal": pending_journal,
        "foreign_files": foreign_files, "legacy_records": legacy_records,
        "entries": len(entries),
        "journaled": journaled,
        "grandfathered": grandfathered,
        "documented_unverified": documented_unverified, "historical": historical, "superseded_records": superseded_records,
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


# Constructors and lineage operations deliberately retain all normal validators.
def _reject_truncated(raw: object) -> None:
    if isinstance(raw, dict):
        if any(raw.get(key) for key in ('truncated', 'isTruncated', 'is_truncated', 'has_more', 'hasMore')):
            raise HelperError('EBADROWS', 'explicitly truncated service result')
        for value in raw.values():
            _reject_truncated(value)
    elif isinstance(raw, list):
        for value in raw:
            _reject_truncated(value)
    elif isinstance(raw, str) and re.search(r'(?im)\[(?:output |content )?truncated[^\]\n]*\]|^.*\b(?:tokens?|characters?|lines?) truncated\b|^\s*(?:output |content )?truncated\s*[:=]\s*true\s*$', raw):
        raise HelperError('EBADROWS', 'explicit text truncation marker')


def _service_json(text: str) -> object:
    try:
        return json.loads(text)
    except (ValueError, UnicodeError) as exc:
        raise HelperError('EBADROWS', 'service result/operation is not valid JSON') from exc


def _tool_rows(raw: object) -> list[dict]:
    _reject_truncated(raw)
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode('utf-8')
        except UnicodeError as exc:
            raise HelperError('EBADROWS', 'service result must be UTF-8') from exc
    if isinstance(raw, str):
        return _tool_rows(_service_json(raw))
    if isinstance(raw, dict):
        if raw.get('isError') or raw.get('error'):
            raise HelperError('EBADROWS', 'tool reported an error')
        if 'structuredContent' in raw:
            return _tool_rows(raw['structuredContent'])
        for key in ('rows', 'results', 'data'):
            if key in raw:
                return _tool_rows(raw[key])
        content = raw.get('content')
        if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) and content[0].get('type') == 'text':
            return _tool_rows(_service_json(content[0]['text']))
    if isinstance(raw, list) and all(isinstance(row, dict) for row in raw):
        return raw
    raise HelperError('EBADROWS', 'expected row list, rows/results/data, structuredContent, or one JSON text block')


def _open_brain_text(raw: object) -> str | None:
    _reject_truncated(raw)
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode('utf-8')
        except UnicodeError as exc:
            raise HelperError('EBADROWS', 'service result must be UTF-8') from exc
    if isinstance(raw, str):
        # Retain compatibility with earlier JSON row receipts.
        if raw.lstrip().startswith(('{', '[')):
            return _open_brain_text(_service_json(raw))
        return raw
    if isinstance(raw, dict):
        if raw.get('isError') or raw.get('error'):
            raise HelperError('EBADROWS', 'tool reported an error')
        content = raw.get('content')
        if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) and content[0].get('type') == 'text':
            return _open_brain_text(content[0].get('text'))
    return None


def _capture_succeeded(text: object) -> bool:
    return isinstance(text, str) and bool(re.fullmatch(r'Captured as [^\r\n]+(?:\r?\n)?', text))


def _open_brain_rows(text: str, operation: str) -> tuple[list[dict], str, dict | None]:
    if text.startswith(('Failed to capture:', 'Search error:', 'Error:')):
        outcome = 'failed' if text.startswith('Failed to capture:') else 'error'
        raise HelperError('EBADROWS', 'Open Brain returned a non-working result',
                          outcome=outcome, result_sha256=_sha256_text(text))
    if re.fullmatch(r'No thoughts found(?: matching "[^\r\n]*")?\.(?:\r?\n)?', text):
        return [], 'no_results', None
    found = re.match(r'(?:Found ([0-9]+) thought\(s\)|([0-9]+) recent thought\(s\)):\r?\n\r?\n', text)
    if found:
        count = int(found[1] or found[2])
        body = text[found.end():]
        starts = list(re.finditer(r'(?m)^--- Result ([0-9]+) \([0-9]+(?:\.[0-9]+)?% match\) ---\r?$', body))
        if found[2]:
            starts = list(re.finditer(r'(?m)^([0-9]+)\. \[[^\r\n]+\] \([^\r\n]+\)\r?$', body))
        if count < 1 or len(starts) != count or starts[0].start() != 0 or [int(m[1]) for m in starts] != list(range(1, count+1)):
            raise HelperError('EBADROWS', 'Open Brain result count/blocks differ')
        rows = [{'text': body[m.start():starts[i+1].start() if i+1 < count else len(body)]}
                for i, m in enumerate(starts)]
        if found[1] and any(not re.search(r'(?m)^Captured: .+', row['text']) or not re.search(r'(?m)^Type: .+', row['text']) for row in rows):
            raise HelperError('EBADROWS', 'incomplete Open Brain thought block')
        return rows, 'found', None
    if _capture_succeeded(text):
        call = _service_json(operation)
        args = call.get('arguments') if isinstance(call, dict) else None
        content = args.get('content') if isinstance(args, dict) else None
        if (not isinstance(call, dict) or (call.get('tool') or call.get('name')) != 'capture_thought'
                or not isinstance(content, str) or not content.strip()):
            raise HelperError('EBADROWS', 'capture success requires exact capture_thought operation and content argument')
        capture = {'status': 'success', 'payload_sha256': _sha256_text(content),
                   'result_text': text, 'result_sha256': _sha256_text(text),
                   'operation_fingerprint': S.fingerprint_operation(operation)}
        return [{'text': text}], 'captured', capture
    # Statistics require the named operation and the documented population header.
    if text.strip() and operation.lstrip().startswith('{'):
        call = _service_json(operation)
        if (isinstance(call, dict) and (call.get('tool') or call.get('name')) == 'thought_stats'
                and re.match(r'Total thoughts: [0-9]+\r?\nDate range: [^\r\n]+\r?\n\r?\nTypes:', text)):
            return [{'text': text}], 'stats', None
    raise HelperError('EBADROWS', 'unrecognized Open Brain result format')


def service_receipt(capability: str, raw: object, operation: str, identity: dict,
                    tool_result_id: str, observed_at: str | None = None) -> dict:
    if capability not in {'tasks_mcp', 'open_brain'} or not operation.strip() or not identity or not tool_result_id:
        raise HelperError('EINPUT', 'capability, exact operation, observed identity and tool result id required')
    _reject_truncated(raw)
    text = _open_brain_text(raw) if capability == 'open_brain' else None
    capture = None
    if text is not None:
        _reject_truncated(text)
        rows, outcome, capture = _open_brain_rows(text, operation)
    else:
        rows = _tool_rows(raw)
    receipt = {'schema_version': S.SCHEMA_VERSION, 'capability': capability, 'identity': identity,
               'tool_result_id': tool_result_id, 'observed_at': observed_at or _utc_now(),
               'operation_fingerprint': S.fingerprint_operation(operation), 'row_count': len(rows),
               'row_fingerprint': S.canonical_row_fingerprint(rows), 'status': 'current'}
    if text is not None:
        receipt.update(result_sha256=_sha256_text(text), outcome=outcome)
    packet = {'receipt': receipt, 'returned_rows_by_capability': {capability: rows}}
    if capture is not None:
        packet['capture_result'] = capture
    return packet


def attach_evidence(envelope: dict, packet: dict) -> dict:
    result = copy.deepcopy(envelope)
    receipt = packet['receipt']; cap = receipt['capability']
    rows = packet['returned_rows_by_capability'][cap]
    failures = S.validate_receipt(receipt, rows, result['invocation_started_at'])
    if failures:
        raise HelperError('EINVALIDENVELOPE', json.dumps(failures))
    result['mcp_receipts'] = [r for r in result.get('mcp_receipts', []) if r.get('capability') != cap] + [receipt]
    result.setdefault('returned_rows_by_capability', {})[cap] = rows
    profile = result['capability_profile']
    profile['external'][cap] = 'working' if receipt['status'] == 'current' else receipt['capability_state']
    profile.setdefault('external_detail', {})[cap] = receipt['identity']
    if cap == 'tasks_mcp':
        intended = result.get('project')
        project = 'portfolio' if receipt['identity'].get('scope') == 'portfolio' else receipt['identity'].get('project')
        if not intended or project != intended or project != 'portfolio' and any(r.get('project') != intended for r in rows):
            raise HelperError('FOREIGN_ROWS', 'set intended project before attaching matching task evidence')
    if envelope.get('evidence_mode') == 'local_only':
        raise HelperError('LOCAL_ONLY', 'local transition makes no current service claims')
    return result


def new_invocation(workspace_root: str, local_only: bool = False) -> dict:
    envelope = new_envelope(workspace_root, local_only)
    scratch = Path(tempfile.mkdtemp(prefix='session-' + envelope['invocation_id'] + '-')).resolve()
    return {'envelope': envelope, 'scratch_dir': str(scratch)}


def bind_approval(envelope: dict, receipt: dict) -> dict:
    result = copy.deepcopy(envelope)
    result['mutation_scope'] = {cls: [({'path': op['path'], 'operation': op['operation']} if cls == 'M2' else op['operation'])
                                    for op in receipt['scope_operations'] if op['class'] == cls] for cls in ('M2','M3','M4')}
    result['approval'] = {'granted': True, 'scope_string': receipt['scope_string']}
    _check_approved_draft(result, None, receipt)
    return result


def _approval_selection(receipt: dict, owner_reply: str) -> dict:
    # Intentional small grammar: ambiguous or corrective language never grants authority.
    match = re.fullmatch(r'\s*(?:approve[d]?|yes|aprobado|s[ií])(?: cleanup)?(?:[.!])?\s*(?:,?\s*(?:skip|except)\s+(.+?))?\s*[.!]?\s*', owner_reply, re.I)
    if not match:
        raise HelperError(S.SCOPE_UNAPPROVED, 'explicit approval or approve, skip/except <displayed operation> required')
    target = match[1]
    if not target:
        return receipt
    target = target.strip().rstrip('.!').lower()
    ops = receipt['scope_operations']
    if target in {'learning','learnings'}:
        excluded = [op for op in ops if op.get('path') == 'pending_learnings.md' and op['operation'] in {'stage','resolve'}]
    else:
        excluded = [op for op in ops if target == (op['class'] + ' ' + op['operation'] + (' ' + op['path'] if 'path' in op else '')).lower()]
    if not excluded or target not in {'learning','learnings'} and len(excluded) != 1:
        raise HelperError(S.SCOPE_UNAPPROVED, 'exclusion must identify displayed operations unambiguously')
    selected = [op for op in ops if op not in excluded]
    if not selected:
        raise HelperError(S.SCOPE_UNAPPROVED, 'no remainder')
    result = dict(receipt, scope_operations=selected, parent_frozen_sha256=receipt['receipt_sha256'])
    number = re.search(r'\(Session #([0-9]+)\)', receipt['scope_lines'])
    result['scope_lines'] = _scope_text(selected, session_number=int(number[1]) if number else None)
    result['scope_sha256'] = _sha256_text(result['scope_lines'])
    result['receipt_sha256'] = _receipt_digest(result)
    return result


def _refresh_binding(envelope: dict) -> dict:
    snap = envelope['local_snapshot']
    return {'project': envelope.get('project'), 'skill': envelope['skill'],
            'sources': {key: {f: (snap.get(key) or {}).get(f) for f in ('path','present','sha256','tail_sha256','latest_session_number')}
                        for key in ('session','index','decisions_archive','audit_policy')},
            'task_expected_versions': envelope.get('task_expected_versions', {}),
            # Conservative: every task row stays identical, including version and identity.
            'task_rows': envelope.get('returned_rows_by_capability', {}).get('tasks_mcp', []),
            'identities': {r['capability']: r.get('identity') for r in envelope.get('mcp_receipts', [])},
            'external': envelope['capability_profile']['external'],
            'source_hashes_used_for_draft': envelope.get('source_hashes_used_for_draft', {})}


def _check_carry_age(origin: str) -> None:
    stamp = _parse_utc(origin)
    now = dt.datetime.now(dt.timezone.utc)
    if stamp is None or stamp > now:
        raise HelperError('ECHRONOLOGY', 'invalid original approval/freeze time')
    if now - stamp > dt.timedelta(hours=24):
        raise HelperError('ESTALEAPPROVAL', 'original approval/freeze is older than 24 hours; obtain new approval')


def refresh_approval(parent: dict, envelope: dict, entry_text: str | None = None,
                     index_text: str | None = None, owner_reply: str = '') -> dict:
    root = _workspace_binding(envelope)
    if parent.get('receipt_sha256') != _receipt_digest(parent) or not parent.get('refresh_binding'):
        raise HelperError('EDRAFTRECEIPT', 'refresh requires an intact witnessed freeze')
    _check_identity(root, parent)
    if not S._same_root(parent.get('workspace_root'), str(root)) or parent.get('invocation_id') == envelope.get('invocation_id'):
        raise HelperError('EDRAFTMISMATCH', 'refresh needs a fresh invocation at the same destination')
    path = _approval_path(root, parent['invocation_id'])
    witness = path if parent.get('approved_at') else path.with_suffix('.draft')
    if not witness.exists():
        raise HelperError('EDRAFTRECEIPT', 'missing durable parent witness')
    if not parent.get('approved_at') and path.exists():
        raise HelperError('EINVOCATIONUSED', 'freeze already approved or superseded; use its approval')
    stored = json.loads(witness.read_text())
    if stored.get('receipt_sha256') != parent['receipt_sha256'] or stored.get('superseded_by'):
        raise HelperError('EINVOCATIONUSED', 'parent changed or superseded')
    if any(r.get('draft_receipt_sha256') == parent['receipt_sha256'] for _, r in _load_intents(root)):
        raise HelperError('EINVOCATIONUSED', 'started chains use resume, not refresh')
    origin = parent.get('carry_origin_at') or parent.get('approved_at') or parent.get('drafted_at')
    _check_carry_age(origin)
    if not parent.get('approved_at'):
        parent_selected = _approval_selection(parent, owner_reply)
    else:
        parent_selected = parent
    captured = _parse_utc(envelope['local_snapshot'].get('captured_at'))
    if not captured or captured <= _parse_utc(parent['snapshot_captured_at']):
        raise HelperError('ECHRONOLOGY', 'refresh cannot copy or backdate capture time')
    if _refresh_binding(envelope) != parent['refresh_binding']:
        raise HelperError('EDRAFTMISMATCH', 'material sources, tasks, identities or intent changed')
    fresh = freeze_draft(envelope, entry_text, index_text)
    keys = ('entry_sha256','index_draft_sha256','scope_operations','local_payload_hashes','continue_parent','observed_tail_sha256')
    if any(fresh.get(key) != parent_selected.get(key) for key in keys):
        raise HelperError('EDRAFTMISMATCH', 'refresh changed approved content or operations')
    # Stage-only may tolerate drift; a scoped resolution keeps its pending preimage strict.
    resolve_paths = {op['path'] for op in fresh['scope_operations'] if op['operation'] == 'resolve'}
    stage_paths = {op['path'] for op in fresh['scope_operations'] if op['operation'] == 'stage'} - resolve_paths
    scoped_paths = {op['path'] for op in fresh['scope_operations'] if op['class'] == 'M2'}
    if any(value != fresh['m2_preimages'].get(key) and key not in stage_paths for key, value in parent['m2_preimages'].items() if key in scoped_paths):
        raise HelperError('EDRAFTMISMATCH', 'non-stage preimage changed')
    now = _utc_now()
    approved = dict(fresh, refresh_binding=parent['refresh_binding'], parent_approval_sha256=parent['receipt_sha256'],
                    carry_origin_at=origin, owner_reply=parent.get('owner_reply') or owner_reply,
                    approved_at=now, scope_string=fresh['scope_lines'])
    approved['receipt_sha256'] = _receipt_digest(approved)
    with _advisory_lock(root, envelope['invocation_id']):
        stored = json.loads(witness.read_text())
        if stored.get('receipt_sha256') != parent['receipt_sha256'] or stored.get('superseded_by'):
            raise HelperError('EINVOCATIONUSED', 'parent already superseded')
        if any(r.get('draft_receipt_sha256') == parent['receipt_sha256'] for _, r in _load_intents(root)):
            raise HelperError('EINVOCATIONUSED', 'started chains use resume, not refresh')
        target = _approval_path(root, envelope['invocation_id'])
        if target.exists():
            raise HelperError('EINVOCATIONUSED', 'fresh invocation already approved')
        # Invalidate parent first. An interruption can lose authority, never duplicate it.
        _atomic_record(path, dict(stored, receipt_sha256='superseded', superseded_by=approved['receipt_sha256']))
        if witness != path:
            _atomic_record(witness, dict(stored, superseded_by=approved['receipt_sha256']))
        _atomic_record(target, {'workspace_root':str(root), 'receipt_sha256':approved['receipt_sha256'], 'approved_draft':approved})
    return approved


def resolved_pending_payload(current: bytes, dispositions: list[dict]) -> bytes | None:
    """Remove only exact disposed blocks. Unknown content remains byte-for-byte."""
    try:
        text = current.decode('utf-8')
    except UnicodeError as exc:
        raise HelperError('ERESOLUTION', 'pending file must be UTF-8') from exc
    starts = [m.start() for m in re.finditer(r'(?m)^## Candidate [0-9]+[^\S\n]*\r?$', text)]
    blocks = [text[start:starts[i+1] if i+1 < len(starts) else len(text)] for i,start in enumerate(starts)]
    by_hash = {}
    for d in dispositions:
        key = d.get('block_sha256')
        if key in by_hash or not isinstance(d.get('owner_reply'),str) or not d['owner_reply'].strip() or d.get('disposition') not in {'discarded','saved'}:
            raise HelperError('ERESOLUTION', 'unique exact block hash and non-empty disposition words required')
        if d['disposition'] == 'saved':
            approval, capture = d.get('capture_approval') or {}, d.get('capture_result') or {}
            block = next((b for b in pending_blocks(text) if b['block_sha256'] == key), None)
            canonical = block['capture_wording_sha256'] if block else None
            payload = approval.get('payload_sha256')
            edited = approval.get('wording')
            edited_bound = (isinstance(edited, str) and bool(edited.strip())
                            and approval.get('block_sha256') == key and payload == _sha256_text(edited))
            if (not block or not isinstance(approval.get('owner_reply'), str) or not approval['owner_reply'].strip()
                or not payload or not ((edited is None and payload == canonical) or edited_bound)
                or approval.get('block_sha256') != key
                or capture.get('payload_sha256') != payload or capture.get('status') != 'success'
                or not _capture_succeeded(capture.get('result_text'))
                or capture.get('result_sha256') != _sha256_text(capture['result_text'])):
                raise HelperError('ERESOLUTION', 'saved requires block-bound approved wording and successful matching capture')
        by_hash[key] = d
    hashes = [_sha256_text(block) for block in blocks]
    if any(hashes.count(key) != 1 for key in by_hash):
        raise HelperError('ERESOLUTION', 'disposition must identify one unique current block')
    if set(by_hash) - set(hashes):
        raise HelperError('ERESOLUTION', 'disposition is not for a current exact block')
    kept = text[:starts[0]] if starts else text
    for block in blocks:
        fields = set(re.findall(r'(?m)^\*\*([^*]+):\*\*', block))
        unknown = fields - {'Type','Insight','Connection','Connects to','Status'}
        headings = re.findall(r'(?m)^#{1,6} .*', block)
        unknown_lines = any(line.strip() and not re.fullmatch(r'## Candidate [0-9]+[ \t]*|\*\*(?:Type|Insight|Connection|Connects to|Status):\*\*.*', line) for line in block.splitlines())
        if _sha256_text(block) not in by_hash or unknown or unknown_lines or len(headings) != 1:
            kept += block
    return kept.encode('utf-8') if kept.strip() else None


def resolve_pending(envelope: dict, receipt: dict, dispositions: list[dict], expect: str) -> dict:
    return write_approved_file(envelope, receipt, 'pending_learnings.md', operation='resolve', expect=expect, dispositions=dispositions)


def pending_blocks(text: str) -> list[dict]:
    starts = [m.start() for m in re.finditer(r'(?m)^## Candidate [0-9]+[^\S\n]*\r?$', text)]
    return [{'block_sha256': _sha256_text(block), 'text': block,
             'capture_wording': _capture_wording(block),
             'capture_wording_sha256': _sha256_text(_capture_wording(block)) if _capture_wording(block) is not None else None}
            for i,start in enumerate(starts)
            for block in [text[start:starts[i+1] if i+1 < len(starts) else len(text)]]]


def _capture_wording(block: str) -> str | None:
    """Canonical capture is one nonempty Insight field, stripped at its edges.

    Multiple fields or multiline legacy content are ambiguous: keep the block;
    no normalization or guessed wording is an approval.
    """
    insights = re.findall(r'(?m)^\*\*Insight:\*\*([^\r\n]*)\r?$', block)
    unknown = any(line.strip() and not re.fullmatch(
        r'## Candidate [0-9]+[ \t]*|\*\*[^*]+:\*\*.*', line) for line in block.splitlines())
    return insights[0].strip() if len(insights) == 1 and insights[0].strip() and not unknown else None
