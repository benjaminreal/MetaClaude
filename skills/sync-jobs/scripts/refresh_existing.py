#!/usr/bin/env python3
"""Preview and compare-and-swap refreshes of existing posting archives.

This module intentionally has no browser transport.  A fresh
``ExistingDescriptionAuditV1`` produced by :mod:`source_verification` is the
only source of proposed description bytes.  Preview writes evidence under a
run directory; commit consumes the immutable preview manifest and changes
only explicitly named Markdown archives and their evidence sidecars. Legacy
V1 manifests retain their original two-file authorization.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

import posting_compensation
import posting_eligibility
from acquisition_capture import revalidate_bundle
from source_verification import (
    AUDIT_SCHEMA,
    _archive_record,
    compare_bodies,
    _load_surfaces,
    _validate_fresh_record,
    digest,
    ensure_not_symlink,
    ensure_safe_run_dir,
    parse_timestamp,
    path_ref,
    read_json,
    sha256_bytes,
    sha256_file,
    tracker_hash,
    write_bytes_new_or_same,
)


PREVIEW_SCHEMA = "DescriptionRefreshPreviewManifestV1"
RECEIPT_SCHEMA = "DescriptionRefreshReceiptV1"
VERSION = "1.0"


class RefreshError(ValueError):
    """An input, identity, or transaction validation failure."""


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _rel(root: Path, path: Path) -> str:
    return path_ref(root, path)


def _lexical_path(value: str | Path, *, base: Path | None = None) -> Path:
    """Resolve ``.``/``..`` without following symlinks."""
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_chain(path: Path, *, stop: Path, label: str) -> None:
    """Reject symlink components in a workspace/run-local lexical path.

    The check intentionally stops at the already-resolved trusted boundary;
    it does not treat macOS's benign ``/var -> /private/var`` alias as a
    caller-controlled workspace component.
    """
    boundary = _lexical_path(stop)
    cursor = _lexical_path(path)
    while True:
        if cursor.exists() and cursor.is_symlink():
            raise RefreshError(f"{label} contains a symlink component: {cursor}")
        if cursor == boundary:
            return
        parent = cursor.parent
        if parent == cursor or not cursor.is_relative_to(boundary):
            raise RefreshError(f"{label} is outside its trusted boundary: {path}")
        cursor = parent


def _safe_regular(path: Path, label: str) -> None:
    ensure_not_symlink(path, label)
    if not path.is_file():
        raise RefreshError(f"{label} is not a regular file: {path}")


def _load_json_regular(path: Path, label: str) -> Any:
    _safe_regular(path, label)
    try:
        return read_json(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise RefreshError(f"invalid {label} {path}: {exc}") from exc


def _write_artifact(path: Path, value: Any) -> str:
    return write_bytes_new_or_same(path, _json_bytes(value))


def _audit_core(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != AUDIT_SCHEMA:
        raise RefreshError(f"audit must have schema {AUDIT_SCHEMA}")
    expected = payload.get("audit_sha256")
    core = {key: value for key, value in payload.items() if key != "audit_sha256"}
    if not _hex(expected) or digest(core) != expected:
        raise RefreshError("audit hash mismatch")
    if payload.get("mode") != "FRESH_CAPTURE_COMPARISON":
        raise RefreshError("refresh requires a fresh-capture audit; local-only validation cannot authorize refresh")
    if not isinstance(payload.get("results"), list) or not isinstance(payload.get("selected_ids"), list):
        raise RefreshError("audit must contain selected_ids and results")
    ids = [str(value) for value in payload["selected_ids"]]
    if len(ids) != len(set(ids)) or any(not value.isdigit() for value in ids):
        raise RefreshError("audit selected_ids must be unique numeric IDs")
    result_ids = [str(result.get("linkedin_id")) for result in payload["results"] if isinstance(result, dict)]
    if result_ids != ids:
        raise RefreshError("audit results must cover selected IDs exactly and in order")
    return payload


def _selection_for_audit(
    payload: dict[str, Any],
    audit_path: Path,
    root: Path,
    tracker: Path,
    *,
    require_current: bool = True,
) -> dict[str, Any]:
    """Load and bind the frozen SelectionV1 retained by a fresh audit.

    Refresh is deliberately selection-bound.  An audit that omits its frozen
    selection cannot authorize a body replacement, even if it happens to
    contain archive paths and hashes that look complete.  ``require_current``
    is relaxed only for an idempotent replay, after the receipt and target
    after-hashes have already been checked.
    """
    selection_ref = payload.get("selection_path")
    if not selection_ref:
        raise RefreshError("fresh audit does not retain its frozen selection manifest")
    candidate = _lexical_path(str(selection_ref), base=root)
    if candidate.is_relative_to(root):
        _reject_symlink_chain(candidate, stop=root, label="selection manifest path")
    if not candidate.is_file() or candidate.is_symlink():
        raise RefreshError(f"audit selection manifest is not a regular file: {candidate}")
    try:
        selection_value = read_json(candidate)
        from source_verification import _validate_selection

        if selection_value.get("selection_sha256") != payload.get("selection_sha256"):
            raise ValueError("selection hash does not match the audit")
        if [str(value) for value in selection_value.get("selected_ids", [])] != [str(value) for value in payload.get("selected_ids", [])]:
            raise ValueError("selection IDs do not match the audit")
        if require_current:
            selection = _validate_selection(selection_value, root, tracker)
        else:
            # The old archive hashes are expected to be stale after a
            # successful commit.  Still validate the manifest's own hash and
            # project/tracker binding before checking canonical identities.
            expected = selection_value.get("selection_sha256")
            core = {key: value for key, value in selection_value.items() if key != "selection_sha256"}
            if not isinstance(expected, str) or digest(core) != expected:
                raise ValueError("selection manifest hash mismatch")
            if str(selection_value.get("project_root")) != str(root.resolve()):
                raise ValueError("selection manifest belongs to another project root")
            if _lexical_path(str(selection_value.get("tracker_path") or ""), base=root) != _lexical_path(tracker):
                raise ValueError("selection tracker path mismatch")
            selection = selection_value
        rows, archives = _load_surfaces(root, tracker)
        for entry in selection.get("entries", []):
            jid = str(entry.get("linkedin_id"))
            if jid not in rows or jid not in archives:
                raise ValueError(f"{jid}: selection no longer resolves to one tracker/archive pair")
            archive_path = _lexical_path(str(entry.get("archive_path") or ""), base=root)
            # The shared surface loader may canonicalize paths while reading
            # them.  Check the frozen lexical path first so a live symlink
            # cannot be silently accepted as the selected archive.
            if archive_path.is_relative_to(root):
                _reject_symlink_chain(archive_path, stop=root, label=f"{jid} archive path")
            sidecar_path = _sidecar_path(root, entry)
            if sidecar_path.is_relative_to(root):
                _reject_symlink_chain(sidecar_path, stop=root, label=f"{jid} sidecar path")
            if archives[jid].resolve() != archive_path:
                raise ValueError(f"{jid}: selection archive path no longer matches canonical mapping")
            if str(rows[jid].get("Tracker ID") or "") != str(entry.get("tracker_id") or ""):
                raise ValueError(f"{jid}: selection Tracker ID no longer matches canonical mapping")
            if str(rows[jid].get("Puesto") or "") != str(entry.get("title") or "") or str(rows[jid].get("Empresa") or "") != str(entry.get("company") or ""):
                raise ValueError(f"{jid}: selection title/company no longer matches canonical mapping")
        return selection
    except (OSError, ValueError, KeyError) as exc:
        raise RefreshError(f"audit selection baseline is stale: {exc}") from exc


def _entry_map(selection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["linkedin_id"]): item for item in selection.get("entries", []) if isinstance(item, dict)}


def _result_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("linkedin_id")): item for item in payload.get("results", []) if isinstance(item, dict)}


def _selected_ids(payload: dict[str, Any], selected_ids: Iterable[str] | None, approve_all_substantive: bool) -> list[str]:
    explicit = [str(value) for value in (selected_ids or [])]
    if explicit and approve_all_substantive:
        raise RefreshError("provide selected IDs or --approve-all-substantive, not both")
    if explicit:
        if len(explicit) != len(set(explicit)) or any(not value.isdigit() for value in explicit):
            raise RefreshError("selected IDs must be unique numeric LinkedIn IDs")
        return explicit
    if not approve_all_substantive:
        raise RefreshError("refresh preview requires --selected-id or --approve-all-substantive")
    return [
        str(item.get("linkedin_id"))
        for item in payload.get("results", [])
        if isinstance(item, dict) and item.get("classification") == "substantive_difference"
    ]


def _validate_target_result(result: dict[str, Any], entry: dict[str, Any], root: Path) -> tuple[str, bytes]:
    jid = str(entry.get("linkedin_id") or "")
    if str(result.get("linkedin_id")) != jid:
        raise RefreshError(f"{jid}: audit result identity mismatch")
    if result.get("tracker_id") != entry.get("tracker_id") or result.get("title") != entry.get("title") or result.get("company") != entry.get("company"):
        raise RefreshError(f"{jid}: audit result metadata differs from frozen selection")
    if result.get("canonical_source_url") != entry.get("source_url"):
        raise RefreshError(f"{jid}: audit result source URL differs from frozen selection")
    if result.get("archive_path") and _lexical_path(str(result["archive_path"]), base=root) != _lexical_path(str(entry.get("archive_path") or ""), base=root):
        raise RefreshError(f"{jid}: audit result archive path differs from frozen selection")
    if result.get("archive_sha256") != entry.get("archive_sha256"):
        raise RefreshError(f"{jid}: audit result archive hash differs from frozen selection")
    if result.get("classification") != "substantive_difference":
        raise RefreshError(f"{jid}: refresh requires classification substantive_difference")
    if result.get("eligible_for_refresh") is not True:
        raise RefreshError(f"{jid}: audit result is not refresh eligible")
    if result.get("fresh_source_validated") is not True or result.get("completeness") is not True:
        raise RefreshError(f"{jid}: source capture is not complete and identity-bound")
    if result.get("source_state") != "verified" or result.get("capture_state") != "complete" or result.get("coverage_state") != "covered":
        raise RefreshError(f"{jid}: source/capture/coverage state cannot authorize refresh")
    live = result.get("live_description")
    if not isinstance(live, str):
        raise RefreshError(f"{jid}: audit does not contain the captured description bytes")
    actual_hash = sha256_bytes(live.encode("utf-8"))
    expected_hash = result.get("live_description_sha256")
    if not _hex(expected_hash) or expected_hash != actual_hash:
        raise RefreshError(f"{jid}: live description hash is missing or inconsistent")
    archive_path = _lexical_path(str(entry.get("archive_path") or result.get("archive_path") or ""), base=root)
    if not archive_path.is_file() or archive_path.is_symlink():
        raise RefreshError(f"{jid}: archive path is not a regular file: {archive_path}")
    archive = _archive_record(archive_path, jid, root=root)
    if compare_bodies(archive["body"], live).get("classification") != "substantive_difference":
        raise RefreshError(f"{jid}: audited source does not represent a substantive current archive difference")
    return actual_hash, live.encode("utf-8")


def _sidecar_path(root: Path, entry: dict[str, Any]) -> Path:
    value = entry.get("sidecar_path")
    if value:
        return _lexical_path(str(value), base=root)
    tracker_id = str(entry.get("tracker_id") or "")
    if not tracker_id:
        raise RefreshError(f"{entry.get('linkedin_id')}: tracker ID is missing")
    return _lexical_path(root / "JobPostings" / "_meta" / "compensation" / f"{tracker_id}_PostingCompensationV1.json")


def _validate_sidecar_identity(sidecar: dict[str, Any], sidecar_path: Path, *, root: Path, entry: dict[str, Any], archive_path: Path, archive_sha256: str) -> None:
    jid = str(entry.get("linkedin_id"))
    try:
        posting_compensation.validate(sidecar, verify_file=False)
    except (ValueError, KeyError, TypeError) as exc:
        raise RefreshError(f"{jid}: existing compensation sidecar is invalid: {exc}") from exc
    if sidecar.get("tracker_id") != entry.get("tracker_id"):
        raise RefreshError(f"{jid}: existing compensation sidecar has conflicting tracker identity")
    posting = sidecar.get("posting")
    if not isinstance(posting, dict):
        raise RefreshError(f"{jid}: existing compensation sidecar has no posting binding")
    bound_path = _lexical_path(str(posting.get("path") or ""), base=root)
    if bound_path != _lexical_path(archive_path):
        raise RefreshError(f"{jid}: existing compensation sidecar is bound to another archive")
    if posting.get("sha256") != archive_sha256:
        raise RefreshError(f"{jid}: existing compensation sidecar is stale for the current archive")
    expected_url = str(entry.get("source_url") or "")
    if posting.get("source_url") not in (None, "", expected_url):
        raise RefreshError(f"{jid}: existing compensation sidecar has conflicting source URL")


def _validate_sidecar_selection_baseline(sidecar_path: Path, entry: dict[str, Any]) -> str:
    expected = entry.get("sidecar_sha256")
    if not _hex(expected):
        raise RefreshError(f"{entry.get('linkedin_id')}: frozen selection has no valid existing sidecar hash")
    actual = sha256_file(sidecar_path)
    if actual != expected:
        raise RefreshError(f"{entry.get('linkedin_id')}: compensation sidecar changed since selection")
    return actual


def _extract_sidecar(full_text: str, archive_path: Path, entry: dict[str, Any], *, root: Path) -> dict[str, Any]:
    """Extract a sidecar against proposed full Markdown bytes.

    ``extract_text`` is used rather than ``extract_file`` so staging never
    points the parser at the canonical file before commit.  The parser's
    source-only interpretation boundary remains unchanged.
    """
    previous_root = posting_compensation.ROOT
    posting_compensation.ROOT = root
    try:
        result = posting_compensation.extract_text(
            full_text,
            posting_path=archive_path,
            tracker_id=str(entry["tracker_id"]),
            source_url=str(entry["source_url"]),
        )
    finally:
        posting_compensation.ROOT = previous_root
    posting_compensation.validate(result, verify_file=False)
    if result.get("posting", {}).get("sha256") != sha256_bytes(full_text.encode("utf-8")):
        raise RefreshError(f"{entry['linkedin_id']}: staged compensation binding does not match staged archive bytes")
    return result


def _sidecar_binding_valid(sidecar: dict[str, Any], *, full_bytes: bytes, archive_path: Path, entry: dict[str, Any]) -> None:
    posting = sidecar.get("posting")
    if not isinstance(posting, dict) or posting.get("sha256") != sha256_bytes(full_bytes):
        raise RefreshError(f"{entry['linkedin_id']}: compensation sidecar hash does not bind staged archive bytes")
    bound_path = _lexical_path(str(posting.get("path") or ""), base=archive_path.parents[2])
    if bound_path != _lexical_path(archive_path):
        raise RefreshError(f"{entry['linkedin_id']}: staged compensation path binding is inconsistent")
    if sidecar.get("tracker_id") != entry.get("tracker_id"):
        raise RefreshError(f"{entry['linkedin_id']}: staged compensation tracker identity is inconsistent")
    if posting.get("source_url") not in (None, "", entry.get("source_url")):
        raise RefreshError(f"{entry['linkedin_id']}: staged compensation source URL is inconsistent")


def _target_paths(root: Path, entry: dict[str, Any]) -> tuple[Path, Path]:
    archive_path = _lexical_path(str(entry.get("archive_path") or ""), base=root)
    sidecar_path = _sidecar_path(root, entry)
    if not archive_path.is_relative_to(root) or not sidecar_path.is_relative_to(root):
        raise RefreshError(f"{entry.get('linkedin_id')}: target path escapes project root")
    _reject_symlink_chain(archive_path, stop=root, label="archive path")
    _reject_symlink_chain(sidecar_path, stop=root, label="sidecar path")
    _safe_regular(archive_path, "archive")
    _safe_regular(sidecar_path, "compensation sidecar")
    return archive_path, sidecar_path


def _before_path(run_dir: Path, entry: dict[str, Any], suffix: str) -> Path:
    return run_dir / "before" / f"{entry['tracker_id']}{suffix}"


def _staged_path(run_dir: Path, entry: dict[str, Any], suffix: str) -> Path:
    return run_dir / "staged" / f"{entry['tracker_id']}{suffix}"


def _diff_text(old: bytes, new: bytes, label: str) -> str:
    old_text = old.decode("utf-8", errors="replace").splitlines(keepends=True)
    new_text = new.decode("utf-8", errors="replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(old_text, new_text, fromfile=f"{label} (before)", tofile=f"{label} (after)"))


def _write_diff(run_dir: Path, diffs: list[str]) -> Path:
    path = run_dir / "diff.md"
    body = "# Description refresh preview\n\n" + "\n".join(diffs)
    write_bytes_new_or_same(path, body.encode("utf-8"))
    return path


def _capture_bundle_for_audit(audit: dict[str, Any], audit_path: Path) -> tuple[Path, dict[str, Any]]:
    value = audit.get("capture_bundle_path")
    if not isinstance(value, str) or not value:
        raise RefreshError("audit has no capture bundle path")
    capture_path = _lexical_path(value, base=audit_path.parent)
    if capture_path.is_relative_to(audit_path.parent):
        _reject_symlink_chain(capture_path, stop=audit_path.parent, label="capture bundle path")
    _safe_regular(capture_path, "capture bundle")
    expected = audit.get("capture_bundle_sha256")
    if not _hex(expected) or sha256_file(capture_path) != expected:
        raise RefreshError("capture bundle hash is stale or missing")
    bundle = _load_json_regular(capture_path, "capture bundle")
    if not isinstance(bundle, dict):
        raise RefreshError("capture bundle must be an object")
    return capture_path, bundle


def _revalidate_capture_targets(
    audit: dict[str, Any],
    audit_path: Path,
    selection: dict[str, Any],
    selected: list[str],
) -> None:
    capture_path, bundle = _capture_bundle_for_audit(audit, audit_path)
    frozen_ids = {str(value) for value in audit.get("selected_ids", [])}
    try:
        # Revalidate against the complete frozen audit population first.  A
        # bundle may intentionally cover only part of it; asking the capture
        # validator to validate just the refresh subset would incorrectly
        # reject a valid bundle that also contains other selected IDs.
        normalized = revalidate_bundle(
            bundle,
            frozen_ids,
            allow_partial=True,
            require_normalized=True,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise RefreshError(f"capture bundle failed revalidation: {exc}") from exc
    records = {str(item.get("id")): item for item in normalized.get("records", []) if isinstance(item, dict)}
    entries = _entry_map(selection)
    try:
        selection_created = parse_timestamp(selection.get("created_at"), field="selection.created_at")
    except ValueError as exc:
        raise RefreshError(str(exc)) from exc
    results = _result_map(audit)
    for jid in selected:
        result = results.get(jid)
        record = records.get(jid)
        if record is None:
            raise RefreshError(f"{jid}: approved refresh lacks a revalidated capture record")
        entry = entries.get(jid)
        if entry is None:
            raise RefreshError(f"{jid}: approved refresh lacks a frozen selection entry")
        try:
            quality, gate_failure = _validate_fresh_record(record, entry, selection_created)
        except (ValueError, KeyError, TypeError) as exc:
            raise RefreshError(f"{jid}: fresh capture gate failed during commit revalidation: {exc}") from exc
        if gate_failure:
            raise RefreshError(f"{jid}: fresh capture gate failed during commit revalidation: {gate_failure}")
        # Recomputed quality and identity gates must agree with the audit.  An
        # edited audit cannot turn a capture with fabricated eligibility or a
        # missing end marker into refresh-ready evidence.
        if not isinstance(result, dict) or result.get("quality") != quality:
            raise RefreshError(f"{jid}: recomputed capture quality differs from audited quality")
        if str(record.get("title")) != str(entry.get("title")) or str(record.get("company")) != str(entry.get("company")):
            raise RefreshError(f"{jid}: revalidated capture identity differs from frozen selection")
        if record.get("description_sha256") != result.get("live_description_sha256"):
            raise RefreshError(f"{jid}: capture description hash differs from audited live bytes")
        if record.get("description") != result.get("live_description"):
            raise RefreshError(f"{jid}: capture description bytes differ from audited live bytes")
    # Keep this local variable use explicit: it makes the source bundle an
    # input to revalidation even when all selected records are already in the
    # audit result.
    _ = capture_path


def _population_entry(path: Path) -> dict[str, str | None]:
    """Describe one tracked population entry without following symlinks."""
    if path.is_symlink():
        try:
            target = os.readlink(path)
        except OSError:
            target = None
        return {
            "type": "symlink",
            "sha256": sha256_bytes(target.encode("utf-8")) if target is not None else None,
        }
    if path.is_file():
        return {"type": "file", "sha256": sha256_file(path)}
    if path.is_dir():
        return {"type": "directory", "sha256": None}
    return {"type": "other", "sha256": None}


def _snapshot_population(root: Path) -> dict[str, dict[str, str | None]]:
    """Describe the complete tracked posting/sidecar population."""
    result: dict[str, dict[str, str | None]] = {}
    for directory, pattern in (
        (root / "JobPostings" / "postings", "*.md"),
        (root / "JobPostings" / "_meta" / "compensation", "*.json"),
        (root / "JobPostings" / "_meta" / "eligibility", "*.json"),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob(pattern)):
            lexical = _lexical_path(path)
            try:
                key = lexical.relative_to(_lexical_path(root)).as_posix()
            except ValueError:
                key = str(lexical)
            result[key] = _population_entry(path)
    return result


def _expected_population_after(
    population_before: dict[str, dict[str, str | None]],
    targets: list[dict[str, Any]],
) -> dict[str, dict[str, str | None]]:
    expected = {key: dict(value) for key, value in population_before.items()}
    for target in targets:
        for kind in ("archive", "sidecar"):
            path_ref_value = str(target[f"{kind}_path"])
            expected[path_ref_value] = {"type": "file", "sha256": str(target[f"new_{kind}_sha256"])}
    return expected


def _append_journal(path: Path, event: dict[str, Any]) -> None:
    ensure_not_symlink(path, "refresh journal")
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSONL framing requires exactly one complete object per line.  Keep this
    # event compact so startup recovery can distinguish a torn final record.
    data = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _load_journal(path: Path) -> list[dict[str, Any]]:
    """Read a durable journal, rejecting a torn final event."""
    if not path.exists():
        return []
    _safe_regular(path, "refresh journal")
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise RefreshError("refresh journal has an incomplete final event")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RefreshError(f"refresh journal event {line_number} is invalid: {exc}") from exc
        if not isinstance(event, dict):
            raise RefreshError(f"refresh journal event {line_number} is not an object")
        events.append(event)
    return events


def _event(target: dict[str, Any], file_kind: str, state: str, **extra: Any) -> dict[str, Any]:
    value = {
        "at": _utc_now(),
        "linkedin_id": target.get("linkedin_id"),
        "tracker_id": target.get("tracker_id"),
        "file_kind": file_kind,
        "state": state,
    }
    value.update(extra)
    return value


def _receipt_core(*, manifest: dict[str, Any], status: str, events: list[dict[str, Any]], tracker_after: str | None, population_before: dict[str, Any] | None = None, population_after: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    core: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "version": VERSION,
        "created_at": _utc_now(),
        "preview_manifest_path": manifest.get("manifest_path"),
        "preview_manifest_sha256": manifest.get("manifest_sha256"),
        "tracker_path": manifest.get("tracker_path"),
        "tracker_sha256_before": manifest.get("tracker_sha256"),
        "tracker_sha256_after": tracker_after,
        "status": status,
        "events": events,
        "targets": manifest.get("targets", []),
        "population_before": population_before,
        "population_after": population_after,
    }
    if error:
        core["error"] = error
    core["receipt_sha256"] = digest(core)
    return core


def _write_receipt(run_dir: Path, receipt: dict[str, Any]) -> None:
    _write_artifact(run_dir / "receipt.json", receipt)


def _validate_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != RECEIPT_SCHEMA:
        raise RefreshError(f"refresh receipt must have schema {RECEIPT_SCHEMA}")
    expected = value.get("receipt_sha256")
    core = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if not _hex(expected) or digest(core) != expected:
        raise RefreshError("refresh receipt hash mismatch")
    return value


def _manifest_core(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != PREVIEW_SCHEMA:
        raise RefreshError(f"preview manifest must have schema {PREVIEW_SCHEMA}")
    expected = payload.get("manifest_sha256")
    core = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    if not _hex(expected) or digest(core) != expected:
        raise RefreshError("preview manifest hash mismatch")
    return payload


def _staged_files_exist(target: dict[str, Any], run_dir: Path) -> tuple[Path, Path, bytes, bytes]:
    run_dir = _lexical_path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise RefreshError(f"refresh run directory is not a regular directory: {run_dir}")
    try:
        archive_ref = Path(str(target["staged_archive_path"]))
        sidecar_ref = Path(str(target["staged_sidecar_path"]))
        if archive_ref.is_absolute() or sidecar_ref.is_absolute():
            raise ValueError("staged paths must be relative to the preview run")
        archive = _lexical_path(archive_ref, base=run_dir)
        sidecar = _lexical_path(sidecar_ref, base=run_dir)
        if not archive.is_relative_to(run_dir) or not sidecar.is_relative_to(run_dir):
            raise ValueError("staged path escapes the preview run")
        _reject_symlink_chain(archive, stop=run_dir, label="staged archive path")
        _reject_symlink_chain(sidecar, stop=run_dir, label="staged sidecar path")
    except (OSError, ValueError) as exc:
        raise RefreshError(f"{target.get('linkedin_id')}: invalid staged path: {exc}") from exc
    _safe_regular(archive, "staged archive")
    _safe_regular(sidecar, "staged compensation sidecar")
    archive_bytes = archive.read_bytes()
    sidecar_bytes = sidecar.read_bytes()
    if sha256_bytes(archive_bytes) != target.get("new_archive_sha256"):
        raise RefreshError(f"{target.get('linkedin_id')}: staged archive hash mismatch")
    if sha256_bytes(sidecar_bytes) != target.get("new_sidecar_sha256"):
        raise RefreshError(f"{target.get('linkedin_id')}: staged sidecar hash mismatch")
    return archive, sidecar, archive_bytes, sidecar_bytes


def _revalidate_manifest_inputs(root: Path, tracker: Path, manifest: dict[str, Any], audit: dict[str, Any], audit_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, str | None]]]:
    if manifest.get("project_root") != str(root.resolve()):
        raise RefreshError("preview manifest belongs to another project root")
    if _lexical_path(str(manifest.get("tracker_path") or ""), base=root) != _lexical_path(tracker):
        raise RefreshError("preview manifest tracker path mismatch")
    if manifest.get("tracker_sha256") != tracker_hash(tracker):
        raise RefreshError("tracker changed since refresh preview")
    if manifest.get("audit_sha256") != audit.get("audit_sha256"):
        raise RefreshError("audit changed since refresh preview")
    selection = _selection_for_audit(audit, audit_path, root, tracker)
    entries = _entry_map(selection)
    results = _result_map(audit)
    targets = manifest.get("targets")
    if not isinstance(targets, list) or not targets:
        raise RefreshError("preview manifest contains no targets")
    ids = [str(target.get("linkedin_id")) for target in targets if isinstance(target, dict)]
    if ids != [str(value) for value in manifest.get("selected_ids", [])] or len(ids) != len(set(ids)):
        raise RefreshError("preview target IDs are not unique or do not match selected_ids")
    audit_ids = set(str(value) for value in audit.get("selected_ids", []))
    if not set(ids).issubset(audit_ids):
        raise RefreshError("preview target is absent from the audit selection")
    _revalidate_capture_targets(audit, audit_path, selection, ids)
    current_population = _snapshot_population(root)
    for target in targets:
        jid = str(target.get("linkedin_id"))
        if jid not in entries or jid not in results:
            raise RefreshError(f"{jid}: preview target is absent from resolved audit data")
        entry = entries[jid]
        result = results[jid]
        expected_live, _ = _validate_target_result(result, entry, root)
        if target.get("live_description_sha256") != expected_live:
            raise RefreshError(f"{jid}: preview live-description hash differs from audit")
        archive_path, sidecar_path = _target_paths(root, entry)
        if _lexical_path(str(target.get("archive_path") or ""), base=root) != archive_path:
            raise RefreshError(f"{jid}: preview archive path differs from the canonical selection")
        if _lexical_path(str(target.get("sidecar_path") or ""), base=root) != sidecar_path:
            raise RefreshError(f"{jid}: preview sidecar path differs from the canonical selection")
        archive = _archive_record(archive_path, jid, root=root)
        if archive["archive_sha256"] != target.get("old_archive_sha256") or archive["archive_sha256"] != entry.get("archive_sha256"):
            raise RefreshError(f"{jid}: archive changed since refresh preview")
        if entry.get("archive_body_sha256") and archive["body_sha256"] != entry.get("archive_body_sha256"):
            raise RefreshError(f"{jid}: archive body changed since selection")
        if archive["title"] != entry.get("title") or archive["company"] != entry.get("company") or archive["url"] != entry.get("source_url"):
            raise RefreshError(f"{jid}: archive identity changed since refresh preview")
        sidecar = _load_json_regular(sidecar_path, "compensation sidecar")
        _validate_sidecar_identity(sidecar, sidecar_path, root=root, entry=entry, archive_path=archive_path, archive_sha256=archive["archive_sha256"])
        if sha256_file(sidecar_path) != target.get("old_sidecar_sha256"):
            raise RefreshError(f"{jid}: compensation sidecar changed since refresh preview")
        _validate_sidecar_selection_baseline(sidecar_path, entry)
        # The preview copies are immutable inputs.  Validate both their hashes
        # and their before snapshots before any live replacement is possible.
        before_archive_ref = Path(str(target.get("before_archive_path") or ""))
        before_sidecar_ref = Path(str(target.get("before_sidecar_path") or ""))
        run_path = _lexical_path(manifest["run_dir"])
        if run_path.is_symlink() or not run_path.is_dir():
            raise RefreshError(f"refresh run directory is not a regular directory: {run_path}")
        if before_archive_ref.is_absolute() or before_sidecar_ref.is_absolute():
            raise RefreshError(f"{jid}: before paths must be relative to the preview run")
        before_archive = _lexical_path(before_archive_ref, base=run_path)
        before_sidecar = _lexical_path(before_sidecar_ref, base=run_path)
        if not before_archive.is_relative_to(run_path) or not before_sidecar.is_relative_to(run_path):
            raise RefreshError(f"{jid}: before path escapes the preview run")
        _reject_symlink_chain(before_archive, stop=run_path, label="before archive path")
        _reject_symlink_chain(before_sidecar, stop=run_path, label="before sidecar path")
        _safe_regular(before_archive, "before archive")
        _safe_regular(before_sidecar, "before compensation sidecar")
        if sha256_file(before_archive) != target.get("old_archive_sha256") or sha256_file(before_sidecar) != target.get("old_sidecar_sha256"):
            raise RefreshError(f"{jid}: preview before copy hash mismatch")
        _staged_archive, staged_sidecar, staged_archive_bytes, staged_sidecar_bytes = _staged_files_exist(target, run_path)
        staged_sidecar_value = _load_json_regular(staged_sidecar, "staged compensation sidecar")
        posting_compensation.validate(staged_sidecar_value, verify_file=False)
        _sidecar_binding_valid(staged_sidecar_value, full_bytes=staged_archive_bytes, archive_path=archive_path, entry=entry)
        try:
            staged_body = staged_archive_bytes[len(archive["prefix"].encode("utf-8")) :]
        except (UnicodeError, TypeError) as exc:
            raise RefreshError(f"{jid}: staged archive bytes cannot be decoded: {exc}") from exc
        if not staged_archive_bytes.startswith(archive["prefix"].encode("utf-8")) or staged_body != str(result.get("live_description") or "").encode("utf-8"):
            raise RefreshError(f"{jid}: staged archive does not preserve header bytes")
    return targets, current_population


def _atomic_replace(path: Path, data: bytes) -> None:
    """Atomically replace one regular file after its caller's hash check.

    The function is deliberately a small seam for deterministic failure
    injection in tests; production has no failure-injection option.
    """
    ensure_not_symlink(path, "live target")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".refresh", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


# Public alias retained as an easy test seam and for callers that used the
# earlier draft name.
atomic_replace = _atomic_replace


def _restore_if_ours(path: Path, expected_new: str, old_bytes: bytes) -> tuple[bool, str | None]:
    try:
        if path.is_symlink() or not path.is_file():
            return False, "live target disappeared or became a symlink"
        current = sha256_file(path)
        if current != expected_new:
            return False, f"concurrent edit detected (current_sha256={current}, expected_new_sha256={expected_new})"
        _atomic_replace(path, old_bytes)
        if sha256_file(path) != sha256_bytes(old_bytes):
            return False, "rollback readback hash mismatch"
        return True, None
    except (OSError, ValueError, RuntimeError) as exc:
        return False, f"rollback replacement failed: {exc}"


def _already_applied(manifest: dict[str, Any], run_dir: Path) -> bool:
    """Retained as a cheap predicate; callers perform full replay validation."""
    targets = manifest.get("targets", [])
    if not targets:
        return False
    for target in targets:
        archive_path = _lexical_path(str(target.get("archive_path") or ""), base=Path(manifest["project_root"]))
        sidecar_path = _lexical_path(str(target.get("sidecar_path") or ""), base=Path(manifest["project_root"]))
        if not archive_path.is_file() or not sidecar_path.is_file() or archive_path.is_symlink() or sidecar_path.is_symlink():
            return False
        if sha256_file(archive_path) != target.get("new_archive_sha256") or sha256_file(sidecar_path) != target.get("new_sidecar_sha256"):
            return False
    return True


def _validate_already_applied(
    root: Path,
    tracker: Path,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    selection: dict[str, Any],
) -> None:
    """Validate every post-commit invariant before returning a replay."""
    if tracker_hash(tracker) != manifest.get("tracker_sha256"):
        raise RefreshError("tracker changed since refresh commit")
    if receipt.get("tracker_sha256_after") != manifest.get("tracker_sha256"):
        raise RefreshError("refresh receipt tracker hash does not match the manifest")
    expected_population = receipt.get("population_after")
    if not isinstance(expected_population, dict):
        raise RefreshError("refresh receipt has no complete post-commit population")
    if _snapshot_population(root) != expected_population:
        raise RefreshError("posting population changed since refresh commit")
    if receipt.get("targets") != manifest.get("targets"):
        raise RefreshError("refresh receipt targets differ from the preview manifest")
    targets = manifest.get("targets")
    selected_ids = [str(value) for value in manifest.get("selected_ids", [])]
    target_ids = [str(target.get("linkedin_id")) for target in targets if isinstance(target, dict)]
    if not isinstance(targets, list) or target_ids != selected_ids or len(target_ids) != len(set(target_ids)):
        raise RefreshError("preview target IDs are not unique or do not match selected_ids")
    entries = _entry_map(selection)
    for target in targets:
        jid = str(target.get("linkedin_id"))
        entry = entries.get(jid)
        if entry is None:
            raise RefreshError(f"{jid}: replay target is absent from the frozen selection")
        archive_path, sidecar_path = _target_paths(root, entry)
        if _lexical_path(str(target.get("archive_path") or ""), base=root) != archive_path:
            raise RefreshError(f"{jid}: replay archive path differs from the canonical selection")
        if _lexical_path(str(target.get("sidecar_path") or ""), base=root) != sidecar_path:
            raise RefreshError(f"{jid}: replay sidecar path differs from the canonical selection")
        archive = _archive_record(archive_path, jid, root=root)
        if archive["archive_sha256"] != target.get("new_archive_sha256") or archive["body_sha256"] != target.get("new_archive_body_sha256"):
            raise RefreshError(f"{jid}: replay archive bytes do not match the committed manifest")
        if archive["title"] != entry.get("title") or archive["company"] != entry.get("company") or archive["url"] != entry.get("source_url"):
            raise RefreshError(f"{jid}: replay archive identity does not match the frozen selection")
        sidecar = _load_json_regular(sidecar_path, "compensation sidecar")
        _validate_sidecar_identity(sidecar, sidecar_path, root=root, entry=entry, archive_path=archive_path, archive_sha256=archive["archive_sha256"])
        if sha256_file(sidecar_path) != target.get("new_sidecar_sha256"):
            raise RefreshError(f"{jid}: replay sidecar bytes do not match the committed manifest")
        _sidecar_binding_valid(sidecar, full_bytes=archive_path.read_bytes(), archive_path=archive_path, entry=entry)


def _recovery_before_bytes(target: dict[str, Any], run_dir: Path, kind: str) -> bytes:
    value = target.get(f"before_{kind}_path")
    if not isinstance(value, str) or not value:
        raise RefreshError(f"{target.get('linkedin_id')}: recovery backup path is missing")
    reference = Path(value)
    if reference.is_absolute():
        raise RefreshError(f"{target.get('linkedin_id')}: recovery backup path must be relative to the preview run")
    path = _lexical_path(reference, base=run_dir)
    if not path.is_relative_to(run_dir):
        raise RefreshError(f"{target.get('linkedin_id')}: recovery backup path escapes the preview run")
    _reject_symlink_chain(path, stop=run_dir, label="recovery backup path")
    _safe_regular(path, "recovery backup")
    data = path.read_bytes()
    expected = target.get(f"old_{kind}_sha256")
    if sha256_bytes(data) != expected:
        raise RefreshError(f"{target.get('linkedin_id')}: recovery backup hash mismatch")
    return data


def _recovery_live_path(root: Path, entry: dict[str, Any], kind: str) -> Path:
    value = entry.get("archive_path") if kind == "archive" else None
    path = _lexical_path(str(value or ""), base=root) if value else _sidecar_path(root, entry)
    if not path.is_relative_to(root):
        raise RefreshError(f"{entry.get('linkedin_id')}: recovery target escapes project root")
    return path


def _recover_interrupted(
    root: Path,
    tracker: Path,
    manifest: dict[str, Any],
    selection: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any] | None:
    """Recover a manifest whose durable journal has no terminal receipt."""
    journal_path = run_dir / "journal.jsonl"
    events = _load_journal(journal_path)
    if not events:
        return None
    if not any(event.get("state") in {"started", "planned", "staged", "backed_up", "replacing", "replaced", "verified", "failed", "recovery_started"} for event in events):
        return None
    started = next((event for event in events if event.get("state") == "started"), None)
    population_before = started.get("population_before") if isinstance(started, dict) else None
    if not isinstance(population_before, dict):
        raise RefreshError("interrupted refresh journal has no durable population baseline")
    if started.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise RefreshError("interrupted refresh journal belongs to another preview manifest")
    durable_intents = {
        (str(event.get("linkedin_id")), str(event.get("file_kind")))
        for event in events
        if event.get("state") in {"replacing", "replaced", "verified"}
    }
    manifest_targets = {
        str(target.get("linkedin_id")): target
        for target in manifest.get("targets", [])
        if isinstance(target, dict)
    }
    for event in events:
        if event.get("state") != "replacing":
            continue
        jid = str(event.get("linkedin_id"))
        kind = str(event.get("file_kind"))
        target = manifest_targets.get(jid)
        if target is None or kind not in {"archive", "sidecar"}:
            raise RefreshError("interrupted refresh journal has an unknown replacement intent")
        if (
            event.get("path") != target.get(f"{kind}_path")
            or event.get("before_path") != target.get(f"before_{kind}_path")
            or event.get("expected_old_sha256") != target.get(f"old_{kind}_sha256")
            or event.get("expected_new_sha256") != target.get(f"new_{kind}_sha256")
        ):
            raise RefreshError("interrupted refresh journal replacement intent does not match the manifest")
    recovery_events = list(events)
    marker = _event({}, "transaction", "recovery_started", manifest_sha256=manifest.get("manifest_sha256"))
    _append_journal(journal_path, marker)
    recovery_events.append(marker)
    entries = _entry_map(selection)
    conflicts: list[dict[str, Any]] = []
    targets = manifest.get("targets", [])
    for target in targets:
        jid = str(target.get("linkedin_id"))
        entry = entries.get(jid)
        if entry is None:
            conflicts.append({"linkedin_id": jid, "file_kind": "transaction", "error": "target is absent from the frozen selection"})
            continue
        for kind in ("archive", "sidecar"):
            try:
                path = _recovery_live_path(root, entry, kind)
                if path.is_symlink() or not path.is_file():
                    raise RefreshError("live target is missing or became a symlink")
                actual = sha256_file(path)
                old_hash = target.get(f"old_{kind}_sha256")
                new_hash = target.get(f"new_{kind}_sha256")
                if actual == old_hash:
                    continue
                if actual != new_hash:
                    raise RefreshError(f"current_sha256={actual}, expected_new_sha256={new_hash}")
                if (jid, kind) not in durable_intents:
                    raise RefreshError("current bytes match proposed output without a durable replacement intent")
                old_bytes = _recovery_before_bytes(target, run_dir, kind)
                ok, error = _restore_if_ours(path, str(new_hash), old_bytes)
                state = "rolled_back" if ok else "failed"
                event = _event(target, kind, state, recovery=True, error=error)
                _append_journal(journal_path, event)
                recovery_events.append(event)
                if not ok:
                    raise RefreshError(error or "recovery rollback failed")
            except (OSError, ValueError, RefreshError) as exc:
                conflicts.append({"linkedin_id": jid, "file_kind": kind, "error": str(exc)})
    population_after = _snapshot_population(root)
    tracker_changed = tracker_hash(tracker) != manifest.get("tracker_sha256")
    population_changed = population_after != population_before
    status = "partial_commit" if conflicts or tracker_changed or population_changed else "rolled_back"
    error_parts = ["recovered interrupted refresh"]
    if conflicts:
        error_parts.append("target conflict preserved")
    if tracker_changed:
        error_parts.append("tracker changed")
    if population_changed:
        error_parts.append("posting population changed")
    receipt = _receipt_core(
        manifest=manifest,
        status=status,
        events=recovery_events,
        tracker_after=tracker_hash(tracker),
        population_before=population_before,
        population_after=population_after,
        error="; ".join(error_parts),
    )
    if conflicts:
        receipt["recovery_conflicts"] = conflicts
        receipt["receipt_sha256"] = digest({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    _write_receipt(run_dir, receipt)
    return receipt


def _validate_manifest_target_paths(root: Path, manifest: dict[str, Any], selection: dict[str, Any]) -> None:
    """Bind every persisted target path to the current frozen selection."""
    entries = _entry_map(selection)
    targets = manifest.get("targets", [])
    for target in targets:
        jid = str(target.get("linkedin_id"))
        entry = entries.get(jid)
        if entry is None:
            raise RefreshError(f"{jid}: preview target is absent from the frozen selection")
        archive_path = _lexical_path(str(entry.get("archive_path") or ""), base=root)
        sidecar_path = _sidecar_path(root, entry)
        if _lexical_path(str(target.get("archive_path") or ""), base=root) != archive_path:
            raise RefreshError(f"{jid}: preview archive path differs from the canonical selection")
        if _lexical_path(str(target.get("sidecar_path") or ""), base=root) != sidecar_path:
            raise RefreshError(f"{jid}: preview sidecar path differs from the canonical selection")


def _preview_refresh_v1(
    *,
    root: Path,
    tracker: Path,
    audit_path: Path,
    out_dir: Path,
    selected_ids: list[str] | None = None,
    approve_all_substantive: bool = False,
) -> dict[str, Any]:
    """Create a reviewable, hash-bound refresh preview without live writes."""
    root = root.resolve()
    tracker = _lexical_path(tracker, base=root)
    _reject_symlink_chain(tracker, stop=root, label="tracker path")
    audit_path = _lexical_path(audit_path)
    if audit_path.is_relative_to(root):
        _reject_symlink_chain(audit_path, stop=root, label="audit path")
    out_dir = ensure_safe_run_dir(root, out_dir, tracker)
    audit = _audit_core(_load_json_regular(audit_path, "audit"))
    selection = _selection_for_audit(audit, audit_path, root, tracker)
    entries = _entry_map(selection)
    results = _result_map(audit)
    selected = _selected_ids(audit, selected_ids, approve_all_substantive)
    if not selected:
        raise RefreshError("refresh selection contains no substantive differences")
    for jid in selected:
        if jid not in entries or jid not in results:
            raise RefreshError(f"{jid}: selected ID is absent from fresh audit")
        _validate_target_result(results[jid], entries[jid], root)
    # Recheck the capture bundle and recompute its identity/quality gates before
    # creating any preview artifacts.  Preview is evidence preparation, but it
    # must not turn stale or fabricated audit booleans into a commit manifest.
    _revalidate_capture_targets(audit, audit_path, selection, selected)
    # Build every target from the same preflight snapshot.  No live file is
    # written until all target identities, sidecars and hashes pass.
    targets: list[dict[str, Any]] = []
    diffs: list[str] = []
    for jid in selected:
        entry = entries[jid]
        result = results[jid]
        archive_path, sidecar_path = _target_paths(root, entry)
        archive = _archive_record(archive_path, jid, root=root)
        if archive["archive_sha256"] != entry.get("archive_sha256"):
            raise RefreshError(f"{jid}: archive changed since audit; create a new audit/selection")
        if entry.get("archive_body_sha256") and archive["body_sha256"] != entry.get("archive_body_sha256"):
            raise RefreshError(f"{jid}: archive body changed since selection; create a new audit/selection")
        sidecar = _load_json_regular(sidecar_path, "compensation sidecar")
        _validate_sidecar_identity(sidecar, sidecar_path, root=root, entry=entry, archive_path=archive_path, archive_sha256=archive["archive_sha256"])
        _validate_sidecar_selection_baseline(sidecar_path, entry)
        live_hash, live_bytes = _validate_target_result(result, entry, root)
        final_bytes = archive["prefix"].encode("utf-8") + live_bytes
        # Header and source metadata are preserved by construction, while a
        # title/company mismatch was already rejected by the audit gates.
        sidecar_value = _extract_sidecar(final_bytes.decode("utf-8"), archive_path, entry, root=root)
        sidecar_bytes = _json_bytes(sidecar_value)
        before_archive = _before_path(out_dir, entry, ".md")
        before_sidecar = _before_path(out_dir, entry, "_PostingCompensationV1.json")
        staged_archive = _staged_path(out_dir, entry, ".md")
        staged_sidecar = _staged_path(out_dir, entry, "_PostingCompensationV1.json")
        write_bytes_new_or_same(before_archive, archive_path.read_bytes())
        write_bytes_new_or_same(before_sidecar, sidecar_path.read_bytes())
        write_bytes_new_or_same(staged_archive, final_bytes)
        write_bytes_new_or_same(staged_sidecar, sidecar_bytes)
        # Validate the exact staged bytes, including the parser binding.  This
        # catches a staging path or encoding mistake before a manifest exists.
        staged_sidecar_loaded = _load_json_regular(staged_sidecar, "staged sidecar")
        posting_compensation.validate(staged_sidecar_loaded, verify_file=False)
        _sidecar_binding_valid(staged_sidecar_loaded, full_bytes=final_bytes, archive_path=archive_path, entry=entry)
        target = {
            "linkedin_id": jid,
            "tracker_id": entry["tracker_id"],
            "title": entry["title"],
            "company": entry["company"],
            "source_url": entry["source_url"],
            "archive_path": _rel(root, archive_path),
            "sidecar_path": _rel(root, sidecar_path),
            "before_archive_path": str(before_archive.relative_to(out_dir).as_posix()),
            "before_sidecar_path": str(before_sidecar.relative_to(out_dir).as_posix()),
            "staged_archive_path": str(staged_archive.relative_to(out_dir).as_posix()),
            "staged_sidecar_path": str(staged_sidecar.relative_to(out_dir).as_posix()),
            "old_archive_sha256": archive["archive_sha256"],
            "new_archive_sha256": sha256_bytes(final_bytes),
            "old_archive_body_sha256": archive["body_sha256"],
            "new_archive_body_sha256": sha256_bytes(live_bytes),
            "old_sidecar_sha256": sha256_file(sidecar_path),
            "new_sidecar_sha256": sha256_bytes(sidecar_bytes),
            "live_description_sha256": live_hash,
            "capture_sha256": result.get("capture_sha256"),
            "capture_bundle_sha256": result.get("capture_bundle_sha256"),
            "header_sha256": archive["header_sha256"],
        }
        targets.append(target)
        diffs.append(_diff_text(archive_path.read_bytes(), final_bytes, _rel(root, archive_path)))
    selection_sha = audit.get("selection_sha256")
    core = {
        "schema": PREVIEW_SCHEMA,
        "version": VERSION,
        "created_at": _utc_now(),
        "project_root": str(root),
        "run_dir": str(out_dir),
        "tracker_path": _rel(root, tracker),
        "tracker_sha256": tracker_hash(tracker),
        "audit_path": str(audit_path),
        "audit_sha256": audit["audit_sha256"],
        "selection_sha256": selection_sha,
        "selected_ids": selected,
        "selection_basis": "explicit_selected_ids" if selected_ids else "all_substantive_difference_results",
        "targets": targets,
        "claims": {
            "preview_only": True,
            "tracker_write": False,
            "live_source_bytes_from_audit": True,
            "source_only_compensation_extraction": True,
        },
    }
    manifest = dict(core)
    manifest["manifest_sha256"] = digest(core)
    write_bytes_new_or_same(out_dir / "preview_manifest.json", _json_bytes(manifest))
    manifest_with_path = dict(manifest)
    manifest_with_path["manifest_path"] = str(out_dir / "preview_manifest.json")
    _write_diff(out_dir, diffs)
    receipt = {
        "schema": "DescriptionRefreshPreviewReceiptV1",
        "version": VERSION,
        "created_at": _utc_now(),
        "status": "PREVIEW_WRITTEN",
        "manifest_path": str(out_dir / "preview_manifest.json"),
        "manifest_sha256": manifest["manifest_sha256"],
        "audit_path": str(audit_path),
        "audit_sha256": audit["audit_sha256"],
        "selected_ids": selected,
        "targets": targets,
    }
    receipt["receipt_sha256"] = digest(receipt)
    _write_artifact(out_dir / "preview_receipt.json", receipt)
    return manifest_with_path


def _commit_refresh_v1(*, root: Path, tracker: Path, preview_manifest: Path, commit: bool = True) -> dict[str, Any]:
    """Apply an immutable preview manifest with per-file CAS and rollback."""
    if not commit:
        raise RefreshError("commit_refresh requires commit=True")
    root = root.resolve()
    tracker = _lexical_path(tracker, base=root)
    _reject_symlink_chain(tracker, stop=root, label="tracker path")
    manifest_path = _lexical_path(preview_manifest)
    if manifest_path.is_relative_to(root):
        _reject_symlink_chain(manifest_path, stop=root, label="preview manifest path")
    persisted_manifest = _manifest_core(_load_json_regular(manifest_path, "preview manifest"))
    manifest = dict(persisted_manifest)
    run_dir = _lexical_path(str(manifest.get("run_dir") or manifest_path.parent))
    if run_dir != _lexical_path(manifest_path.parent):
        raise RefreshError("preview manifest run directory does not match its file location")
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise RefreshError(f"refresh run directory is not a regular directory: {run_dir}")
    manifest["manifest_path"] = str(manifest_path)
    audit_path = _lexical_path(str(manifest.get("audit_path") or ""), base=root)
    audit = _audit_core(_load_json_regular(audit_path, "audit"))
    # Replaying a successful manifest is explicitly idempotent and does not
    # require treating already-replaced bytes as stale old inputs.  We still
    # bind paths to the self-hashed frozen selection before returning.
    selection_for_replay = _selection_for_audit(audit, audit_path, root, tracker, require_current=False)
    _validate_manifest_target_paths(root, manifest, selection_for_replay)
    receipt_path = run_dir / "receipt.json"
    if receipt_path.is_file() and not receipt_path.is_symlink():
        receipt = _validate_receipt(_load_json_regular(receipt_path, "refresh receipt"))
        if receipt.get("preview_manifest_sha256") != persisted_manifest.get("manifest_sha256"):
            raise RefreshError("refresh receipt belongs to another preview manifest")
        if receipt.get("status") in {"rolled_back", "partial_commit", "failed"}:
            return receipt
        if receipt.get("status") == "committed":
            _validate_already_applied(root, tracker, manifest, receipt, selection_for_replay)
            replay = {**receipt, "status": "already_applied", "idempotent_replay": True}
            replay["receipt_sha256"] = digest({key: value for key, value in replay.items() if key != "receipt_sha256"})
            return replay
    recovered = _recover_interrupted(root, tracker, manifest, selection_for_replay, run_dir)
    if recovered is not None:
        return recovered
    targets, population_before = _revalidate_manifest_inputs(root, tracker, manifest, audit, audit_path)
    journal_path = run_dir / "journal.jsonl"
    events: list[dict[str, Any]] = []
    started = _event(
        {},
        "transaction",
        "started",
        manifest_sha256=manifest.get("manifest_sha256"),
        population_before=population_before,
    )
    _append_journal(journal_path, started)
    events.append(started)
    for target in targets:
        for kind in ("archive", "sidecar"):
            item = _event(target, kind, "planned", expected_old_sha256=target[f"old_{kind}_sha256"], expected_new_sha256=target[f"new_{kind}_sha256"])
            _append_journal(journal_path, item)
            events.append(item)
        for kind in ("archive", "sidecar"):
            item = _event(target, kind, "staged", staged_path=target[f"staged_{kind}_path"])
            _append_journal(journal_path, item)
            events.append(item)
        for kind in ("archive", "sidecar"):
            item = _event(target, kind, "backed_up", before_path=target[f"before_{kind}_path"], before_sha256=target[f"old_{kind}_sha256"])
            _append_journal(journal_path, item)
            events.append(item)
    replaced: list[tuple[dict[str, Any], str, Path, bytes, str]] = []
    current_target: dict[str, Any] = targets[0] if targets else {}
    current_kind = "transaction"

    def rollback_result(error: str, *, force_partial: bool = False) -> dict[str, Any]:
        """Restore only bytes that still carry this run's replacement hash."""
        failed_event = _event(current_target, current_kind, "failed", error=error)
        _append_journal(journal_path, failed_event)
        events.append(failed_event)
        rollback_conflicts: list[dict[str, Any]] = []
        rollback_ok = True
        for target, kind, path, old_bytes, new_hash in reversed(replaced):
            ok, rollback_error = _restore_if_ours(path, new_hash, old_bytes)
            state = "rolled_back" if ok else "failed"
            rollback_event = _event(target, kind, state, error=rollback_error)
            _append_journal(journal_path, rollback_event)
            events.append(rollback_event)
            if not ok:
                rollback_ok = False
                rollback_conflicts.append({
                    "linkedin_id": target.get("linkedin_id"),
                    "file_kind": kind,
                    "path": str(path),
                    "error": rollback_error,
                })
        status = "rolled_back" if rollback_ok and not force_partial else "partial_commit"
        population_after = _snapshot_population(root)
        receipt = _receipt_core(
            manifest=manifest,
            status=status,
            events=events,
            tracker_after=tracker_hash(tracker),
            population_before=population_before,
            population_after=population_after,
            error=error,
        )
        if rollback_conflicts:
            receipt["rollback_conflicts"] = rollback_conflicts
            receipt["receipt_sha256"] = digest({key: value for key, value in receipt.items() if key != "receipt_sha256"})
        _write_receipt(run_dir, receipt)
        return receipt

    try:
        for target in targets:
            current_target = target
            archive_path = _lexical_path(target["archive_path"], base=root)
            sidecar_path = _lexical_path(target["sidecar_path"], base=root)
            staged_archive, staged_sidecar, archive_bytes, sidecar_bytes = _staged_files_exist(target, run_dir)
            for kind, path, data in (("archive", archive_path, archive_bytes), ("sidecar", sidecar_path, sidecar_bytes)):
                current_kind = kind
                _safe_regular(path, f"live {kind}")
                current_hash = sha256_file(path)
                expected_old = target[f"old_{kind}_sha256"]
                if current_hash != expected_old:
                    raise RefreshError(f"{target['linkedin_id']}: concurrent or stale {kind} before replacement")
                old_bytes = path.read_bytes()
                expected_new = target[f"new_{kind}_sha256"]
                replacing = _event(
                    target,
                    kind,
                    "replacing",
                    path=target[f"{kind}_path"],
                    before_path=target[f"before_{kind}_path"],
                    expected_old_sha256=expected_old,
                    expected_new_sha256=expected_new,
                )
                _append_journal(journal_path, replacing)
                events.append(replacing)
                try:
                    atomic_replace(path, data)
                except BaseException:
                    # A mocked or interrupted replacer can fail after its
                    # rename.  If the expected new bytes are now present,
                    # track that replacement before propagating the failure so
                    # rollback cannot leave an untracked mutation behind.
                    if path.is_file() and not path.is_symlink() and sha256_file(path) == expected_new:
                        replaced.append((target, kind, path, old_bytes, expected_new))
                    raise
                # Track the mutation immediately after the atomic rename and
                # before readback or journal I/O.  Any later failure therefore
                # has enough information to restore it safely.
                replaced.append((target, kind, path, old_bytes, expected_new))
                after = sha256_file(path)
                entry = _event(target, kind, "replaced", before_sha256=current_hash, after_sha256=after)
                _append_journal(journal_path, entry)
                events.append(entry)
                if after != expected_new:
                    raise RefreshError(f"{target['linkedin_id']}: {kind} replacement readback hash mismatch")
    except BaseException as exc:  # rollback is part of the transaction contract
        return rollback_result(str(exc))
    population_after = _snapshot_population(root)
    if tracker_hash(tracker) != manifest.get("tracker_sha256"):
        current_kind = "tracker"
        return rollback_result("tracker changed during refresh", force_partial=True)
    for target in targets:
        for kind in ("archive", "sidecar"):
            path = _lexical_path(target[f"{kind}_path"], base=root)
            expected = target[f"new_{kind}_sha256"]
            actual = sha256_file(path)
            if actual != expected:
                current_target = target
                current_kind = kind
                return rollback_result(f"post-commit hash mismatch: {actual}")
    # The complete tracked population must be unchanged except for the target
    # files' expected after-hashes.  This catches additions, removals, and type
    # changes while rollback only restores files replaced by this run.
    expected_population_after = _expected_population_after(population_before, targets)
    if population_after != expected_population_after:
        current_kind = "transaction"
        return rollback_result("posting population changed during refresh", force_partial=True)
    for target in targets:
        for kind in ("archive", "sidecar"):
            event = _event(target, kind, "verified", after_sha256=target[f"new_{kind}_sha256"])
            _append_journal(journal_path, event)
            events.append(event)
    receipt = _receipt_core(manifest=manifest, status="committed", events=events, tracker_after=tracker_hash(tracker), population_before=population_before, population_after=population_after)
    _write_receipt(run_dir, receipt)
    return receipt


