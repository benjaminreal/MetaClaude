#!/usr/bin/env python3
"""Build one deterministic harness-specific Boss Hunt skill installation tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_VERSION = "1.2.9"
IGNORED_PARTS = {"__pycache__", ".git", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
CLAUDE_LOADER = Path("skills/boss-hunt-research/SKILL.md")
INSTALL_METADATA = Path("INSTALL-METADATA.json")
HARNESS_EXCLUSIONS = {
    "CODEX": {CLAUDE_LOADER},
    "CLAUDE_CODE": set(),
}


class InstallBuildError(ValueError):
    """A requested installation tree cannot be built safely."""


def included_files(root: Path, exclusions: set[Path] | None = None) -> list[Path]:
    exclusions = exclusions or set()
    files: list[Path] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if relative in exclusions:
            continue
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES:
            continue
        files.append(path)
    return files


def sha_tree(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    files = included_files(root)
    for path in files:
        relative = path.relative_to(root)
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    if not files:
        raise InstallBuildError(f"INSTALL_SOURCE empty: {root}")
    return "sha256:" + digest.hexdigest(), len(files)


def build(harness: str, output: Path) -> dict[str, object]:
    source = ROOT.resolve()
    output = output.resolve()
    if (source / INSTALL_METADATA).exists():
        raise InstallBuildError("INSTALL_SOURCE must be the canonical source tree, not a derived install")
    if output.exists():
        raise InstallBuildError(f"INSTALL output exists; refusing to overwrite: {output}")
    if source == output or source in output.parents:
        raise InstallBuildError("INSTALL output must be outside the canonical source tree")
    output.parent.mkdir(parents=True, exist_ok=True)
    exclusions = HARNESS_EXCLUSIONS[harness]
    source_sha, source_count = sha_tree(source)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        for path in included_files(source, exclusions):
            relative = path.relative_to(source)
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)

        skill_entries = sorted(str(path.relative_to(staging)) for path in staging.rglob("SKILL.md"))
        if harness == "CODEX":
            if skill_entries != ["SKILL.md"]:
                raise InstallBuildError(f"CODEX install must expose exactly canonical SKILL.md: {skill_entries}")
            if not (staging / "agents" / "openai.yaml").is_file():
                raise InstallBuildError("CODEX install lacks canonical agents/openai.yaml")
        elif CLAUDE_LOADER.as_posix() not in skill_entries:
            raise InstallBuildError("CLAUDE_CODE install lacks its nested skills-dir loader")

        install_metadata = {
            "schema_version": "BossHuntHarnessInstallMetadataV1",
            "candidate_version": CANDIDATE_VERSION,
            "harness": harness,
            "source_sha256": source_sha,
            "source_file_count": source_count,
            "excluded_files": sorted(str(path) for path in exclusions),
            "skill_entries": skill_entries,
        }
        (staging / INSTALL_METADATA).write_text(
            json.dumps(install_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        staging.rename(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    install_sha, install_count = sha_tree(output)
    return {
        "schema_version": "BossHuntHarnessInstallBuildV1",
        "candidate_version": CANDIDATE_VERSION,
        "harness": harness,
        "source_root": str(source),
        "source_sha256": source_sha,
        "source_file_count": source_count,
        "output_root": str(output),
        "install_sha256": install_sha,
        "install_file_count": install_count,
        "excluded_files": sorted(str(path) for path in exclusions),
        "skill_entries": skill_entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", required=True, choices=sorted(HARNESS_EXCLUSIONS))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        manifest = args.manifest_output.resolve() if args.manifest_output else None
        if manifest:
            if manifest.exists():
                raise InstallBuildError(f"INSTALL manifest exists; refusing to overwrite: {manifest}")
            if manifest == output or output in manifest.parents:
                raise InstallBuildError("INSTALL manifest must be outside the output tree")
            source = ROOT.resolve()
            if manifest == source or source in manifest.parents:
                raise InstallBuildError("INSTALL manifest must be outside the canonical source tree")
        result = build(args.harness, args.output)
        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if manifest:
            manifest.parent.mkdir(parents=True, exist_ok=True)
            try:
                manifest.write_text(payload, encoding="utf-8")
            except OSError:
                shutil.rmtree(output, ignore_errors=True)
                raise
        print(payload, end="")
    except (OSError, InstallBuildError) as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
