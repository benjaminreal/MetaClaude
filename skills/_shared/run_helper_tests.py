#!/usr/bin/env python3
"""Run the Phase 2 deterministic local-helper fixture gate."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import helper_fixtures  # noqa: E402


def run() -> int:
    print("=" * 66)
    print("Session-skill Phase 2 helper tests")
    print("=" * 66)
    problems: list[str] = []
    for label, check in helper_fixtures.CHECKS:
        current = check()
        problems.extend(f"{label}: {problem}" for problem in current)
        print(f"  [{'PASS' if not current else 'FAIL'}] {label}")
        for problem in current:
            print(f"        └─ {problem}")

    print("\n" + "=" * 66)
    if problems:
        print(f"PHASE 2 HELPER TESTS: FAILED ({len(problems)})")
        for problem in problems:
            print("  -", problem)
        return 1
    print("PHASE 2 HELPER TESTS: PASSED")
    print("  compare-and-swap, journal, audit, projection and deploy fixtures ✓")
    return 0


if __name__ == "__main__":
    sys.exit(run())
