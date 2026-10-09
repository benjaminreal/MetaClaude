import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

import openpyxl

import test_workflow as fixture

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import build_worklist
import sync_ingest
from private_files import publish_private_file
from write_tracker import main as write_tracker_main


def mode(path):
    return stat.S_IMODE(Path(path).stat().st_mode)


def output_path(stdout):
    match = re.search(r"-> (.+)$", stdout, re.MULTILINE)
    if not match:
        raise AssertionError(f"no output path in command output: {stdout}")
    return Path(match.group(1).strip())


class PrivateFileSafety(unittest.TestCase):
    setUp = fixture.Workflow.setUp
    tearDown = fixture.Workflow.tearDown
    runstage = fixture.Workflow.runstage

    def test_default_worklist_and_diff_paths_are_unique(self):
        worklist_paths = []
        for root in (self.root, self.root / "second-project"):
            root.mkdir(exist_ok=True)
            tracker = self.tracker if root == self.root else root / "jobs.xlsx"
            if root != self.root:
                shutil.copyfile(self.tracker, tracker)
            old_root = build_worklist.PROJECT_ROOT
            build_worklist.PROJECT_ROOT = str(root)
            try:
                captured = io.StringIO()
                with contextlib.redirect_stdout(captured):
                    self.assertEqual(build_worklist.main(["--tracker", str(tracker)]), 0)
                path = output_path(captured.getvalue())
                worklist_paths.append(path)
                self.addCleanup(shutil.rmtree, path.parent)
            finally:
                build_worklist.PROJECT_ROOT = old_root
        self.assertNotEqual(worklist_paths[0], worklist_paths[1])
        for path in worklist_paths:
            self.assertEqual(mode(path.parent), 0o700)
            self.assertEqual(mode(path), 0o600)

        old_root = sync_ingest.PROJECT_ROOT
        old_postings = sync_ingest.POSTINGS_DIR
        sync_ingest.PROJECT_ROOT = str(self.root)
        sync_ingest.POSTINGS_DIR = str(self.root / "JobPostings/postings")
        try:
            diff_paths = []
            for _ in range(2):
                captured = io.StringIO()
                args = type("Args", (), {"saved_json": [str(self.saved)],
                                         "tracker": str(self.tracker), "out": None})()
                with contextlib.redirect_stdout(captured):
                    self.assertEqual(sync_ingest.cmd_diff(args), 0)
                path = output_path(captured.getvalue())
                diff_paths.append(path)
                self.addCleanup(shutil.rmtree, path.parent)
        finally:
            sync_ingest.PROJECT_ROOT = old_root
            sync_ingest.POSTINGS_DIR = old_postings
        self.assertNotEqual(diff_paths[0], diff_paths[1])
        for path in diff_paths:
            self.assertEqual(mode(path.parent), 0o700)
            self.assertEqual(mode(path), 0o600)

    def test_explicit_output_refuses_existing_regular_and_symlink_targets(self):
        regular = self.root / "existing.json"
        regular.write_bytes(b"preserve this regular file")
        before = regular.read_bytes()
        with self.assertRaises(FileExistsError):
            publish_private_file(regular, "replacement")
        self.assertEqual(regular.read_bytes(), before)

        target = self.root / "symlink-target.json"
        target.write_bytes(b"preserve symlink target")
        link = self.root / "output-link.json"
        link.symlink_to(target)
        with self.assertRaises(FileExistsError):
            publish_private_file(link, "replacement")
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), b"preserve symlink target")

    def test_direct_external_helper_refuses_without_touching_tracker(self):
        tracker = self.root / "disposable.xlsx"
        tracker.write_bytes(b"synthetic tracker bytes")
        before = tracker.read_bytes()
        records = self.root / "records.json"
        records.write_text(json.dumps({"records": []}), encoding="utf-8")
        backup_root = self.root / "backup-root"
        result = subprocess.run(
            [sys.executable, str(SKILL / "scripts/external_intake.py"),
             "--project-root", str(self.root), "--tracker", str(tracker),
             "--records-json", str(records), "--backup-dir", str(backup_root)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sync_jobs.py", result.stderr)
        self.assertEqual(tracker.read_bytes(), before)
        self.assertFalse(backup_root.exists())

    def test_writer_staging_and_backups_are_private_under_umask_022(self):
        old_umask = os.umask(0o022)
        try:
            external_payload = self.root / "external-records.json"
            external_payload.write_text(json.dumps({"records": [{
                "title": "Synthetic role", "company": "Example Corp",
                "location": "Example location",
                "url": "https://careers.example.com/jobs/42",
                "description": "Coordinate a fully synthetic example process. Fixture ends here.",
                "status": "Saved",
                "provenance": {"browser": "synthetic-browser", "method": "rendered_dom_text",
                               "captured_at": "2030-01-01T20:00:00Z", "complete_text": True,
                               "completion_evidence": "Read the final sentence.", "status_certain": True},
                "quality_evidence": {"end_verified": True, "end_marker": "Fixture ends here.",
                                     "truncation_flags": []},
            }]}), encoding="utf-8")
            external_parent = self.root / "external-backups"
            external_parent.mkdir(mode=0o751)
            external_parent_mode = mode(external_parent)
            result = self.runstage("external-ingest", "--records-json", external_payload,
                                   "--backup-dir", external_parent)
            self.assertEqual(mode(external_parent), external_parent_mode)
            stage = Path(json.loads(result.stdout)["stage"])
            self.assertEqual(mode(stage), 0o700)
            external_files = list(stage.rglob("*"))
            self.assertTrue(any(p.name.endswith(".backup.xlsx") for p in external_files))
            for path in external_files:
                if path.is_file():
                    self.assertEqual(mode(path), 0o600, path)
                elif path.is_dir():
                    self.assertEqual(mode(path), 0o700, path)

            ingest_parent = self.root / "ingest-backups"
            ingest_parent.mkdir(mode=0o751)
            ingest_parent_mode = mode(ingest_parent)
            old_globals = (sync_ingest.PROJECT_ROOT, sync_ingest.POSTINGS_DIR,
                           sync_ingest.JOBPOSTINGS_TREE, sync_ingest.META_DIR)
            sync_ingest.PROJECT_ROOT = str(self.root)
            sync_ingest.POSTINGS_DIR = str(self.root / "JobPostings/postings")
            sync_ingest.JOBPOSTINGS_TREE = str(self.root / "JobPostings")
            sync_ingest.META_DIR = str(self.root / "JobPostings/_meta")
            ingest_output = io.StringIO()
            try:
                with contextlib.redirect_stdout(ingest_output):
                    self.assertEqual(sync_ingest.main([
                        "--tracker", str(self.tracker), "--backup-dir", str(ingest_parent),
                        "ingest", "--jobs-json", str(self.jobs), "--dry-run"]), 0)
            finally:
                (sync_ingest.PROJECT_ROOT, sync_ingest.POSTINGS_DIR,
                 sync_ingest.JOBPOSTINGS_TREE, sync_ingest.META_DIR) = old_globals
            self.assertEqual(mode(ingest_parent), ingest_parent_mode)
            backup_line = next(line for line in ingest_output.getvalue().splitlines()
                               if line.startswith("sync_ingest: backup -> "))
            ingest_run = Path(backup_line.split(" -> ", 1)[1]).parent
            self.assertEqual(mode(ingest_run), 0o700)
            for path in ingest_run.rglob("*"):
                self.assertEqual(mode(path), 0o600 if path.is_file() else 0o700, path)

            tracker = self.root / "writer.xlsx"
            shutil.copyfile(self.tracker, tracker)
            results = self.root / "writer-results.json"
            results.write_text(json.dumps({"report_batch": "synthetic-batch.json",
                "results": {"J-000001": {"cells": {"Triage Summary": "Synthetic summary"}}}}),
                encoding="utf-8")
            writer_parent = self.root / "writer-backups"
            writer_parent.mkdir(mode=0o751)
            writer_parent_mode = mode(writer_parent)
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(write_tracker_main([
                    "--tracker", str(tracker), "--results", str(results), "--dry-run",
                    "--backup-dir", str(writer_parent)]), 0)
            self.assertEqual(mode(writer_parent), writer_parent_mode)
            write_run = output_path(captured.getvalue().replace("write_tracker: backup -> ", "-> "))
            self.assertEqual(mode(write_run.parent), 0o700)
            for path in write_run.parent.rglob("*"):
                self.assertEqual(mode(path), 0o600 if path.is_file() else 0o700, path)
        finally:
            os.umask(old_umask)


if __name__ == "__main__":
    unittest.main()
