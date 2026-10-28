#!/usr/bin/env python3
"""Command-line bridge for the session-skill runtime helpers.

The CLI keeps fragile filesystem and hashing work out of model-authored scratch
code. It has no network client and accepts evidence only as JSON files, or as
JSON on stdin when the file argument is "-" (for harnesses that block scratch
writes).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import helpers  # noqa: E402
import schemas  # noqa: E402
import workflow


def _json_file(path: str) -> object:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _text_file(path: str, preserve_newlines: bool = False) -> str:
    if preserve_newlines:
        return (sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()).decode("utf-8")
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser("snapshot", help="capture bounded local evidence")
    snapshot.add_argument("workspace_root")
    snapshot.add_argument("--entries", type=int, default=2)
    constructor = commands.add_parser("new-envelope", help="capture incomplete envelope from package identity")
    constructor.add_argument("workspace_root")
    fingerprint = commands.add_parser("fingerprint-operation")
    fingerprint.add_argument("text_file")
    skip = commands.add_parser("skip-plan")
    skip.add_argument("names")
    resume = commands.add_parser("resume")
    resume.add_argument("workspace_root")
    resume.add_argument("approved_draft_json", nargs="?")
    resume.add_argument("--abandon")
    resume.add_argument("--owner-reply", default="")
    writer = commands.add_parser("write-approved")
    writer.add_argument("envelope_json")
    writer.add_argument("approved_draft_json")
    writer.add_argument("relative_path")
    writer.add_argument("content", nargs="?")
    writer.add_argument("--operation", choices=("replace", "delete", "stage"), default="replace")
    writer.add_argument("--expect", required=True)
    writer.add_argument("--mirror-rows")
    writer.add_argument("--owner-reply", default="")

    validate = commands.add_parser("validate", help="validate an evidence envelope")
    validate.add_argument("envelope_json")

    freeze = commands.add_parser("freeze-draft", help="bind draft snapshot and entry before showing the draft")
    freeze.add_argument("envelope_json")
    freeze.add_argument("entry_markdown", nargs="?")
    freeze.add_argument("index_markdown", nargs="?")
    freeze.add_argument("--index-draft")
    freeze.add_argument("--continue", dest="continue_parent")

    approve = commands.add_parser("approve-draft", help="stamp approval on a frozen draft (after explicit approval)")
    approve.add_argument("draft_receipt_json")
    approve.add_argument("scope_string")
    approve.add_argument("--owner-reply", default="")

    append = commands.add_parser("append", help="CAS append and journal a session entry")
    append.add_argument("envelope_json")
    append.add_argument("entry_markdown")
    append.add_argument("approved_draft_json")

    audit = commands.add_parser("audit", help="audit session entries against the journal")
    audit.add_argument("workspace_root")

    sync = commands.add_parser("verify-sync", help="compare canonical and target trees")
    sync.add_argument("canonical_dir")
    sync.add_argument("target_dirs", nargs="+")

    rows = commands.add_parser("fingerprint-rows", help="fingerprint returned MCP rows")
    rows.add_argument("rows_json")

    words = commands.add_parser("count-words", help="count words in a file or stdin (wc -w rule)")
    words.add_argument("text_file")

    mirror = commands.add_parser("render-mirror", help="render the Active TODOs mirror from receipt rows")
    mirror.add_argument("rows_json")
    mirror.add_argument("local_date")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        file_fields = ("envelope_json", "entry_markdown", "index_markdown", "index_draft", "draft_receipt_json", "approved_draft_json", "content", "mirror_rows", "rows_json", "text_file")
        if sum(getattr(args, field, None) == "-" for field in file_fields) > 1:
            raise helpers.HelperError("EINPUT", "one stdin argument per call")
        if args.command == "snapshot":
            result = helpers.capture_local_snapshot(args.workspace_root, entries=args.entries)
        elif args.command == "new-envelope":
            result = helpers.new_envelope(args.workspace_root)
        elif args.command == "fingerprint-operation":
            result = {"operation_fingerprint": schemas.fingerprint_operation(_text_file(args.text_file))}
        elif args.command == "skip-plan":
            result = workflow.plan_skip_paths({n.removeprefix("SKIP-") for n in args.names.split(",") if n})
        elif args.command == "resume":
            result = helpers.resume_append(args.workspace_root, _json_file(args.approved_draft_json) if args.approved_draft_json else None, args.abandon, args.owner_reply)
        elif args.command == "write-approved":
            result = helpers.write_approved_file(_json_file(args.envelope_json), _json_file(args.approved_draft_json), args.relative_path,
                       _text_file(args.content, preserve_newlines=args.operation == "stage") if args.content else None, args.operation, args.expect,
                       _json_file(args.mirror_rows) if args.mirror_rows else None, args.owner_reply)
        elif args.command == "validate":
            envelope = _json_file(args.envelope_json)
            returned = envelope.get("returned_rows_by_capability") or {}
            result = schemas.validate_envelope(envelope, returned)
        elif args.command == "freeze-draft":
            envelope = _json_file(args.envelope_json)
            entry = _text_file(args.entry_markdown) if args.entry_markdown else None
            index_arg = args.index_draft or args.index_markdown
            result = helpers.freeze_draft(envelope, entry, _text_file(index_arg) if index_arg else None, args.continue_parent)
        elif args.command == "approve-draft":
            result = helpers.approve_draft(_json_file(args.draft_receipt_json), args.scope_string, args.owner_reply)
        elif args.command == "append":
            envelope = _json_file(args.envelope_json)
            entry = _text_file(args.entry_markdown)
            result = helpers.append_session_entry(envelope, entry, _json_file(args.approved_draft_json))
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
                "fingerprinted_at": helpers._utc_now(),
            }
        elif args.command == "count-words":
            result = {"words": helpers.count_words(_text_file(args.text_file)), "rule": "whitespace-delimited"}
        elif args.command == "render-mirror":
            rows = _json_file(args.rows_json)
            result = {"markdown": helpers.render_task_mirror(rows, args.local_date)}
        else:  # pragma: no cover - argparse prevents this branch
            raise AssertionError(args.command)
    except helpers.HelperError as exc:
        _emit({"ok": False, "error": {"code": exc.code, "detail": exc.detail, **exc.context}})
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
