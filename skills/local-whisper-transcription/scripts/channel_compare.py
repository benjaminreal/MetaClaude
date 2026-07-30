#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TOKEN_RE = re.compile(r"[\wÀ-ÖØ-öø-ÿ']+", re.UNICODE)
HALLUCINATION_RE = re.compile(
    r"\b(music|música|musica|applause|aplausos|silence|silencio|"
    r"background music|subtitles?|suscr[ií]bete|thank you for watching)\b",
    re.IGNORECASE,
)


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
    if channels < 1 or duration <= 0:
        die("invalid audio metadata")
    return {
        "channels": channels,
        "duration_seconds": duration,
        "sample_rate": int(streams[0].get("sample_rate") or 0),
    }


def sample_starts(duration: float, sample_seconds: float) -> list[float]:
    if duration <= sample_seconds:
        return [0.0]
    if duration <= sample_seconds * 3:
        return [max(0.0, (duration - sample_seconds) / 2)]
    starts = []
    for fraction in (0.15, 0.50, 0.85):
        start = min(
            max(0.0, duration * fraction - sample_seconds / 2),
            duration - sample_seconds,
        )
        rounded = round(start, 3)
        if rounded not in starts:
            starts.append(rounded)
    return starts


def wav_metrics(path: Path) -> dict[str, float]:
    with wave.open(str(path), "rb") as handle:
        if (
            handle.getnchannels() != 1
            or handle.getsampwidth() != 2
            or handle.getcomptype() != "NONE"
        ):
            die(f"expected mono PCM16 WAV: {path}")
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if not frames:
        return {
            "rms_dbfs": -120.0,
            "peak_dbfs": -120.0,
            "active_ratio": 0.0,
            "clipping_ratio": 0.0,
            "signal_score": 0.0,
        }

    count = len(frames) // 2
    samples = struct.unpack(f"<{count}h", frames)
    sum_squares = sum(value * value for value in samples)
    rms = math.sqrt(sum_squares / max(1, count))
    peak = max(abs(value) for value in samples)
    clipping_ratio = sum(abs(value) >= 32700 for value in samples) / max(1, count)
    rms_dbfs = 20 * math.log10(max(rms, 1.0) / 32768)
    peak_dbfs = 20 * math.log10(max(peak, 1.0) / 32768)

    frame_size = max(1, int(sample_rate * 0.02))
    active = 0
    total_frames = 0
    for offset in range(0, count, frame_size):
        window = samples[offset : offset + frame_size]
        if not window:
            continue
        frame_rms = math.sqrt(sum(value * value for value in window) / len(window))
        frame_dbfs = 20 * math.log10(max(frame_rms, 1.0) / 32768)
        total_frames += 1
        if frame_dbfs > -45:
            active += 1
    active_ratio = active / max(1, total_frames)

    if -35 <= rms_dbfs <= -12:
        level_score = 30.0
    else:
        distance = min(abs(rms_dbfs + 35), abs(rms_dbfs + 12))
        level_score = max(0.0, 30.0 - distance * 1.5)
    signal_score = (
        min(50.0, active_ratio * 62.5)
        + level_score
        + max(0.0, 20.0 - clipping_ratio * 3000)
    )
    return {
        "rms_dbfs": round(rms_dbfs, 3),
        "peak_dbfs": round(peak_dbfs, 3),
        "active_ratio": round(active_ratio, 4),
        "clipping_ratio": round(clipping_ratio, 6),
        "signal_score": round(max(0.0, min(100.0, signal_score)), 3),
    }


