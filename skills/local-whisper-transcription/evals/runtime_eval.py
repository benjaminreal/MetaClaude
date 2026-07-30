#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


def run(*args: str, expected: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in expected:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write_srt(path: Path, segments: list[tuple[str, str, str]]) -> None:
    parts = []
    for index, (start, end, text) in enumerate(segments, start=1):
        parts.extend([str(index), f"{start} --> {end}", text, ""])
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        print("SKIP: ffmpeg and ffprobe are required for runtime eval")
        return 0

    checks: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(
        prefix="local-whisper-runtime-", dir="/private/tmp"
    ) as temp_dir:
        root = Path(temp_dir)
        source = root / "stereo.wav"
        run(
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=12:sample_rate=16000",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=12:sample_rate=16000",
            "-filter_complex",
            "[0:a]volume=0.5[left];[1:a]volume=0.03[right];"
            "[left][right]amerge=inputs=2[a]",
            "-map",
            "[a]",
            "-c:a",
            "pcm_s16le",
            str(source),
        )

        comparison_dir = root / "comparison"
        prepare_result = run(
            str(SCRIPTS / "channel_compare.py"),
            "prepare",
            "--input",
            str(source),
            "--output-dir",
            str(comparison_dir),
            "--sample-seconds",
            "3",
        )
        manifest_path = Path(prepare_result.stdout.strip())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks.append(("channel prepare finds stereo", manifest["source_channels"] == 2))
        checks.append(("channel prepare samples multiple positions", len(manifest["samples"]) == 6))

        for sample in manifest["samples"]:
            transcript = Path(f"{sample['transcript_prefix']}.txt")
            if sample["channel"] == 0:
                text = (
                    "The interview discusses product strategy, customer evidence, "
                    "delivery decisions, and measurable business outcomes."
                )
            else:
                text = "[Music] thank you for watching [Music] thank you for watching"
            transcript.write_text(text + "\n", encoding="utf-8")

        score_result = run(
            str(SCRIPTS / "channel_compare.py"),
            "score",
            "--manifest",
            str(manifest_path),
        )
        selection = json.loads(
            Path(score_result.stdout.strip()).read_text(encoding="utf-8")
        )
        checks.append(("channel scorer selects stronger evidence", selection["selected_channel"] == 0))
        manual_result = run(
            str(SCRIPTS / "channel_compare.py"),
            "score",
            "--manifest",
            str(manifest_path),
            "--output",
            str(comparison_dir / "manual_selection.json"),
            "--minimum-margin",
            "100",
            expected=(4,),
        )
        manual_selection = json.loads(
            Path(manual_result.stdout.strip()).read_text(encoding="utf-8")
        )
        checks.append(
            (
                "channel scorer preserves manual-review boundary",
                manual_selection["status"] == "manual_review_required"
                and manual_selection["selected_channel"] is None,
            )
        )

        rejected_chunks = run(
            str(SCRIPTS / "chunk_audio.py"),
            "--input",
            str(source),
            "--output-dir",
            str(root / "rejected_stereo_chunks"),
            "--chunk-seconds",
            "5",
            "--overlap-seconds",
            "1",
            expected=(1,),
        )
        checks.append(
            (
                "chunker rejects implicit stereo mixdown",
                "input is not mono" in rejected_chunks.stderr,
            )
        )

        mono = root / "selected.wav"
        run(
            str(SCRIPTS / "channel_compare.py"),
            "extract",
            "--input",
            str(source),
            "--channel",
            "0",
            "--output",
            str(mono),
        )
        probe = json.loads(
            run(
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=channels,sample_rate",
                "-of",
                "json",
                str(mono),
            ).stdout
        )
        checks.append(
            (
                "selected extraction is mono 16 kHz",
                probe["streams"][0]["channels"] == 1
                and probe["streams"][0]["sample_rate"] == "16000",
            )
        )

        chunks_dir = root / "chunks"
        chunk_result = run(
            str(SCRIPTS / "chunk_audio.py"),
            "--input",
            str(mono),
            "--output-dir",
            str(chunks_dir),
            "--chunk-seconds",
            "5",
            "--overlap-seconds",
            "1",
        )
        chunks_manifest_path = Path(chunk_result.stdout.strip())
        chunks_manifest = json.loads(
            chunks_manifest_path.read_text(encoding="utf-8")
        )
        chunks = chunks_manifest["chunks"]
        checks.append(("chunker creates three physical windows", len(chunks) == 3))
        checks.append(
            (
                "chunker records global offsets",
                [(item["start_ms"], item["end_ms"]) for item in chunks]
                == [(0, 5000), (4000, 9000), (8000, 12000)],
            )
        )
        checks.append(
            (
                "chunker retains hashes",
                bool(chunks_manifest["source_sha256"])
                and all(item["audio_sha256"] for item in chunks),
            )
        )

        write_srt(
            Path(f"{chunks[0]['transcript_prefix']}.srt"),
            [
                ("00:00:00,000", "00:00:02,000", "Welcome to the interview."),
                ("00:00:04,000", "00:00:05,000", "This overlap sentence."),
            ],
        )
        write_srt(
            Path(f"{chunks[1]['transcript_prefix']}.srt"),
            [
                ("00:00:00,000", "00:00:01,000", "This overlap sentence."),
                ("00:00:01,000", "00:00:03,000", "We discuss the next decision."),
                ("00:00:04,000", "00:00:05,000", "Second shared boundary."),
            ],
        )
        write_srt(
            Path(f"{chunks[2]['transcript_prefix']}.srt"),
            [
                ("00:00:00,000", "00:00:01,000", "Second shared boundary."),
                ("00:00:01,000", "00:00:03,000", "The call closes clearly."),
            ],
        )
        for chunk in chunks:
            Path(f"{chunk['transcript_prefix']}.txt").write_text(
                "fixture transcript\n", encoding="utf-8"
            )
            Path(f"{chunk['transcript_prefix']}.json").write_text(
                '{"fixture": true}\n', encoding="utf-8"
            )
        assembled_prefix = root / "assembled"
        run(
            str(SCRIPTS / "assemble_transcript.py"),
            "--manifest",
            str(chunks_manifest_path),
            "--output-prefix",
            str(assembled_prefix),
        )
        audit = json.loads(
            Path(f"{assembled_prefix}.json").read_text(encoding="utf-8")
        )
        checks.append(("assembler removes two overlap duplicates", audit["skipped_duplicate_count"] == 2))
        checks.append(("assembler has no ambiguous overlap in fixture", not audit["overlap_review_required"]))
        checks.append(
            (
                "assembler publishes four non-empty artifacts",
                all(
                    Path(f"{assembled_prefix}.{suffix}").stat().st_size > 0
                    for suffix in ("txt", "srt", "json", "md")
                ),
            )
        )

        fake_model = root / "ggml-small.bin"
        fake_model.write_bytes(b"model")
        policy = root / "policy.conf"
        policy.write_text(
            "\n".join(
                [
                    "version=1",
                    "whisper_cli=/usr/bin/true",
                    f"default_model={fake_model}",
                    f"allowed_root={root}",
                    f"allowed_model={fake_model}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        doctor_result = run(
            str(SCRIPTS / "doctor.py"),
            "--policy",
            str(policy),
            "--model-dir",
            str(root),
            "--json",
        )
        doctor = json.loads(doctor_result.stdout)
        checks.append(("doctor reports configured fixture ready", doctor["status"] == "ready"))
        checks.append(("doctor treats policy default as authoritative", doctor["recommendation"]["authoritative"]))
        absent_doctor_result = run(
            str(SCRIPTS / "doctor.py"),
            "--policy",
            str(root / "absent-policy.conf"),
            "--model-dir",
            str(root),
            "--json",
            expected=(3,),
        )
        absent_doctor = json.loads(absent_doctor_result.stdout)
        checks.append(
            (
                "doctor stops when local policy is absent",
                absent_doctor["status"] == "setup_required"
                and any("configure_local_policy" in action for action in absent_doctor["actions"]),
            )
        )

    failed = False
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
        failed = failed or not passed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
