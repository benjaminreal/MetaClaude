#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
CPU_RUNNER = SKILL_DIR / "scripts" / "run_whisper_chunk.sh"
METAL_RUNNER = SKILL_DIR / "scripts" / "run_whisper_metal_default.sh"
CONFIGURATOR = SKILL_DIR / "scripts" / "configure_local_policy.sh"
DOCTOR = SKILL_DIR / "scripts" / "doctor.py"
CHANNEL_COMPARE = SKILL_DIR / "scripts" / "channel_compare.py"
CHUNK_AUDIO = SKILL_DIR / "scripts" / "chunk_audio.py"
ASSEMBLER = SKILL_DIR / "scripts" / "assemble_transcript.py"


def cpu_dry_run(*extra: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="local-whisper-eval-") as temp_dir:
        root = Path(temp_dir)
        source = root / "input.wav"
        model = root / "model.bin"
        source.touch()
        model.touch()
        env = os.environ.copy()
        env["WHISPER_CLI"] = "/usr/bin/true"
        return subprocess.run(
            [
                str(CPU_RUNNER),
                "--input",
                str(source),
                "--model",
                str(model),
                "--output",
                str(root / "chunk_00"),
                "--dry-run",
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )


def main() -> int:
    checks: list[tuple[str, bool]] = []
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    metal_text = METAL_RUNNER.read_text(encoding="utf-8")

    checks.append(("skill defines purpose and scope", "## 1. Purpose and scope" in skill_text))
    checks.append(("skill defines preflight", "## 2. Preflight" in skill_text))
    checks.append(("skill defines workflow", "## 3. Workflow" in skill_text))
    checks.append(("skill defines harness adaptations", "## 4. Harness adaptations" in skill_text))
    checks.append(("skill defines decision rules", "## 5. Decision rules" in skill_text))
    checks.append(("skill defines evaluation criteria", "## 6. Evaluation criteria" in skill_text))
    checks.append(("skill defines transfer status", "## 7. Version and transfer status" in skill_text))
    checks.append(("skill keeps Metal optional", "must not become a correctness dependency" in skill_text))
    checks.append(
        (
            "skill scripts are executable",
            all(
                os.access(path, os.X_OK)
                for path in (
                    CPU_RUNNER,
                    METAL_RUNNER,
                    CONFIGURATOR,
                    DOCTOR,
                    CHANNEL_COMPARE,
                    CHUNK_AUDIO,
                    ASSEMBLER,
                )
            ),
        )
    )
    checks.append(("skill diagnoses before setup", "scripts/doctor.py --json" in skill_text))
    checks.append(("skill forbids implicit install/download", "Never install" in skill_text))
    checks.append(("skill requires channel margin", "score margin below 7" in skill_text))
    checks.append(("skill requires physical chunk manifest", "scripts/chunk_audio.py" in skill_text))
    checks.append(("skill requires structural SRT assembly", "scripts/assemble_transcript.py" in skill_text))
    # Shipped files must carry no machine-, user-, or project-specific path.
    # These patterns are deliberately generic: spelling out real directory or
    # account names here would publish exactly what the check exists to keep
    # out of the skill.
    private_path_patterns = (
        r"/Volumes/",              # mounted volume (external disk, sync root)
        r"/home/(?![$~{])",        # hardcoded POSIX home
        r"/Users/(?![$~{])",       # hardcoded macOS home; $(id -un), ${USER}, ~ are fine
        r"(?<![\w.])\d{2,}_[A-Za-z]",  # numbered project directory
    )
    shipped_texts = {path.name: path.read_text(encoding="utf-8") for path in
                     (METAL_RUNNER, CPU_RUNNER, CONFIGURATOR, DOCTOR,
                      CHANNEL_COMPARE, CHUNK_AUDIO, ASSEMBLER)}
    shipped_texts["SKILL.md"] = skill_text
    checks.append(
        (
            "shipped files contain no owner, machine, or project path",
            not [
                f"{name}:{pattern}"
                for name, text in shipped_texts.items()
                for pattern in private_path_patterns
                if re.search(pattern, text)
            ],
        )
    )

    cpu = cpu_dry_run()
    checks.append(("CPU dry run succeeds", cpu.returncode == 0))
    checks.append(("CPU dry run adds -ng", " -ng " in f" {cpu.stdout} "))
    checks.append(("CPU backend is disclosed", "backend: CPU (-ng)" in cpu.stderr))

    with tempfile.TemporaryDirectory(prefix="local-whisper-eval-", dir="/private/tmp") as temp_dir:
        root = Path(temp_dir)
        source = root / "input.wav"
        model = root / "model.bin"
        policy = root / "policy.conf"
        source.touch()
        model.touch()
        policy.write_text(
            "\n".join(
                [
                    "version=1",
                    "whisper_cli=/usr/bin/true",
                    f"default_model={model}",
                    f"allowed_root={root}",
                    f"allowed_model={model}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        safe = subprocess.run(
            [
                str(METAL_RUNNER),
                "--input",
                str(source),
                "--output",
                str(root / "chunk_00"),
                "--test-policy",
                str(policy),
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        lines = safe.stdout.splitlines()
        checks.append(("Metal-first dry run succeeds", safe.returncode == 0))
        checks.append(("Metal-first policy is disclosed", bool(lines) and "Metal-first with automatic CPU fallback" in lines[0]))
        checks.append(("Metal command omits -ng", len(lines) >= 2 and " -ng " not in f" {lines[1]} "))
        checks.append(("fallback command adds -ng", len(lines) >= 3 and " -ng " in f" {lines[2]} "))

        unsafe_option = subprocess.run(
            [
                str(METAL_RUNNER),
                "--input",
                str(source),
                "--output",
                str(root / "chunk_01"),
                "--test-policy",
                str(policy),
                "--dry-run",
                "--force",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        checks.append(("unsafe force option is rejected", unsafe_option.returncode == 2))

        unsafe_output = subprocess.run(
            [
                str(METAL_RUNNER),
                "--input",
                str(source),
                "--output",
                str(SKILL_DIR / "chunk_02"),
                "--test-policy",
                str(policy),
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        checks.append(("output outside policy is rejected", unsafe_output.returncode == 2))

        live_policy_override = subprocess.run(
            [
                str(METAL_RUNNER),
                "--input",
                str(source),
                "--output",
                str(root / "chunk_03"),
                "--test-policy",
                str(policy),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        checks.append(("test policy cannot execute inference", live_policy_override.returncode == 2))

    failed = False
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
        failed = failed or not passed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
