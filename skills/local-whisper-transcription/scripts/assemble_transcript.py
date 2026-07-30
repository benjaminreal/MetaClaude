#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TIMECODE_RE = re.compile(
    r"^(?P<sh>\d{2,}):(?P<sm>\d{2}):(?P<ss>\d{2})[,.](?P<sms>\d{3})"
    r"\s+-->\s+"
    r"(?P<eh>\d{2,}):(?P<em>\d{2}):(?P<es>\d{2})[,.](?P<ems>\d{3})"
)


def die(message: str) -> None:
    raise SystemExit(f"error: {message}")


def to_ms(hours: str, minutes: str, seconds: str, milliseconds: str) -> int:
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(milliseconds)
    )


def format_srt_time(value: int) -> str:
    value = max(0, value)
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def format_markdown_time(value: int) -> str:
    value = max(0, value)
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds = remainder // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def parse_srt(path: Path) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").strip())
    segments: list[dict[str, Any]] = []
    for block_number, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_index = 1 if lines[0].strip().isdigit() else 0
        if time_index >= len(lines):
            die(f"{path}: block {block_number} has no timecode")
        match = TIMECODE_RE.match(lines[time_index].strip())
        if not match:
            die(f"{path}: block {block_number} has an invalid timecode")
        text = "\n".join(lines[time_index + 1 :]).strip()
        if not text:
            die(f"{path}: block {block_number} has no transcript text")
        groups = match.groupdict()
        segments.append(
            {
                "local_start_ms": to_ms(
                    groups["sh"], groups["sm"], groups["ss"], groups["sms"]
                ),
                "local_end_ms": to_ms(
                    groups["eh"], groups["em"], groups["es"], groups["ems"]
                ),
                "text": text,
            }
        )
    if not segments:
        die(f"{path}: no SRT segments parsed")
    return segments


