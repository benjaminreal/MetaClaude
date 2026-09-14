import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]

class AcquisitionCapture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='acquisition-capture-')
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def run_cli(self, payload, ids, ok=True):
        src=self.root/'source.json';out=self.root/'evidence.json';src.write_text(json.dumps(payload))
        cmd=[sys.executable,str(SKILL/'scripts/sync_jobs.py'),'acquire-save','--records-json',str(src),'--out',str(out)]
        for jid in ids: cmd += ['--selected-id',jid]
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode==0,ok,result.stdout+result.stderr)
        return result,out
    def record(self):
        return {'id':'123','title':'Role','company':'Company','location':'Example location','status':'Saved','url':'https://www.linkedin.com/jobs/view/123/','description':'Complete role text with a visible final section.','provenance':{'browser':'authorized-browser-a','method':'native_text','captured_at':'2030-01-01T00:00:00Z','complete_text':True,'completion_evidence':'Read through the visible final section.','status_certain':False,'status_uncertainty':'Board card status was not visible.'}}
    def test_atomic_bundle_has_hashes_and_boundary_claims(self):
        result,out=self.run_cli({'records':[self.record()],'failures':[]},['123'])
        data=json.loads(out.read_text());self.assertFalse(data['complete']);self.assertFalse(data['claims']['official_new_ids'])
        self.assertFalse(data['quality_complete']);self.assertEqual(data['quality_blocked_ids'],['123'])
        self.assertEqual(len(data['records'][0]['description_sha256']),64);self.assertIn('SAVED_AND_READ_BACK_WITH_QUALITY_BLOCKS',result.stdout)
    def test_selected_failure_is_retained(self):
        _,out=self.run_cli({'records':[],'failures':[{'id':'123','reason':'Complete text unavailable after bounded fallback.','attempts':['authorized-browser-a','authorized-browser-b'],'status_uncertainty':'Board status was not reliably visible.'}]},['123'])
        data=json.loads(out.read_text());self.assertFalse(data['complete']);self.assertEqual(data['failures'][0]['id'],'123')
    def test_partial_or_unattested_record_is_rejected(self):
        bad=self.record();bad['provenance']['complete_text']=False
        self.run_cli({'records':[bad],'failures':[]},['123'],ok=False)
    def test_unselected_record_is_rejected(self):
        self.run_cli({'records':[self.record()],'failures':[]},['999'],ok=False)
    def test_transfer_hash_mismatch_is_rejected(self):
        bad=self.record();bad['description_sha256']='0'*64
        self.run_cli({'records':[bad],'failures':[]},['123'],ok=False)
    def test_existing_output_is_not_overwritten(self):
        src=self.root/'source.json';out=self.root/'evidence.json';out.write_text('history')
        src.write_text(json.dumps({'records':[self.record()],'failures':[]}))
        cmd=[sys.executable,str(SKILL/'scripts/sync_jobs.py'),'acquire-save','--records-json',str(src),'--out',str(out),'--selected-id','123']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(out.read_text(),'history')
    def test_sensitive_unknown_field_is_rejected(self):
        bad=self.record();bad['csrf_token']='secret'
        self.run_cli({'records':[bad],'failures':[]},['123'],ok=False)

if __name__=='__main__': unittest.main()
