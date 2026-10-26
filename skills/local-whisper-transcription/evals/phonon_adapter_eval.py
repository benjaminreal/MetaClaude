#!/usr/bin/env python3
"""Synthetic Phonon conversion and assembly regressions; never run a model."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
MODEL_ID = "FermionResearch/Phonon-2"
VERSION = "0.2.4"
PACKED_FORMAT = "fermion-five-value-parakeet-v1"
ADAPTER_PATH = SCRIPTS / "convert_phonon_json.py"
ASSEMBLER_PATH = SCRIPTS / "assemble_transcript.py"

spec = importlib.util.spec_from_file_location("phonon_adapter", ADAPTER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load adapter at {ADAPTER_PATH}")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=True).encode("utf-8")


def payload(
    *,
    model: str = MODEL_ID,
    duration: float = 5.0,
    segments: list[dict[str, Any]] | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    if segments is None:
        segments = [
            {"start": 0.0, "end": 2.0, "text": "  Synthetic   first window. "},
            {"start": 2.0, "end": 5.0, "text": "Second window."},
        ]
    if text is None:
        text = " ".join(" ".join(s["text"].split()) for s in segments if s["text"].strip())
    return {
        "model": model,
        "profile": "five-value",
        "backend": "phonon2-five-value",
        "engine": "mlx",
        "text": text,
        "duration_seconds": duration,
        "segment_count": len(segments),
        "truncated": False,
        "producer_note": {"fixture": True},
        "segments": copy.deepcopy(segments),
    }


def make_profile_fixture(
    root: Path,
    *,
    packed_manifest: dict[str, Any] | None = None,
    profile_changes: dict[str, Any] | None = None,
    receipt_changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create disposable synthetic identity files; no installed model is read."""
    root.mkdir(parents=True, exist_ok=True)
    model_dir = root / "synthetic-model"
    model_dir.mkdir()
    file_data = {
        "config.json": json_bytes({"model": MODEL_ID, "fixture": True}),
        "packed_manifest.json": json_bytes(
            packed_manifest
            if packed_manifest is not None
            else {"format": PACKED_FORMAT, "container": "model.fermion"}
        ),
        "model.fermion": b"synthetic packed model bytes; not loadable weights\n",
    }
    entries = []
    for name, content in file_data.items():
        (model_dir / name).write_bytes(content)
        entries.append(
            {
                "path": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    receipt_path = root / "synthetic-installation-receipt.json"
    receipt: dict[str, Any] = {
        "model": MODEL_ID,
        "model_directory": str(model_dir),
        "revision": "synthetic-revision",
        "cli_version": VERSION,
        "files": entries,
    }
    if receipt_changes:
        receipt.update(receipt_changes)
    receipt_path.write_bytes(json_bytes(receipt))

    profile_path = root / "synthetic-model-profile.json"
    profile: dict[str, Any] = {
        "version": 1,
        "model_id": MODEL_ID,
        "model_directory": str(model_dir),
        "engine": "mlx",
        "installation_receipt": str(receipt_path),
    }
    if profile_changes:
        profile.update(profile_changes)
    profile_path.write_bytes(json_bytes(profile))
    return {
        "model_dir": model_dir,
        "profile_path": profile_path,
        "receipt_path": receipt_path,
        "profile_bytes": profile_path.read_bytes(),
        "receipt_bytes": receipt_path.read_bytes(),
        "file_data": file_data,
    }


def call_convert(data: dict[str, Any], producer_contract: dict[str, Any]) -> dict[str, str]:
    return adapter.convert(json_bytes(data), producer_contract=producer_contract)


def write_artifacts(prefix: Path, artifacts: dict[str, str]) -> None:
    for extension in ("txt", "srt", "json"):
        Path(f"{prefix}.{extension}").write_text(artifacts[extension], encoding="utf-8")


def manifest_for(root: Path, chunks: list[dict[str, Any]], overlap_seconds: float = 0) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "chunks.json"
    path.write_text(
        json.dumps(
            {"schema_version": 1, "overlap_seconds": overlap_seconds, "chunks": chunks},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def chunk(index: int, start_ms: int, end_ms: int, prefix: Path) -> dict[str, Any]:
    return {
        "index": index,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "duration_ms": end_ms - start_ms,
        "transcript_prefix": str(prefix),
    }


def run_assembler(manifest: Path, output_prefix: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ASSEMBLER_PATH),
            "--manifest",
            str(manifest),
            "--output-prefix",
            str(output_prefix),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def assert_no_assembly_outputs(test: unittest.TestCase, prefix: Path) -> None:
    for extension in ("txt", "srt", "json", "md"):
        test.assertFalse(Path(f"{prefix}.{extension}").exists(), extension)


class PhononAdapterEval(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="phonon-adapter-eval-")
        # macOS temp roots may use /var -> /private/var. Resolve the ordinary
        # fixture root; deliberate symlink fixtures below remain unresolved.
        self.root = Path(self.temp.name).resolve()
        self.repo_contract = adapter.load_producer_contract(fermion_version=VERSION)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_repository_identity_is_caller_declared_and_does_not_invent_installation(self) -> None:
        contract = self.repo_contract
        self.assertEqual(contract["fermion_version"], VERSION)
        self.assertEqual(contract["model_id"], MODEL_ID)
        self.assertIsNone(contract["model_directory"])
        self.assertIsNone(contract["revision"])
        evidence = json.dumps(contract["evidence"], sort_keys=True)
        self.assertIn("caller_declared", evidence)
        self.assertNotIn("actual_run_verified", evidence)

    def test_local_profile_receipt_hashes_paths_and_version_provenance(self) -> None:
        fixture = make_profile_fixture(self.root)
        contract = adapter.load_producer_contract(
            model_profile=fixture["profile_path"], fermion_version=VERSION
        )
        self.assertEqual(contract["fermion_version"], VERSION)
        self.assertEqual(contract["model_id"], MODEL_ID)
        self.assertEqual(contract["model_directory"], str(fixture["model_dir"]))
        self.assertEqual(contract["revision"], "synthetic-revision")
        evidence = json.dumps(contract["evidence"], sort_keys=True)
        expected_hashes = {
            hashlib.sha256(fixture["profile_bytes"]).hexdigest(),
            hashlib.sha256(fixture["receipt_bytes"]).hexdigest(),
        }
        for digest in expected_hashes:
            self.assertIn(digest, evidence)
        self.assertIn("installation_receipt", evidence)
        self.assertNotIn("actual_run_verified", evidence)
        self.assertEqual(fixture["profile_path"].read_bytes(), fixture["profile_bytes"])
        self.assertEqual(fixture["receipt_path"].read_bytes(), fixture["receipt_bytes"])

    def test_profile_receipt_reject_bad_version_identity_hash_size_paths_and_container(self) -> None:
        with self.subTest("no inferred package version"):
            with self.assertRaises((ValueError, TypeError)):
                adapter.load_producer_contract()
        with self.subTest("unsupported package version"):
            with self.assertRaises(ValueError):
                adapter.load_producer_contract(fermion_version="0.2.5")
        with self.subTest("profile and caller version disagree"):
            fixture = make_profile_fixture(self.root / "version-mismatch")
            with self.assertRaises(ValueError):
                adapter.load_producer_contract(
                    model_profile=fixture["profile_path"], fermion_version="0.2.5"
                )

        invalid_profiles = [
            {"version": 2},
            {"model_id": "Other/Model"},
            {"engine": "cpu"},
            {"model_directory": "relative/model"},
            {"model_directory": "/different/synthetic-model"},
        ]
        for index, changes in enumerate(invalid_profiles):
            with self.subTest(profile_changes=changes):
                case = self.root / f"bad-profile-{index}"
                case.mkdir()
                fixture = make_profile_fixture(case, profile_changes=changes)
                with self.assertRaises((ValueError, OSError)):
                    adapter.load_producer_contract(model_profile=fixture["profile_path"])

        bad_receipts = [
            {"model": "Other/Model"},
            {"cli_version": "0.2.5"},
            {"model_directory": "../escape"},
            {"files": [{"path": "../outside", "bytes": 1, "sha256": "0" * 64}]},
            {"files": [{"path": "config.json", "bytes": 999, "sha256": "0" * 64}]},
        ]
        for index, changes in enumerate(bad_receipts):
            with self.subTest(receipt_changes=changes):
                case = self.root / f"bad-receipt-{index}"
                case.mkdir()
                fixture = make_profile_fixture(case, receipt_changes=changes)
                with self.assertRaises((ValueError, OSError)):
                    adapter.load_producer_contract(model_profile=fixture["profile_path"])

        with self.subTest("unsupported packed format"):
            case = self.root / "bad-container"
            case.mkdir()
            fixture = make_profile_fixture(
                case, packed_manifest={"format": "unknown", "container": "other.bin"}
            )
            with self.assertRaises((ValueError, OSError)):
                adapter.load_producer_contract(model_profile=fixture["profile_path"])

        with self.subTest("model file hash mismatch"):
            case = self.root / "corrupt-model-file"
            case.mkdir()
            fixture = make_profile_fixture(case)
            model_file = fixture["model_dir"] / "model.fermion"
            content = model_file.read_bytes()
            model_file.write_bytes(b"X" + content[1:])
            with self.assertRaises((ValueError, OSError)):
                adapter.load_producer_contract(model_profile=fixture["profile_path"])

        with self.subTest("missing model file"):
            fixture = make_profile_fixture(self.root / "missing-model-file")
            (fixture["model_dir"] / "model.fermion").unlink()
            with self.assertRaises((ValueError, OSError)):
                adapter.load_producer_contract(model_profile=fixture["profile_path"])

        with self.subTest("symlinked model member"):
            case = self.root / "symlink-model"
            case.mkdir()
            fixture = make_profile_fixture(case)
            outside = case / "outside.json"
            outside.write_bytes(fixture["file_data"]["config.json"])
            (fixture["model_dir"] / "config.json").unlink()
            (fixture["model_dir"] / "config.json").symlink_to(outside)
            with self.assertRaises((ValueError, OSError)):
                adapter.load_producer_contract(model_profile=fixture["profile_path"])

        with self.subTest("symlinked profile or receipt"):
            case = self.root / "symlink-profile-receipt"
            case.mkdir()
            fixture = make_profile_fixture(case)
            linked_profile = case / "profile-link.json"
            linked_profile.symlink_to(fixture["profile_path"])
            with self.assertRaises((ValueError, OSError)):
                adapter.load_producer_contract(model_profile=linked_profile)
            linked_receipt = case / "receipt-link.json"
            linked_receipt.symlink_to(fixture["receipt_path"])
            linked_profile.unlink()
            profile_data = json.loads(fixture["profile_path"].read_text(encoding="utf-8"))
            profile_data["installation_receipt"] = str(linked_receipt)
            fixture["profile_path"].write_bytes(json_bytes(profile_data))
            with self.assertRaises((ValueError, OSError)):
                adapter.load_producer_contract(model_profile=fixture["profile_path"])

    def test_convert_preserves_raw_fields_and_attaches_context_and_hash(self) -> None:
        sample = payload()
        sample["segments"][0]["id"] = "window-a"
        sample["timing_detail"] = {"fixture_key": "preserved"}
        raw = json_bytes(sample)
        artifacts = adapter.convert(raw, producer_contract=self.repo_contract)
        converted = json.loads(artifacts["json"])
        metadata = converted["_local_transcription"]
        self.assertEqual(metadata["adapter_version"], 2)
        self.assertEqual(metadata["source_json_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(metadata["timing_precision"], "decoding_window")
        self.assertEqual(metadata["speaker_labels"], "not_provided")
        self.assertEqual(metadata["producer_contract"], self.repo_contract)
        self.assertEqual(
            metadata["producer"],
            {key: sample[key] for key in ("model", "profile", "backend", "engine")},
        )
        self.assertEqual(converted["producer_note"], sample["producer_note"])
        self.assertEqual(converted["timing_detail"], sample["timing_detail"])
        self.assertEqual(converted["segments"][0]["id"], "window-a")
        self.assertEqual(artifacts["txt"], "Synthetic first window. Second window.\n")
        self.assertIn("00:00:00,000 --> 00:00:02,000", artifacts["srt"])
        self.assertIn("00:00:02,000 --> 00:00:05,000", artifacts["srt"])
        with self.assertRaises((ValueError, TypeError)):
            call_convert(payload(model="/unprofiled/local/model"), self.repo_contract)

    def test_convert_rejects_incomplete_or_mismatched_producer_signatures(self) -> None:
        invalid = []
        for key, value in [
            ("model", "Other/Model"),
            ("profile", "four-value"),
            ("backend", "other-backend"),
            ("engine", "cpu"),
            ("truncated", True),
            ("truncated", None),
            ("duration_seconds", 0),
            ("duration_seconds", float("nan")),
            ("duration_seconds", float("inf")),
            ("segment_count", 4),
            ("text", "mismatched top-level words"),
            ("segments", None),
        ]:
            sample = payload()
            sample[key] = value
            invalid.append(sample)

        for field, value in [
            ("start", -0.001),
            ("end", 5.001),
            ("start", float("inf")),
            ("end", 0),
            ("end", 0.0001),
        ]:
            sample = payload()
            sample["segments"][0][field] = value
            invalid.append(sample)

        sample = payload()
        sample["segments"][1]["start"] = 1.5
        invalid.append(sample)
        sample = payload()
        sample["segments"][0]["text"] = 17
        invalid.append(sample)
        sample = payload()
        sample["_local_transcription"] = {"adapter_version": 1}
        invalid.append(sample)

        for sample in invalid:
            with self.subTest(sample=sample):
                with self.assertRaises((ValueError, TypeError)):
                    call_convert(sample, self.repo_contract)

    def test_empty_windows_and_zero_segment_completion_are_preserved(self) -> None:
        mixed = payload(
            segments=[
                {"start": 0.0, "end": 1.0, "text": " \n  "},
                {"start": 1.0, "end": 3.0, "text": "A synthetic phrase."},
                {"start": 3.0, "end": 5.0, "text": ""},
            ],
        )
        artifacts = call_convert(mixed, self.repo_contract)
        converted = json.loads(artifacts["json"])
        metadata = converted["_local_transcription"]
        self.assertEqual(metadata["completion_state"], "completed")
        self.assertEqual(metadata["cue_count"], 1)
        self.assertEqual(metadata["empty_segment_count"], 2)
        self.assertEqual(artifacts["txt"], "A synthetic phrase.\n")
        self.assertEqual(len([line for line in artifacts["srt"].splitlines() if line.isdigit()]), 1)
        self.assertEqual(len(converted["segments"]), 3)

        silent = payload(segments=[], text="")
        silent_artifacts = call_convert(silent, self.repo_contract)
        silent_json = json.loads(silent_artifacts["json"])
        silent_meta = silent_json["_local_transcription"]
        self.assertEqual(silent_meta["completion_state"], "completed_no_text")
        self.assertEqual(silent_meta["cue_count"], 0)
        self.assertEqual(silent_meta["empty_segment_count"], 0)
        self.assertEqual(silent_artifacts["txt"], "\n")
        self.assertEqual(silent_artifacts["srt"], "")
        self.assertEqual(silent_json["segments"], [])

    def test_cli_profile_flags_and_converter_publication_safety(self) -> None:
        fixture = make_profile_fixture(self.root / "cli-profile")
        sample = payload(model=str(fixture["model_dir"]))
        raw_path = self.root / "raw.json"
        raw_bytes = json_bytes(sample)
        raw_path.write_bytes(raw_bytes)
        output_prefix = self.root / "converted"
        command = [
            sys.executable,
            str(ADAPTER_PATH),
            "--input",
            str(raw_path),
            "--output-prefix",
            str(output_prefix),
            "--model-profile",
            str(fixture["profile_path"]),
            "--fermion-version",
            VERSION,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(raw_path.read_bytes(), raw_bytes)
        converted = json.loads(Path(f"{output_prefix}.json").read_text(encoding="utf-8"))
        self.assertEqual(converted["_local_transcription"]["producer_contract"]["revision"], "synthetic-revision")

        existing_before = {
            extension: Path(f"{output_prefix}.{extension}").read_bytes()
            for extension in ("txt", "srt", "json")
        }
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            existing_before,
            {extension: Path(f"{output_prefix}.{extension}").read_bytes() for extension in existing_before},
        )

        invalid_path = self.root / "invalid.json"
        invalid = payload()
        invalid["truncated"] = True
        invalid_path.write_bytes(json_bytes(invalid))
        invalid_prefix = self.root / "invalid-output"
        bad_command = command.copy()
        bad_command[bad_command.index(str(raw_path))] = str(invalid_path)
        bad_command[bad_command.index(str(output_prefix))] = str(invalid_prefix)
        result = subprocess.run(bad_command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        for extension in ("txt", "srt", "json"):
            self.assertFalse(Path(f"{invalid_prefix}.{extension}").exists())

        symlinked_parent = self.root / "linked-parent"
        symlinked_parent.symlink_to(self.root, target_is_directory=True)
        symlink_prefix = symlinked_parent / "new-output"
        symlink_command = command.copy()
        symlink_command[symlink_command.index(str(output_prefix))] = str(symlink_prefix)
        result = subprocess.run(symlink_command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        for extension in ("txt", "srt", "json"):
            self.assertFalse(Path(f"{symlink_prefix}.{extension}").exists())

    def test_phonon_assembly_offsets_and_audit_schema(self) -> None:
        prefix = self.root / "chunk-0"
        write_artifacts(prefix, call_convert(payload(), self.repo_contract))
        manifest = manifest_for(self.root, [chunk(0, 10_000, 15_000, prefix)])
        output = self.root / "assembled"
        result = run_assembler(manifest, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        assembled_srt = Path(f"{output}.srt").read_text(encoding="utf-8")
        self.assertIn("00:00:10,000 --> 00:00:12,000", assembled_srt)
        self.assertIn("00:00:12,000 --> 00:00:15,000", assembled_srt)
        audit = json.loads(Path(f"{output}.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["schema_version"], 2)
        self.assertEqual(audit["transcription_engine"], "phonon")
        self.assertEqual(audit["completion_state"], "completed")
        self.assertEqual(len(audit["producers"]), 1)
        self.assertIn(VERSION, json.dumps(audit["producers"], sort_keys=True))
        self.assertIn("caller_declared", json.dumps(audit["producers"], sort_keys=True))
        markdown = Path(f"{output}.md").read_text(encoding="utf-8").casefold()
        self.assertIn("phonon-2", markdown)
        self.assertIn("decoding windows", markdown)
        self.assertIn("not word alignment", markdown)
        self.assertIn("machine-generated", markdown)

    def test_assembly_detects_isolated_txt_srt_and_json_edits_before_publication(self) -> None:
        for variant in ("txt", "srt-time", "srt-text", "srt-index", "json"):
            with self.subTest(variant=variant):
                case = self.root / f"tamper-{variant}"
                case.mkdir()
                prefix = case / "chunk-0"
                write_artifacts(prefix, call_convert(payload(), self.repo_contract))
                extension = "srt" if variant.startswith("srt-") else variant
                target = Path(f"{prefix}.{extension}")
                if variant == "txt":
                    target.write_text(target.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
                elif variant.startswith("srt-"):
                    replacements = {
                        "srt-time": ("00:00:02,000", "00:00:02,001"),
                        "srt-text": ("Synthetic first window.", "Edited first window."),
                        "srt-index": ("1\n", "8\n"),
                    }
                    old, new = replacements[variant]
                    target.write_text(
                        target.read_text(encoding="utf-8").replace(old, new, 1),
                        encoding="utf-8",
                    )
                else:
                    changed = json.loads(target.read_text(encoding="utf-8"))
                    changed["segments"][0]["text"] = "Edited synthetic phrase."
                    changed["text"] = "Edited synthetic phrase. Second window."
                    target.write_text(json.dumps(changed), encoding="utf-8")
                manifest = manifest_for(case, [chunk(0, 0, 5000, prefix)])
                output = case / "assembled"
                result = run_assembler(manifest, output)
                self.assertNotEqual(result.returncode, 0)
                assert_no_assembly_outputs(self, output)

    def test_assembly_rejects_missing_corrupt_or_unmarked_phonon_metadata(self) -> None:
        variants = (
            "missing",
            "unsupported-version",
            "producer-mismatch",
            "invalid-evidence",
            "unmarked-raw",
            "completion-state",
            "cue-count",
            "segment-count",
            "truncated",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                case = self.root / f"metadata-{variant}"
                case.mkdir()
                prefix = case / "chunk-0"
                artifacts = call_convert(payload(), self.repo_contract)
                write_artifacts(prefix, artifacts)
                json_path = Path(f"{prefix}.json")
                converted = json.loads(json_path.read_text(encoding="utf-8"))
                if variant == "missing":
                    del converted["_local_transcription"]
                    json_path.write_text(json.dumps(converted), encoding="utf-8")
                elif variant == "unsupported-version":
                    converted["_local_transcription"]["adapter_version"] = 99
                    json_path.write_text(json.dumps(converted), encoding="utf-8")
                elif variant == "producer-mismatch":
                    converted["_local_transcription"]["producer"]["engine"] = "cpu"
                    json_path.write_text(json.dumps(converted), encoding="utf-8")
                elif variant == "invalid-evidence":
                    converted["_local_transcription"]["producer_contract"]["evidence"] = "unknown-source"
                    json_path.write_text(json.dumps(converted), encoding="utf-8")
                elif variant in ("completion-state", "cue-count", "segment-count", "truncated"):
                    if variant == "completion-state":
                        converted["_local_transcription"]["completion_state"] = "completed_no_text"
                    elif variant == "cue-count":
                        converted["_local_transcription"]["cue_count"] = 0
                    elif variant == "segment-count":
                        converted["segment_count"] = 0
                    else:
                        converted["truncated"] = True
                    json_path.write_text(json.dumps(converted), encoding="utf-8")
                else:
                    json_path.write_bytes(json_bytes(payload()))
                manifest = manifest_for(case, [chunk(0, 0, 5000, prefix)])
                output = case / "assembled"
                result = run_assembler(manifest, output)
                self.assertNotEqual(result.returncode, 0)
                assert_no_assembly_outputs(self, output)

    def test_assembly_checks_manifest_span_and_rejects_large_timing_mismatch(self) -> None:
        cases = [
            ("producer duration", {"start_ms": 0, "end_ms": 5002, "duration_ms": 5002}),
            ("short manifest", {"start_ms": 0, "end_ms": 4998, "duration_ms": 4998}),
            ("manifest duration", {"start_ms": 0, "end_ms": 5000, "duration_ms": 5001}),
        ]
        for label, values in cases:
            with self.subTest(label=label):
                case = self.root / f"bad-timing-{label.replace(' ', '-') }"
                case.mkdir()
                prefix = case / "chunk-0"
                write_artifacts(prefix, call_convert(payload(), self.repo_contract))
                chunk_value = {
                    "index": 0,
                    **values,
                    "transcript_prefix": str(prefix),
                }
                manifest = manifest_for(case, [chunk_value])
                output = case / "assembled"
                result = run_assembler(manifest, output)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                assert_no_assembly_outputs(self, output)

    def test_assembly_normalizes_only_one_millisecond_boundary_rounding(self) -> None:
        case = self.root / "rounding-boundary"
        case.mkdir()
        sample = payload(
            duration=5.0,
            segments=[{"start": 0.0, "end": 5.0, "text": "Boundary phrase."}],
        )
        prefix = case / "chunk-0"
        write_artifacts(prefix, call_convert(sample, self.repo_contract))
        manifest = manifest_for(case, [chunk(0, 10_000, 14_999, prefix)])
        output = case / "assembled"
        result = run_assembler(manifest, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "00:00:10,000 --> 00:00:14,999",
            Path(f"{output}.srt").read_text(encoding="utf-8"),
        )
        audit = json.loads(Path(f"{output}.json").read_text(encoding="utf-8"))
        producer_audit = audit["producers"][0]
        adjustments = [
            value
            for key, value in producer_audit.items()
            if "adjust" in key.casefold() and value not in (None, False, 0, "")
        ]
        self.assertTrue(adjustments, producer_audit)

    def test_mixed_engine_manifest_is_rejected_before_any_output(self) -> None:
        phonon_prefix = self.root / "phonon-chunk"
        write_artifacts(phonon_prefix, call_convert(payload(), self.repo_contract))
        whisper_prefix = self.root / "whisper-chunk"
        Path(f"{whisper_prefix}.txt").write_text("Legacy synthetic transcript.\n", encoding="utf-8")
        Path(f"{whisper_prefix}.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nLegacy synthetic transcript.\n\n",
            encoding="utf-8",
        )
        Path(f"{whisper_prefix}.json").write_text('{"fixture":"legacy-whisper"}\n', encoding="utf-8")
        manifest = manifest_for(
            self.root,
            [chunk(0, 0, 5000, phonon_prefix), chunk(1, 5000, 10_000, whisper_prefix)],
        )
        output = self.root / "mixed-output"
        result = run_assembler(manifest, output)
        self.assertNotEqual(result.returncode, 0)
        assert_no_assembly_outputs(self, output)

    def test_all_no_text_and_mixed_completion_publish_complete_coverage(self) -> None:
        silent_prefix = self.root / "silent-chunk"
        silent = payload(segments=[], text="")
        write_artifacts(silent_prefix, call_convert(silent, self.repo_contract))
        manifest = manifest_for(self.root, [chunk(0, 0, 5000, silent_prefix)])
        output = self.root / "no-text-output"
        result = run_assembler(manifest, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(f"{output}.txt").read_text(encoding="utf-8"), "\n")
        self.assertEqual(Path(f"{output}.srt").read_bytes(), b"")
        audit = json.loads(Path(f"{output}.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["completion_state"], "completed_no_text")
        self.assertEqual(audit["segment_count"], 0)
        self.assertEqual(audit["schema_version"], 2)
        markdown = Path(f"{output}.md").read_text(encoding="utf-8").casefold()
        self.assertIn("no text", markdown)

        spoken_prefix = self.root / "spoken-chunk"
        spoken = payload(segments=[{"start": 0.0, "end": 5.0, "text": "Synthetic speech."}])
        write_artifacts(spoken_prefix, call_convert(spoken, self.repo_contract))
        mixed_manifest = manifest_for(
            self.root / "mixed-completion",
            [chunk(0, 0, 5000, silent_prefix), chunk(1, 5000, 10_000, spoken_prefix)],
        )
        mixed_output = self.root / "mixed-completion-output"
        result = run_assembler(mixed_manifest, mixed_output)
        self.assertEqual(result.returncode, 0, result.stderr)
        mixed_audit = json.loads(Path(f"{mixed_output}.json").read_text(encoding="utf-8"))
        self.assertEqual(mixed_audit["completion_state"], "completed")
        self.assertEqual(len(mixed_audit["producers"]), 2)
        self.assertEqual(Path(f"{mixed_output}.txt").read_text(encoding="utf-8"), "Synthetic speech.\n")

    def test_ambiguous_overlap_retains_exit_four_review_flag(self) -> None:
        first = self.root / "overlap-first"
        second = self.root / "overlap-second"
        write_artifacts(
            first,
            call_convert(
                payload(segments=[{"start": 3.0, "end": 4.8, "text": "A distinct first-window statement."}]),
                self.repo_contract,
            ),
        )
        write_artifacts(
            second,
            call_convert(
                payload(segments=[{"start": 0.2, "end": 1.8, "text": "A different second-window statement."}]),
                self.repo_contract,
            ),
        )
        manifest = manifest_for(
            self.root,
            [chunk(0, 0, 5000, first), chunk(1, 4000, 9000, second)],
            overlap_seconds=1,
        )
        output = self.root / "overlap-output"
        result = run_assembler(manifest, output)
        self.assertEqual(result.returncode, 4, result.stderr)
        audit = json.loads(Path(f"{output}.json").read_text(encoding="utf-8"))
        self.assertTrue(audit["overlap_review_required"])
        self.assertTrue(audit["overlap_review_items"])
        self.assertTrue(Path(f"{output}.md").is_file())

    def test_legacy_whisper_assembly_keeps_schema_one_and_heading(self) -> None:
        prefix = self.root / "legacy-whisper"
        Path(f"{prefix}.txt").write_text("Legacy fixture words.\n", encoding="utf-8")
        Path(f"{prefix}.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nLegacy fixture words.\n\n",
            encoding="utf-8",
        )
        Path(f"{prefix}.json").write_text('{"fixture":"legacy-whisper"}\n', encoding="utf-8")
        manifest = manifest_for(self.root, [chunk(0, 0, 5000, prefix)])
        output = self.root / "legacy-output"
        result = run_assembler(manifest, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        audit = json.loads(Path(f"{output}.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["schema_version"], 1)
        self.assertNotIn("transcription_engine", audit)
        self.assertIn("Assembled local Whisper transcript", Path(f"{output}.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
