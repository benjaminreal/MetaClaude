#!/usr/bin/env python3
"""Verify frozen candidate identities; --write deliberately freezes new ones."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
SKILLS = SHARED.parent
sys.path.insert(0, str(SHARED))
import helpers  # noqa: E402


def identities() -> dict:
    result = {}
    for skill in ("newbeginning", "closingtime"):
        root = SKILLS / skill
        source = (root / "SKILL.md").read_text(encoding="utf-8")
        frontmatter, body = source.split("\n---", 1)
        version = re.search(r'version:\s*"([^"]+)"', frontmatter)
        if version is None:
            raise ValueError(f"{skill}: version absent")
        result[skill] = {
            "version": version.group(1),
            "candidate_tree_sha256": helpers._tree_hash(root),
            "instruction_bytes_loaded": len(body.lstrip("\n").encode("utf-8")),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "candidate_manifest.json"
    actual = identities()
    if args.write:
        path.write_text(json.dumps({"schema_version": "1.0", "candidates": actual}, indent=2) + "\n")
        print("Candidate identities frozen; earlier model evidence is not reused.")
        return 0
    expected = json.loads(path.read_text())["candidates"]
    matches = actual == expected
    print(json.dumps({"matches_frozen_candidates": matches, "candidates": actual}, indent=2))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
