#!/usr/bin/env python3
"""Command-line bridge for the session-skill runtime helpers.

The CLI keeps fragile filesystem and hashing work out of model-authored scratch
code. It has no network client and accepts evidence only as JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import helpers  # noqa: E402
import schemas  # noqa: E402


def _json_file(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser("snapshot", help="capture bounded local evidence")
    snapshot.add_argument("workspace_root")

    validate = commands.add_parser("validate", help="validate an evidence envelope")
    validate.add_argument("envelope_json")

    append = commands.add_parser("append", help="CAS append and journal a session entry")
    append.add_argument("envelope_json")
    append.add_argument("entry_markdown")

    audit = commands.add_parser("audit", help="audit session entries against the journal")
    audit.add_argument("workspace_root")

    sync = commands.add_parser("verify-sync", help="compare canonical and target trees")
    sync.add_argument("canonical_dir")
    sync.add_argument("target_dirs", nargs="+")

    rows = commands.add_parser("fingerprint-rows", help="fingerprint returned MCP rows")
    rows.add_argument("rows_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            result = helpers.capture_local_snapshot(args.workspace_root)
        elif args.command == "validate":
            envelope = _json_file(args.envelope_json)
            returned = envelope.get("returned_rows_by_capability") or {}
            result = schemas.validate_envelope(envelope, returned)
        elif args.command == "append":
            envelope = _json_file(args.envelope_json)
            entry = Path(args.entry_markdown).read_text(encoding="utf-8")
            result = helpers.append_session_entry(envelope, entry)
        elif args.command == "audit":
            result = helpers.audit_session_log(args.workspace_root)
        elif args.command == "verify-sync":
            result = helpers.verify_skill_sync(args.canonical_dir, args.target_dirs)
        elif args.command == "fingerprint-rows":
            rows = _json_file(args.rows_json)
            if not isinstance(rows, list):
                raise helpers.HelperError("EBADROWS", "rows JSON must contain a list")
            result = {
                "row_count": len(rows),
                "row_fingerprint": schemas.canonical_row_fingerprint(rows),
            }
        else:  # pragma: no cover - argparse prevents this branch
            raise AssertionError(args.command)
    except helpers.HelperError as exc:
        _emit({"ok": False, "error": {"code": exc.code, "detail": exc.detail}})
        return 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        _emit({"ok": False, "error": {"code": "EINPUT", "detail": str(exc)}})
        return 2

    _emit(result)
    if args.command == "validate" and not result["valid"]:
        return 1
    if args.command == "verify-sync" and not result["matches_all"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
