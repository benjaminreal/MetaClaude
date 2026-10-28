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
INSTRUCTION_NAMES = ("AGENTS.md", "CLAUDE.md")
GIT_CHANGED_PATHS_CAP = 20
SYNC_PATTERNS = ("*conflicted copy*", "*.sync-conflict-*", "*(case conflict*")
ARCHIVE_NAMES = ("project_decisions_archive.md",)

SESSION_HEADER_RE = re.compile(
    r"^### Session #(?P<number>\d+)[ \t]*\|[ \t]*(?P<date>\d{4}-\d{2}-\d{2})[ \t]*\|[ \t]*[^\s|][^\n|]*$",
    re.MULTILINE,
)
ENTRY_RE = re.compile(
    r"(?ms)(?:\A|\n)(---\n\n### Session #(?P<number>\d+).*?)"
    r"(?=\n---\n\n### Session #|\Z)"
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
    matches = list(SESSION_HEADER_RE.finditer(text))
    if not matches:
        return "", 0
    selected = matches[-count:]
    start = selected[0].start()
    tail = text[start:].strip()
    latest = max(int(match.group("number")) for match in matches)
    return tail, latest


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
            folded = child.name.casefold()
            generic = any(fnmatch.fnmatch(folded, pattern) for pattern in SYNC_PATTERNS)
            specific = any(re.fullmatch(re.escape(stem) + r"(?: \d+| copy| \(\d+\))\.md", folded) for stem in stems)
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
        headers = list(SESSION_HEADER_RE.finditer(session_text))
        if "### Session" in session_text and not headers:
            warnings.append("session_unparseable")
        if any(not SESSION_HEADER_RE.fullmatch(line) for line in session_text.splitlines() if line.startswith("### Session")):
            warnings.append("session_header_malformed")
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
    out = json.loads(json.dumps(projection))
    if full_bytes <= cap:
        return out, full_bytes, full_bytes
    out["truncated"] = True
    # Drop whole older entries first. Keep the latest header at the start.
    while len(_canonical_json(out)) > cap:
        headers = list(SESSION_HEADER_RE.finditer(out["session"]["tail"]))
        if len(headers) < 2:
            break
        out["session"]["tail"] = out["session"]["tail"][headers[1].start():]
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
        return json.loads(path.read_text()).get("kind") in {"append_intent", "write_intent"}
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
                        if p.suffix == ".pending" or (p.suffix == ".json" and p.name != GRANDFATHER_POLICY and _is_intent_file(p))) if journal.is_dir() else []
    return {
        "index": {**file_observation(index_path, index_text), "alternates": index_alts},
        "session": {
            **file_observation(session_path, session_text), "alternates": session_alts,
            "tail_sha256": _sha256_text(session_tail),
            "latest_session_number": latest_number,
        },
        "pending_learnings": {**file_observation(pending_path, _read_text(root, pending_path)), "alternates": pending_alts},
        "decisions_archive": {**file_observation(archive_path, _read_text(root, archive_path)), "alternates": archive_alts},
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
    for match in ENTRY_RE.finditer(text):
        if int(match.group("number")) == session_number:
            return match.group(1).rstrip() + "\n"
    return None


def _journal_dir(root: Path) -> Path:
    path = _contained(root, root / "private-artifacts/session-journal")
    path.mkdir(parents=True, exist_ok=True)
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


def _workspace_binding(envelope: dict) -> Path:
    root = _resolve_root(envelope.get("workspace_root", ""))
    snapshot = envelope.get("local_snapshot") or {}
    if snapshot.get("workspace_root") != str(root):
        raise HelperError("EWORKSPACEMISMATCH", "snapshot must belong to resolved workspace")
    return root


def _scope_operations(envelope: dict) -> list[dict]:
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
                pending = (snap.get("pending_learnings") or {}).get("path") or PENDING_NAMES[0]
                default = ["append"] if name == session else (["replace", "delete"] if name == pending else ["replace"])
                kinds = [item["operation"]] if isinstance(item, dict) and "operation" in item else default
                for kind in kinds:
                    if kind not in {"append", "replace", "delete"}:
                        raise HelperError("EINPUT", "unknown local operation kind")
                    result.append({"class": cls, "operation": kind, "path": name})
            else:
                if not isinstance(item, str) or not item.strip() or "\n" in item or "\r" in item:
                    raise HelperError("EINPUT", "external/repository scope needs exact operation identifier")
                result.append({"class": cls, "operation": item})
    return sorted(result, key=lambda v: _canonical_json(v))


def _scope_text(operations: list[dict]) -> str:
    return "\n".join(op["class"] + " " + op["operation"] + (" " + op["path"] if "path" in op else "") +
                     (" (+ journal receipt under private-artifacts/session-journal/)" if op["operation"] == "append" else "") for op in operations)


def _observed_targets(envelope: dict) -> dict:
    snap = envelope["local_snapshot"]
    return {field: ((snap.get(field) or {}).get("path") or names[0]) for field, names in
            (("index", INDEX_NAMES), ("pending_learnings", PENDING_NAMES), ("decisions_archive", ARCHIVE_NAMES))}


def _unfinished(root: Path) -> list[str]:
    journal = _contained(root, root / "private-artifacts/session-journal")
    if not journal.is_dir():
        return []
    return [str(p.relative_to(root)) for p in sorted(journal.iterdir()) if p.suffix == ".pending" or
            (p.suffix == ".json" and p.name != GRANDFATHER_POLICY and _is_intent_file(p))]


def freeze_draft(envelope: dict, entry_text: str | None = None, index_text: str | None = None) -> dict:
    if not envelope:
        raise HelperError(S.MISSING_RECEIPT, "envelope absent")
    verdict = S.validate_envelope(envelope, envelope.get("returned_rows_by_capability") or {})
    codes = {f["code"] for f in verdict["failures"]} - {S.SCOPE_UNAPPROVED}
    if codes and S.WORKSPACE_MISMATCH not in codes:
        raise HelperError("EINVALIDENVELOPE", ",".join(sorted(codes)))
    root = _workspace_binding(envelope)
    if _unfinished(root):
        raise HelperError("EUNFINISHED", "run resume: " + ", ".join(_unfinished(root)))
    operations = _scope_operations(envelope)
    targets = _observed_targets(envelope)
    if envelope.get("skill") == "newbeginning" and any(op["operation"] == "append" for op in operations):
        raise HelperError("ESKILL", "newbeginning never appends")
    if targets["index"] in [op.get("path") for op in operations] and index_text is None:
        raise HelperError("EDRAFTMISMATCH", "index in scope requires exact index draft")
    archive = targets["decisions_archive"]
    if any(op.get("path") == archive and op["operation"] == "replace" for op in operations):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", (envelope.get("local_payload_hashes") or {}).get(archive, "")):
            raise HelperError("EDRAFTMISMATCH", "archive scope requires local_payload_hashes binding")
    if entry_text is not None:
        _render_entry(entry_text, (envelope["local_snapshot"].get("session") or {}).get("latest_session_number", 0) + 1)
    elif any(op["operation"] == "append" for op in operations):
        raise HelperError("EENTRYFORMAT", "append scope requires entry")
    preimages = {}
    for field, name in targets.items():
        obs = envelope["local_snapshot"].get(field) or {}
        preimages[name] = obs.get("sha256") if obs.get("present") else "absent"
    receipt = {
        "schema_version": S.SCHEMA_VERSION, "kind": DRAFT_RECEIPT_KIND, "recovery_version": 2,
        "invocation_id": envelope.get("invocation_id"), "workspace_root": str(root),
        "snapshot_sha256": _sha256_bytes(_canonical_json(envelope["local_snapshot"])),
        "snapshot_observed_at": envelope["local_snapshot"].get("observed_at"),
        "observed_tail_sha256": (envelope["local_snapshot"].get("session") or {}).get("tail_sha256"),
        "entry_sha256": _sha256_text(entry_text) if entry_text is not None else None,
        "entry_words": count_words(entry_text or ""),
        "index_draft_sha256": _sha256_text(index_text) if index_text is not None else None,
        "index_draft": index_text,
        "m2_preimages": preimages, "scope_operations": operations,
        "local_payload_hashes": envelope.get("local_payload_hashes") or {},
        "scope_lines": _scope_text(operations), "scope_sha256": _sha256_text(_scope_text(operations)),
        "drafted_at": _utc_now(), "approved_at": None, "scope_string": None, "owner_reply": None,
    }
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    return receipt


def approve_draft(receipt: dict, scope_string: str, owner_reply: str = "") -> dict:
    if not isinstance(receipt, dict) or receipt.get("kind") != DRAFT_RECEIPT_KIND or receipt.get("recovery_version") != 2:
        raise HelperError("EDRAFTRECEIPT", "not a current draft receipt; freeze again")
    if receipt.get("receipt_sha256") != _receipt_digest(receipt) or receipt.get("approved_at"):
        raise HelperError("EDRAFTRECEIPT", "modified or already approved receipt")
    if not scope_string or scope_string != receipt.get("scope_lines"):
        raise HelperError(S.SCOPE_UNAPPROVED, "approval must equal exact rendered scope; exclusions require a new freeze")
    now = dt.datetime.now(dt.timezone.utc)
    drafted = _parse_utc(receipt.get("drafted_at"))
    if drafted is None or drafted >= now:
        raise HelperError("ECHRONOLOGY", "draft time must precede helper approval time")
    approved = dict(receipt, approved_at=now.isoformat().replace("+00:00", "Z"), scope_string=scope_string, owner_reply=owner_reply)
    approved["receipt_sha256"] = _receipt_digest(approved)
    return approved


def _check_approved_draft(envelope: dict, entry_text: str | None, receipt: dict | None) -> None:
    if not isinstance(receipt, dict) or receipt.get("kind") != DRAFT_RECEIPT_KIND or receipt.get("recovery_version") != 2:
        raise HelperError("EDRAFTRECEIPT", "requires current approved draft receipt")
    if receipt.get("receipt_sha256") != _receipt_digest(receipt) or not receipt.get("approved_at"):
        raise HelperError("EDRAFTRECEIPT", "modified or unapproved draft receipt")
    scope = _scope_text(_scope_operations(envelope))
    if receipt.get("invocation_id") != envelope.get("invocation_id") or not S._same_root(receipt.get("workspace_root"), envelope.get("workspace_root")) or receipt.get("snapshot_sha256") != _sha256_bytes(_canonical_json(envelope.get("local_snapshot"))) or receipt.get("scope_lines") != scope or receipt.get("scope_sha256") != _sha256_text(scope):
        raise HelperError("EDRAFTMISMATCH", "invocation, root, snapshot or scope differs from frozen draft")
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
    result = S.validate_envelope(envelope, envelope.get("returned_rows_by_capability") or {})
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
        if path.name == GRANDFATHER_POLICY or path.is_dir():
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
        if record.get("kind") not in {"append_intent", "write_intent"}:
            if path.suffix != ".json" or S.validate_journal_record(record):
                raise HelperError("ERECOVERY", f"foreign record: {path}")
            continue  # legacy journals are audit-only, never rewritten
        if record.get("workspace_root") != str(root) or record.get("record_sha256") != _intent_digest(record):
            raise HelperError("ERECOVERY", f"wrong root or modified intent: {path}")
        required = {"workspace_root", "target", "preimage", "draft_receipt_sha256", "invocation_id", "approved_scope", "written_at", "approved_envelope", "approved_draft"}
        required |= ({"append_bytes", "append_length", "append_sha256", "session_number", "entry_sha256", "m2_operations"} if record["kind"] == "append_intent" else {"relative_path", "operation", "postimage", "transition_id"})
        if not required <= record.keys() or not isinstance(record["target"], str):
            raise HelperError("ERECOVERY", f"incomplete intent: {path}")
        draft = record["approved_draft"]
        saved_envelope = record["approved_envelope"]
        if not isinstance(draft, dict) or not isinstance(saved_envelope, dict) or draft.get("receipt_sha256") != record["draft_receipt_sha256"] or draft.get("receipt_sha256") != _receipt_digest(draft) or not S._same_root(saved_envelope.get("workspace_root"), str(root)):
            raise HelperError("ERECOVERY", f"recovery inputs differ from intent: {path}")
        for state in [record["preimage"]] + ([record["postimage"]] if record["kind"] == "write_intent" else []):
            if not isinstance(state, dict) or set(state) != {"exists", "length", "sha256"} or not isinstance(state["exists"], bool) or type(state["length"]) is not int or state["length"] < 0 or not isinstance(state["sha256"], str):
                raise HelperError("ERECOVERY", f"invalid byte state: {path}")
        target = _contained(root, Path(record.get("target", "")))
        if str(target) != record.get("target"):
            raise HelperError("ERECOVERY", "noncanonical target")
        records.append((path, record))
    keys = [(r["draft_receipt_sha256"], r["kind"], r.get("transition_id", "append")) for p, r in records if p.suffix != ".abandoned"]
    allocations = [(r["target"], r["session_number"]) for p, r in records if r["kind"] == "append_intent" and p.suffix != ".abandoned"]
    if len(keys) != len(set(keys)) or len(allocations) != len(set(allocations)):
        raise HelperError("ERECOVERY", "multiple conflicting intent matches")
    return records


def _intent_digest(record: dict) -> str:
    return _sha256_bytes(_canonical_json({k: v for k, v in record.items() if k != "record_sha256"}))


def _persist_intent(root: Path, record: dict) -> Path:
    record["record_sha256"] = _intent_digest(record)
    path = _journal_dir(root) / (uuid.uuid4().hex + ".pending")
    _atomic_record(path, record)
    return path


def _append_classification(record: dict, final: bool = False) -> str:
    path = Path(record["target"])
    if _state_matches(path, record["preimage"]):
        return "not_appended"
    data = path.read_bytes() if path.exists() else b""
    pre = record["preimage"]
    appended = base64.b64decode(record["append_bytes"], validate=True)
    expected_length = pre["length"] + len(appended)
    if len(appended) != record["append_length"] or _sha256_bytes(appended) != record["append_sha256"]:
        raise HelperError("ERECOVERY", "intent append hash/length mismatch")
    prefix_ok = (not pre["exists"] and pre["length"] == 0) or _sha256_bytes(data[:pre["length"]]) == pre["sha256"]
    if prefix_ok and data[pre["length"]:expected_length] == appended and (len(data) == expected_length or (final and len(data) > expected_length)):
        return "appended"
    return "partial_or_conflicted"


def _append_bytes(path: Path, data: bytes) -> None:
    with path.open("ab") as stream:
        if stream.write(data) != len(data):
            raise OSError("short append")
        stream.flush()
        os.fsync(stream.fileno())


def _conditional_rollback(record: dict, pending: Path) -> bool:
    if _append_classification(record) != "appended":
        return False
    path = Path(record["target"])
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
    return True


def _remaining_paths(root: Path, record: dict, records: list[tuple[Path, dict]]) -> list[dict]:
    remaining = []
    for name, operation in record.get("m2_operations", {}).items():
        transitions = [(p, r) for p, r in records if r["kind"] == "write_intent" and r["draft_receipt_sha256"] == record["draft_receipt_sha256"] and r["relative_path"] == name and p.suffix != ".abandoned"]
        if transitions:
            # Later approved closes may legitimately revise the same file.
            lineage = [(p, r) for p, r in records if r["kind"] == "write_intent" and r["relative_path"] == name and p.suffix != ".abandoned"]
            latest = max(lineage, key=lambda pair: pair[1]["written_at"])[1]
            if _file_state(_contained(root, root / name)) != latest["postimage"]:
                raise HelperError("ERECOVERY", "completed local write changed: " + name)
        else:
            actual = _file_state(_contained(root, root / name))
            if actual["sha256"] != operation["preimage"]:
                raise HelperError("ERECOVERY", "uncompleted local preimage changed: " + name)
            remaining.append({"path": name, **operation})
    return remaining


def append_session_entry(envelope: dict, entry_text: str, approved_draft: dict | None = None) -> dict:
    if envelope and envelope.get("skill") != "closingtime":
        raise HelperError("ESKILL", "only closingtime appends")
    root = _approved_context(envelope, approved_draft, entry_text)
    if not envelope.get("skill_version"):
        raise HelperError("EMISSINGVERSION", "skill_version required")
    warnings = []
    try:
        with _advisory_lock(root, envelope["invocation_id"]) as recovered:
            if recovered:
                warnings.append("ELOCK_STALE_RECOVERED")
            _check_conflicts(root)
            records = _load_intents(root)
            for path, record in records:
                if record["kind"] == "append_intent" and record["draft_receipt_sha256"] == approved_draft["receipt_sha256"] and path.suffix != ".abandoned":
                    state = _append_classification(record, final=path.suffix != ".pending")
                    if state == "appended":
                        if path.suffix == ".pending":
                            path = _move_record(path, ".json" if record["m2_operations"] else ".done")
                        return {"session_number": record["session_number"], "entry_sha256": record["entry_sha256"], "journal_record_path": str(path), "already_appended": True, "readback_ok": True, "warnings": warnings}
                    raise HelperError("EUNFINISHED", "existing intent; run resume")
            if _unfinished(root):
                raise HelperError("EUNFINISHED", "run resume before another close")
            session_path = _session_path_from_envelope(root, envelope)
            relative = session_path.relative_to(root).as_posix()
            if {"class": "M2", "operation": "append", "path": relative} not in approved_draft["scope_operations"]:
                raise HelperError(S.SCOPE_UNAPPROVED, "session append not in scope")
            _, alternates = _named_observation(root, SESSION_NAMES)
            current_text = _read_text(root, session_path if session_path.exists() else None)
            history = _parse_warnings("", current_text)
            if alternates or any(w in history for w in ("session_unparseable", "duplicate_session_number", "session_header_malformed")):
                raise HelperError("EHISTORY", "ambiguous or malformed session history")
            tail, latest = _last_session_entries(current_text, 2)
            if _sha256_text(tail) != approved_draft["observed_tail_sha256"]:
                raise HelperError("ESTALE", "session tail changed after draft")
            chunk = _render_entry(entry_text, latest + 1)
            date = dt.date.fromisoformat(SESSION_HEADER_RE.search(chunk).group("date"))
            local_date = dt.date.fromisoformat(envelope["local_snapshot"]["local_date"])
            if abs((date-local_date).days) > 1:
                warnings.append("ENTRY_DATE_SKEW")
            preimage = _file_state(session_path)
            prefix = "# Session Log\n\n" if not preimage["exists"] else ("" if current_text.endswith("\n\n") else "\n" if current_text.endswith("\n") else "\n\n")
            data = (prefix + chunk).encode("utf-8")
            m2 = {name: {"preimage": expected, "payload_sha256": approved_draft["index_draft_sha256"] if name == _observed_targets(envelope)["index"] else (approved_draft.get("local_payload_hashes") or {}).get(name)} for name, expected in approved_draft["m2_preimages"].items() if any(op.get("path") == name for op in approved_draft["scope_operations"])}
            record = {"schema_version": S.SCHEMA_VERSION, "kind": "append_intent", "workspace_root": str(root),
                      "target": str(session_path), "preimage": preimage, "session_number": latest + 1,
                      "entry_sha256": _sha256_text(chunk), "append_sha256": _sha256_bytes(data), "append_length": len(data),
                      "append_bytes": base64.b64encode(data).decode(), "invocation_id": envelope["invocation_id"],
                      "draft_receipt_sha256": approved_draft["receipt_sha256"], "approved_scope": approved_draft["scope_lines"],
                      "m2_operations": m2, "envelope_sha256": _sha256_bytes(_canonical_json(envelope)),
                      "written_at": _utc_now(), "skill_version": envelope["skill_version"], "approved_at": approved_draft["approved_at"],
                      "approved_envelope": envelope, "approved_draft": approved_draft}
            try:
                pending = _persist_intent(root, record)
            except OSError as exc:
                raise HelperError("EJOURNAL", f"intent not durable; log untouched: {exc}") from exc
            try:
                # Recheck after intent I/O as well as under the shared lock.
                if not _state_matches(session_path, preimage):
                    raise HelperError("EPARTIAL_APPEND", f"preimage changed after intent: {pending}")
                _append_bytes(session_path, data)
                readback = _readback_entry(session_path, latest + 1)
                if readback is None or _sha256_text(readback) != record["entry_sha256"] or _append_classification(record) != "appended":
                    raise OSError("appended bytes did not read back")
            except (OSError, UnicodeError) as exc:
                try:
                    rolled_back = _conditional_rollback(record, pending)
                except (OSError, HelperError):
                    rolled_back = False
                raise HelperError("EREADBACK" if rolled_back else "EPARTIAL_APPEND", str(exc), rolled_back=rolled_back, pending_record=str(pending), session_number=latest + 1, entry_sha256=record["entry_sha256"], state="not_appended" if rolled_back else "partial_or_conflicted") from exc
            try:
                final = _move_record(pending, ".json" if m2 else ".done")
            except OSError as exc:
                raise HelperError("EPARTIAL_APPEND", str(exc), pending_record=str(pending), session_number=latest + 1, entry_sha256=record["entry_sha256"], state="appended") from exc
            result = {"session_number": latest + 1, "entry_sha256": record["entry_sha256"], "journal_record_path": str(final), "readback_ok": True, "warnings": warnings}
        return result
    except OSError as exc:
        raise HelperError("EPARTIAL_APPEND", f"inspect retained intent via resume: {exc}") from exc


def _writer_target(root: Path, envelope: dict, relative_path: str) -> tuple[Path, str]:
    if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise HelperError("EPERM", "relative contained target required")
    targets = _observed_targets(envelope)
    if relative_path not in targets.values():
        raise HelperError("EPERM", "writer allows observed index, pending learnings and decisions archive only")
    field = next(k for k, v in targets.items() if v == relative_path)
    names = {"index": INDEX_NAMES, "pending_learnings": PENDING_NAMES, "decisions_archive": ARCHIVE_NAMES}[field]
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


def write_approved_file(envelope: dict, receipt: dict, relative_path: str, content: str | None = None,
                        operation: str = "replace", expect: str | None = None,
                        mirror_rows: list[dict] | None = None, owner_reply: str = "") -> dict:
    root = _approved_context(envelope, receipt)
    if operation not in {"replace", "delete"} or expect is None or (expect != "absent" and not re.fullmatch(r"sha256:[a-f0-9]{64}", expect)):
        raise HelperError("EINPUT", "replace/delete and explicit --expect sha256|absent required")
    if {"class": "M2", "operation": operation, "path": relative_path} not in receipt["scope_operations"]:
        raise HelperError(S.SCOPE_UNAPPROVED, "target/operation not in approved scope")
    if operation == "replace" and content is None or operation == "delete" and content is not None:
        raise HelperError("EINPUT", "replace needs payload; delete has none")
    try:
        with _advisory_lock(root, envelope["invocation_id"]):
            _check_conflicts(root)
            target, field = _writer_target(root, envelope, relative_path)
            records = _load_intents(root)
            previous = [(p, r) for p, r in records if r["kind"] == "write_intent" and r["draft_receipt_sha256"] == receipt["receipt_sha256"] and r["relative_path"] == relative_path and p.suffix != ".abandoned"]
            if any(p.suffix == ".pending" for p, r in records):
                raise HelperError("EUNFINISHED", "resume pending intent before writing")
            if field == "index":
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
            if field == "decisions_archive" and operation == "replace" and receipt["local_payload_hashes"].get(relative_path) != _sha256_text(content):
                raise HelperError("EDRAFTMISMATCH", "archive payload differs from approved hash")
            if not previous and expect != receipt["m2_preimages"][relative_path]:
                raise HelperError("ESOURCECHANGED", "first transition must use observed preimage")
            if previous:
                latest = max(previous, key=lambda pair: pair[1]["written_at"])[1]
                if expect != latest["postimage"]["sha256"]:
                    raise HelperError("ESOURCECHANGED", "revision must follow last verified transition")
            preimage = _file_state(target)
            if preimage["sha256"] != expect:
                raise HelperError("ESOURCECHANGED", "current bytes differ from expected preimage")
            payload = content.encode("utf-8") if content is not None else None
            postimage = {"exists": True, "length": len(payload), "sha256": _sha256_bytes(payload)} if payload is not None else {"exists": False, "length": 0, "sha256": "absent"}
            record = {"schema_version": S.SCHEMA_VERSION, "kind": "write_intent", "workspace_root": str(root),
                      "target": str(target), "relative_path": relative_path, "operation": operation,
                      "preimage": preimage, "postimage": postimage, "payload_sha256": postimage["sha256"],
                      "draft_receipt_sha256": receipt["receipt_sha256"], "invocation_id": envelope["invocation_id"],
                      "approved_scope": receipt["scope_lines"], "owner_reply": owner_reply,
                      "transition_id": uuid.uuid4().hex, "written_at": _utc_now(),
                      "payload_bytes": base64.b64encode(payload).decode() if payload is not None else None,
                      "approved_envelope": envelope, "approved_draft": receipt}
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
            # Mark the parent complete only after every approved local path has
            # a verified transition. External effects never inferred here.
            records = _load_intents(root)
            for parent, record in records:
                if record["kind"] == "append_intent" and record["draft_receipt_sha256"] == receipt["receipt_sha256"] and parent.suffix == ".json":
                    if not _remaining_paths(root, record, records):
                        _move_record(parent, ".done")
            return {"path": relative_path, "operation": operation, "readback_sha256": postimage["sha256"], "bytes": postimage["length"], "readback_ok": True, "journal_record_path": str(final)}
    except OSError as exc:
        raise HelperError("EPARTIAL_WRITE", f"inspect intent via resume: {exc}") from exc


def resume_append(workspace_root: str | os.PathLike[str], receipt: dict | None = None,
                  abandon: str | None = None, owner_reply: str = "") -> dict:
    root = _resolve_root(workspace_root)
    try:
        with _advisory_lock(root, "resume"):
            _check_conflicts(root)
            records = _load_intents(root)
            all_records = records
            if receipt is not None:
                if receipt.get("workspace_root") != str(root) or receipt.get("receipt_sha256") != _receipt_digest(receipt):
                    raise HelperError("ERECOVERY", "wrong or modified receipt")
                records = [(p, r) for p, r in records if r["draft_receipt_sha256"] == receipt["receipt_sha256"]]
                if not records:
                    raise HelperError("ERECOVERY", "receipt has no durable intent")
            if abandon:
                if not owner_reply.strip():
                    raise HelperError(S.SCOPE_UNAPPROVED, "abandon needs recorded explicit owner approval")
                selected = _contained(root, root / abandon)
                if selected not in {p for p, r in records}:
                    raise HelperError("ERECOVERY", "unknown intent")
                _move_record(selected, ".abandoned")
                # Separate annotation keeps the original intent bytes unchanged.
                note = {"workspace_root": str(root), "intent": str(selected), "owner_reply": owner_reply, "written_at": _utc_now()}
                _atomic_record(selected.with_name(selected.name + ".abandon-note"), note)
                return {"state": "abandoned", "intent": str(selected)}
            results = []
            for path, record in records:
                if path.suffix == ".abandoned":
                    continue
                if record["kind"] == "append_intent":
                    state = _append_classification(record, final=path.suffix != ".pending")
                    if path.suffix != ".pending" and state != "appended":
                        raise HelperError("ERECOVERY", "final entry missing or edited: " + str(path))
                    if state == "partial_or_conflicted":
                        results.append({"intent": str(path), "state": state}); continue
                    remaining = _remaining_paths(root, record, all_records)
                    if path.suffix == ".pending":
                        path = _move_record(path, ".abandoned" if state == "not_appended" else ".json" if remaining else ".done")
                    elif path.suffix == ".json" and not remaining:
                        path = _move_record(path, ".done")
                    result = {"intent": str(path), "state": state, "session_number": record["session_number"], "remaining_paths": remaining}
                    if remaining:
                        result["recovery_inputs"] = {"envelope": record["approved_envelope"], "approved_draft": record["approved_draft"], "index_draft": record["approved_draft"].get("index_draft")}
                    results.append(result)
                else:
                    actual = _file_state(Path(record["target"]))
                    # Later sanctioned revisions supersede earlier postconditions.
                    newer = [r for p, r in all_records if r["kind"] == "write_intent" and r["target"] == record["target"] and r["written_at"] > record["written_at"] and p.suffix != ".abandoned"]
                    if newer:
                        next_record = min(newer, key=lambda r: r["written_at"])
                        if next_record["preimage"] != record["postimage"]:
                            raise HelperError("ERECOVERY", "broken transition chain")
                        state = "superseded"
                    elif actual == record["postimage"]:
                        state = "applied"
                        if path.suffix == ".pending":
                            path = _move_record(path, ".done")
                    elif actual == record["preimage"] and path.suffix == ".pending":
                        state = "not_applied"; path = _move_record(path, ".abandoned")
                    else:
                        state = "partial_or_conflicted"
                    result = {"intent": str(path), "state": state, "path": record["relative_path"]}
                    if state == "not_applied":
                        result["recovery_inputs"] = {"envelope": record["approved_envelope"], "approved_draft": record["approved_draft"], "content": base64.b64decode(record["payload_bytes"]).decode("utf-8") if record.get("payload_bytes") is not None else None,
                                                     "operation": record["operation"], "expect": record["preimage"]["sha256"]}
                    results.append(result)
            partial = any(r["state"] == "partial_or_conflicted" for r in results)
            return {"state": "partial_or_conflicted" if partial else (results[0]["state"] if len(results) == 1 else "inspected"), "operations": results,
                    "unfinished_operations": _unfinished(root), "external_retry": "fresh preconditions and approval required"}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HelperError("ERECOVERY", f"preserve recovery evidence: {exc}") from exc


def new_envelope(workspace_root: str | os.PathLike[str]) -> dict:
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
    return {"schema_version": S.SCHEMA_VERSION, "skill": name.group(1), "skill_version": version.group(1),
            "invocation_id": str(uuid.uuid4()), "invocation_started_at": snapshot["observed_at"],
            "workspace_root": snapshot["workspace_root"], "project": None, "local_snapshot": snapshot,
            "capability_profile": {"schema_version": S.SCHEMA_VERSION,
                "local": {"shell_available": True, "git_available": snapshot["git"]["available"],
                          "temporary_workspace_available": temporary_available, "parallel_read_only_available": False},
                "external": {"tasks_mcp": "unprobed", "open_brain": "unprobed"}},
            "mcp_receipts": [], "returned_rows_by_capability": {}, "mutation_scope": {"M2": [], "M3": [], "M4": []},
            "approval": {"granted": False, "scope_string": None}}


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
    journal_dir = _contained(root, root / "private-artifacts" / "session-journal")

    if not journal_dir.is_dir():
        return {
            "entries": len(entries),
            "journaled": 0,
            "grandfathered": [],
            "documented_unverified": [],
            "unjournaled": entries,
            "orphan_records": [],
            "errors": ["ENOJOURNAL"], "pending_records": [], "pending_journal": [], "foreign_files": [], "legacy_records": [],
        }

    ceiling, exceptions, errors = _read_audit_policy(root, journal_dir)
    records: list[tuple[Path, dict]] = []
    orphan_records: list[dict] = []
    for path in sorted(list(journal_dir.glob("*.json")) + list(journal_dir.glob("*.done"))):
        if path.name == GRANDFATHER_POLICY:
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
        if record.get("kind") == "write_intent":
            if record.get("workspace_root") != str(root) or record.get("record_sha256") != _intent_digest(record):
                orphan_records.append({"path": str(path), "reason": "foreign_or_modified_intent"})
            continue
        if record.get("kind") == "append_intent" and (record.get("workspace_root") != str(root) or record.get("record_sha256") != _intent_digest(record)):
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

    pending_records = []
    pending_journal = []
    for path in sorted(journal_dir.glob("*.pending")):
        try:
            _inside(root, path)
            r = json.loads(path.read_text())
            pending_records.append({"path": str(path), "kind": r.get("kind")})
            if r.get("kind") == "append_intent" and r.get("workspace_root") == str(root) and r.get("record_sha256") == _intent_digest(r):
                for entry in unjournaled[:]:
                    if entry["session_number"] == r.get("session_number") and entry["entry_sha256"] == r.get("entry_sha256"):
                        pending_journal.append(entry); unjournaled.remove(entry)
        except (OSError, ValueError, HelperError):
            errors.append("ERECOVERY:" + str(path))
    if _sync_conflicts(root):
        errors.append(S.SYNC_CONFLICT)
    known_suffixes = {".json", ".done", ".pending", ".abandoned", ".abandon-note"}
    foreign_files = [str(p) for p in journal_dir.iterdir() if p.is_file() and p.suffix not in known_suffixes]
    legacy_records = [str(p) for p, r in records if r.get("kind") != "append_intent"]
    return {
        "pending_records": pending_records, "pending_journal": pending_journal,
        "foreign_files": foreign_files, "legacy_records": legacy_records,
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