def duplicate_match(
    segment: dict[str, Any],
    candidates: list[dict[str, Any]],
    threshold: float,
) -> tuple[dict[str, Any] | None, float]:
    current = normalize(segment["text"])
    if not current:
        return None, 0.0
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    for candidate in candidates:
        existing = normalize(candidate["text"])
        if not existing:
            continue
        if current == existing and len(current) >= 4:
            return candidate, 1.0
        if min(len(current), len(existing)) < 12:
            continue
        ratio = difflib.SequenceMatcher(None, current, existing).ratio()
        containment = current in existing or existing in current
        if containment:
            ratio = max(ratio, min(len(current), len(existing)) / max(len(current), len(existing)))
        if ratio > best_ratio:
            best, best_ratio = candidate, ratio
    if best_ratio >= threshold:
        return best, best_ratio
    return None, best_ratio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assemble chunk SRT files with global timestamps and conservative overlap deduplication."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--duplicate-threshold", type=float, default=0.88)
    args = parser.parse_args()

    if not 0.5 <= args.duplicate_threshold <= 1.0:
        die("--duplicate-threshold must be between 0.5 and 1.0")
    manifest_path = args.manifest.expanduser().resolve()
    if not manifest_path.is_file():
        die(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunks = sorted(manifest.get("chunks", []), key=lambda item: int(item["index"]))
    if not chunks:
        die("manifest has no chunks")

    output_prefix = args.output_prefix.expanduser().resolve()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    outputs = {
        "txt": Path(f"{output_prefix}.txt"),
        "srt": Path(f"{output_prefix}.srt"),
        "json": Path(f"{output_prefix}.json"),
        "md": Path(f"{output_prefix}.md"),
    }
    for path in outputs.values():
        if path.exists() or path.is_symlink():
            die(f"output exists: {path}")

    kept: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    previous_chunk_end = 0

    for chunk in chunks:
        prefix = str(chunk["transcript_prefix"])
        artifacts = {
            suffix: Path(f"{prefix}.{suffix}") for suffix in ("txt", "srt", "json")
        }
        for suffix, artifact in artifacts.items():
            if not artifact.is_file() or artifact.stat().st_size == 0:
                die(f"missing or empty chunk {suffix.upper()}: {artifact}")
        try:
            json.loads(artifacts["json"].read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            die(f"invalid chunk JSON: {artifacts['json']}: {error}")
        srt_path = artifacts["srt"]
        chunk_start = int(chunk["start_ms"])
        chunk_end = int(chunk["end_ms"])
        parsed = parse_srt(srt_path)
        for local_index, local in enumerate(parsed):
            segment = {
                "chunk_index": int(chunk["index"]),
                "local_index": local_index,
                "start_ms": chunk_start + int(local["local_start_ms"]),
                "end_ms": min(chunk_end, chunk_start + int(local["local_end_ms"])),
                "text": local["text"],
                "source_srt": str(srt_path),
            }
            if segment["end_ms"] <= segment["start_ms"]:
                decisions.append(
                    {
                        "action": "skip_invalid_time",
                        "chunk_index": segment["chunk_index"],
                        "local_index": local_index,
                    }
                )
                continue

            in_chunk_overlap = (
                segment["chunk_index"] > 0
                and segment["start_ms"] < previous_chunk_end
            )
            if in_chunk_overlap:
                candidates = [
                    candidate
                    for candidate in kept
                    if candidate["chunk_index"] < segment["chunk_index"]
                    if candidate["end_ms"] >= chunk_start - 2000
                    and candidate["start_ms"] <= previous_chunk_end + 2000
                ]
                match, ratio = duplicate_match(
                    segment, candidates, args.duplicate_threshold
                )
                if match is not None:
                    decisions.append(
                        {
                            "action": "skip_overlap_duplicate",
                            "chunk_index": segment["chunk_index"],
                            "local_index": local_index,
                            "matched_chunk_index": match["chunk_index"],
                            "similarity": round(ratio, 4),
                            "text": segment["text"],
                        }
                    )
                    continue
                review_items.append(
                    {
                        "chunk_index": segment["chunk_index"],
                        "local_index": local_index,
                        "start_ms": segment["start_ms"],
                        "end_ms": segment["end_ms"],
                        "best_similarity": round(ratio, 4),
                        "text": segment["text"],
                    }
                )
            kept.append(segment)
        previous_chunk_end = max(previous_chunk_end, chunk_end)

    kept.sort(
        key=lambda item: (
            item["start_ms"],
            item["end_ms"],
            item["chunk_index"],
            item["local_index"],
        )
    )
    if not kept:
        die("assembly produced no transcript segments")

    srt_parts = []
    txt_parts = []
    markdown_parts = [
        "# Assembled local Whisper transcript",
        "",
        (
            f"Source manifest: `{manifest_path}`. Machine-generated; "
            "not certified verbatim."
        ),
        "",
    ]
    for index, segment in enumerate(kept, start=1):
        srt_parts.extend(
            [
                str(index),
                (
                    f"{format_srt_time(segment['start_ms'])} --> "
                    f"{format_srt_time(segment['end_ms'])}"
                ),
                segment["text"],
                "",
            ]
        )
        txt_parts.append(segment["text"])
        markdown_parts.append(
            f"[{format_markdown_time(segment['start_ms'])}] {segment['text']}"
        )

    audit = {
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "source": manifest.get("source"),
        "duplicate_threshold": args.duplicate_threshold,
        "segment_count": len(kept),
        "skipped_duplicate_count": sum(
            item["action"] == "skip_overlap_duplicate" for item in decisions
        ),
        "overlap_review_required": bool(review_items),
        "overlap_review_items": review_items,
        "decisions": decisions,
        "segments": kept,
        "boundary": (
            "Only high-confidence temporal overlap duplicates were removed. "
            "Review flagged overlap items and speaker turns against the audio."
        ),
    }

    with tempfile.TemporaryDirectory(
        prefix=".assemble-stage-", dir=str(output_prefix.parent)
    ) as temp_dir:
        stage = Path(temp_dir)
        staged = {
            "txt": stage / "result.txt",
            "srt": stage / "result.srt",
            "json": stage / "result.json",
            "md": stage / "result.md",
        }
        staged["txt"].write_text("\n".join(txt_parts) + "\n", encoding="utf-8")
        staged["srt"].write_text("\n".join(srt_parts), encoding="utf-8")
        staged["json"].write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        staged["md"].write_text("\n".join(markdown_parts) + "\n", encoding="utf-8")
        for key, destination in outputs.items():
            os.replace(staged[key], destination)

    print(output_prefix)
    return 0 if not review_items else 4


if __name__ == "__main__":
    raise SystemExit(main())
