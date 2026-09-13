#!/usr/bin/env python3
"""On-demand, evidence-bound verification of archived LinkedIn descriptions.

The module deliberately has no browser transport.  ``prepare`` freezes the
population and local baseline, while ``compare`` consumes a separately
captured ``SelectedPostingAcquisitionV1`` bundle.  ``local-check`` is useful
for checking archive/sidecar structure, but its output can never be used as a
fresh-source refresh audit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterable

import openpyxl

from acquisition_capture import revalidate_bundle
from acquisition_quality import validate_quality
from sync_integrity import surfaces


SELECTION_SCHEMA = "SelectionV1"
AUDIT_SCHEMA = "ExistingDescriptionAuditV1"
AUDIT_VERSION = "1.0"
MODES = {"FRESH_CAPTURE_COMPARISON", "LOCAL_ARTIFACT_VALIDATION_ONLY"}
CLASSIFICATIONS = {
    "exact_match",
    "match_whitespace_or_ui",
    "substantive_difference",
    "source_unavailable",
    "capture_failed",
    "unvisited",
    "identity_mismatch",
}
ID_RE = re.compile(r"^\d+$")
TRACKER_ID_RE = re.compile(r"^J-(\d+)$", re.I)
JOB_URL_RE = re.compile(
    r"^https://(?:www\.)?linkedin\.com/jobs/view/(\d+)/?(?:\?.*)?$",
    re.I,
)
JOB_URL_SEARCH_RE = re.compile(r"/jobs/view/(\d+)", re.I)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any, *, field: str = "timestamp", require_aware: bool = True) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty ISO-8601 timestamp")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        if require_aware:
            raise ValueError(f"{field} must include a timezone")
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def reject_materially_future(value: dt.datetime, *, field: str, tolerance_minutes: int = 5) -> None:
    if value > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=tolerance_minutes):
        raise ValueError(f"{field} is materially in the future")


def path_ref(root: Path, path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve_path(value: str | Path, *, base: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    return path.resolve(strict=False)


def ensure_not_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink: {path}")


def ensure_no_symlink_chain(path: Path, *, stop: Path | None = None, label: str = "path") -> None:
    """Reject a symlink anywhere in a caller-controlled lexical path chain."""
    # macOS exposes temporary directories through the system ``/var`` and
    # ``/tmp`` symlinks.  They are OS aliases, not caller-controlled workspace
    # redirects; inspect every component below them as usual.
    system_aliases = {Path("/var"), Path("/tmp")}
    resolved = path.resolve(strict=False)
    boundary = stop.resolve(strict=False) if stop is not None else None
    cursor = path.absolute()
    while True:
        if cursor.exists() and cursor.is_symlink() and cursor not in system_aliases:
            raise ValueError(f"{label} contains a symlink component: {cursor}")
        if boundary is not None and cursor == boundary:
            break
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent


def resolve_input_path(value: str | Path, *, base: Path | None = None, label: str = "input") -> Path:
    """Resolve a user supplied path only after checking its lexical chain."""
    lexical = Path(value).expanduser()
    if not lexical.is_absolute() and base is not None:
        lexical = base / lexical
    ensure_no_symlink_chain(lexical, stop=base, label=label)
    resolved = lexical.resolve(strict=False)
    ensure_no_symlink_chain(resolved, stop=base, label=label)
    return resolved


def ensure_safe_run_dir(root: Path, path: str | Path, tracker: Path) -> Path:
    """Resolve an output directory without allowing live-tree clobbering."""
    lexical = Path(path).expanduser()
    ensure_no_symlink_chain(lexical, label="output directory")
    out = resolve_path(path)
    root = root.resolve()
    tracker = tracker.resolve()
    postings = (root / "JobPostings" / "postings").resolve(strict=False)
    meta = (root / "JobPostings" / "_meta").resolve(strict=False)
    jobpostings = (root / "JobPostings").resolve(strict=False)
    forbidden = {
        tracker,
        postings,
        meta,
        jobpostings,
    }
    if out in forbidden:
        raise ValueError(f"output directory cannot be a live tracker/postings/meta path: {out}")
    if out.is_relative_to(postings) or out.is_relative_to(meta):
        raise ValueError(f"output directory cannot be inside live postings or metadata: {out}")
    # Existing symlink parents resolve above; reject an existing symlink at the
    # leaf so a later mkdir/replace cannot redirect the run.
    if out.exists() and out.is_symlink():
        raise ValueError(f"output directory cannot be a symlink: {out}")
    ensure_no_symlink_chain(out, stop=root if out.is_relative_to(root) else None, label="output directory")
    out.mkdir(parents=True, exist_ok=True)
    ensure_not_symlink(out, "output directory")
    return out


def write_bytes_new_or_same(path: Path, data: bytes) -> str:
    """Write a run artifact atomically; never follow a symlink or clobber data."""
    ensure_not_symlink(path, "run artifact")
    if path.exists():
        if path.read_bytes() == data:
            return "unchanged"
        raise ValueError(f"run artifact already exists with different bytes: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_not_symlink(path.parent, "run artifact parent")
    ensure_no_symlink_chain(path, stop=path.parent, label="run artifact")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise ValueError(f"run artifact was created concurrently: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    if path.read_bytes() != data:
        raise RuntimeError(f"exact readback mismatch for {path}")
    return "written"


def write_json(path: Path, value: Any) -> str:
    return write_bytes_new_or_same(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def read_json(path: str | Path) -> Any:
    resolved = resolve_path(path)
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"JSON input is not a regular file: {resolved}")
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input {resolved}: {exc}") from exc


def tracker_hash(tracker: Path) -> str:
    ensure_not_symlink(tracker, "tracker")
    if not tracker.is_file():
        raise ValueError(f"tracker does not exist: {tracker}")
    return sha256_file(tracker)


def _tracker_id_number(value: Any) -> int | None:
    match = TRACKER_ID_RE.fullmatch(str(value or "").strip())
    return int(match.group(1)) if match else None


def _job_id_from_value(value: Any) -> str | None:
    raw = str(value or "").strip()
    if ID_RE.fullmatch(raw):
        return raw
    match = JOB_URL_SEARCH_RE.search(raw)
    return match.group(1) if match else None


def _archive_record(path: Path, jid: str, *, root: Path | None = None) -> dict[str, Any]:
    """Parse an archive while retaining exact header/body bytes."""
    ensure_not_symlink(path, "archive")
    ensure_no_symlink_chain(path, stop=root, label="archive")
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"archive {jid} cannot be read as UTF-8: {exc}") from exc
    marker = re.search(r"(?m)^##\s+About the Job\s*\r?\n(?:\r?\n)?", text)
    if marker is None:
        raise ValueError(f"Archive {jid} lacks a recoverable ## About the Job body")
    prefix = text[: marker.end()]
    body = text[marker.end() :]
    if not body.strip():
        raise ValueError(f"Archive {jid} lacks a recoverable full description")
    lines = text[: marker.start()].splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"Archive {jid} lacks a title header")
    title = lines[0][2:]
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    company = fields.get("Company", "").strip()
    if not company:
        raise ValueError(f"Archive {jid} lacks Company metadata")
    source_url = fields.get("Source", "").strip()
    url_match = JOB_URL_RE.fullmatch(source_url)
    if not url_match or url_match.group(1) != jid:
        raise ValueError(f"Archive {jid} has an ID-conflicting Source URL")
    canonical_url = f"https://www.linkedin.com/jobs/view/{jid}/"
    base_root = root or Path(os.environ.get("SYNC_JOBS_ROOT", path.parents[2]))
    return {
        "id": jid,
        "title": title,
        "company": company,
        "location": fields.get("Location", "Unknown"),
        "type": fields.get("Type", "Unknown"),
        "posted": fields.get("Posted", ""),
        "url": canonical_url,
        "observed_source_url": source_url,
        "path": path,
        "path_ref": path_ref(base_root, path),
        "raw_text": text,
        "prefix": prefix,
        "body": body,
        "body_bytes": body.encode("utf-8"),
        "archive_sha256": sha256_bytes(raw),
        "header_sha256": sha256_bytes(prefix.encode("utf-8")),
        "body_sha256": sha256_bytes(body.encode("utf-8")),
    }


def _load_surfaces(root: Path, tracker: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    postings = root / "JobPostings" / "postings"
    if not postings.is_dir():
        raise ValueError(f"posting archive directory does not exist: {postings}")
    try:
        rows, archives = surfaces(tracker, root, postings)
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError(f"cannot resolve tracker/archive surfaces: {exc}") from exc
    return rows, archives


def _sidecar_path(root: Path, tracker_id: str) -> Path:
    return root / "JobPostings" / "_meta" / "compensation" / f"{tracker_id}_PostingCompensationV1.json"


def _archive_manifest_entry(root: Path, tracker_id: str, jid: str, row: dict[str, Any], archive_path: Path) -> dict[str, Any]:
    ensure_no_symlink_chain(archive_path, stop=root, label="archive")
    archive = _archive_record(archive_path, jid, root=root)
    tracker_title = str(row.get("Puesto") or "").strip()
    tracker_company = str(row.get("Empresa") or "").strip()
    if not tracker_title or not tracker_company:
        raise ValueError(f"{jid}: tracker row lacks title or company")
    if archive["title"] != tracker_title or archive["company"] != tracker_company:
        raise ValueError(
            f"{jid}: archive/tracker identity mismatch (archive={archive['title']!r}/{archive['company']!r}, "
            f"tracker={tracker_title!r}/{tracker_company!r})"
        )
    row_url = str(row.get("Link puesto linkedin") or "").strip()
    row_match = JOB_URL_RE.fullmatch(row_url)
    if row_match is None or row_match.group(1) != jid:
        raise ValueError(f"{jid}: tracker LinkedIn URL is missing or ID-conflicting")
    jd_value = str(row.get("JD File") or "").strip()
    if not jd_value:
        raise ValueError(f"{jid}: tracker JD File is missing")
    jd_path = resolve_path(jd_value, base=root)
    if jd_path != archive_path.resolve():
        raise ValueError(f"{jid}: tracker JD File does not match the unique archive")
    sidecar = _sidecar_path(root, tracker_id)
    ensure_no_symlink_chain(sidecar, stop=root, label="compensation sidecar")
    if sidecar.exists() and (sidecar.is_symlink() or not sidecar.is_file()):
        raise ValueError(f"{jid}: compensation sidecar is not a regular file")
    sidecar_sha = sha256_file(sidecar) if sidecar.is_file() else None
    eligibility = root / "JobPostings" / "_meta" / "eligibility" / f"{tracker_id}_PostingEligibilityV1.json"
    ensure_no_symlink_chain(eligibility, stop=root, label="eligibility sidecar")
    if eligibility.exists() and (eligibility.is_symlink() or not eligibility.is_file()): raise ValueError(f"{jid}: eligibility sidecar is not a regular file")
    return {
        "linkedin_id": jid,
        "tracker_id": tracker_id,
        "title": tracker_title,
        "company": tracker_company,
        "source_url": archive["url"],
        "observed_source_url": archive["observed_source_url"],
        "archive_path": path_ref(root, archive_path),
        "archive_sha256": archive["archive_sha256"],
        "archive_body_sha256": archive["body_sha256"],
        "sidecar_path": path_ref(root, sidecar),
        "sidecar_sha256": sidecar_sha,
        "eligibility_path": path_ref(root, eligibility),
        "eligibility_sha256": sha256_file(eligibility) if eligibility.is_file() else None,
        "archive": archive,
        "tracker_row": {
            "Tracker ID": tracker_id,
            "Puesto": tracker_title,
            "Empresa": tracker_company,
            "Estatus": row.get("Estatus"),
            "JD File": jd_value,
            "Link puesto linkedin": row_url,
        },
    }


def _extract_order_entries(value: Any) -> list[tuple[str, dt.datetime]]:
    """Extract explicit per-ID acquisition timestamps from a read-only record."""
    explicit_schema = isinstance(value, dict) and value.get("schema") in ("AcquisitionOrderV1", "IngestOrderV1")
    if isinstance(value, dict) and value.get("schema") not in (None, "AcquisitionOrderV1", "IngestOrderV1"):
        return []
    candidates: list[Any] = []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, dict):
        for key in ("acquisitions", "acquisition_order", "records", "entries", "selected", "jobs"):
            if isinstance(value.get(key), list):
                candidates.extend(value[key])
    result: list[tuple[str, dt.datetime]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        jid = None
        for key in ("linkedin_id", "job_id", "source_id", "id"):
            jid = _job_id_from_value(item.get(key))
            if jid:
                break
        timestamp = None
        # Only explicit ingest/acquisition timestamps qualify as chronology.
        # A capture timestamp in an arbitrary JSON file is not a durable order
        # record and therefore falls back to Tracker ID order.
        timestamp_keys = ("acquired_at", "acquisition_at", "ingested_at", "downloaded_at")
        if explicit_schema:
            timestamp_keys = timestamp_keys + ("captured_at",)
        for key in timestamp_keys:
            if item.get(key):
                try:
                    timestamp = parse_timestamp(item[key], field=key)
                except ValueError:
                    timestamp = None
                break
        if jid and timestamp is not None:
            result.append((jid, timestamp))
    return result


def _order_files(root: Path) -> Iterable[Path]:
    # This is intentionally read-only discovery.  No ledger is created by
    # this release; audit runs and refresh outputs are excluded as they are
    # derived evidence rather than ingest chronology.
    for candidate in sorted(root.rglob("*.json")):
        lowered = str(candidate).lower()
        name = candidate.name.lower()
        if name in {"acquisition_order.json", "ingest_order.json", "acquisition_ledger.json", "ingest_history.json"}:
            if any(token in lowered for token in ("audit", "refresh", "selection")):
                continue
            yield candidate


def _trustworthy_acquisition_order(root: Path, candidate_ids: set[str]) -> tuple[list[str], str, str] | None:
    accepted: list[tuple[list[str], Path, str]] = []
    for path in _order_files(root):
        try:
            data = read_json(path)
            entries = _extract_order_entries(data)
        except ValueError:
            continue
        if not entries:
            continue
        mapping: dict[str, dt.datetime] = {}
        conflict = False
        for jid, stamp in entries:
            if jid not in candidate_ids:
                continue
            if jid in mapping and mapping[jid] != stamp:
                conflict = True
                break
            mapping[jid] = stamp
        if conflict or set(mapping) != candidate_ids or len(mapping) != len(entries):
            continue
        order = [jid for jid, _ in sorted(mapping.items(), key=lambda item: (item[1], int(item[0])))]
        accepted.append((order, path, sha256_file(path)))
    if not accepted:
        return None
    first_order = accepted[0][0]
    if any(item[0] != first_order for item in accepted[1:]):
        return None
    return first_order, f"existing_acquisition_record:{path_ref(root, accepted[0][1])}", accepted[0][2]


def resolve_selection(root: Path, tracker: Path, selected_ids: list[str] | None = None, latest_n: int | None = None) -> dict[str, Any]:
    if bool(selected_ids) == (latest_n is not None):
        raise ValueError("provide exactly one of --selected-id or --latest-n")
    rows, archives = _load_surfaces(root, tracker)
    candidate_ids = set(rows) & set(archives)
    if not candidate_ids:
        raise ValueError("no tracker/archive identities are available for selection")
    if selected_ids:
        ids = [str(value) for value in selected_ids]
        if any(not ID_RE.fullmatch(value) for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("selected IDs must be unique numeric LinkedIn IDs")
        missing = [jid for jid in ids if jid not in candidate_ids]
        if missing:
            raise ValueError(f"selected LinkedIn IDs lack an unambiguous tracker/archive pair: {missing}")
        basis = "explicit_selected_ids"
        order_source = "owner_selected_order"
        order_hash = None
    else:
        if not isinstance(latest_n, int) or latest_n <= 0:
            raise ValueError("--latest-n must be a positive integer")
        chronology = _trustworthy_acquisition_order(root, candidate_ids)
        if chronology:
            chronology_ids, order_source, order_hash = chronology
            ids = list(reversed(chronology_ids))[:latest_n]
            basis = "existing_acquisition_order"
        else:
            # Tracker ID is the only stable historical fallback available in
            # this release.  Never use physical row order or filesystem mtime.
            ids = sorted(
                candidate_ids,
                key=lambda jid: (
                    -(_tracker_id_number(rows[jid].get("Tracker ID")) or -1),
                    -int(jid),
                ),
            )[:latest_n]
            basis = "tracker_id_order_fallback"
            order_source = "numeric Tracker ID descending; true acquisition order unavailable"
            order_hash = None
    entries = []
    for jid in ids:
        row = rows[jid]
        tracker_id = str(row.get("Tracker ID") or "").strip()
        if not tracker_id:
            raise ValueError(f"{jid}: tracker row has no Tracker ID")
        # Keep the surface path lexical until the symlink-chain checks run;
        # resolving it first would erase evidence that a tracker/archive path
        # was redirected through a caller-controlled symlink.
        entry = _archive_manifest_entry(root, tracker_id, jid, row, archives[jid])
        entry.pop("archive", None)
        entries.append(entry)
    created_at = utc_now()
    core = {
        "schema": SELECTION_SCHEMA,
        "version": "1.1",
        "created_at": created_at,
        "project_root": str(root.resolve()),
        "tracker_path": path_ref(root, tracker),
        "tracker_sha256": tracker_hash(tracker),
        "selected_ids": ids,
        "selection_basis": basis,
        "order_source": order_source,
        "order_source_sha256": order_hash,
        "entries": entries,
    }
    core["archive_manifest_sha256"] = digest(
        [
            {
                key: entry.get(key)
                for key in ("linkedin_id", "tracker_id", "title", "company", "source_url", "observed_source_url", "archive_path", "archive_sha256", "archive_body_sha256", "sidecar_path", "sidecar_sha256", "eligibility_path", "eligibility_sha256")
            }
            for entry in entries
        ]
    )
    payload = dict(core)
    payload["selection_sha256"] = digest(core)
    return payload


def _validate_selection(payload: Any, root: Path, tracker: Path) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != SELECTION_SCHEMA:
        raise ValueError("selection input must have schema SelectionV1")
    expected = payload.get("selection_sha256")
    core = {key: value for key, value in payload.items() if key != "selection_sha256"}
    if not isinstance(expected, str) or expected != digest(core):
        raise ValueError("selection manifest hash mismatch")
    ids = payload.get("selected_ids")
    entries = payload.get("entries")
    if not isinstance(ids, list) or not ids or any(not ID_RE.fullmatch(str(jid)) for jid in ids) or len(ids) != len(set(map(str, ids))):
        raise ValueError("selection manifest selected_ids must be unique numeric IDs")
    if not isinstance(entries, list) or [str(item.get("linkedin_id")) for item in entries if isinstance(item, dict)] != [str(jid) for jid in ids]:
        raise ValueError("selection manifest entries must cover selected_ids exactly and in order")
    created = parse_timestamp(payload.get("created_at"), field="selection.created_at")
    reject_materially_future(created, field="selection.created_at")
    if str(payload.get("project_root")) != str(root.resolve()):
        raise ValueError("selection manifest belongs to another project root")
    tracker_ref = resolve_path(str(payload.get("tracker_path") or ""), base=root)
    if tracker_ref != tracker.resolve() or payload.get("tracker_sha256") != tracker_hash(tracker):
        raise ValueError("selection tracker baseline is stale")
    rows, archives = _load_surfaces(root, tracker)
    manifest_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("selection entry must be an object")
        for field in ("linkedin_id", "tracker_id", "title", "company", "source_url", "archive_path", "archive_sha256", "archive_body_sha256", "sidecar_path"):
            if not str(entry.get(field) or "").strip():
                raise ValueError(f"selection entry missing {field}")
        jid = str(entry["linkedin_id"])
        tracker_id = str(entry["tracker_id"])
        if not ID_RE.fullmatch(jid) or not TRACKER_ID_RE.fullmatch(tracker_id):
            raise ValueError(f"selection entry has invalid identity for {jid}")
        current_row = rows.get(jid)
        if current_row is None or str(current_row.get("Tracker ID") or "") != tracker_id:
            raise ValueError(f"selection tracker identity is stale for {jid}")
        if str(current_row.get("Puesto") or "").strip() != str(entry.get("title") or ""):
            raise ValueError(f"selection tracker title is stale for {jid}")
        if str(current_row.get("Empresa") or "").strip() != str(entry.get("company") or ""):
            raise ValueError(f"selection tracker company is stale for {jid}")
        current_row_url = str(current_row.get("Link puesto linkedin") or "").strip()
        current_row_match = JOB_URL_RE.fullmatch(current_row_url)
        if current_row_match is None or current_row_match.group(1) != jid:
            raise ValueError(f"selection tracker URL is stale for {jid}")
        if jid not in archives:
            raise ValueError(f"selection archive mapping is missing for {jid}")
        if not HEX64_RE.fullmatch(str(entry["archive_sha256"])):
            raise ValueError("selection archive hash is invalid")
        if not HEX64_RE.fullmatch(str(entry["archive_body_sha256"])):
            raise ValueError("selection archive body hash is invalid")
        archive_path = resolve_input_path(entry["archive_path"], base=root, label="selection archive")
        if not archive_path.is_file() or archive_path.is_symlink():
            raise ValueError(f"selection archive is not a regular file: {archive_path}")
        ensure_no_symlink_chain(archive_path, stop=root, label="selection archive")
        current_archive_path = archives[jid]
        ensure_no_symlink_chain(current_archive_path, stop=root, label="current archive")
        if current_archive_path.is_symlink() or not current_archive_path.is_file():
            raise ValueError(f"selection current archive is not a regular file for {jid}")
        if archive_path != current_archive_path.resolve():
            raise ValueError(f"selection archive mapping is stale or ambiguous for {jid}")
        # Selection is a frozen baseline.  Comparing against a changed archive
        # is unsafe; the caller can create a new selection instead.
        if sha256_file(archive_path) != entry["archive_sha256"]:
            raise ValueError(f"selection archive baseline is stale for {entry['linkedin_id']}")
        archive = _archive_record(archive_path, jid, root=root)
        if archive["body_sha256"] != entry["archive_body_sha256"]:
            raise ValueError(f"selection archive body baseline is stale for {jid}")
        if entry["source_url"] != archive["url"]:
            raise ValueError(f"selection source URL is not canonical for {jid}")
        if archive["title"] != str(entry.get("title") or "") or archive["company"] != str(entry.get("company") or ""):
            raise ValueError(f"selection archive identity is stale for {jid}")
        expected_sidecar = _sidecar_path(root, tracker_id).resolve()
        sidecar_path = resolve_input_path(entry["sidecar_path"], base=root, label="selection sidecar")
        if sidecar_path != expected_sidecar:
            raise ValueError(f"selection sidecar path is not canonical for {jid}")
        ensure_no_symlink_chain(sidecar_path, stop=root, label="selection sidecar")
        current_sidecar_sha = None
        if sidecar_path.exists():
            if sidecar_path.is_symlink() or not sidecar_path.is_file():
                raise ValueError(f"selection sidecar is not a regular file for {jid}")
            current_sidecar_sha = sha256_file(sidecar_path)
        if current_sidecar_sha != entry.get("sidecar_sha256"):
            raise ValueError(f"selection sidecar baseline is stale for {jid}")
        if "eligibility_path" in entry:
            expected_eligibility=(root/"JobPostings"/"_meta"/"eligibility"/f"{tracker_id}_PostingEligibilityV1.json").resolve()
            eligibility_path=resolve_input_path(entry["eligibility_path"],base=root,label="selection eligibility sidecar")
            if eligibility_path!=expected_eligibility: raise ValueError(f"selection eligibility path is not canonical for {jid}")
            ensure_no_symlink_chain(eligibility_path,stop=root,label="selection eligibility sidecar")
            current_eligibility_sha=None
            if eligibility_path.exists():
                if eligibility_path.is_symlink() or not eligibility_path.is_file(): raise ValueError(f"selection eligibility sidecar is not a regular file for {jid}")
                current_eligibility_sha=sha256_file(eligibility_path)
            if current_eligibility_sha!=entry.get("eligibility_sha256"): raise ValueError(f"selection eligibility baseline is stale for {jid}")
        manifest_entries.append({
            key: entry.get(key)
            for key in (("linkedin_id", "tracker_id", "title", "company", "source_url", "observed_source_url", "archive_path", "archive_sha256", "archive_body_sha256", "sidecar_path", "sidecar_sha256", "eligibility_path", "eligibility_sha256") if "eligibility_path" in entry else ("linkedin_id", "tracker_id", "title", "company", "source_url", "observed_source_url", "archive_path", "archive_sha256", "archive_body_sha256", "sidecar_path", "sidecar_sha256"))
        })
    expected_manifest = digest(manifest_entries)
    if payload.get("archive_manifest_sha256") != expected_manifest:
        raise ValueError("selection archive manifest hash mismatch")
    return payload


def _comparison_normalize(text: str) -> str:
    # Preserve source Unicode/code points.  The comparison boundary only
    # normalizes line endings and whitespace; NFKC could hide substantive
    # distinctions such as superscript digits or ligatures.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", normalized).strip()


UI_LINE_PATTERNS = (
    re.compile(r"^(?:show|see) (?:more|less|fewer)$", re.I),
    re.compile(r"^(?:report|save|share|apply|follow|message) ?(?:this job|job)?$", re.I),
    re.compile(r"^(?:easy apply|job alert|set alert for similar jobs|dismiss)$", re.I),
    re.compile(r"^(?:apply on (?:company )?website|view job|see who .* applied)$", re.I),
)


def _is_ui_line(line: str) -> bool:
    cleaned = _comparison_normalize(line)
    if not cleaned:
        return True
    return any(pattern.fullmatch(cleaned) for pattern in UI_LINE_PATTERNS)


def _without_recognized_ui_tail(text: str) -> tuple[str, list[str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    removed: list[str] = []
    # An explicit boundary permits an archive-only LinkedIn footer.  Keep the
    # boundary itself out of comparison only if every following line is UI.
    for index, line in enumerate(lines):
        if line.strip() in {"---", "[LinkedIn UI]", "LinkedIn UI:"} and all(_is_ui_line(item) for item in lines[index + 1 :]):
            removed = lines[index:]
            return "\n".join(lines[:index]).rstrip(), removed
    # Without an explicit boundary, even a familiar word such as ``Apply``
    # may be employer-authored prose.  Keep it in the comparison so UI
    # cleanup cannot silently erase substantive source text.
    return normalized.rstrip(), removed


def first_difference(archive: str, live: str) -> dict[str, Any] | None:
    if archive == live:
        return None
    matcher = difflib.SequenceMatcher(a=archive, b=live, autojunk=False)
    for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if tag != "equal":
            return {
                "operation": tag,
                "archive_offset": a_start,
                "live_offset": b_start,
                "archive_excerpt": archive[max(0, a_start - 60) : min(len(archive), a_end + 60)],
                "live_excerpt": live[max(0, b_start - 60) : min(len(live), b_end + 60)],
            }
    return None


def compare_bodies(archive_body: str, live_body: str) -> dict[str, Any]:
    archive_norm = _comparison_normalize(archive_body)
    live_norm = _comparison_normalize(live_body)
    archive_ui, archive_removed = _without_recognized_ui_tail(archive_body)
    live_ui, live_removed = _without_recognized_ui_tail(live_body)
    archive_ui_norm = _comparison_normalize(archive_ui)
    live_ui_norm = _comparison_normalize(live_ui)
    if archive_body == live_body:
        classification = "exact_match"
    elif archive_norm == live_norm:
        classification = "match_whitespace_or_ui"
    elif archive_ui_norm == live_ui_norm and (archive_removed or live_removed):
        classification = "match_whitespace_or_ui"
    else:
        classification = "substantive_difference"
    return {
        "classification": classification,
        "archive_raw_sha256": sha256_bytes(archive_body.encode("utf-8")),
        "live_raw_sha256": sha256_bytes(live_body.encode("utf-8")),
        "archive_raw_length": len(archive_body.encode("utf-8")),
        "live_raw_length": len(live_body.encode("utf-8")),
        "archive_comparison_sha256": sha256_bytes(archive_norm.encode("utf-8")),
        "live_comparison_sha256": sha256_bytes(live_norm.encode("utf-8")),
        "archive_comparison_length": len(archive_norm),
        "live_comparison_length": len(live_norm),
        "first_difference": first_difference(archive_norm, live_norm),
        "ui_boundary": {
            "archive_removed_lines": archive_removed,
            "live_removed_lines": live_removed,
            "recognized": bool(archive_removed or live_removed),
        },
    }


def _record_capture_timestamp(record: dict[str, Any]) -> dt.datetime:
    return parse_timestamp(record.get("provenance", {}).get("captured_at"), field=f"{record.get('id')}.captured_at")


def _validate_fresh_record(record: dict[str, Any], entry: dict[str, Any], selected_at: dt.datetime) -> tuple[dict[str, Any], str | None]:
    """Return recomputed quality and a gate failure, without trusting embedded results."""
    jid = str(entry["linkedin_id"])
    if str(record.get("id")) != jid:
        return {}, "identity_mismatch"
    url_match = JOB_URL_RE.fullmatch(str(record.get("url") or ""))
    if not url_match or url_match.group(1) != jid:
        return {}, "identity_mismatch"
    if str(record.get("title") or "") != str(entry["title"]):
        return {}, "identity_mismatch"
    if str(record.get("company") or "") != str(entry["company"]):
        return {}, "identity_mismatch"
    try:
        captured_at = _record_capture_timestamp(record)
    except ValueError as exc:
        return {"error": str(exc)}, "capture_failed"
    if captured_at < selected_at:
        return {"error": "capture timestamp precedes selection creation"}, "capture_failed"
    try:
        reject_materially_future(captured_at, field=f"{jid}.captured_at")
    except ValueError as exc:
        return {"error": str(exc)}, "capture_failed"
    quality = validate_quality(record)
    if quality.get("status") != "PASS":
        return quality, "capture_failed"
    evidence = record.get("quality_evidence") or {}
    independent = evidence.get("independent_check")
    if isinstance(independent, dict):
        try:
            independent_at = parse_timestamp(independent.get("captured_at"), field=f"{jid}.independent_check.captured_at")
        except ValueError as exc:
            return {"error": str(exc), "quality": quality}, "capture_failed"
        if independent_at < selected_at:
            return {"error": "independent check precedes selection creation", "quality": quality}, "capture_failed"
        try:
            reject_materially_future(independent_at, field=f"{jid}.independent_check.captured_at")
        except ValueError as exc:
            return {"error": str(exc), "quality": quality}, "capture_failed"
    return quality, None


def _source_evidence(record: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if isinstance(record.get("source_evidence"), dict):
        evidence["source_evidence"] = record["source_evidence"]
    if isinstance(record.get("native_nodes"), list):
        evidence["native_nodes"] = record["native_nodes"]
        evidence["inline_link_labels"] = [node.get("text") for node in record["native_nodes"] if isinstance(node, dict) and node.get("role") == "link"]
    if isinstance(record.get("quality_evidence"), dict):
        evidence["quality_evidence"] = record["quality_evidence"]
    return evidence


def _result_for_failure(entry: dict[str, Any], failure: dict[str, Any], bundle_path: Path, bundle_sha: str) -> dict[str, Any]:
    kind = failure.get("failure_kind", "capture_failed")
    if kind not in {"source_unavailable", "capture_failed", "unvisited"}:
        kind = "capture_failed"
    evidence = failure.get("evidence") or failure.get("browser_evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}
    return {
        "linkedin_id": entry["linkedin_id"],
        "tracker_id": entry["tracker_id"],
        "title": entry["title"],
        "company": entry["company"],
        "canonical_source_url": entry["source_url"],
        "archive_path": entry["archive_path"],
        "archive_sha256": entry["archive_sha256"],
        "capture_bundle_path": str(bundle_path),
        "capture_bundle_sha256": bundle_sha,
        "capture_path": failure.get("capture_path"),
        "capture_sha256": failure.get("capture_sha256"),
        "source_description_sha256": None,
        "capture_timestamp": failure.get("captured_at") or evidence.get("captured_at"),
        "browser": failure.get("browser") or evidence.get("browser") or evidence.get("surface"),
        "method": failure.get("method") or evidence.get("method"),
        "completeness": False,
        "end_evidence": failure.get("completion_evidence") or evidence,
        "classification": kind,
        "historical_cause": None,
        "source_state": "unavailable" if kind == "source_unavailable" else "unknown",
        "capture_state": "failed" if kind != "unvisited" else "not_attempted",
        "coverage_state": "attempted" if kind != "unvisited" else "unvisited",
        "fresh_source_validated": False,
        "failure_kind": kind,
        "failure": failure,
        "raw_evidence": evidence,
    }


def _failure_freshness(failure: dict[str, Any], selected_at: dt.datetime) -> str | None:
    """Return a gate failure for timestamped unavailable evidence."""
    kind = failure.get("failure_kind", "capture_failed")
    if kind != "source_unavailable":
        return None
    evidence = failure.get("evidence") or failure.get("browser_evidence") or {}
    captured_at = failure.get("captured_at") or (evidence.get("captured_at") if isinstance(evidence, dict) else None)
    try:
        observed = parse_timestamp(captured_at, field=f"{failure.get('id')}.unavailable.captured_at")
        reject_materially_future(observed, field=f"{failure.get('id')}.unavailable.captured_at")
    except ValueError as exc:
        return str(exc)
    if observed < selected_at:
        return "unavailable-source evidence precedes selection creation"
    return None


def _raw_evidence_document(root: Path, out_dir: Path, entry: dict[str, Any], result: dict[str, Any], archive_body: str, live_body: str | None) -> str:
    raw_dir = out_dir / "raw_differences"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{entry['linkedin_id']}.json"
    document = {
        "schema": "RawDescriptionComparisonV1",
        "linkedin_id": entry["linkedin_id"],
        "archive_path": entry["archive_path"],
        "archive_body": archive_body,
        "live_body": live_body,
        "classification": result.get("classification"),
        "source_evidence": result.get("source_evidence") or result.get("raw_evidence"),
        "comparison": result.get("comparison"),
    }
    write_json(path, document)
    return path_ref(root, path)


def _audit_report(payload: dict[str, Any]) -> str:
    counts = payload.get("counts", {})
    lines = [
        "# Existing description audit",
        "",
        f"Mode: `{payload.get('mode')}`",
        f"Selection: `{payload.get('selection_sha256')}`",
        f"Audit hash: `{payload.get('audit_sha256')}`",
        "",
        "| LinkedIn ID | Title | Company | Classification | Source | Capture | Coverage |",
        "|---|---|---|---|---|---|---|",
    ]
    for result in payload.get("results", []):
        lines.append(
            f"| {result.get('linkedin_id')} | {str(result.get('title','')).replace('|','\\|')} | "
            f"{str(result.get('company','')).replace('|','\\|')} | {result.get('classification')} | "
            f"{result.get('source_state')} | {result.get('capture_state')} | {result.get('coverage_state')} |"
        )
    lines += ["", "Counts:", ""]
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")
    return "\n".join(lines) + "\n"


def _write_audit(root: Path, out_dir: Path, payload_core: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload_core)
    payload["audit_sha256"] = digest(payload_core)
    write_json(out_dir / "audit.json", payload)
    write_bytes_new_or_same(out_dir / "Report.md", _audit_report(payload).encode("utf-8"))
    return payload


def _audit_core(root: Path, out_dir: Path, selection: dict[str, Any], mode: str, results: list[dict[str, Any]], capture_path: Path | None = None, capture_sha: str | None = None) -> dict[str, Any]:
    counts = {classification: 0 for classification in sorted(CLASSIFICATIONS)}
    for result in results:
        classification = result.get("classification")
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"unsupported audit classification {classification!r}")
        counts[classification] += 1
    counts.update(
        {
            "selected": len(results),
            "covered": sum(1 for result in results if result.get("coverage_state") == "covered"),
            "attempted": sum(1 for result in results if result.get("coverage_state") == "attempted"),
            "unvisited": sum(1 for result in results if result.get("classification") == "unvisited"),
            "refresh_eligible": sum(1 for result in results if result.get("eligible_for_refresh") is True),
        }
    )
    core = {
        "schema": AUDIT_SCHEMA,
        "version": AUDIT_VERSION,
        "created_at": utc_now(),
        "mode": mode,
        "selection_path": path_ref(root, out_dir.parent / "selection.json") if (out_dir.parent / "selection.json").exists() else selection.get("selection_path"),
        "selection_sha256": selection.get("selection_sha256"),
        "tracker_path": selection.get("tracker_path"),
        "tracker_sha256": selection.get("tracker_sha256"),
        "capture_bundle_path": str(capture_path) if capture_path else None,
        "capture_bundle_sha256": capture_sha,
        "selected_ids": selection.get("selected_ids"),
        "results": results,
        "counts": counts,
        "claims": {
            "fresh_source_verification": mode == "FRESH_CAPTURE_COMPARISON" and all(
                result.get("classification") in {"exact_match", "match_whitespace_or_ui", "substantive_difference"}
                for result in results
            ),
            "local_only": mode == "LOCAL_ARTIFACT_VALIDATION_ONLY",
            "refresh_candidates_require_fresh_complete_identity_bound_capture": True,
        },
    }
    return _write_audit(root, out_dir, core)


def compare_capture(root: Path, tracker: Path, selection_path: Path, capture_path: Path, out_dir: Path) -> dict[str, Any]:
    selection_path = resolve_input_path(selection_path, label="selection")
    capture_path = resolve_input_path(capture_path, label="capture bundle")
    selection = _validate_selection(read_json(selection_path), root, tracker)
    selection = dict(selection)
    selection["selection_path"] = path_ref(root, selection_path)
    selection_created = parse_timestamp(selection["created_at"], field="selection.created_at")
    capture_bytes = capture_path.read_bytes()
    bundle = read_json(capture_path)
    try:
        normalized = revalidate_bundle(
            bundle,
            set(map(str, selection["selected_ids"])),
            allow_partial=True,
            require_normalized=True,
        )
    except ValueError as exc:
        raise ValueError(f"capture bundle failed normalized revalidation: {exc}") from exc
    bundle_sha = sha256_bytes(capture_bytes)
    records = {str(record["id"]): record for record in normalized["records"]}
    failures = {str(failure["id"]): failure for failure in normalized["failures"]}
    if set(records) & set(failures):
        raise ValueError("capture bundle has an ID in both records and failures")
    results: list[dict[str, Any]] = []
    rows, archives = _load_surfaces(root, tracker)
    for entry in selection["entries"]:
        jid = str(entry["linkedin_id"])
        archive_path = resolve_path(entry["archive_path"], base=root)
        archive = _archive_record(archive_path, jid, root=root)
        if jid in failures:
            failure = dict(failures[jid])
            freshness_error = _failure_freshness(failure, selection_created)
            if freshness_error:
                failure["failure_kind"] = "capture_failed"
                failure["reason"] = f"{failure.get('reason', 'Unavailable source evidence')} ({freshness_error})"
                failure["freshness_gate"] = freshness_error
            result = _result_for_failure(entry, failure, capture_path, bundle_sha)
            result["current_archive_sha256"] = archive["archive_sha256"]
            result["raw_evidence_path"] = _raw_evidence_document(root, out_dir, entry, result, archive["body"], None)
            results.append(result)
            continue
        if jid not in records:
            result = _result_for_failure(entry, {"id": jid, "failure_kind": "unvisited", "reason": "No attempted capture record was supplied.", "status_uncertainty": "No capture was present in the bundle."}, capture_path, bundle_sha)
            result["current_archive_sha256"] = archive["archive_sha256"]
            result["raw_evidence_path"] = _raw_evidence_document(root, out_dir, entry, result, archive["body"], None)
            results.append(result)
            continue
        record = records[jid]
        quality, gate_failure = _validate_fresh_record(record, entry, selection_created)
        base = {
            "linkedin_id": jid,
            "tracker_id": entry["tracker_id"],
            "title": entry["title"],
            "company": entry["company"],
            "canonical_source_url": entry["source_url"],
            "archive_path": entry["archive_path"],
            "archive_sha256": entry["archive_sha256"],
            "current_archive_sha256": archive["archive_sha256"],
            "capture_bundle_path": str(capture_path),
            "capture_bundle_sha256": bundle_sha,
            "capture_path": record.get("capture_path"),
            "capture_sha256": record.get("capture_sha256"),
            "source_description_sha256": record.get("description_sha256"),
            "capture_timestamp": record.get("provenance", {}).get("captured_at"),
            "browser": record.get("provenance", {}).get("browser"),
            "method": record.get("provenance", {}).get("method"),
            "completeness": record.get("provenance", {}).get("complete_text") is True and quality.get("status") == "PASS",
            "end_evidence": record.get("quality_evidence"),
            "source_evidence": _source_evidence(record),
            "quality": quality,
            "live_description": record.get("description"),
            "live_description_sha256": record.get("description_sha256"),
        }
        if gate_failure:
            base.update(
                {
                    "classification": gate_failure,
                    "historical_cause": None,
                    "source_state": "identity_conflict" if gate_failure == "identity_mismatch" else "unknown",
                    "capture_state": "failed",
                    "coverage_state": "attempted",
                    "fresh_source_validated": False,
                    "eligible_for_refresh": False,
                    "failure": quality.get("error") if isinstance(quality, dict) else None,
                }
            )
            result = base
            result["raw_evidence_path"] = _raw_evidence_document(root, out_dir, entry, result, archive["body"], record.get("description"))
            results.append(result)
            continue
        comparison = compare_bodies(archive["body"], str(record["description"]))
        result = {**base, **comparison}
        result.update(
            {
                "classification": comparison["classification"],
                "historical_cause": "unresolved" if comparison["classification"] == "substantive_difference" else None,
                "source_state": "verified",
                "capture_state": "complete",
                "coverage_state": "covered",
                "fresh_source_validated": True,
                "eligible_for_refresh": comparison["classification"] == "substantive_difference",
            }
        )
        result["raw_evidence_path"] = _raw_evidence_document(root, out_dir, entry, result, archive["body"], record["description"])
        results.append(result)
    if len(results) != len(selection["selected_ids"]):
        raise RuntimeError("audit did not emit exactly one result per selected ID")
    return _audit_core(root, out_dir, selection, "FRESH_CAPTURE_COMPARISON", results, capture_path, bundle_sha)


def local_check(root: Path, tracker: Path, selection_path: Path, out_dir: Path) -> dict[str, Any]:
    selection_path = resolve_input_path(selection_path, label="selection")
    selection = _validate_selection(read_json(selection_path), root, tracker)
    selection = dict(selection)
    selection["selection_path"] = path_ref(root, selection_path)
    results: list[dict[str, Any]] = []
    for entry in selection["entries"]:
        archive_path = resolve_path(entry["archive_path"], base=root)
        archive = _archive_record(archive_path, str(entry["linkedin_id"]), root=root)
        sidecar_path = resolve_path(entry["sidecar_path"], base=root)
        sidecar_status = "missing"
        sidecar_sha = None
        if sidecar_path.is_file() and not sidecar_path.is_symlink():
            sidecar_sha = sha256_file(sidecar_path)
            try:
                sidecar = read_json(sidecar_path)
                from posting_compensation import validate as validate_compensation

                validate_compensation(sidecar, verify_file=False)
                posting = sidecar.get("posting", {})
                if sidecar.get("tracker_id") != entry["tracker_id"]:
                    raise ValueError("tracker_id binding mismatch")
                posting_path = resolve_path(str(posting.get("path") or ""), base=root)
                if posting_path != archive_path:
                    raise ValueError("posting path binding mismatch")
                if posting.get("sha256") != archive["archive_sha256"]:
                    raise ValueError("posting hash binding mismatch")
                if posting.get("source_url") != entry["source_url"]:
                    raise ValueError("source URL binding mismatch")
                sidecar_status = "valid"
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                sidecar_status = f"invalid: {exc}"
        eligibility_status="not_frozen"
        eligibility_sha=None
        if entry.get("eligibility_path"):
            eligibility_path=resolve_path(entry["eligibility_path"],base=root);eligibility_status="missing"
            if eligibility_path.is_file() and not eligibility_path.is_symlink():
                eligibility_sha=sha256_file(eligibility_path)
                try:
                    import posting_eligibility
                    previous=posting_eligibility.ROOT;posting_eligibility.ROOT=root
                    try: eligibility=read_json(eligibility_path);posting_eligibility.validate(eligibility,verify_file=True)
                    finally: posting_eligibility.ROOT=previous
                    if eligibility.get("tracker_id")!=entry["tracker_id"] or eligibility.get("posting",{}).get("source_url")!=entry["source_url"]: raise ValueError("eligibility identity mismatch")
                    eligibility_status="valid"
                except (ValueError,OSError,json.JSONDecodeError) as exc: eligibility_status=f"invalid: {exc}"
        result = {
            "linkedin_id": entry["linkedin_id"],
            "tracker_id": entry["tracker_id"],
            "title": entry["title"],
            "company": entry["company"],
            "canonical_source_url": entry["source_url"],
            "archive_path": entry["archive_path"],
            "archive_sha256": entry["archive_sha256"],
            "current_archive_sha256": archive["archive_sha256"],
            "sidecar_path": entry["sidecar_path"],
            "sidecar_sha256": sidecar_sha,
            "local_artifact": {
                "archive_valid": True,
                "archive_matches_selection": archive["archive_sha256"] == entry["archive_sha256"],
                "sidecar_status": sidecar_status,
                "eligibility_status": eligibility_status,
                "eligibility_sha256": eligibility_sha,
            },
            "classification": "unvisited",
            "historical_cause": None,
            "source_state": "not_verified",
            "capture_state": "not_provided",
            "coverage_state": "local_only",
            "fresh_source_validated": False,
            "eligible_for_refresh": False,
            "raw_evidence_path": _raw_evidence_document(root, out_dir, entry, {"classification": "unvisited", "raw_evidence": {"local_artifact": sidecar_status}}, archive["body"], None),
        }
        results.append(result)
    return _audit_core(root, out_dir, selection, "LOCAL_ARTIFACT_VALIDATION_ONLY", results)


def prepare(root: Path, tracker: Path, out_dir: Path, selected_ids: list[str] | None, latest_n: int | None) -> dict[str, Any]:
    selection = resolve_selection(root, tracker, selected_ids=selected_ids, latest_n=latest_n)
    write_json(out_dir / "selection.json", selection)
    baseline = {
        "schema": "SelectionBaselineV1",
        "selection_sha256": selection["selection_sha256"],
        "created_at": selection["created_at"],
        "tracker_path": selection["tracker_path"],
        "tracker_sha256": selection["tracker_sha256"],
        "entries": [
            {
                key: entry.get(key)
                for key in ("linkedin_id", "tracker_id", "archive_path", "archive_sha256", "archive_body_sha256", "sidecar_path", "sidecar_sha256")
            }
            for entry in selection["entries"]
        ],
    }
    baseline["baseline_sha256"] = digest({key: value for key, value in baseline.items() if key != "baseline_sha256"})
    write_json(out_dir / "baseline.json", baseline)
    return {"status": "SELECTION_PREPARED", "selection_path": str(out_dir / "selection.json"), "selection_sha256": selection["selection_sha256"], "selected_ids": selection["selected_ids"], "selection_basis": selection["selection_basis"], "order_source": selection["order_source"]}


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--tracker")
    sub = parser.add_subparsers(dest="phase", required=True)
    prep = sub.add_parser("prepare", help="freeze selected IDs and local baseline before browser capture")
    prep_sel = prep.add_mutually_exclusive_group(required=True)
    prep_sel.add_argument("--selected-id", action="append")
    prep_sel.add_argument("--latest-n", type=int)
    prep.add_argument("--out-dir", required=True)
    comp = sub.add_parser("compare", help="compare a frozen selection with a separately captured bundle")
    comp.add_argument("--selection", required=True)
    comp.add_argument("--capture-bundle", required=True)
    comp.add_argument("--out-dir", required=True)
    local = sub.add_parser("local-check", help="validate local archives/sidecars; never a fresh-source audit")
    local.add_argument("--selection")
    local_sel = local.add_mutually_exclusive_group()
    local_sel.add_argument("--selected-id", action="append")
    local_sel.add_argument("--latest-n", type=int)
    local.add_argument("--out-dir", required=True)

    # Keep the original ``--local-only`` spelling as a compatibility shim for
    # callers that have not yet adopted the explicit three-phase interface.
    # It still freezes a selection before running local validation and never
    # creates a fresh-source claim.
    known_phases = {"prepare", "compare", "local-check"}
    if not any(token in known_phases for token in argv):
        legacy = argparse.ArgumentParser(description=__doc__)
        legacy.add_argument("--project-root", required=True)
        legacy.add_argument("--tracker")
        legacy.add_argument("--local-only", action="store_true")
        legacy.add_argument("--capture-bundle")
        legacy_sel = legacy.add_mutually_exclusive_group(required=True)
        legacy_sel.add_argument("--selected-id", action="append")
        legacy_sel.add_argument("--latest-n", type=int)
        legacy.add_argument("--out-dir", required=True)
        legacy_args = legacy.parse_args(argv)
        root = resolve_path(legacy_args.project_root)
        tracker = resolve_input_path(legacy_args.tracker or "jobs.xlsx", base=root, label="tracker")
        if not root.is_dir() or not tracker.is_file():
            legacy.error("project root and tracker must exist")
        if not legacy_args.local_only and not legacy_args.capture_bundle:
            legacy.error("legacy audit mode requires --local-only or --capture-bundle")
        try:
            out_dir = ensure_safe_run_dir(root, legacy_args.out_dir, tracker)
            prep_result = prepare(root, tracker, out_dir, legacy_args.selected_id, legacy_args.latest_n)
            selection_path = resolve_path(prep_result["selection_path"])
            if legacy_args.local_only:
                audit = local_check(root, tracker, selection_path, out_dir)
                result = {"status": "LOCAL_CHECK_WRITTEN", "audit_path": str(out_dir / "audit.json"), "audit_sha256": audit["audit_sha256"], "mode": audit["mode"], "counts": audit["counts"]}
            else:
                capture_path = resolve_input_path(legacy_args.capture_bundle, label="capture bundle")
                audit = compare_capture(root, tracker, selection_path, capture_path, out_dir)
                result = {"status": "AUDIT_WRITTEN", "audit_path": str(out_dir / "audit.json"), "audit_sha256": audit["audit_sha256"], "mode": audit["mode"], "counts": audit["counts"]}
        except (OSError, ValueError, KeyError) as exc:
            legacy.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    args = parser.parse_args(argv)
    root = resolve_path(args.project_root)
    if not root.is_dir():
        parser.error(f"project root does not exist: {root}")
    tracker = resolve_input_path(args.tracker or "jobs.xlsx", base=root, label="tracker")
    if not tracker.is_relative_to(root):
        parser.error("tracker must be inside the selected workspace")
    if not tracker.is_file():
        parser.error(f"tracker does not exist: {tracker}")
    try:
        if args.phase == "prepare":
            out_dir = ensure_safe_run_dir(root, args.out_dir, tracker)
            result = prepare(root, tracker, out_dir, args.selected_id, args.latest_n)
        elif args.phase == "compare":
            out_dir = ensure_safe_run_dir(root, args.out_dir, tracker)
            capture_path = resolve_input_path(args.capture_bundle, label="capture bundle")
            if not capture_path.is_file() or capture_path.is_symlink():
                raise ValueError(f"capture bundle is not a regular file: {capture_path}")
            result = compare_capture(root, tracker, resolve_input_path(args.selection, label="selection"), capture_path, out_dir)
            result = {"status": "AUDIT_WRITTEN", "audit_path": str(out_dir / "audit.json"), "audit_sha256": result["audit_sha256"], "mode": result["mode"], "counts": result["counts"]}
        else:
            out_dir = ensure_safe_run_dir(root, args.out_dir, tracker)
            if args.selection:
                selection_path = resolve_input_path(args.selection, label="selection")
            else:
                if not args.selected_id and args.latest_n is None:
                    parser.error("local-check requires --selection or a selection option")
                prepare_result = prepare(root, tracker, out_dir, args.selected_id, args.latest_n)
                selection_path = resolve_input_path(prepare_result["selection_path"], label="selection")
            result = local_check(root, tracker, selection_path, out_dir)
            result = {"status": "LOCAL_CHECK_WRITTEN", "audit_path": str(out_dir / "audit.json"), "audit_sha256": result["audit_sha256"], "mode": result["mode"], "counts": result["counts"]}
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
