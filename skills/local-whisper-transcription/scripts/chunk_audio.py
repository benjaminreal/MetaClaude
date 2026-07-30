#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def die(message: str) -> None:
    raise SystemExit(f"error: {message}")


def resolve_tool(explicit: str | None, name: str) -> str:
    path = explicit or shutil.which(name)
    if not path:
        die(f"{name} is not installed or not on PATH")
    return str(Path(path).resolve())


def probe_audio(ffprobe: str, source: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=channels,sample_rate:format=duration",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    if not streams:
        die("source has no audio stream")
    try:
        channels = int(streams[0]["channels"])
        duration = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        die("could not determine channel count and duration")
    return {
        "channels": channels,
        "sample_rate": int(streams[0].get("sample_rate") or 0),
        "duration_seconds": duration,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def windows(duration_ms: int, chunk_ms: int, overlap_ms: int) -> list[tuple[int, int]]:
    result = []
    start = 0
    step = chunk_ms - overlap_ms
    while start < duration_ms:
        end = min(duration_ms, start + chunk_ms)
        result.append((start, end))
        if end >= duration_ms:
            break
        start += step
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create auditable physical mono WAV chunks with global offsets."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="whisper_chunk")
    parser.add_argument("--chunk-seconds", type=float, default=370.0)
    parser.add_argument("--overlap-seconds", type=float, default=20.0)
    parser.add_argument(
        "--allow-mixdown",
        action="store_true",
        help="Explicitly allow stereo/multichannel mixdown instead of requiring selected mono.",
    )
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    args = parser.parse_args()

    if args.chunk_seconds <= 0:
        die("--chunk-seconds must be positive")
    if args.overlap_seconds < 0:
        die("--overlap-seconds cannot be negative")
    if args.overlap_seconds >= args.chunk_seconds:
        die("--overlap-seconds must be smaller than --chunk-seconds")
    if not args.prefix or "/" in args.prefix:
        die("--prefix must be a plain filename prefix")

    ffmpeg = resolve_tool(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_tool(args.ffprobe, "ffprobe")
    source = args.input.expanduser().resolve()
    if not source.is_file():
        die(f"input not found: {source}")
    metadata = probe_audio(ffprobe, source)
    if metadata["channels"] != 1 and not args.allow_mixdown:
        die(
            "input is not mono; select a channel first or explicitly pass --allow-mixdown"
        )

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "chunks.json"
    if manifest_path.exists() or manifest_path.is_symlink():
        die(f"manifest already exists: {manifest_path}")

    duration_ms = round(metadata["duration_seconds"] * 1000)
    chunk_ms = round(args.chunk_seconds * 1000)
    overlap_ms = round(args.overlap_seconds * 1000)
    planned = windows(duration_ms, chunk_ms, overlap_ms)
    final_paths = [
        output_dir
        / f"{args.prefix}_{index:03d}_{start:09d}-{end:09d}.wav"
        for index, (start, end) in enumerate(planned)
    ]
    for path in final_paths:
        if path.exists() or path.is_symlink():
            die(f"chunk output exists: {path}")

    stage_dir = Path(
        tempfile.mkdtemp(prefix=".chunk-stage-", dir=str(output_dir))
    ).resolve()
    chunks: list[dict[str, Any]] = []
    try:
        for index, ((start, end), final_path) in enumerate(zip(planned, final_paths)):
            staged_path = stage_dir / final_path.name
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source),
                    "-ss",
                    f"{start / 1000:.3f}",
                    "-t",
                    f"{(end - start) / 1000:.3f}",
                    "-map",
                    "0:a:0",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(staged_path),
                ],
                check=True,
            )
            chunks.append(
                {
                    "index": index,
                    "start_ms": start,
                    "end_ms": end,
                    "duration_ms": end - start,
                    "audio_file": str(final_path),
                    "audio_sha256": sha256(staged_path),
                    "transcript_prefix": str(final_path.with_suffix("")),
                }
            )

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "source": str(source),
            "source_sha256": sha256(source),
            "source_duration_ms": duration_ms,
            "source_channels": metadata["channels"],
            "mixdown_explicit": bool(args.allow_mixdown and metadata["channels"] != 1),
            "chunk_ms": chunk_ms,
            "overlap_ms": overlap_ms,
            "sample_rate": 16000,
            "format": "mono PCM16 WAV",
            "chunks": chunks,
        }
        staged_manifest = stage_dir / "chunks.json"
        staged_manifest.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        for staged_path, final_path in zip(
            [stage_dir / path.name for path in final_paths], final_paths
        ):
            os.replace(staged_path, final_path)
        os.replace(staged_manifest, manifest_path)
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)

    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
