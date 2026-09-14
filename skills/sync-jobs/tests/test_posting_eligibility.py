import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import posting_eligibility as pe

class PostingEligibility(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); pe.ROOT=self.root
        self.path=self.root/"JobPostings/postings/x.md"; self.path.parent.mkdir(parents=True)
    def tearDown(self): self.tmp.cleanup()
    def extract(self, body, **kw):
        text="# Visa Sponsorship Manager\r\n\r\nSource: https://www.linkedin.com/jobs/view/42/\r\n\r\n## About the Job\r\n\r\n"+body
        self.path.write_bytes(text.encode()); return pe.extract_file(self.path,tracker_id="J-000001",source_url="https://www.linkedin.com/jobs/view/42/",linkedin_id="42",**kw),text
    def test_exact_multilingual_and_negation(self):
        body=("We sponsor visas. We cannot provide visa sponsorship now or in future.\r\n\r\n"
              "Debe contar con permiso de trabajo; patrocinio de visado sujeto a región.\r\n\r\n"
              "Autorisation de travail requise. Arbeitserlaubnis erforderlich.")
        value,text=self.extract(body)
        self.assertEqual(value["status"],"EVIDENCE_FOUND")
        self.assertIn("employer_sponsorship_willingness",value["mentions"][0]["categories"])
        for mention in value["mentions"]:
            loc=mention["source_locator"]; self.assertEqual(text[loc["character_start"]:loc["character_end"]],mention["raw_text"])
        self.assertIn("cannot", " ".join(m["raw_text"] for m in value["mentions"]))
    def test_empty_and_false_positives(self):
        value,_=self.extract("Sponsor stakeholder workshops. We are an equal opportunity employer without regard to national origin or citizenship.")
        self.assertEqual(value["status"],"NO_MATCHES_DETECTED"); self.assertEqual(value["display_status"],"NOT STATED ON SOURCE")
        self.assertIn("does not mean no sponsorship",value["detection_limitation"])
    def test_relocation_requirement_is_unclassified(self):
        value,_=self.extract("You must relocate at your own expense.")
        self.assertEqual(value["status"],"AMBIGUOUS"); self.assertFalse(value["mentions"])
    def test_title_not_scanned(self):
        value,_=self.extract("Build products."); self.assertEqual(value["status"],"NO_MATCHES_DETECTED")
    def test_capture_binding_and_locator_tamper(self):
        body="Must be authorized to work."
        description_hash=hashlib.sha256(body.encode()).hexdigest()
        provenance={"captured_at":"2026-09-08T00:00:00Z","record_sha256":"a"*64,"linkedin_id":"42","source_url":"https://www.linkedin.com/jobs/view/42/","description_sha256":description_hash}
        value,text=self.extract(body,captured_at=provenance["captured_at"],capture_provenance=provenance)
        self.assertEqual(value["source_capture"]["captured_at"],provenance["captured_at"])
        bad=copy.deepcopy(value);bad["mentions"][0]["source_locator"]["character_start"]+=1
        with self.assertRaises(ValueError): pe.validate(bad,source_text=text)

if __name__=="__main__": unittest.main()
