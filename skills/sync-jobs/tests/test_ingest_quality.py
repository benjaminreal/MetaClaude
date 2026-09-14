import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

import test_workflow as fixture


SKILL = fixture.SKILL
digest = fixture.digest


class IngestQuality(fixture.Workflow):
    def _record(self):
        description = "A complete role description with a verified final section."
        return {
            "id": "200",
            "title": "Role",
            "company": "Fixture",
            "location": "Example location",
            "url": "https://www.linkedin.com/jobs/view/200/",
            "description": description,
            "status": "Saved",
            "provenance": {
                "browser": "authorized-browser-a",
                "method": "rendered_dom_text",
                "captured_at": "2026-09-08T00:00:00Z",
                "complete_text": True,
                "completion_evidence": "Expanded and read through the final section.",
                "status_certain": True,
            },
            "quality_evidence": {
                "end_verified": True,
                "end_marker": "verified final section.",
                "truncation_flags": [],
            },
        }

    def _write(self, payload):
        self.jobs.write_text(json.dumps(payload))

    def _assert_no_workspace_write(self, before):
        self.assertEqual(digest(self.tracker), before)
        self.assertEqual(list(self.root.glob("*.backup_*.xlsx")), [])
        self.assertEqual(
            sorted(p.name for p in (self.root / "JobPostings/postings").glob("*.md")),
            ["existing.md"],
        )

    def test_valid_acquisition_bundle_ingests(self):
        self._write({
            "schema": "SelectedPostingAcquisitionV1",
            "selected_ids": ["200"],
            "complete": True,
            "quality_complete": True,
            "records": [self._record()],
            "failures": [],
        })
        self.runstage("ingest", "--jobs-json", self.jobs, commit=True)
        self.assertEqual(len(list((self.root / "JobPostings/postings").glob("*.md"))), 2)

    def test_bundle_with_dropped_selected_record_is_blocked_before_writes(self):
        self._write({
            "schema": "SelectedPostingAcquisitionV1",
            "selected_ids": ["200", "201"],
            "complete": True,
            "quality_complete": True,
            "records": [self._record()],
            "failures": [],
        })
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("cover selected_ids exactly", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)

    def test_records_envelope_without_schema_cannot_bypass_dropped_record_gate(self):
        self._write({
            "selected_ids": ["200", "201"],
            "complete": True,
            "quality_complete": True,
            "records": [self._record()],
            "failures": [],
        })
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("require schema SelectedPostingAcquisitionV1", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)

    def test_records_envelope_with_wrong_schema_cannot_bypass_dropped_record_gate(self):
        self._write({
            "schema": "HandEditedBundleV1",
            "selected_ids": ["200", "201"],
            "complete": True,
            "quality_complete": True,
            "records": [self._record()],
            "failures": [],
        })
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("require schema SelectedPostingAcquisitionV1", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)

    def test_bare_legacy_record_without_quality_is_blocked_before_writes(self):
        record = self._record()
        record.pop("quality_evidence")
        self._write([record])
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("acquisition quality blocked", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)

    def test_native_exact_512_node_without_independent_check_is_blocked(self):
        record = self._record()
        record["description"] = "S" * 512
        record["provenance"]["browser"] = "authorized-browser-b"
        record["provenance"]["method"] = "native_text"
        record["native_nodes"] = [{"role": "text", "text": record["description"]}]
        record["quality_evidence"] = {
            "end_verified": True,
            "end_marker": "S" * 24,
            "truncation_flags": [],
            "native_scope": "job_description_only",
        }
        self._write({
            "schema": "SelectedPostingAcquisitionV1", "selected_ids": ["200"],
            "complete": True, "quality_complete": True,
            "records": [record], "failures": [],
        })
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("NATIVE_NODE_EXACT_512", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)

    def test_tampered_description_recomputes_quality_and_blocks(self):
        record = self._record()
        # A stale embedded PASS must not authorize changed description bytes.
        record["quality"] = {
            "schema": "CaptureQualityV1",
            "status": "PASS",
            "eligible_for_ingest": True,
            "description_sha256": hashlib.sha256(record["description"].encode()).hexdigest(),
        }
        record["description"] += " Tampered after validation."
        self._write({
            "schema": "SelectedPostingAcquisitionV1", "selected_ids": ["200"],
            "complete": True, "quality_complete": True,
            "records": [record], "failures": [],
        })
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("END_MARKER_MISMATCH", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)

    def test_bundle_failures_block_valid_subset_before_writes(self):
        payload = {
            "schema": "SelectedPostingAcquisitionV1",
            "selected_ids": ["200", "999"],
            "complete": False,
            "quality_complete": False,
            "records": [self._record()],
            "failures": [{"id": "999", "reason": "Complete text unavailable."}],
        }
        self._write(payload)
        before = digest(self.tracker)
        result = self.runstage("ingest", "--jobs-json", self.jobs, commit=True, ok=False)
        self.assertIn("retains blocked failure", result.stderr + result.stdout)
        self._assert_no_workspace_write(before)


if __name__ == "__main__":
    unittest.main()
