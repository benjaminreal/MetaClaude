#!/usr/bin/env python3
"""Select an installed stable whisper.cpp CLI without loading a model."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MINIMUM_VERSION = (1, 9, 5)
MINIMUM_VERSION_TEXT = ".".join(map(str, MINIMUM_VERSION))


def installed_candidates() -> list[Path]:
    candidates = [Path(entry) / "whisper-cli" for entry in os.get_exec_path()]
    for prefix in (Path("/opt/homebrew"), Path("/usr/local"), Path.home() / ".linuxbrew"):
        for formula in ("whisper.cpp", "whisper-cpp"):
            candidates.append(prefix / "opt" / formula / "bin" / "whisper-cli")
            cellar = prefix / "Cellar" / formula
            if cellar.is_dir():
                candidates.extend(sorted(cellar.glob("*/bin/whisper-cli")))
    return candidates


def probe(path: Path) -> dict:
    result = {"path": str(path), "version": None, "eligible": False}
    try:
        resolved = path.expanduser().resolve(strict=True)
        result["path"] = str(resolved)
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise ValueError("not an executable file")
        output = subprocess.run([str(resolved), "--version"], capture_output=True,
                                text=True, timeout=10, check=False)
        if output.returncode != 0:
            raise ValueError("--version failed")
        # Require the CLI's version banner; reject unknown and prerelease builds.
        match = re.search(r"^whisper(?:\.cpp|-cli)\s+(?:version:?\s*)?v?"
                          r"(\d+)\.(\d+)\.(\d+)(?:\+[\w.]+)?\s*$",
                          output.stdout + "\n" + output.stderr, re.MULTILINE)
        if not match:
            raise ValueError("no recognized stable whisper.cpp version banner")
        version = tuple(map(int, match.groups()))
        result["version"] = ".".join(map(str, version))
        if version < MINIMUM_VERSION:
            raise ValueError(f"requires whisper.cpp >= {MINIMUM_VERSION_TEXT}")
        result["eligible"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
    return result


def select_runtime(configured: str = "auto") -> dict:
    paths = installed_candidates() if configured == "auto" else [
        Path(shutil.which(configured) or configured)]
    candidates = []
    seen = set()
    for path in paths:
        if configured == "auto" and (not path.is_file() or not os.access(path, os.X_OK)):
            continue
        try:
            identity = str(path.expanduser().resolve())
        except OSError:
            identity = str(path)
        if identity in seen:
            continue
        seen.add(identity)
        candidates.append(probe(path))
    eligible = [item for item in candidates if item["eligible"]]
    selected = max(eligible, key=lambda item: tuple(map(int, item["version"].split(".")))) if eligible else None
    return {"mode": "auto" if configured == "auto" else "pinned",
            "minimum_version": MINIMUM_VERSION_TEXT,
            "selected": selected, "candidates": candidates,
            "error": None if selected else f"No verified stable whisper.cpp >= {MINIMUM_VERSION_TEXT}; setup required."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configured", default="auto", help="auto or an explicit executable pin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = select_runtime(args.configured)
    if args.json:
        print(json.dumps(report, indent=2))
    elif report["selected"]:
        print(report["selected"]["path"])
        print(f"whisper.cpp version: {report['selected']['version']} ({report['mode']}); "
              f"executable: {report['selected']['path']}", file=sys.stderr)
    else:
        print(report["error"], file=sys.stderr)
    return 0 if report["selected"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
