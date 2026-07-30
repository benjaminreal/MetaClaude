#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MODEL_GLOBS = ("ggml-*.bin", "*.gguf")


def read_memory_bytes() -> int | None:
    if platform.system() == "Darwin":
        try:
            value = subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", "hw.memsize"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            return int(value)
        except (OSError, subprocess.SubprocessError, ValueError):
            try:
                payload = json.loads(
                    subprocess.check_output(
                        ["/usr/sbin/system_profiler", "SPHardwareDataType", "-json"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                )
                value = payload["SPHardwareDataType"][0]["physical_memory"]
                match = re.fullmatch(
                    r"\s*(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)\s*",
                    value,
                    flags=re.IGNORECASE,
                )
                if not match:
                    return None
                multipliers = {
                    "KB": 1024,
                    "MB": 1024**2,
                    "GB": 1024**3,
                    "TB": 1024**4,
                }
                return int(float(match.group(1)) * multipliers[match.group(2).upper()])
            except (
                OSError,
                subprocess.SubprocessError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                return None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                try:
                    return int(line.split()[1]) * 1024
                except (IndexError, ValueError):
                    return None
    return None


def parse_policy(path: Path) -> tuple[dict[str, Any], list[str]]:
    policy: dict[str, Any] = {
        "version": None,
        "whisper_cli": None,
        "default_model": None,
        "allowed_roots": [],
        "allowed_models": [],
    }
    errors: list[str] = []
    if not path.is_file():
        return policy, ["policy file is absent"]

    seen_singletons: set[str] = set()
    for number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line or raw_line.startswith("#"):
            continue
        if "=" not in raw_line:
            errors.append(f"line {number}: missing '='")
            continue
        key, value = raw_line.split("=", 1)
        if not value:
            errors.append(f"line {number}: empty value")
            continue
        if key in {"version", "whisper_cli", "default_model"}:
            if key in seen_singletons:
                errors.append(f"line {number}: duplicate {key}")
                continue
            seen_singletons.add(key)
            policy[key] = value
        elif key == "allowed_root":
            policy["allowed_roots"].append(value)
        elif key == "allowed_model":
            policy["allowed_models"].append(value)
        else:
            errors.append(f"line {number}: unknown key {key}")

    if policy["version"] != "1":
        errors.append("policy version must be 1")
    if not policy["whisper_cli"]:
        errors.append("whisper_cli is missing")
    if not policy["default_model"]:
        errors.append("default_model is missing")
    if not policy["allowed_roots"]:
        errors.append("no allowed_root entries")
    if not policy["allowed_models"]:
        errors.append("no allowed_model entries")

    for key in ("whisper_cli", "default_model"):
        value = policy[key]
        if value and not Path(value).is_file():
            errors.append(f"{key} does not exist: {value}")
    if policy["whisper_cli"] and Path(policy["whisper_cli"]).is_file():
        if not os.access(policy["whisper_cli"], os.X_OK):
            errors.append(f"whisper_cli is not executable: {policy['whisper_cli']}")
    for value in policy["allowed_roots"]:
        if not Path(value).is_dir():
            errors.append(f"allowed_root does not exist: {value}")
    for value in policy["allowed_models"]:
        if not Path(value).is_file():
            errors.append(f"allowed_model does not exist: {value}")
    if (
        policy["default_model"]
        and policy["allowed_models"]
        and policy["default_model"] not in policy["allowed_models"]
    ):
        errors.append("default_model is not included in allowed_model")
    return policy, errors


def classify_model(path: Path) -> dict[str, Any]:
    name = path.name.lower()
    if "large-v3-turbo" in name:
        family, quality = "large-v3-turbo", 95
    elif "large-v3" in name:
        family, quality = "large-v3", 100
    elif "large-v2" in name:
        family, quality = "large-v2", 93
    elif "large" in name:
        family, quality = "large", 90
    elif "medium" in name:
        family, quality = "medium", 80
    elif "small" in name:
        family, quality = "small", 65
    elif "base" in name:
        family, quality = "base", 45
    elif "tiny" in name:
        family, quality = "tiny", 25
    else:
        family, quality = "unknown", 0

    quantization = "full"
    penalty = 0
    for marker, marker_penalty in (
        ("q2", 15),
        ("q3", 11),
        ("q4", 8),
        ("q5", 4),
        ("q6", 3),
        ("q8", 1),
    ):
        if marker in name:
            quantization = marker
            penalty = marker_penalty
            break

    size = path.stat().st_size
    estimated_working_set = int(size * 1.35 + 768 * 1024 * 1024)
    return {
        "path": str(path),
        "filename": path.name,
        "size_bytes": size,
        "family": family,
        "quantization": quantization,
        "quality_rank": max(0, quality - penalty),
        "estimated_working_set_bytes": estimated_working_set,
    }


def discover_models(policy: dict[str, Any], extra_dirs: list[Path]) -> list[dict[str, Any]]:
    directories: list[Path] = [
        Path.home() / ".cache" / "whisper.cpp",
        Path.home() / ".cache" / "whisper",
        Path.home() / "Library" / "Caches" / "whisper.cpp",
    ]
    directories.extend(extra_dirs)
    for value in policy.get("allowed_models", []):
        directories.append(Path(value).expanduser().parent)

    candidates: dict[str, Path] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for pattern in MODEL_GLOBS:
            for path in directory.glob(pattern):
                if path.is_file():
                    try:
                        resolved = path.resolve()
                    except OSError:
                        continue
                    candidates[str(resolved)] = resolved
    return [classify_model(path) for path in candidates.values()]


def recommendation_score(model: dict[str, Any], preference: str) -> float:
    size_mb = max(1.0, model["size_bytes"] / (1024 * 1024))
    quality = float(model["quality_rank"])
    if preference == "quality":
        return quality
    if preference == "speed":
        return -size_mb
    turbo_bonus = 6.0 if model["family"] == "large-v3-turbo" else 0.0
    return quality + turbo_bonus - 7.0 * math.log2(max(1.0, size_mb / 500.0))


def tool_version(path: str | None, name: str) -> str | None:
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, "-version" if name in {"ffmpeg", "ffprobe"} else "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout + "\n" + result.stderr).strip().splitlines()
    return output[0] if result.returncode == 0 and output else None


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    policy_path = (
        args.policy.expanduser()
        if args.policy
        else Path.home() / ".config" / "local-whisper-transcription" / "policy.conf"
    )
    policy, policy_errors = parse_policy(policy_path)
    memory_bytes = read_memory_bytes()
    models = discover_models(policy, [path.expanduser() for path in args.model_dir])
    for model in models:
        model["fits_memory"] = (
            None
            if memory_bytes is None
            else model["estimated_working_set_bytes"] <= int(memory_bytes * 0.65)
        )

    dependencies = {}
    for name in ("ffmpeg", "ffprobe", "whisper-cli"):
        discovered = shutil.which(name)
        if name == "whisper-cli" and policy.get("whisper_cli"):
            configured = Path(policy["whisper_cli"])
            if configured.is_file() and os.access(configured, os.X_OK):
                discovered = str(configured)
        dependencies[name] = {
            "available": discovered is not None,
            "path": discovered,
            "version": tool_version(discovered, name),
        }

    default_model = policy.get("default_model")
    installed_by_path = {model["path"]: model for model in models}
    selected: dict[str, Any] | None = None
    reason = ""
    if not policy_errors and default_model:
        try:
            resolved_default = str(Path(default_model).resolve())
        except OSError:
            resolved_default = str(default_model)
        selected = installed_by_path.get(resolved_default)
        if selected:
            reason = "local policy default"

    if selected is None:
        fitting = [
            model
            for model in models
            if model["fits_memory"] is not False and model["family"] != "unknown"
        ]
        if fitting:
            selected = max(
                fitting,
                key=lambda model: recommendation_score(model, args.preference),
            )
            reason = (
                f"installed candidate for {args.preference} preference; "
                "configure it explicitly before inference"
            )

    actions: list[str] = []
    if not dependencies["ffmpeg"]["available"] or not dependencies["ffprobe"]["available"]:
        actions.append("Install a local ffmpeg distribution that provides ffmpeg and ffprobe.")
    if not dependencies["whisper-cli"]["available"]:
        actions.append("Install whisper.cpp locally; do not substitute a cloud transcription service.")
    if not models:
        actions.append("Obtain a verified local GGML/GGUF Whisper model from a trusted distribution.")
    if policy_errors:
        actions.append("Create or repair the owner-only local policy with configure_local_policy.sh.")
    if selected is None and models:
        actions.append("Review installed model compatibility and select an allowlisted default model.")
    if selected is not None and selected["fits_memory"] is False:
        actions.append(
            "The selected model exceeds the doctor's conservative memory-fit threshold; "
            "choose a smaller installed model or explicitly validate the risk."
        )

    ready = (
        all(item["available"] for item in dependencies.values())
        and not policy_errors
        and selected is not None
        and selected["fits_memory"] is not False
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if ready else "setup_required",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "memory_bytes": memory_bytes,
        },
        "dependencies": dependencies,
        "policy": {
            "path": str(policy_path),
            "present": policy_path.is_file(),
            "valid": not policy_errors,
            "errors": policy_errors,
            "default_model": default_model,
            "allowed_root_count": len(policy.get("allowed_roots", [])),
            "allowed_model_count": len(policy.get("allowed_models", [])),
        },
        "models": sorted(models, key=lambda item: item["quality_rank"], reverse=True),
        "recommendation": {
            "preference": args.preference,
            "model": selected,
            "reason": reason or None,
            "authoritative": reason == "local policy default",
            "boundary": (
                "Candidate ranking uses filename family, quantization marker, file size, "
                "and a conservative memory estimate; it is not a measured accuracy benchmark."
            ),
        },
        "actions": actions,
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    platform_info = report["platform"]
    memory = platform_info["memory_bytes"]
    memory_text = "unknown" if memory is None else f"{memory / (1024**3):.1f} GiB"
    print(
        "system: "
        f"{platform_info['system']} {platform_info['machine']} "
        f"(memory {memory_text})"
    )
    for name, state in report["dependencies"].items():
        print(f"{name}: {state['path'] if state['available'] else 'missing'}")
    policy = report["policy"]
    print(f"policy: {'valid' if policy['valid'] else 'needs setup'} ({policy['path']})")
    for error in policy["errors"]:
        print(f"  policy error: {error}")
    recommendation = report["recommendation"]
    if recommendation["model"]:
        marker = "selected" if recommendation["authoritative"] else "candidate"
        print(f"model {marker}: {recommendation['model']['path']}")
        print(f"reason: {recommendation['reason']}")
    else:
        print("model: no compatible installed candidate found")
    for action in report["actions"]:
        print(f"next: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose local Whisper readiness without installing or downloading anything."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        help="Read an explicit policy file for diagnostics.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        action="append",
        default=[],
        help="Add a directory to the read-only model scan.",
    )
    parser.add_argument(
        "--preference",
        choices=("quality", "balanced", "speed"),
        default="quality",
        help="Rank installed candidates when no valid policy default exists.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()
    report = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0 if report["status"] == "ready" else 3


if __name__ == "__main__":
    raise SystemExit(main())