V2_PREVIEW_SCHEMA = "DescriptionRefreshPreviewManifestV2"
V2_RECEIPT_SCHEMA = "DescriptionRefreshReceiptV2"

def _eligibility_path(root: Path, tracker_id: str) -> Path:
    return root / "JobPostings" / "_meta" / "eligibility" / f"{tracker_id}_PostingEligibilityV1.json"

def preview_refresh(**kwargs: Any) -> dict[str, Any]:
    """Build the reviewed three-file manifest while reusing v1 audit gates."""
    legacy = _preview_refresh_v1(**kwargs)
    root=Path(kwargs["root"]).resolve(); run_dir=Path(legacy["run_dir"])
    audit=_audit_core(_load_json_regular(Path(legacy["audit_path"]),"audit")); results=_result_map(audit)
    targets=[]
    for target in legacy["targets"]:
        jid=str(target["linkedin_id"]); tid=target["tracker_id"]
        staged_archive=run_dir/target["staged_archive_path"]; final_bytes=staged_archive.read_bytes(); text=final_bytes.decode("utf-8")
        eligibility_path=_eligibility_path(root,tid)
        before_exists=eligibility_path.exists()
        if before_exists and (eligibility_path.is_symlink() or not eligibility_path.is_file()): raise RefreshError(f"{jid}: eligibility target is not a regular file")
        if before_exists:
            previous_root=posting_eligibility.ROOT;posting_eligibility.ROOT=root
            try:
                existing=_load_json_regular(eligibility_path,"eligibility sidecar");posting_eligibility.validate(existing,verify_file=True)
            finally: posting_eligibility.ROOT=previous_root
            if existing.get("tracker_id")!=tid or existing.get("posting",{}).get("source_url")!=target["source_url"] or existing.get("posting",{}).get("linkedin_id")!=jid:
                raise RefreshError(f"{jid}: existing eligibility identity conflicts with selection")
        captured_at=results[jid].get("capture_timestamp")
        provenance=None
        if captured_at:
            marker=__import__('re').search(r"^## About the Job\s*\r?\n",text,__import__('re').M)
            archived_description=text[marker.end():].strip() if marker else text
            provenance={"captured_at":captured_at,"record_sha256":target["capture_bundle_sha256"],"linkedin_id":jid,"source_url":target["source_url"],"description_sha256":sha256_bytes(archived_description.encode("utf-8")),"kind":"validated_refresh_audit_bundle"}
        previous=posting_eligibility.ROOT;posting_eligibility.ROOT=root
        try:
            value=posting_eligibility.extract_text(text,posting_path=root/target["archive_path"],tracker_id=tid,source_url=target["source_url"],linkedin_id=jid,captured_at=captured_at,capture_provenance=provenance)
        finally: posting_eligibility.ROOT=previous
        data=_json_bytes(value); staged=run_dir/"staged"/f"{tid}_PostingEligibilityV1.json"
        write_bytes_new_or_same(staged,data)
        before_ref=None
        if before_exists:
            before=run_dir/"before"/f"{tid}_PostingEligibilityV1.json";write_bytes_new_or_same(before,eligibility_path.read_bytes());before_ref=before.relative_to(run_dir).as_posix()
        files=[
            {"kind":"archive","operation":"replace","path":target["archive_path"],"expected_old_state":"present","old_sha256":target["old_archive_sha256"],"new_sha256":target["new_archive_sha256"],"before_path":target["before_archive_path"],"staged_path":target["staged_archive_path"]},
            {"kind":"compensation","operation":"replace","path":target["sidecar_path"],"expected_old_state":"present","old_sha256":target["old_sidecar_sha256"],"new_sha256":target["new_sidecar_sha256"],"before_path":target["before_sidecar_path"],"staged_path":target["staged_sidecar_path"]},
            {"kind":"eligibility","operation":"replace" if before_exists else "create","path":_rel(root,eligibility_path),"expected_old_state":"present" if before_exists else "absent","old_sha256":sha256_file(eligibility_path) if before_exists else None,"new_sha256":sha256_bytes(data),"before_path":before_ref,"staged_path":staged.relative_to(run_dir).as_posix()},
        ]
        targets.append({**target,"eligibility_path":_rel(root,eligibility_path),"old_eligibility_sha256":sha256_file(eligibility_path) if before_exists else None,"new_eligibility_sha256":sha256_bytes(data),"staged_eligibility_path":staged.relative_to(run_dir).as_posix(),"before_eligibility_path":before_ref,"files":files})
    core={k:v for k,v in legacy.items() if k not in {"manifest_sha256","manifest_path","schema","version","targets","claims"}}
    core.update({"schema":V2_PREVIEW_SCHEMA,"version":"2.0","targets":targets,"population_before":_snapshot_population(root),"claims":{**legacy["claims"],"source_only_eligibility_extraction":True}})
    manifest={**core,"manifest_sha256":digest(core)}; path=run_dir/"preview_manifest.json";_atomic_replace(path,_json_bytes(manifest))
    preview_receipt={"schema":"DescriptionRefreshPreviewReceiptV2","version":"2.0","created_at":_utc_now(),"status":"PREVIEW_WRITTEN","manifest_path":str(path),"manifest_sha256":manifest["manifest_sha256"],"audit_path":str(kwargs["audit_path"]),"audit_sha256":manifest["audit_sha256"],"selected_ids":manifest["selected_ids"],"targets":targets}
    preview_receipt["receipt_sha256"]=digest(preview_receipt)
    _atomic_replace(run_dir/"preview_receipt.json",_json_bytes(preview_receipt))
    return {**manifest,"manifest_path":str(path)}

