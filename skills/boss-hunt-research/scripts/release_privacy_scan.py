#!/usr/bin/env python3
"""Offline privacy, secret, and publication-surface scan for this skill tree."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IGNORED_PARTS = {"__pycache__", ".git", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
ALLOWED_EMAIL_DOMAINS = {"example.com", "example.net", "example.org", "example.invalid"}

EMAIL = re.compile(r"(?i)(?<![A-Z0-9._%+-])([A-Z0-9._%+-]+)@([A-Z0-9.-]+\.[A-Z]{2,})(?![A-Z0-9._%+-])")
POSIX_OWNER_HOME = re.compile("/" + r"(?:Users|home)/[^/\s`'\"]+/")
OWNER_VOLUME = re.compile("/" + r"Volumes/[^/\s`'\"]+/")
WINDOWS_OWNER_HOME = re.compile(r"(?i)[A-Z]:\\Users\\[^\\\r\n]+\\")
PRIVATE_KEY = re.compile("-" * 5 + r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY" + "-" * 5)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|password)"
    r"\s*[\"']?\s*[:=]\s*[\"'][^\"'\r\n]{8,}[\"']"
)
HIGH_SIGNAL_TOKEN = re.compile(
    r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9]{32,})"
)


def included_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES or relative == Path("INSTALL-METADATA.json"):
            continue
        files.append(path)
    return files


def finding(code: str, relative: Path, line: int | None, detail: str) -> dict[str, object]:
    return {"code": code, "path": relative.as_posix(), "line": line, "detail": detail}


def scan_text(relative: Path, text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for code, pattern, detail in (
            ("OWNER_LOCAL_PATH", POSIX_OWNER_HOME, "owner-specific POSIX home path"),
            ("OWNER_LOCAL_PATH", OWNER_VOLUME, "owner-specific mounted-volume path"),
            ("OWNER_LOCAL_PATH", WINDOWS_OWNER_HOME, "owner-specific Windows home path"),
            ("PRIVATE_KEY", PRIVATE_KEY, "private-key material"),
            ("SECRET_ASSIGNMENT", SECRET_ASSIGNMENT, "credential-like assignment"),
            ("HIGH_SIGNAL_TOKEN", HIGH_SIGNAL_TOKEN, "provider token shape"),
        ):
            if pattern.search(line):
                findings.append(finding(code, relative, line_number, detail))
        for match in EMAIL.finditer(line):
            domain = match.group(2).lower()
            if domain not in ALLOWED_EMAIL_DOMAINS:
                findings.append(finding("NON_SYNTHETIC_EMAIL", relative, line_number, f"email domain {domain}"))
    return findings


def scan_tree(root: Path = ROOT) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in included_files(root):
        relative = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(finding("NON_TEXT_FILE", relative, None, "publishable skill file is not UTF-8 text"))
            continue
        findings.extend(scan_text(relative, text))
    return findings


def untracked_publication_files(root: Path = ROOT) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--", "."],
        capture_output=True,
        check=True,
    )
    tracked = {
        Path(item.decode("utf-8")).as_posix()
        for item in completed.stdout.split(b"\0")
        if item
    }
    return [
        path.relative_to(root).as_posix()
        for path in included_files(root)
        if path.relative_to(root).as_posix() not in tracked
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-git-tracked", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    findings = scan_tree(root)
    if args.require_git_tracked:
        try:
            for relative in untracked_publication_files(root):
                findings.append(finding("UNTRACKED_PUBLICATION_FILE", Path(relative), None, "file is absent from the Git index"))
        except (OSError, subprocess.CalledProcessError) as exc:
            findings.append(finding("GIT_INVENTORY_FAILED", Path("."), None, str(exc)))
    report = {
        "schema_version": "BossHuntReleasePrivacyScanV1",
        "root": str(root),
        "files_scanned": len(included_files(root)),
        "result": "PASS" if not findings else "FAIL",
        "findings": findings,
        "limitations": [
            "Offline pattern scan; it does not prove absence of every sensitive datum.",
            "Reserved example domains are allowed as synthetic fixtures.",
            "Runtime debris and generated install metadata are excluded from publication scope.",
        ],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif findings:
        for item in findings:
            location = item["path"] + (f":{item['line']}" if item["line"] else "")
            print(f"FAIL {item['code']} {location}: {item['detail']}")
        print(f"FAIL: {len(findings)} finding(s) across {report['files_scanned']} files")
    else:
        print(f"PASS: {report['files_scanned']} publishable files; no owner-local paths, non-synthetic emails, private keys, credential assignments, or high-signal tokens")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
