#!/usr/bin/env python3
"""Copy the shared runtime and references into both deployable skills."""

from __future__ import annotations

import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
RUNTIME_FILES = ("helpers.py", "schemas.py", "runtime_cli.py", "workflow.py")
REFERENCE_FILES = (
    "runtime_contract.md",
    "task_operations.md",
    "candidate_quality_contract.md",
)
REFERENCE_OVERRIDES = {
    "newbeginning": {"task_operations.md": "task_operations_newbeginning.md"},
}


def reference_source(skill: str, name: str, shared: Path = HERE) -> Path:
    """Resolve common references and the opening skill's narrower task scope."""
    return shared / REFERENCE_OVERRIDES.get(skill, {}).get(name, name)


def sync(skills_root: Path = SKILLS) -> list[Path]:
    written: list[Path] = []
    shared = skills_root / "_shared"
    for skill in ("newbeginning", "closingtime"):
        scripts = skills_root / skill / "scripts"
        references = skills_root / skill / "references"
        scripts.mkdir(parents=True, exist_ok=True)
        references.mkdir(parents=True, exist_ok=True)
        for name in RUNTIME_FILES:
            target = scripts / name
            shutil.copy2(shared / name, target)
            written.append(target)
        for name in REFERENCE_FILES:
            target = references / name
            shutil.copy2(reference_source(skill, name, shared), target)
            written.append(target)
    return written


if __name__ == "__main__":
    for path in sync():
        print(path)
