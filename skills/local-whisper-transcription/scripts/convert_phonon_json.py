#!/usr/bin/env python3
"""Validate Fermion 0.2.4 Phonon JSON and export artifacts; no inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

MODEL_ID = "FermionResearch/Phonon-2"
FERMION_VERSION = "0.2.4"
MODEL_FILES = ("config.json", "packed_manifest.json", "model.fermion")
PACKED_FORMAT = "fermion-five-value-parakeet-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTEXT_TOKEN = object()


class ProducerContract(Mapping):
    """Immutable loader result, distinct from portable, caller-supplied JSON.

    This prevents accidentally treating unchecked dictionaries as verified
    local records. It is not a security boundary against same-process code.
    """

    __slots__ = ("_serialized",)

    def __init__(self, values: dict, *, _token: object = None):
        if _token is not _CONTEXT_TOKEN:
            raise TypeError("use load_producer_contract() to obtain producer context")
        object.__setattr__(self, "_serialized", json.dumps(values, allow_nan=False))

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("producer context is immutable")

    def _snapshot(self) -> dict:
        return json.loads(self._serialized)

    def __getitem__(self, key: str):
        return self._snapshot()[key]

    def __iter__(self):
        return iter(self._snapshot())

    def __len__(self) -> int:
        return len(self._snapshot())


def check_path(path: Path) -> None:
    if (not path.is_absolute() or ".." in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError("paths must be absolute and contain no symlinks or parent traversal")


def absolute_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("expected an absolute path")
    path = Path(value)
    check_path(path)
    if str(path) != value:
        raise ValueError("path must use its normalized absolute spelling")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_object(raw: bytes) -> dict:
    def unique(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def valid_hash(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_producer_contract(contract: dict) -> None:
    """Validate recorded evidence structurally; never inspect installed files here."""
    if not isinstance(contract, dict):
        raise ValueError("producer_contract must be an object")
    if contract.get("fermion_version") != FERMION_VERSION or contract.get("model_id") != MODEL_ID:
        raise ValueError("unsupported Fermion version or model identity")
    if set(contract) != {"fermion_version", "model_id", "model_directory", "revision", "evidence"}:
        raise ValueError("unsupported producer context fields")
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("missing producer evidence")
    if "model_directory" not in contract or "revision" not in contract:
        raise ValueError("missing producer context fields")
    directory, revision = contract["model_directory"], contract["revision"]
    if directory is None:
        expected = {"fermion_version": "caller_declared", "model_id": "supported_contract",
                    "model_directory": "unavailable", "revision": "unavailable",
                    "file_hashes": "unavailable"}
        if revision is not None or evidence.get("files") != []:
            raise ValueError("repository-only context cannot claim installed state")
        if evidence.get("model_profile_sha256") is not None or evidence.get("installation_receipt_sha256") is not None:
            raise ValueError("repository-only context cannot claim local evidence hashes")
    else:
        # Portable validation: no filesystem checks on a recorded local directory.
        if (not isinstance(directory, str) or not Path(directory).is_absolute()
                or ".." in Path(directory).parts or str(Path(directory)) != directory):
            raise ValueError("invalid recorded model directory")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError("invalid installation revision")
        expected = {"fermion_version": "installation_receipt", "model_id": "owner_profile",
                    "model_directory": "owner_profile", "revision": "installation_receipt",
                    "file_hashes": "installation_receipt"}
        for name in ("model_profile_sha256", "installation_receipt_sha256"):
            if not valid_hash(evidence.get(name)):
                raise ValueError("invalid profile/receipt evidence hash")
        records = evidence.get("files")
        if not isinstance(records, list) or len(records) != len(MODEL_FILES):
            raise ValueError("invalid model file evidence")
        seen = set()
        for entry in records:
            if not isinstance(entry, dict):
                raise ValueError("invalid model file evidence entry")
            name = entry.get("path")
            if not isinstance(name, str) or name not in MODEL_FILES or name in seen:
                raise ValueError("invalid or duplicate model evidence path")
            seen.add(name)
            if type(entry.get("bytes")) is not int or entry["bytes"] <= 0 or not valid_hash(entry.get("sha256")):
                raise ValueError("invalid model file size/hash evidence")
    for field, source in expected.items():
        if evidence.get(field) != source:
            raise ValueError(f"invalid evidence source for {field}")
    # A context is a local compatibility/integrity record, never run attestation.
    allowed = set(expected) | {"model_profile_sha256", "installation_receipt_sha256", "files"}
    if set(evidence) != allowed:
        raise ValueError("unsupported producer evidence fields")


def load_producer_contract(*, model_profile: Path | None = None,
                           fermion_version: str | None = None) -> ProducerContract:
    """Verify local owner records once for reuse across conversions, without model imports."""
    if fermion_version is not None and fermion_version != FERMION_VERSION:
        raise ValueError("only exact Fermion 0.2.4 is supported")
    if model_profile is None:
        if fermion_version is None:
            raise ValueError("provide a model profile or explicit Fermion version")
        contract = {"fermion_version": fermion_version, "model_id": MODEL_ID,
                    "model_directory": None, "revision": None,
                    "evidence": {"fermion_version": "caller_declared", "model_id": "supported_contract",
                                 "model_directory": "unavailable", "revision": "unavailable",
                                 "file_hashes": "unavailable", "model_profile_sha256": None,
                                 "installation_receipt_sha256": None, "files": []}}
    else:
        model_profile = Path(model_profile)
        check_path(model_profile)
        if not model_profile.is_file():
            raise ValueError("model profile must be a regular file")
        profile_raw = model_profile.read_bytes()
        profile = json_object(profile_raw)
        if type(profile.get("version")) is not int or profile["version"] != 1:
            raise ValueError("unsupported model profile version")
        if profile.get("model_id") != MODEL_ID or profile.get("engine") != "mlx":
            raise ValueError("unsupported model profile identity/engine")
        directory = absolute_path(profile.get("model_directory"))
        receipt_path = absolute_path(profile.get("installation_receipt"))
        if not directory.is_dir() or not receipt_path.is_file():
            raise ValueError("model directory or installation receipt missing")
        receipt_raw = receipt_path.read_bytes()
        receipt = json_object(receipt_raw)
        version = receipt.get("cli_version")
        if version != FERMION_VERSION or (fermion_version is not None and version != fermion_version):
            raise ValueError("unsupported or conflicting receipt CLI version")
        if receipt.get("model") != MODEL_ID or receipt.get("model_directory") != str(directory):
            raise ValueError("profile/receipt model identity mismatch")
        entries = receipt.get("files")
        if not isinstance(entries, list) or len(entries) != len(MODEL_FILES):
            raise ValueError("receipt must identify the three model files")
        records = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid receipt file record")
            name = entry.get("path")
            # Receipt member names are confined basenames, as in the owner receipt.
            # The receipt location itself and model directory must be absolute.
            if not isinstance(name, str) or name not in MODEL_FILES or name in seen:
                raise ValueError("receipt member path must be a unique model-file basename")
            seen.add(name)
            target = directory / name
            check_path(target)
            if not target.is_file():
                raise ValueError("model file must exist and be regular")
            size, digest = entry.get("bytes"), entry.get("sha256")
            if type(size) is not int or size <= 0 or not valid_hash(digest):
                raise ValueError("invalid receipt size/hash")
            if target.stat().st_size != size or sha256(target) != digest:
                raise ValueError("model file integrity mismatch")
            records.append({"path": name, "bytes": size, "sha256": digest})
        packed = json_object((directory / "packed_manifest.json").read_bytes())
        if packed.get("format") != PACKED_FORMAT or packed.get("container") != "model.fermion":
            raise ValueError("unsupported packed model format/container")
        weights = next(entry for entry in records if entry["path"] == "model.fermion")
        for field, value in (("container_bytes", weights["bytes"]), ("container_sha256", weights["sha256"])):
            if field in packed and (type(packed[field]) is not type(value) or packed[field] != value):
                raise ValueError("packed manifest disagrees with receipt")
        # Verify config is readable JSON, without importing model/runtime packages.
        json_object((directory / "config.json").read_bytes())
        contract = {"fermion_version": version, "model_id": MODEL_ID,
                    "model_directory": str(directory), "revision": receipt.get("revision"),
                    "evidence": {"fermion_version": "installation_receipt", "model_id": "owner_profile",
                                 "model_directory": "owner_profile", "revision": "installation_receipt",
                                 "file_hashes": "installation_receipt",
                                 "model_profile_sha256": hashlib.sha256(profile_raw).hexdigest(),
                                 "installation_receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
                                 "files": sorted(records, key=lambda item: item["path"])}}
    validate_producer_contract(contract)
    return ProducerContract(contract, _token=_CONTEXT_TOKEN)


def seconds(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("timestamps/duration must be numeric")
    if not math.isfinite(value) or value < 0:
        raise ValueError("timestamps/duration must be finite and nonnegative")
    return float(value)


def milliseconds(value: object) -> int:
    seconds(value)
    scaled = Decimal(str(value)) * 1000
    if scaled != scaled.to_integral_value():
        raise ValueError("timestamps/duration must have millisecond precision")
    return int(scaled)


def timecode(value: float) -> str:
    hours, rem = divmod(milliseconds(value), 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def canonical_artifacts(data: dict, *, producer_contract: dict) -> dict:
    """Revalidate producer semantics and return canonical artifacts and cue counts."""
    validate_producer_contract(producer_contract)
    if not isinstance(data, dict) or data.get("truncated") is not False:
        raise ValueError("missing/true truncated flag; chunk is not complete")
    if (data.get("profile") != "five-value" or data.get("backend") != "phonon2-five-value"
            or data.get("engine") != "mlx"):
        raise ValueError("unsupported producer profile/backend/engine")
    model = data.get("model")
    if model != MODEL_ID and (producer_contract["model_directory"] is None or model != producer_contract["model_directory"]):
        raise ValueError("producer model does not match the validated context")
    if not isinstance(data.get("text"), str):
        raise ValueError("top-level text must be a string")
    duration = milliseconds(data.get("duration_seconds"))
    if duration <= 0:
        raise ValueError("duration must be positive")
    segments = data.get("segments")
    if not isinstance(segments, list):
        raise ValueError("missing segments")
    if type(data.get("segment_count")) is not int or data["segment_count"] != len(segments):
        raise ValueError("segment_count mismatch")
    cues, texts, parsed, previous_end, empty_count = [], [], [], 0, 0
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("invalid segment")
        start, end = milliseconds(segment.get("start")), milliseconds(segment.get("end"))
        text = segment.get("text")
        if not isinstance(text, str):
            raise ValueError("segment text must be a string")
        if start < previous_end or end <= start or end > duration:
            raise ValueError("unordered, overlapping or out-of-bounds segment")
        previous_end = end
        text = " ".join(text.split())
        if not text:
            empty_count += 1
            continue
        cues.append(f"{len(cues) + 1}\n{timecode(segment['start'])} --> {timecode(segment['end'])}\n{text}\n")
        texts.append(text)
        parsed.append({"local_start_ms": start, "local_end_ms": end, "text": text})
    joined = " ".join(texts)
    if " ".join(data["text"].split()) != joined:
        raise ValueError("top-level text disagrees with segments")
    return {"txt": joined + "\n", "srt": "\n".join(cues), "cues": parsed,
            "cue_count": len(cues), "empty_segment_count": empty_count,
            "completion_state": "completed" if cues else "completed_no_text"}


def validate_converted(data: dict) -> dict:
    """Validate portable adapter metadata, then regenerate the canonical artifacts."""
    metadata = data.get("_local_transcription") if isinstance(data, dict) else None
    if not isinstance(metadata, dict) or type(metadata.get("adapter_version")) is not int or metadata["adapter_version"] != 2:
        raise ValueError("missing or unsupported Phonon adapter metadata")
    if set(metadata) != {"adapter_version", "source_json_sha256", "timing_precision", "speaker_labels",
                         "producer_contract", "producer", "completion_state", "cue_count", "empty_segment_count"}:
        raise ValueError("unsupported Phonon adapter metadata fields")
    if (not valid_hash(metadata.get("source_json_sha256"))
            or metadata.get("timing_precision") != "decoding_window"
            or metadata.get("speaker_labels") != "not_provided"):
        raise ValueError("invalid Phonon source/timing/speaker metadata")
    expected = canonical_artifacts(data, producer_contract=metadata.get("producer_contract"))
    producer = {name: data[name] for name in ("model", "profile", "backend", "engine")}
    if metadata.get("producer") != producer:
        raise ValueError("adapter producer identity disagrees with source")
    for field in ("cue_count", "empty_segment_count"):
        if type(metadata.get(field)) is not int or metadata[field] != expected[field]:
            raise ValueError("adapter cue/empty-window count mismatch")
    if metadata.get("completion_state") != expected["completion_state"]:
        raise ValueError("adapter completion state mismatch")
    return expected


def looks_like_phonon(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    model = data.get("model")
    return ("_local_transcription" in data
            or (isinstance(model, str) and "phonon" in model.casefold())
            or (isinstance(data.get("backend"), str) and "phonon" in data["backend"].casefold())
            or data.get("profile") == "five-value"
            or {"profile", "backend", "engine", "segment_count", "truncated"}.issubset(data)
            or {"duration_seconds", "segment_count", "segments", "truncated"}.issubset(data))


def convert(raw: bytes, *, producer_contract: ProducerContract) -> dict[str, str]:
    if type(producer_contract) is not ProducerContract:
        raise ValueError("producer_contract must come from load_producer_contract()")
    context = producer_contract._snapshot()
    data = json_object(raw)
    if "_local_transcription" in data:
        raise ValueError("input already has conversion metadata")
    canonical = canonical_artifacts(data, producer_contract=context)
    data["_local_transcription"] = {
        "adapter_version": 2, "source_json_sha256": hashlib.sha256(raw).hexdigest(),
        "timing_precision": "decoding_window", "speaker_labels": "not_provided",
        "producer_contract": context,
        "producer": {name: data[name] for name in ("model", "profile", "backend", "engine")},
        **{name: canonical[name] for name in ("completion_state", "cue_count", "empty_segment_count")},
    }
    return {"txt": canonical["txt"], "srt": canonical["srt"],
            "json": json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--model-profile", type=Path)
    parser.add_argument("--fermion-version")
    args = parser.parse_args()
    published = []
    try:
        check_path(args.input)
        check_path(args.output_prefix)
        outputs = {ext: Path(f"{args.output_prefix}.{ext}") for ext in ("txt", "srt", "json")}
        if not args.output_prefix.parent.is_dir():
            raise ValueError("output parent directory must already exist")
        for target in outputs.values():
            check_path(target)
            if target.exists():
                raise ValueError(f"output exists: {target}")
        context = load_producer_contract(model_profile=args.model_profile, fermion_version=args.fermion_version)
        artifacts = convert(args.input.read_bytes(), producer_contract=context)
        with tempfile.TemporaryDirectory(prefix=".phonon-convert-", dir=args.output_prefix.parent) as staging:
            for ext, content in artifacts.items():
                staged = Path(staging) / ext
                staged.write_text(content, encoding="utf-8")
                staged.chmod(0o600)
            for ext, target in outputs.items():
                os.link(Path(staging) / ext, target)
                published.append(target)
    except (ValueError, OSError, TypeError, OverflowError) as error:
        for target in published:
            target.unlink()
        parser.exit(2, f"error: {error}\n")
    print("Converted Phonon-2 output; SRT timing precision: decoding windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