def prepare(args: argparse.Namespace) -> int:
    ffmpeg = resolve_tool(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_tool(args.ffprobe, "ffprobe")
    source = args.input.expanduser().resolve()
    if not source.is_file():
        die(f"input not found: {source}")
    if args.sample_seconds <= 0:
        die("--sample-seconds must be positive")

    metadata = probe_audio(ffprobe, source)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "channel_samples.json"
    if manifest_path.exists():
        die(f"manifest already exists: {manifest_path}")

    starts = sample_starts(metadata["duration_seconds"], args.sample_seconds)
    samples: list[dict[str, Any]] = []
    for channel in range(metadata["channels"]):
        for sample_index, start in enumerate(starts):
            duration = min(args.sample_seconds, metadata["duration_seconds"] - start)
            basename = f"channel_{channel:02d}_sample_{sample_index:02d}"
            wav_path = output_dir / f"{basename}.wav"
            if wav_path.exists() or wav_path.is_symlink():
                die(f"sample output exists: {wav_path}")
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source),
                    "-ss",
                    f"{start:.3f}",
                    "-t",
                    f"{duration:.3f}",
                    "-map",
                    "0:a:0",
                    "-af",
                    f"pan=mono|c0=c{channel}",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wav_path),
                ],
                check=True,
            )
            samples.append(
                {
                    "channel": channel,
                    "sample_index": sample_index,
                    "start_ms": round(start * 1000),
                    "end_ms": round((start + duration) * 1000),
                    "audio_file": str(wav_path),
                    "transcript_prefix": str(wav_path.with_suffix("")),
                    "signal": wav_metrics(wav_path),
                }
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source": str(source),
        "source_duration_ms": round(metadata["duration_seconds"] * 1000),
        "source_channels": metadata["channels"],
        "sample_seconds": args.sample_seconds,
        "sample_positions": "centered at 15%, 50%, and 85% when duration permits",
        "samples": samples,
        "selection_status": (
            "mono_source" if metadata["channels"] == 1 else "needs_transcript_comparison"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


def text_metrics(text: str, duration_seconds: float) -> dict[str, float | int]:
    tokens = [token.casefold() for token in TOKEN_RE.findall(text)]
    trigrams = list(zip(tokens, tokens[1:], tokens[2:]))
    counts = Counter(trigrams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    repetition_ratio = repeated / max(1, len(trigrams))
    lexical_diversity = len(set(tokens)) / max(1, len(tokens))
    hallucination_markers = len(HALLUCINATION_RE.findall(text))
    marker_rate = hallucination_markers / max(1, len(tokens) / 100)
    chars_per_second = len(re.sub(r"\s+", "", text)) / max(1.0, duration_seconds)

    transcript_score = (
        min(1.0, chars_per_second / 8.0) * 35
        + lexical_diversity * 25
        + (1 - min(1.0, repetition_ratio)) * 25
        + (1 - min(1.0, marker_rate)) * 15
    )
    if len(tokens) < 3:
        transcript_score = 0.0
    return {
        "token_count": len(tokens),
        "chars_per_second": round(chars_per_second, 3),
        "lexical_diversity": round(lexical_diversity, 4),
        "repetition_ratio": round(repetition_ratio, 4),
        "hallucination_markers": hallucination_markers,
        "transcript_score": round(max(0.0, min(100.0, transcript_score)), 3),
    }


def score(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.expanduser().resolve()
    if not manifest_path.is_file():
        die(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    missing: list[str] = []
    for sample in manifest.get("samples", []):
        transcript = Path(f"{sample['transcript_prefix']}.txt")
        if not transcript.is_file():
            missing.append(str(transcript))
        groups[int(sample["channel"])].append(sample)
    if missing:
        die("missing sample transcripts: " + ", ".join(missing))

    channels = []
    for channel, samples in sorted(groups.items()):
        texts = []
        duration = 0.0
        for sample in samples:
            transcript = Path(f"{sample['transcript_prefix']}.txt")
            texts.append(transcript.read_text(encoding="utf-8", errors="replace"))
            duration += (sample["end_ms"] - sample["start_ms"]) / 1000
        transcript_metrics = text_metrics("\n".join(texts), duration)
        signal_score = sum(item["signal"]["signal_score"] for item in samples) / len(
            samples
        )
        combined = transcript_metrics["transcript_score"] * 0.8 + signal_score * 0.2
        channels.append(
            {
                "channel": channel,
                "sample_count": len(samples),
                "signal_score": round(signal_score, 3),
                "transcript": transcript_metrics,
                "combined_score": round(combined, 3),
            }
        )

    channels.sort(key=lambda item: item["combined_score"], reverse=True)
    if len(channels) == 1:
        status = "selected"
        selected_channel = channels[0]["channel"]
        margin = None
        reason = "mono source"
    else:
        margin = round(channels[0]["combined_score"] - channels[1]["combined_score"], 3)
        if margin >= args.minimum_margin:
            status = "selected"
            selected_channel = channels[0]["channel"]
            reason = (
                "heuristic score exceeds runner-up by "
                f"{margin:.3f}; spot-check before final use"
            )
        else:
            status = "manual_review_required"
            selected_channel = None
            reason = (
                f"score margin {margin:.3f} is below the "
                f"{args.minimum_margin:.3f} selection threshold"
            )

    output = (
        args.output.expanduser().resolve()
        if args.output
        else manifest_path.with_name("channel_selection.json")
    )
    if output.exists() or output.is_symlink():
        die(f"output exists: {output}")
    result = {
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "status": status,
        "selected_channel": selected_channel,
        "minimum_margin": args.minimum_margin,
        "observed_margin": margin,
        "reason": reason,
        "channels": channels,
        "boundary": (
            "Scores are triage heuristics, not speech-recognition accuracy proof. "
            "Review names, amounts, decisions, and hallucination-prone spans."
        ),
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if status == "selected" else 4


def extract(args: argparse.Namespace) -> int:
    ffmpeg = resolve_tool(args.ffmpeg, "ffmpeg")
    ffprobe = resolve_tool(args.ffprobe, "ffprobe")
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        die(f"input not found: {source}")
    if output.exists() or output.is_symlink():
        die(f"output exists: {output}")
    metadata = probe_audio(ffprobe, source)
    if args.channel < 0 or args.channel >= metadata["channels"]:
        die(
            f"--channel must be between 0 and {metadata['channels'] - 1} "
            f"for this source"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-af",
            f"pan=mono|c0=c{args.channel}",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        check=True,
    )
    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare, score, and extract deterministic stereo-channel comparisons."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_parser.add_argument("--sample-seconds", type=float, default=30.0)
    prepare_parser.add_argument("--ffmpeg")
    prepare_parser.add_argument("--ffprobe")
    prepare_parser.set_defaults(handler=prepare)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--manifest", type=Path, required=True)
    score_parser.add_argument("--output", type=Path)
    score_parser.add_argument("--minimum-margin", type=float, default=7.0)
    score_parser.set_defaults(handler=score)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--input", type=Path, required=True)
    extract_parser.add_argument("--channel", type=int, required=True)
    extract_parser.add_argument("--output", type=Path, required=True)
    extract_parser.add_argument("--ffmpeg")
    extract_parser.add_argument("--ffprobe")
    extract_parser.set_defaults(handler=extract)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except subprocess.CalledProcessError as error:
        print(f"error: media tool failed with exit {error.returncode}", file=sys.stderr)
        return error.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