def _create_claim_path(run_dir: Path, path: Path, manifest_sha256: str) -> Path:
    return run_dir / "claims" / f"{path.name}.{manifest_sha256}.create-claim"

def _create_no_clobber(path: Path, data: bytes, claim: Path) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    claim.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(claim,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as h:h.write(data);h.flush();os.fsync(h.fileno())
        os.link(claim,path)
    except Exception:
        claim.unlink(missing_ok=True)
        raise

def _commit_refresh_v2(*, root: Path, tracker: Path, preview_manifest: Path) -> dict[str, Any]:
    root=root.resolve(); path=Path(preview_manifest); manifest=_load_json_regular(path,"preview manifest")
    expected=manifest.get("manifest_sha256");core={k:v for k,v in manifest.items() if k!="manifest_sha256"}
    if manifest.get("schema")!=V2_PREVIEW_SCHEMA or manifest.get("version")!="2.0" or digest(core)!=expected: raise RefreshError("invalid v2 preview manifest")
    if manifest.get("project_root")!=str(root) or tracker_hash(tracker)!=manifest.get("tracker_sha256"): raise RefreshError("refresh workspace/tracker baseline changed")
    run_dir=Path(manifest["run_dir"])
    if _lexical_path(run_dir)!=_lexical_path(path.parent) or run_dir.is_symlink() or not run_dir.is_dir(): raise RefreshError("v2 run_dir must equal manifest parent")
    receipt_path=run_dir/"receipt.json"; journal=run_dir/"journal.jsonl"
    def current(file):
        p=_lexical_path(file["path"],base=root)
        if not p.is_relative_to(root): raise RefreshError("refresh target escapes workspace")
        _reject_symlink_chain(p,stop=root,label="refresh target")
        return p
    def run_file(reference, label):
        ref=Path(str(reference or ""))
        if ref.is_absolute() or not str(reference or ""): raise RefreshError(f"{label} must be a relative run path")
        candidate=_lexical_path(ref,base=run_dir)
        if not candidate.is_relative_to(run_dir): raise RefreshError(f"{label} escapes preview run")
        _reject_symlink_chain(candidate,stop=run_dir,label=label)
        return candidate
    audit_path=_lexical_path(str(manifest.get("audit_path") or ""),base=root)
    audit=_audit_core(_load_json_regular(audit_path,"audit"))
    selection=_selection_for_audit(audit,audit_path,root,tracker,require_current=False);entries=_entry_map(selection)
    for target in manifest.get("targets",[]):
        entry=entries.get(str(target.get("linkedin_id")))
        if entry is None or entry.get("tracker_id")!=target.get("tracker_id"): raise RefreshError("v2 target is absent from frozen selection")
        canonical_archive,canonical_comp=_target_paths(root,entry)
        expected_paths={"archive":_rel(root,canonical_archive),"compensation":_rel(root,canonical_comp),"eligibility":_rel(root,_eligibility_path(root,target["tracker_id"]))}
        if target.get("archive_path")!=expected_paths["archive"] or target.get("sidecar_path")!=expected_paths["compensation"] or target.get("eligibility_path")!=expected_paths["eligibility"]: raise RefreshError("v2 target aliases differ from canonical selection")
        files=target.get("files")
        if not isinstance(files,list) or [f.get("kind") for f in files]!=["archive","compensation","eligibility"]: raise RefreshError("v2 target must authorize exactly archive, compensation, eligibility")
        for file in files:
            if file.get("path")!=expected_paths[file["kind"]]: raise RefreshError("descriptor path differs from canonical target")
            if file.get("operation") not in {"replace","create"} or file.get("expected_old_state") not in {"present","absent"}: raise RefreshError("invalid descriptor operation/state")
            run_file(file.get("staged_path"),"staged path")
            if file["operation"]=="replace": run_file(file.get("before_path"),"before path")
            elif file.get("before_path") is not None or file.get("old_sha256") is not None or file.get("expected_old_state")!="absent" or file["kind"]!="eligibility": raise RefreshError("only eligibility supports missing-before create")
    if receipt_path.exists():
        receipt=read_json(receipt_path)
        if receipt.get("schema")==V2_RECEIPT_SCHEMA:
            receipt_hash=receipt.get("receipt_sha256");receipt_core={k:v for k,v in receipt.items() if k!="receipt_sha256"}
            if digest(receipt_core)!=receipt_hash or receipt.get("preview_manifest_sha256")!=expected: raise RefreshError("refresh receipt hash or manifest binding mismatch")
            if receipt.get("status") in {"rolled_back","partial_commit","failed"}: return receipt
            if receipt.get("status")!="committed" or receipt.get("targets")!=manifest.get("targets"): raise RefreshError("unknown refresh receipt status or targets")
            for target in manifest["targets"]:
                for file in target["files"]:
                    p=current(file)
                    if not p.is_file() or p.is_symlink() or sha256_file(p)!=file["new_sha256"]: raise RefreshError("committed refresh replay target changed")
                    if file["operation"]=="create": _create_claim_path(run_dir,p,expected).unlink(missing_ok=True)
            if _snapshot_population(root)!=receipt.get("population_after"): raise RefreshError("posting population changed since refresh")
            replay={**receipt,"status":"already_applied","idempotent_replay":True};replay["receipt_sha256"]=digest({k:v for k,v in replay.items() if k!="receipt_sha256"});return replay
    prior=_load_journal(journal)
    if prior:
        started=next((event for event in prior if event.get("state")=="started"),None)
        if not started or started.get("manifest_sha256")!=expected: raise RefreshError("interrupted journal belongs to another manifest")
        intents={(e.get("linkedin_id"),e.get("file_kind")) for e in prior if e.get("state") in {"replacing","creating","replaced","created"}}
        conflicts=[]
        recovery_started={"state":"recovery_started","file_kind":"transaction","manifest_sha256":expected};_append_journal(journal,recovery_started);prior.append(recovery_started)
        for target in reversed(manifest["targets"]):
            for file in reversed(target["files"]):
                key=(target["linkedin_id"],file["kind"]);p=current(file)
                matching=[e for e in prior if (e.get("linkedin_id"),e.get("file_kind"))==key and e.get("state") in {"replacing","creating","replaced","created"}]
                for event in matching:
                    if event.get("path")!=file["path"] or event.get("expected_old_sha256")!=file["old_sha256"] or event.get("expected_new_sha256")!=file["new_sha256"] or event.get("expected_old_state")!=file["expected_old_state"]: raise RefreshError("journal intent differs from manifest descriptor")
                if key not in intents:
                    if p.is_file() and not p.is_symlink() and sha256_file(p)==file["new_sha256"]:
                        conflicts.append({"linkedin_id":target["linkedin_id"],"file_kind":file["kind"],"error":"new bytes exist without durable replacement intent"})
                    continue
                if file["expected_old_state"]=="present" and p.is_file() and not p.is_symlink() and sha256_file(p)==file["old_sha256"]: continue
                if file["expected_old_state"]=="absent" and not p.exists(): continue
                if p.is_file() and not p.is_symlink() and sha256_file(p)==file["new_sha256"]:
                    before_event={"state":"recovery_unlinking" if file["operation"]=="create" else "recovery_restoring","linkedin_id":target["linkedin_id"],"file_kind":file["kind"],"expected_new_sha256":file["new_sha256"]};_append_journal(journal,before_event);prior.append(before_event)
                    if file["operation"]=="create":
                        claim=_create_claim_path(run_dir,p,expected)
                        if not claim.is_file() or claim.is_symlink() or not os.path.samefile(claim,p):
                            conflicts.append({"linkedin_id":target["linkedin_id"],"file_kind":file["kind"],"error":"create ownership claim missing or mismatched"})
                            continue
                        p.unlink();claim.unlink()
                    else:
                        backup=run_file(file["before_path"],"recovery backup");_safe_regular(backup,"recovery backup")
                        old=backup.read_bytes()
                        if sha256_bytes(old)!=file["old_sha256"]: raise RefreshError("recovery backup hash mismatch")
                        atomic_replace(p,old)
                    after_event={"state":"rolled_back","linkedin_id":target["linkedin_id"],"file_kind":file["kind"],"recovery":True};_append_journal(journal,after_event);prior.append(after_event)
                elif file["operation"]=="create" and not p.exists(): continue
                else:
                    conflict={"linkedin_id":target["linkedin_id"],"file_kind":file["kind"],"error":"concurrent recovery conflict"};conflicts.append(conflict)
                    event={"state":"recovery_conflict",**conflict};_append_journal(journal,event);prior.append(event)
        status="partial_commit" if conflicts or _snapshot_population(root)!=manifest["population_before"] else "rolled_back"
        receipt={"schema":V2_RECEIPT_SCHEMA,"version":"2.0","status":status,"preview_manifest_sha256":expected,"events":prior,"population_before":manifest["population_before"],"population_after":_snapshot_population(root),"recovery_conflicts":conflicts}
        receipt["receipt_sha256"]=digest(receipt);_write_artifact(receipt_path,receipt);return receipt
    _revalidate_manifest_inputs(root,tracker,manifest,audit,audit_path)
    files=[]
    for target in manifest.get("targets",[]):
        kinds=[f.get("kind") for f in target.get("files",[])]
        if kinds!=["archive","compensation","eligibility"]: raise RefreshError("v2 target must authorize exactly archive, compensation, eligibility")
        for file in target["files"]:
            p=current(file); staged=run_file(file["staged_path"],"staged refresh file")
            _safe_regular(staged,"staged refresh file");data=staged.read_bytes()
            if sha256_bytes(data)!=file["new_sha256"]: raise RefreshError("staged refresh hash mismatch")
            if file["kind"]=="eligibility":
                staged_archive=run_file(target["files"][0]["staged_path"],"staged archive");archive_text=staged_archive.read_bytes().decode("utf-8")
                candidate=_load_json_regular(staged,"staged eligibility sidecar");posting_eligibility.validate(candidate,source_text=archive_text)
                if candidate.get("tracker_id")!=target["tracker_id"] or candidate.get("posting",{}).get("path")!=target["archive_path"] or candidate.get("posting",{}).get("source_url")!=target["source_url"] or candidate.get("posting",{}).get("linkedin_id")!=target["linkedin_id"]: raise RefreshError("staged eligibility binding mismatch")
            if file["expected_old_state"]=="absent":
                if p.exists(): raise RefreshError("eligibility absence CAS conflict")
            elif not p.is_file() or p.is_symlink() or sha256_file(p)!=file["old_sha256"]: raise RefreshError("refresh old-state CAS conflict")
            if file["operation"]=="replace":
                backup=run_file(file["before_path"],"before refresh file");_safe_regular(backup,"before refresh file")
                if sha256_file(backup)!=file["old_sha256"]: raise RefreshError("before refresh hash mismatch")
            if file["kind"]=="eligibility" and file["operation"]=="replace":
                previous=posting_eligibility.ROOT;posting_eligibility.ROOT=root
                try:
                    existing=_load_json_regular(p,"existing eligibility sidecar");posting_eligibility.validate(existing,verify_file=True)
                finally: posting_eligibility.ROOT=previous
                if existing.get("tracker_id")!=target["tracker_id"]: raise RefreshError("existing eligibility identity mismatch")
            files.append((target,file,p,data))
    population_before=_snapshot_population(root)
    if population_before!=manifest["population_before"]: raise RefreshError("posting population changed since preview")
    events=[];replaced=[]
    start={"state":"started","file_kind":"transaction","manifest_sha256":expected,"population_before":population_before};_append_journal(journal,start);events.append(start)
    for target,file,_p,_data in files:
        stages=[("planned",{"expected_old_state":file["expected_old_state"],"expected_old_sha256":file["old_sha256"],"expected_new_sha256":file["new_sha256"]}),
                ("staged",{"staged_path":file["staged_path"],"staged_sha256":file["new_sha256"]})]
        stages.append(("backed_up",{"before_path":file["before_path"],"before_sha256":file["old_sha256"]}) if file["operation"]=="replace" else ("absence_frozen",{"expected_old_state":"absent"}))
        for state,extra in stages:
            evidence={"state":state,"linkedin_id":target["linkedin_id"],"tracker_id":target["tracker_id"],"file_kind":file["kind"],**extra};_append_journal(journal,evidence);events.append(evidence)
    attempted=set()
    try:
        for target,file,p,data in files:
            state="creating" if file["operation"]=="create" else "replacing"
            event={"state":state,"linkedin_id":target["linkedin_id"],"tracker_id":target["tracker_id"],"file_kind":file["kind"],"path":file["path"],"expected_old_state":file["expected_old_state"],"expected_old_sha256":file["old_sha256"],"expected_new_sha256":file["new_sha256"]};_append_journal(journal,event);events.append(event)
            attempted.add((target["linkedin_id"],file["kind"]))
            if file["operation"]=="create":
                claim=_create_claim_path(run_dir,p,expected)
                event["claim_path"]=claim.relative_to(run_dir).as_posix()
                _create_no_clobber(p,data,claim);old=None
            else:
                if sha256_file(p)!=file["old_sha256"]: raise RefreshError("refresh concurrent CAS conflict")
                backup=run_file(file["before_path"],"before refresh file");_safe_regular(backup,"before refresh file");old=backup.read_bytes()
                if sha256_bytes(old)!=file["old_sha256"]: raise RefreshError("before refresh hash mismatch")
                atomic_replace(p,data)
            if sha256_file(p)!=file["new_sha256"]: raise RefreshError("refresh readback mismatch")
            replaced.append((file,p,old));done={**event,"state":"created" if file["operation"]=="create" else "replaced"};_append_journal(journal,done);events.append(done)
            verified={"state":"verified","linkedin_id":target["linkedin_id"],"tracker_id":target["tracker_id"],"file_kind":file["kind"],"after_sha256":file["new_sha256"]};_append_journal(journal,verified);events.append(verified)
        expected_population=dict(population_before)
        for _target,file,_p,_data in files: expected_population[file["path"]]={"type":"file","sha256":file["new_sha256"]}
        if tracker_hash(tracker)!=manifest["tracker_sha256"] or _snapshot_population(root)!=expected_population: raise RefreshError("tracker or posting population changed during refresh")
        for target in manifest["targets"]:
            archive=(root/target["archive_path"]).read_bytes()
            comp=_load_json_regular(root/target["sidecar_path"],"committed compensation");posting_compensation.validate(comp,verify_file=False);_sidecar_binding_valid(comp,full_bytes=archive,archive_path=root/target["archive_path"],entry=target)
            previous_root=posting_eligibility.ROOT;posting_eligibility.ROOT=root
            try: posting_eligibility.validate(_load_json_regular(root/target["eligibility_path"],"committed eligibility"),verify_file=True)
            finally: posting_eligibility.ROOT=previous_root
    except Exception as exc:
        # An injected failure may occur after the atomic rename but before the
        # replacement was added to the in-memory list. Recover those bytes by
        # the durable intent and exact proposed hash.
        for target,file,p,data in files:
            if any(existing[0] is file for existing in replaced): continue
            if (target["linkedin_id"],file["kind"]) not in attempted: continue
            if p.is_file() and not p.is_symlink() and sha256_file(p)==file["new_sha256"]:
                if file["operation"]=="create":
                    claim=_create_claim_path(run_dir,p,expected)
                    if not claim.is_file() or claim.is_symlink() or not os.path.samefile(claim,p): continue
                old=None if file["operation"]=="create" else run_file(file["before_path"],"rollback backup").read_bytes()
                if old is not None and sha256_bytes(old)!=file["old_sha256"]: continue
                replaced.append((file,p,old))
        conflicts=[]
        for file,p,old in reversed(replaced):
            if not p.is_file() or p.is_symlink() or sha256_file(p)!=file["new_sha256"]: conflicts.append({"file_kind":file["kind"],"error":"concurrent rollback conflict"});continue
            if file["operation"]=="create":
                p.unlink();_create_claim_path(run_dir,p,expected).unlink(missing_ok=True)
            else:atomic_replace(p,old)
            rolled={"state":"rolled_back","file_kind":file["kind"]};_append_journal(journal,rolled);events.append(rolled)
        status="partial_commit" if conflicts or _snapshot_population(root)!=population_before else "rolled_back"
        receipt={"schema":V2_RECEIPT_SCHEMA,"version":"2.0","status":status,"error":str(exc),"events":events,"preview_manifest_sha256":expected,"population_before":population_before,"population_after":_snapshot_population(root),"rollback_conflicts":conflicts};receipt["receipt_sha256"]=digest(receipt);_write_artifact(receipt_path,receipt);return receipt
    receipt={"schema":V2_RECEIPT_SCHEMA,"version":"2.0","status":"committed","events":events,"targets":manifest["targets"],"preview_manifest_sha256":expected,"tracker_sha256_before":manifest["tracker_sha256"],"tracker_sha256_after":tracker_hash(tracker),"population_before":population_before,"population_after":_snapshot_population(root)};receipt["receipt_sha256"]=digest(receipt);_write_artifact(receipt_path,receipt)
    for _target,file,p,_data in files:
        if file["operation"]=="create": _create_claim_path(run_dir,p,expected).unlink(missing_ok=True)
    return receipt

def commit_refresh(*, root: Path, tracker: Path, preview_manifest: Path, commit: bool = True) -> dict[str, Any]:
    if not commit: raise RefreshError("commit_refresh requires commit=True")
    value=_load_json_regular(Path(preview_manifest),"preview manifest")
    if value.get("schema")==V2_PREVIEW_SCHEMA and value.get("version")=="2.0": return _commit_refresh_v2(root=root,tracker=tracker,preview_manifest=preview_manifest)
    if value.get("schema")==PREVIEW_SCHEMA and value.get("version")==VERSION:
        for target in value.get("targets",[]):
            eligibility=_eligibility_path(root,target["tracker_id"])
            if eligibility.exists(): raise RefreshError("legacy v1 refresh cannot leave a present eligibility sidecar stale")
        return _commit_refresh_v1(root=root,tracker=tracker,preview_manifest=preview_manifest,commit=True)
    raise RefreshError("unknown or mixed refresh manifest version")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--tracker")
    parser.add_argument("--audit")
    parser.add_argument("--preview-manifest")
    parser.add_argument("--out-dir")
    parser.add_argument("--selected-id", action="append")
    parser.add_argument("--approve-all-substantive", action="store_true")
    parser.add_argument("--commit", action="store_true", help="apply the selected refresh preview; without it only stages reviewable files")
    args = parser.parse_args(argv)
    root = _lexical_path(args.project_root)
    if not root.is_dir():
        parser.error(f"project root does not exist: {root}")
    tracker = _lexical_path(args.tracker or "jobs.xlsx", base=root)
    if not tracker.is_file():
        parser.error(f"tracker does not exist: {tracker}")
    try:
        if args.commit:
            if not args.preview_manifest or args.audit or args.selected_id or args.approve_all_substantive:
                parser.error("--commit requires --preview-manifest and cannot combine with audit selection options")
            result = commit_refresh(root=root, tracker=tracker, preview_manifest=_lexical_path(args.preview_manifest), commit=True)
            if result.get("status") in {"rolled_back", "partial_commit", "failed"}:
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
                return 2
        else:
            if not args.audit or args.preview_manifest:
                parser.error("preview requires --audit and cannot take --preview-manifest")
            if not args.out_dir:
                parser.error("preview requires --out-dir")
            result = preview_refresh(
                root=root,
                tracker=tracker,
                audit_path=_lexical_path(args.audit),
                out_dir=_lexical_path(args.out_dir),
                selected_ids=args.selected_id,
                approve_all_substantive=args.approve_all_substantive,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, UnicodeError, RefreshError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
