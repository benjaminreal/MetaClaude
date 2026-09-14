import json
import datetime as dt
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import openpyxl
from openpyxl.worksheet.table import Table

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
from source_verification import compare_bodies


HEADERS = [
    "Tracker ID", "Previous Row", "Puesto", "Empresa", "Pais", "Estatus",
    "Next Action", "JD File", "Link puesto linkedin", "Comentarios", "Track",
    "Link puesto empresa", "Fit Score", "Priority", "Sponsor Status",
    "Next Action Date", "Triage Summary", "Decision Driver",
    "Primary Risk / Blocker", "Key Uplifts", "Triage Date", "Triage Batch",
    "Aplique (Fecha)",
]


class SourceVerificationCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-verification-")
        self.root = Path(self.temp.name)
        self.tracker = self.root / "jobs.xlsx"
        postings = self.root / "JobPostings" / "postings"
        postings.mkdir(parents=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Jobs"
        ws.append(HEADERS)
        for index, (tracker_id, jid, title, company) in enumerate(
            (("J-000001", "100", "Role | Platform", "Fixture"),
             ("J-000002", "200", "Second Role", "Fixture")), start=1
        ):
            filename = f"{jid}.md"
            ws.append([
                tracker_id, None, title, company, "MX", "Saved", None,
                f"JobPostings/postings/{filename}",
                f"https://www.linkedin.com/jobs/view/{jid}/", None, None,
                None, None, None, None, None, None, None, None, None, None,
                None, None,
            ])
            self._write_archive(postings / filename, jid, title, company, f"Original body for {jid}.\n")
        ws.add_table(Table(displayName="JobsTable", ref="A1:W3"))
        wb.save(self.tracker)

    def tearDown(self):
        self.temp.cleanup()

    def _write_archive(self, path, jid, title, company, body):
        path.write_text(
            f"# {title}\nCompany: {company}\nLocation: Example location\n"
            f"Source: https://www.linkedin.com/jobs/view/{jid}/\n\n"
            f"## About the Job\n\n{body}", encoding="utf-8"
        )

    def _run(self, *args, ok=True):
        cmd = [
            sys.executable, str(SCRIPTS / "sync_jobs.py"),
            "--project-root", str(self.root), "--profile", "example",
            *map(str, args),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def _record(self, jid="100", title="Role | Platform", body=None, captured_at=None):
        body = body or "Original body for 100 with salary USD 100-200.\n"
        captured_at = captured_at or dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "id": jid,
            "title": title,
            "company": "Fixture",
            "location": "Example location",
            "status": "Saved",
            "url": f"https://www.linkedin.com/jobs/view/{jid}/",
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
                "inline_links": ["Apply here"],
                "widget_text": "Salary widget observed separately.",
            },
        }

    def _capture(self, records, selected_ids, failures=None, name=None):
        source = self.root / "capture-input.json"
        output = self.root / (name or ("capture-" + "-".join(selected_ids) + ".json"))
        source.write_text(json.dumps({"records": records, "failures": failures or []}), encoding="utf-8")
        args = [
            "acquire-save", "--records-json", source, "--out", output,
        ]
        for jid in selected_ids:
            args += ["--selected-id", jid]
        self._run(*args)
        return output

    def test_prepare_compare_preserves_pipe_identity_and_raw_source_evidence(self):
        run = self.root / "audit-run"
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", run)
        selection = json.loads((run / "selection.json").read_text())
        self.assertEqual(selection["entries"][0]["title"], "Role | Platform")
        body = "Original body for 100 with salary USD 110-220.\n"
        capture = self._capture([self._record(body=body)], ["100"])
        audit_run = self.root / "compare-run"
        self._run(
            "audit-existing", "compare", "--selection", run / "selection.json",
            "--capture-bundle", capture, "--out-dir", audit_run,
        )
        audit = json.loads((audit_run / "audit.json").read_text())
        result = audit["results"][0]
        self.assertEqual(result["classification"], "substantive_difference")
        self.assertEqual(result["historical_cause"], "unresolved")
        self.assertTrue(result["fresh_source_validated"])
        self.assertEqual(result["source_evidence"]["source_evidence"]["inline_links"], ["Apply here"])
        raw = json.loads((audit_run / "raw_differences" / "100.json").read_text())
        self.assertEqual(raw["live_body"], body)

    def test_partial_capture_is_explicitly_unvisited(self):
        selection_run = self.root / "selection-two"
        self._run(
            "audit-existing", "prepare", "--selected-id", "100", "--selected-id", "200",
            "--out-dir", selection_run,
        )
        capture = self._capture([self._record(body="Original body for 100.\n")], ["100"])
        audit_run = self.root / "partial-audit"
        self._run(
            "audit-existing", "compare", "--selection", selection_run / "selection.json",
            "--capture-bundle", capture, "--out-dir", audit_run,
        )
        audit = json.loads((audit_run / "audit.json").read_text())
        statuses = {row["linkedin_id"]: row["classification"] for row in audit["results"]}
        self.assertEqual(statuses, {"100": "exact_match", "200": "unvisited"})
        self.assertEqual(audit["counts"]["selected"], 2)
        self.assertEqual(audit["counts"]["unvisited"], 1)
        self.assertFalse(audit["claims"]["fresh_source_verification"])

    def test_local_check_cannot_claim_fresh_source(self):
        selection_run = self.root / "local-selection"
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", selection_run)
        local_run = self.root / "local-audit"
        self._run(
            "audit-existing", "local-check", "--selection", selection_run / "selection.json",
            "--out-dir", local_run,
        )
        audit = json.loads((local_run / "audit.json").read_text())
        self.assertEqual(audit["mode"], "LOCAL_ARTIFACT_VALIDATION_ONLY")
        self.assertFalse(audit["claims"]["fresh_source_verification"])
        self.assertFalse(audit["results"][0]["fresh_source_validated"])

    def test_latest_n_uses_tracker_id_fallback_and_not_mtime(self):
        run = self.root / "latest"
        self._run("audit-existing", "prepare", "--latest-n", "1", "--out-dir", run)
        selection = json.loads((run / "selection.json").read_text())
        self.assertEqual(selection["selection_basis"], "tracker_id_order_fallback")
        self.assertEqual(selection["selected_ids"], ["200"])
        (self.root / "JobPostings" / "postings" / "200.md").touch()
        rerun = self.root / "latest-two"
        self._run("audit-existing", "prepare", "--latest-n", "1", "--out-dir", rerun)
        self.assertEqual(json.loads((rerun / "selection.json").read_text())["selected_ids"], ["200"])

    def test_latest_n_prefers_explicit_trustworthy_acquisition_order(self):
        order_dir = self.root / "JobPostings" / "_meta"
        order_dir.mkdir(parents=True)
        (order_dir / "acquisition_order.json").write_text(json.dumps({
            "schema": "AcquisitionOrderV1",
            "records": [
                {"id": "100", "acquired_at": "2026-09-08T00:00:00Z"},
                {"id": "200", "acquired_at": "2026-09-08T02:00:00Z"},
            ],
        }), encoding="utf-8")
        run = self.root / "ordered-latest"
        self._run("audit-existing", "prepare", "--latest-n", "1", "--out-dir", run)
        selection = json.loads((run / "selection.json").read_text())
        self.assertEqual(selection["selection_basis"], "existing_acquisition_order")
        self.assertEqual(selection["selected_ids"], ["200"])

    def test_identity_mismatch_is_not_a_refresh_candidate(self):
        selection_run = self.root / "identity-selection"
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", selection_run)
        capture = self._capture([self._record(title="Wrong title")], ["100"], name="identity-capture.json")
        audit_run = self.root / "identity-audit"
        self._run("audit-existing", "compare", "--selection", selection_run / "selection.json", "--capture-bundle", capture, "--out-dir", audit_run)
        result = json.loads((audit_run / "audit.json").read_text())["results"][0]
        self.assertEqual(result["classification"], "identity_mismatch")
        self.assertFalse(result["eligible_for_refresh"])

    def test_unavailable_and_stale_unavailable_evidence_are_distinct_from_capture_failure(self):
        selection_run = self.root / "unavailable-selection"
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", selection_run)
        failure = {
            "id": "100", "failure_kind": "source_unavailable",
            "reason": "LinkedIn reports this job is no longer available.",
            "attempts": ["authorized-browser-a"],
            "evidence": {
                "id": "100", "canonical_url": "https://www.linkedin.com/jobs/view/100/",
                "browser": "authorized-browser-a", "method": "rendered_dom_text",
                "captured_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "unavailable",
            },
        }
        capture = self._capture([], ["100"], failures=[failure], name="unavailable-capture.json")
        audit_run = self.root / "unavailable-audit"
        self._run("audit-existing", "compare", "--selection", selection_run / "selection.json", "--capture-bundle", capture, "--out-dir", audit_run)
        result = json.loads((audit_run / "audit.json").read_text())["results"][0]
        self.assertEqual(result["classification"], "source_unavailable")
        self.assertEqual(result["browser"], "authorized-browser-a")
        self.assertEqual(result["capture_timestamp"], failure["evidence"]["captured_at"])
        stale = dict(failure)
        stale["evidence"] = dict(failure["evidence"], captured_at="2020-01-01T00:00:00Z")
        stale_capture = self._capture([], ["100"], failures=[stale], name="stale-unavailable-capture.json")
        stale_run = self.root / "stale-unavailable-audit"
        self._run("audit-existing", "compare", "--selection", selection_run / "selection.json", "--capture-bundle", stale_capture, "--out-dir", stale_run)
        stale_result = json.loads((stale_run / "audit.json").read_text())["results"][0]
        self.assertEqual(stale_result["classification"], "capture_failed")

    def test_open_status_with_unrelated_closed_note_cannot_be_unavailable(self):
        source = self.root / "open-with-note.json"
        source.write_text(json.dumps({
            "records": [],
            "failures": [{
                "id": "100", "failure_kind": "source_unavailable",
                "reason": "The page is open; this note mentions a closed role from another review.",
                "evidence": {
                    "id": "100", "canonical_url": "https://www.linkedin.com/jobs/view/100/",
                    "browser": "authorized-browser-a", "method": "rendered_dom_text",
                    "captured_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                    "status": "open", "note": "A different posting was closed",
                },
            }],
        }), encoding="utf-8")
        self._run("acquire-save", "--records-json", source, "--out", self.root / "rejected.json", "--selected-id", "100", ok=False)

    def test_capture_before_selection_and_stale_independent_check_block_fresh_status(self):
        selection_run = self.root / "freshness-selection"
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", selection_run)
        body = "S" * 512 + "\nverified ending"
        record = self._record(body=body, captured_at="2020-01-01T00:00:00Z")
        record["provenance"]["browser"] = "authorized-browser-b"
        record["provenance"]["method"] = "native_text"
        record["native_nodes"] = [{"role": "text", "text": "S" * 512}, {"role": "text", "text": "verified ending"}]
        record["quality_evidence"] = {
            "end_verified": True, "end_marker": "verified ending",
            "truncation_flags": [], "native_scope": "job_description_only",
            "independent_check": {
                "kind": "independent_comparison", "browser": "authorized-browser-a",
                "method": "rendered_dom_text", "captured_at": "2020-01-01T00:01:00Z",
                "description": body,
                "description_sha256": __import__("hashlib").sha256(body.encode()).hexdigest(),
                "complete": True, "evidence": "Independent complete DOM capture.",
            },
        }
        capture = self._capture([record], ["100"], name="stale-native-capture.json")
        audit_run = self.root / "stale-native-audit"
        self._run("audit-existing", "compare", "--selection", selection_run / "selection.json", "--capture-bundle", capture, "--out-dir", audit_run)
        result = json.loads((audit_run / "audit.json").read_text())["results"][0]
        self.assertEqual(result["classification"], "capture_failed")

    def test_ambiguous_and_missing_archive_stop_selection(self):
        duplicate = self.root / "JobPostings" / "postings" / "duplicate.md"
        duplicate.write_text((self.root / "JobPostings" / "postings" / "100.md").read_text(), encoding="utf-8")
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", self.root / "ambiguous", ok=False)
        duplicate.unlink()
        (self.root / "JobPostings" / "postings" / "100.md").unlink()
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", self.root / "missing", ok=False)

    def test_handcrafted_input_without_normalized_hashes_cannot_be_audit_capture(self):
        run = self.root / "selection"
        self._run("audit-existing", "prepare", "--selected-id", "100", "--out-dir", run)
        raw_bundle = self.root / "raw.json"
        raw_bundle.write_text(json.dumps({
            "schema": "SelectedPostingAcquisitionV1", "selected_ids": ["100"],
            "records": [self._record()], "failures": [],
            "created_at": "2099-01-01T00:00:00Z",
        }), encoding="utf-8")
        self._run(
            "audit-existing", "compare", "--selection", run / "selection.json",
            "--capture-bundle", raw_bundle, "--out-dir", self.root / "bad-audit", ok=False,
        )

    def test_independent_check_comparison_keeps_meaningful_unicode_and_ui_boundaries(self):
        self.assertEqual(compare_bodies("A\nB", "A B")["classification"], "match_whitespace_or_ui")
        self.assertEqual(compare_bodies("A²", "A2")["classification"], "substantive_difference")
        self.assertEqual(compare_bodies("A\n---\nReport this job", "A")["classification"], "match_whitespace_or_ui")
        self.assertEqual(compare_bodies("Employer body\nApply", "Employer body")["classification"], "substantive_difference")
        self.assertEqual(compare_bodies("A", "A\nHealth insurance is included")["classification"], "substantive_difference")


if __name__ == "__main__":
    unittest.main()
