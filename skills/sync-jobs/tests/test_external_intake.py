import hashlib
import json
from pathlib import Path
import sys
import unittest
import openpyxl

import test_workflow as fixture

SKILL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SKILL/"scripts"))
from source_acquisition import FetchResponse,acquire_urls

class ExternalIntake(unittest.TestCase):
    setUp=fixture.Workflow.setUp
    tearDown=fixture.Workflow.tearDown
    runstage=fixture.Workflow.runstage

    def record(self):
        description="Coordinate a fully synthetic example process. This fixture ends here."
        return {"title":"Example role","company":"Example Corp","location":"Example location","url":"https://careers.example.com/jobs/42?utm_source=email","description":description,"status":"Saved","provenance":{"browser":"authorized-browser-a","method":"rendered_dom_text","captured_at":"2030-01-01T20:00:00Z","complete_text":True,"completion_evidence":"Expanded the posting and verified its final sentence.","status_certain":True},"quality_evidence":{"end_verified":True,"end_marker":"This fixture ends here.","truncation_flags":[]}}

    def test_external_dry_run_commit_and_idempotency(self):
        payload=self.root/"external.json";payload.write_text(json.dumps({"records":[self.record()]}))
        before=fixture.digest(self.tracker)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"dry")
        self.assertEqual(fixture.digest(self.tracker),before)
        self.assertEqual(len(list((self.root/"JobPostings/postings").glob("*ext-*.md"))),0)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"live",commit=True)
        wb=openpyxl.load_workbook(self.tracker,read_only=True,data_only=True);ws=wb["Jobs"]
        self.assertEqual(ws.max_row,3);self.assertEqual(ws.cell(3,6).value,"Saved")
        self.assertEqual(ws.cell(3,9).value,self.record()["url"]);self.assertEqual(ws.cell(3,12).value,self.record()["url"]);wb.close()
        archive=next((self.root/"JobPostings/postings").glob("*ext-*.md"));self.assertIn("Source: https://careers.example.com/jobs/42?utm_source=email",archive.read_text())
        sidecar=json.loads(next((self.root/"JobPostings/_meta/eligibility").glob("J-000002_*.json")).read_text())
        self.assertTrue(sidecar["posting"]["source_id"].startswith("ext-"));self.assertIsNone(sidecar["posting"]["linkedin_id"])
        after=fixture.digest(self.tracker)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"again",commit=True)
        self.assertEqual(fixture.digest(self.tracker),after)

    def test_external_quality_and_identity_fail_closed(self):
        record=self.record();record["quality_evidence"]["end_marker"]="wrong ending"
        payload=self.root/"bad.json";payload.write_text(json.dumps({"records":[record]}));before=fixture.digest(self.tracker)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"bad",commit=True,ok=False)
        self.assertEqual(fixture.digest(self.tracker),before)

    def test_source_neutral_v2_dry_run_commit_and_sidecar(self):
        url="https://careers.unknown.example/openings/42"
        body=(SKILL/"tests/fixtures/source_acquisition/generic_jsonld.html").read_bytes()
        def fetch(target):
            return FetchResponse(target,target,200,{"content-type":"text/html; charset=utf-8"},body)
        bundle=acquire_urls([url],fetch)
        payload=self.root/"source-v2.json";payload.write_text(json.dumps(bundle))
        before=fixture.digest(self.tracker)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"v2-dry")
        self.assertEqual(fixture.digest(self.tracker),before)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"v2-live",commit=True)
        wb=openpyxl.load_workbook(self.tracker,read_only=True,data_only=True);ws=wb["Jobs"]
        self.assertIsNone(ws.cell(3,9).value)
        self.assertEqual(ws.cell(3,12).value,url)
        wb.close()
        source_path=self.root/"JobPostings/_meta/sources/J-000002_PostingSourceProvenanceV2.json"
        self.assertTrue(source_path.exists())
        source=json.loads(source_path.read_text())
        self.assertEqual(source["schema"],"PostingSourceProvenanceV2")
        self.assertEqual(source["discovery_url"],url)
        self.assertEqual(source["acquisition_bundle_sha256"],bundle["bundle_sha256"])
        eligibility=json.loads((self.root/"JobPostings/_meta/eligibility/J-000002_PostingEligibilityV1.json").read_text())
        worklist=self.root/"worklist-v2.json"
        self.runstage("worklist","--out",worklist)
        row=next(item for item in json.loads(worklist.read_text())["rows"] if item["tracker_id"]=="J-000002")
        self.assertEqual(row["job_url"],url)
        self.assertEqual(row["eligibility_evidence"]["availability"],"valid",{"worklist":row["eligibility_evidence"],"posting":eligibility.get("posting")})

    def test_incomplete_or_tampered_v2_bundle_blocks_before_writes(self):
        url="https://www.linkedin.com/jobs/view/1234567890"
        bundle=acquire_urls([url],lambda _: self.fail("LinkedIn must not call HTTP"))
        payload=self.root/"incomplete-v2.json";payload.write_text(json.dumps(bundle));before=fixture.digest(self.tracker)
        self.runstage("external-ingest","--records-json",payload,"--backup-dir",self.root/"incomplete",commit=True,ok=False)
        self.assertEqual(fixture.digest(self.tracker),before)

if __name__=="__main__":unittest.main()
