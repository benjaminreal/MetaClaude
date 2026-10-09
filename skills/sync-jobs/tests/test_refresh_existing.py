import hashlib
import json
import datetime as dt
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock

import openpyxl
from openpyxl.worksheet.table import Table


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import acquisition_capture
import build_worklist
import posting_compensation
import posting_eligibility
from refresh_existing import RefreshError, commit_refresh, main, preview_refresh
from source_verification import compare_capture, digest, prepare


HEADERS = [
    "Tracker ID", "Previous Row", "Puesto", "Empresa", "Pais", "Estatus",
    "Next Action", "JD File", "Link puesto linkedin", "Comentarios", "Track",
    "Link puesto empresa", "Fit Score", "Priority", "Sponsor Status",
    "Next Action Date", "Triage Summary", "Decision Driver",
    "Primary Risk / Blocker", "Key Uplifts", "Triage Date", "Triage Batch",
    "Aplique (Fecha)",
]


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RefreshExisting(unittest.TestCase):
    def setUp(self):
        # ``/var`` is a macOS symlink to ``/private/var``.  The runtime
        # path-safety checks intentionally reject symlink components, so keep
        # deterministic fixtures under the real temporary root.
        self.temp = tempfile.TemporaryDirectory(prefix="refresh-existing-", dir="/private/tmp")
        self.root = Path(self.temp.name)
        self.tracker = self.root / "jobs.xlsx"
        postings = self.root / "JobPostings" / "postings"
        compensation = self.root / "JobPostings" / "_meta" / "compensation"
        postings.mkdir(parents=True)
        compensation.mkdir(parents=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Jobs"
        ws.append(HEADERS)
        ws.append([
            "J-000001", None, "Role | Platform", "Fixture", "MX", "Saved", None,
            "JobPostings/postings/100.md", "https://www.linkedin.com/jobs/view/100/",
            "preserve", None, None, None, None, None, None, None, None, None,
            None, None, None, None, None,
        ])
        ws.add_table(Table(displayName="JobsTable", ref="A1:W2"))
        wb.save(self.tracker)
        self.archive = postings / "100.md"
        self.source_url = "https://www.linkedin.com/jobs/view/100/"
        self.old_body = "Original body for 100 with salary USD 100-200.\n"
        self.new_body = "Updated body for 100 with salary USD 120-240 and an inline link.\n"
        self._write_archive(self.old_body)
        self.sidecar = compensation / "J-000001_PostingCompensationV1.json"
        old_sidecar = posting_compensation.extract_text(
            self.archive.read_text(encoding="utf-8"),
            posting_path=self.archive,
            tracker_id="J-000001",
            source_url=self.source_url,
        )
        self.sidecar.write_text(json.dumps(old_sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write_archive(self, body: str):
        self.archive.write_text(
            "# Role | Platform\nCompany: Fixture\nLocation: Example location\n"
            "Source: https://www.linkedin.com/jobs/view/100/\n"
            "Metadata: preserve | exactly\n\n## About the Job\n\n" + body,
            encoding="utf-8",
        )

    def _record(self, body: str | None = None, captured_at: str | None = None):
        body = body or self.new_body
        captured_at = captured_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "id": "100",
            "title": "Role | Platform",
            "company": "Fixture",
            "location": "Example location",
            "status": "Saved",
            "url": self.source_url,
            "description": body,
            "provenance": {
                "browser": "authorized-browser-a",
                "method": "rendered_dom_text",
                "captured_at": captured_at,
                "complete_text": True,
                "completion_evidence": "Expanded and read through the final section.",
                "status_certain": True,
            },
            "quality_evidence": {
                "end_verified": True,
                "end_marker": body[-18:],
                "truncation_flags": [],
            },
            "source_evidence": {
                "inline_links": ["inline link"],
                "widget_text": "Salary widget observed separately.",
            },
        }

    def _audit(self):
        selection_dir = self.root / "selection"
        prepare(self.root, self.tracker, selection_dir, ["100"], None)
        normalized = acquisition_capture.validate_record(self._record(), {"100"})
        bundle = {
            "schema": "SelectedPostingAcquisitionV1",
            "mode": "ACQUISITION_ONLY_NOT_OFFICIAL_NEW_IDS",
            "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "selected_ids": ["100"],
            "records": [normalized],
            "failures": [],
            "complete": True,
            "quality_complete": True,
            "quality_blocked_ids": [],
            "claims": {
                "official_new_ids": False,
                "sync_completed": False,
                "tracker_or_archive_gates_run": False,
            },
            "source_input_sha256": "0" * 64,
        }
        capture = self.root / "capture.json"
        capture.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        audit_dir = self.root / "audit"
        audit = compare_capture(self.root, self.tracker, selection_dir / "selection.json", capture, audit_dir)
        self.assertEqual(audit["results"][0]["classification"], "substantive_difference")
        return audit_dir / "audit.json"

    def _rehash_manifest(self, run: Path, mutate):
        path = run / "preview_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        mutate(manifest)
        core = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        manifest["manifest_sha256"] = digest(core)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def test_preview_preserves_header_and_writes_only_run_artifacts(self):
        audit_path = self._audit()
        tracker_before = file_sha(self.tracker)
        archive_before = self.archive.read_bytes()
        sidecar_before = self.sidecar.read_bytes()
        run = self.root / "refresh"
        manifest = preview_refresh(
            root=self.root,
            tracker=self.tracker,
            audit_path=audit_path,
            out_dir=run,
            selected_ids=["100"],
        )
        self.assertEqual(file_sha(self.tracker), tracker_before)
        self.assertEqual(self.archive.read_bytes(), archive_before)
        self.assertEqual(self.sidecar.read_bytes(), sidecar_before)
        self.assertEqual(manifest["selected_ids"], ["100"])
        self.assertTrue((run / "before" / "J-000001.md").is_file())
        self.assertTrue((run / "staged" / "J-000001.md").is_file())
        staged = (run / "staged" / "J-000001.md").read_bytes()
        self.assertTrue(staged.startswith(archive_before.split(b"## About the Job", 1)[0] + b"## About the Job"))
        self.assertIn(self.new_body.encode(), staged)
        self.assertNotEqual(file_sha(self.sidecar), manifest["targets"][0]["new_sidecar_sha256"])

    def test_commit_changes_only_target_and_replay_is_idempotent(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        manifest = preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        before_tracker = file_sha(self.tracker)
        result = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(result["status"], "committed")
        self.assertEqual(file_sha(self.tracker), before_tracker)
        self.assertIn(self.new_body, self.archive.read_text(encoding="utf-8"))
        sidecar = json.loads(self.sidecar.read_text(encoding="utf-8"))
        posting_compensation.validate(sidecar, verify_file=False)
        self.assertEqual(sidecar["posting"]["sha256"], file_sha(self.archive))
        replay = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(replay["status"], "already_applied")
        self.assertTrue(replay["idempotent_replay"])

    def test_stale_archive_aborts_before_any_live_write(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        before_sidecar = self.sidecar.read_bytes()
        self.archive.write_bytes(self.archive.read_bytes() + b"concurrent edit\n")
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(self.sidecar.read_bytes(), before_sidecar)
        self.assertFalse((run / "receipt.json").exists())

    def test_stale_capture_aborts_before_any_live_write(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        capture_path = self.root / "capture.json"
        capture_path.write_bytes(capture_path.read_bytes() + b"\n")
        old_archive = self.archive.read_bytes()
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(self.archive.read_bytes(), old_archive)
        self.assertFalse((run / "receipt.json").exists())

    def test_raw_capture_rewrapped_with_new_audit_hash_is_rejected(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        capture_path = self.root / "capture.json"
        bundle = json.loads(capture_path.read_text(encoding="utf-8"))
        # Replace the normalized emitted record with the input-only shape, then
        # rehash both artifacts.  Refresh must still reject it because the
        # capture bundle itself is required to retain normalized derived fields.
        bundle["records"] = [self._record()]
        capture_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        audit["capture_bundle_sha256"] = file_sha(capture_path)
        audit_core = {key: value for key, value in audit.items() if key != "audit_sha256"}
        audit["audit_sha256"] = digest(audit_core)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        old_archive = self.archive.read_bytes()
        with self.assertRaises(RefreshError):
            preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        self.assertEqual(self.archive.read_bytes(), old_archive)
        self.assertFalse((run / "preview_manifest.json").exists())

    def test_injected_failure_rolls_back_replaced_archive(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes()
        calls = []
        real_replace = __import__("refresh_existing").atomic_replace

        def fail_on_sidecar(path, data):
            calls.append(path)
            if path == self.sidecar:
                raise OSError("simulated sidecar failure")
            return real_replace(path, data)

        with mock.patch("refresh_existing.atomic_replace", side_effect=fail_on_sidecar):
            result = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(self.archive.read_bytes(), old_archive)
        self.assertIn("rolled_back", (run / "journal.jsonl").read_text(encoding="utf-8"))

    def test_concurrent_edit_during_rollback_is_preserved_as_partial_commit(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes()
        module = __import__("refresh_existing")
        real_replace = module.atomic_replace

        def fail_after_concurrent_archive_edit(path, data):
            if path == self.sidecar:
                # Simulate an owner edit landing after the archive replacement
                # and before rollback begins.
                self.archive.write_bytes(self.archive.read_bytes() + b"owner edit\n")
                raise OSError("simulated sidecar failure")
            return real_replace(path, data)

        with mock.patch("refresh_existing.atomic_replace", side_effect=fail_after_concurrent_archive_edit):
            result = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(result["status"], "partial_commit")
        self.assertNotEqual(self.archive.read_bytes(), old_archive)
        self.assertTrue(result.get("rollback_conflicts"))

    def test_process_death_recovery_uses_durable_replacing_intent(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes()
        old_sidecar = self.sidecar.read_bytes()
        child = textwrap.dedent(
            """
            import os
            import sys
            from pathlib import Path
            sys.path.insert(0, sys.argv[1])
            import refresh_existing as module
            original = module.atomic_replace
            def crash_after_replace(path, data):
                original(path, data)
                os._exit(77)
            module.atomic_replace = crash_after_replace
            module.commit_refresh(
                root=Path(sys.argv[2]),
                tracker=Path(sys.argv[3]),
                preview_manifest=Path(sys.argv[4]),
            )
            """
        )
        crashed = subprocess.run(
            [sys.executable, "-c", child, str(SCRIPTS), str(self.root), str(self.tracker), str(run / "preview_manifest.json")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(crashed.returncode, 77, crashed.stderr)
        self.assertNotEqual(self.archive.read_bytes(), old_archive)
        self.assertIn('"state":"replacing"', (run / "journal.jsonl").read_text(encoding="utf-8"))
        recovered = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(recovered["status"], "rolled_back")
        self.assertEqual(self.archive.read_bytes(), old_archive)
        self.assertEqual(self.sidecar.read_bytes(), old_sidecar)
        receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "rolled_back")

    def test_recovery_preserves_matching_bytes_without_durable_intent(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        module = __import__("refresh_existing")
        manifest = json.loads((run / "preview_manifest.json").read_text(encoding="utf-8"))
        population_before = module._snapshot_population(self.root)
        proposed_archive = (run / "staged" / "J-000001.md").read_bytes()
        self.archive.write_bytes(proposed_archive)
        module._append_journal(
            run / "journal.jsonl",
            module._event(
                {},
                "transaction",
                "started",
                manifest_sha256=manifest["manifest_sha256"],
                population_before=population_before,
            ),
        )
        recovered = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(recovered["status"], "partial_commit")
        self.assertEqual(self.archive.read_bytes(), proposed_archive)
        self.assertTrue(recovered.get("recovery_conflicts"))

    def test_recovery_rejects_journal_for_another_manifest(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        module = __import__("refresh_existing")
        manifest = json.loads((run / "preview_manifest.json").read_text(encoding="utf-8"))
        module._append_journal(
            run / "journal.jsonl",
            module._event(
                {},
                "transaction",
                "started",
                manifest_sha256="0" * 64,
                population_before=module._snapshot_population(self.root),
            ),
        )
        old_archive = self.archive.read_bytes()
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(self.archive.read_bytes(), old_archive)

    def test_population_addition_rolls_back_ours_and_preserves_addition(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes()
        old_sidecar = self.sidecar.read_bytes()
        module = __import__("refresh_existing")
        real_replace = module.atomic_replace
        addition = self.root / "JobPostings" / "postings" / "concurrent.md"

        def add_after_sidecar(path, data):
            result = real_replace(path, data)
            if path == self.sidecar:
                addition.write_bytes(b"concurrent posting addition\n")
            return result

        with mock.patch("refresh_existing.atomic_replace", side_effect=add_after_sidecar):
            result = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(result["status"], "partial_commit")
        self.assertEqual(self.archive.read_bytes(), old_archive)
        self.assertEqual(self.sidecar.read_bytes(), old_sidecar)
        self.assertEqual(addition.read_bytes(), b"concurrent posting addition\n")

    def test_replay_rejects_tracker_or_population_change(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        addition = self.root / "JobPostings" / "postings" / "concurrent.md"
        addition.write_bytes(b"post-commit addition\n")
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        addition.unlink()
        self.tracker.write_bytes(self.tracker.read_bytes() + b"tracker edit")
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")

    def test_public_module_cli_runs_preview_and_commit(self):
        audit_path = self._audit()
        run = self.root / "cli-refresh"
        preview_rc = main([
            "--project-root", str(self.root), "--audit", str(audit_path),
            "--out-dir", str(run), "--selected-id", "100",
        ])
        self.assertEqual(preview_rc, 0)
        commit_rc = main([
            "--project-root", str(self.root), "--preview-manifest",
            str(run / "preview_manifest.json"), "--commit",
        ])
        self.assertEqual(commit_rc, 0)

    def test_all_substantive_requires_a_fresh_audit(self):
        audit_path = self._audit()
        run = self.root / "refresh"
        manifest = preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, approve_all_substantive=True)
        self.assertEqual(manifest["selection_basis"], "all_substantive_difference_results")

    def test_v2_rejects_self_rehashed_redirected_target(self):
        audit_path = self._audit(); run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        foreign = "JobPostings/postings/redirected.md"
        def redirect(manifest):
            manifest["targets"][0]["archive_path"] = foreign
            manifest["targets"][0]["files"][0]["path"] = foreign
        path = self._rehash_manifest(run, redirect)
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=path)

    def test_v2_rejects_wrong_run_dir_even_when_rehashed(self):
        audit_path = self._audit(); run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        path = self._rehash_manifest(run, lambda manifest: manifest.__setitem__("run_dir", str(self.root / "elsewhere")))
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=path)

    def test_v2_rejects_tampered_staged_eligibility_before_write(self):
        audit_path = self._audit(); run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes(); old_sidecar = self.sidecar.read_bytes()
        (run / "staged" / "J-000001_PostingEligibilityV1.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(self.archive.read_bytes(), old_archive); self.assertEqual(self.sidecar.read_bytes(), old_sidecar)

    def test_v2_rejects_bad_before_hash_before_write(self):
        audit_path = self._audit(); run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes(); old_sidecar = self.sidecar.read_bytes()
        (run / "before" / "J-000001.md").write_bytes(b"tampered backup\n")
        with self.assertRaises(RefreshError):
            commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(self.archive.read_bytes(), old_archive); self.assertEqual(self.sidecar.read_bytes(), old_sidecar)

    def test_v2_foreign_same_bytes_create_race_is_preserved(self):
        audit_path = self._audit(); run = self.root / "refresh"
        manifest = preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        eligibility = self.root / manifest["targets"][0]["eligibility_path"]
        proposed = (run / manifest["targets"][0]["staged_eligibility_path"]).read_bytes()
        def foreign_create(path, data, claim):
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            raise FileExistsError("simulated concurrent same-byte create")
        with mock.patch("refresh_existing._create_no_clobber", side_effect=foreign_create):
            result = commit_refresh(root=self.root, tracker=self.tracker, preview_manifest=run / "preview_manifest.json")
        self.assertEqual(result["status"], "partial_commit")
        self.assertEqual(eligibility.read_bytes(), proposed)

    def test_v2_process_death_after_created_event_recovers_owned_create(self):
        audit_path = self._audit(); run = self.root / "refresh"
        preview_refresh(root=self.root, tracker=self.tracker, audit_path=audit_path, out_dir=run, selected_ids=["100"])
        old_archive = self.archive.read_bytes(); old_sidecar = self.sidecar.read_bytes()
        child = textwrap.dedent(
            """
            import os,sys
            from pathlib import Path
            sys.path.insert(0,sys.argv[1]);import refresh_existing as module
            original=module._write_artifact
            def crash_before_receipt(path,value):
                if path.name=='receipt.json': os._exit(77)
                return original(path,value)
            module._write_artifact=crash_before_receipt
            module.commit_refresh(root=Path(sys.argv[2]),tracker=Path(sys.argv[3]),preview_manifest=Path(sys.argv[4]))
            """
        )
        crashed=subprocess.run([sys.executable,"-c",child,str(SCRIPTS),str(self.root),str(self.tracker),str(run/"preview_manifest.json")])
        self.assertEqual(crashed.returncode,77)
        recovered=commit_refresh(root=self.root,tracker=self.tracker,preview_manifest=run/"preview_manifest.json")
        self.assertEqual(recovered["status"],"rolled_back")
        self.assertEqual(self.archive.read_bytes(),old_archive);self.assertEqual(self.sidecar.read_bytes(),old_sidecar)
        self.assertFalse((self.root/"JobPostings/_meta/eligibility/J-000001_PostingEligibilityV1.json").exists())

    def test_worklist_distinguishes_stale_sidecar_without_quotes(self):
        eligibility_dir = self.root / "JobPostings" / "_meta" / "eligibility"; eligibility_dir.mkdir()
        previous_root = posting_eligibility.ROOT; posting_eligibility.ROOT = self.root
        try:
            value = posting_eligibility.extract_file(self.archive, tracker_id="J-000001", source_url=self.source_url, linkedin_id="100")
        finally:
            posting_eligibility.ROOT = previous_root
        (eligibility_dir / "J-000001_PostingEligibilityV1.json").write_text(json.dumps(value), encoding="utf-8")
        self.archive.write_bytes(self.archive.read_bytes() + b"new current bytes\n")
        previous_project = build_worklist.PROJECT_ROOT; build_worklist.PROJECT_ROOT = str(self.root)
        try:
            evidence = build_worklist.eligibility_evidence("J-000001", str(self.archive), self.source_url)
        finally:
            build_worklist.PROJECT_ROOT = previous_project
        self.assertEqual(evidence["availability"], "stale")
        self.assertEqual(evidence["mentions"], [])
        self.assertEqual(evidence["unclassified_candidate_spans"], [])


if __name__ == "__main__":
    unittest.main()
