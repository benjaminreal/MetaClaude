import hashlib
import json
from pathlib import Path
import sys
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from acquisition_quality import ordered_native_text, validate_quality

CASES = json.loads((SKILL / 'tests/fixtures/acquisition_quality_cases.json').read_text())

def evidence(description):
    end = description[-80:]
    return {'end_verified': True, 'end_marker': end, 'truncation_flags': [], 'native_scope':'job_description_only'}

def native_record(jid, description):
    return {
        'id': jid, 'description': description,
        'provenance': {'browser':'authorized-browser-a','method':'native_text','captured_at':'2030-01-01T00:00:00Z'},
        'native_nodes': [{'role':'text','text':x} for x in description.splitlines() if x.strip()],
        'quality_evidence': evidence(description)
    }

class AcquisitionQuality(unittest.TestCase):
    def test_minimal_real_512_node_false_attestation_is_blocked(self):
        source=CASES['native_512_case']
        description=source['repeat_character']*source['repeat_count']
        self.assertEqual(len(description),512)
        record=native_record(source['id'],description)
        record['provenance']['complete_text']=True
        quality=validate_quality(record)
        self.assertEqual(quality['status'],'BLOCKED')
        self.assertIn('NATIVE_NODE_EXACT_512',quality['unresolved_flags'])
        with self.assertRaises(ValueError): validate_quality(record,require_pass=True)
    def test_minimal_known_good_native_capture_passes(self):
        source=CASES['known_good_case']
        quality=validate_quality(native_record(source['id'],source['description']))
        self.assertEqual(quality['status'],'PASS')
    def test_ordered_link_labels_are_required_in_description(self):
        record=native_record('1','first\nlast')
        record['native_nodes']=[{'role':'text','text':'first'},{'role':'link','text':'Request Form'},{'role':'text','text':'last'}]
        quality=validate_quality(record)
        self.assertIn('ORDERED_NATIVE_TEXT_MISMATCH',quality['unresolved_flags'])
    def test_512_flag_requires_distinct_matching_check(self):
        description='x'*512+'\nverified ending'
        record=native_record('2',description)
        quality=validate_quality(record);self.assertEqual(quality['status'],'BLOCKED')
        record['quality_evidence']['independent_check']={
            'kind':'independent_comparison','browser':'authorized-browser-b','method':'rendered_dom_text',
            'description':description,
            'captured_at':'2030-01-01T00:01:00Z','description_sha256':hashlib.sha256(description.encode()).hexdigest(),
            'complete':True,'evidence':'Independent DOM capture matched complete text.'}
        self.assertEqual(validate_quality(record)['status'],'PASS')
    def test_same_native_source_retry_cannot_clear_512(self):
        description='x'*512+'\nverified ending';record=native_record('4',description)
        record['quality_evidence']['independent_check']={
            'kind':'reacquisition','browser':'AUTHORIZED-BROWSER-A','method':'native_text','captured_at':'later',
            'description':description,'description_sha256':hashlib.sha256(description.encode()).hexdigest(),
            'complete':True,'evidence':'Repeated same capped surface.'}
        quality=validate_quality(record)
        self.assertEqual(quality['status'],'BLOCKED')
        self.assertIn('INDEPENDENT_CHECK_NOT_DISTINCT_COMPLETE_TEXT_MATCH',quality['unresolved_flags'])
    def test_dom_needs_end_boundary_but_not_second_browser(self):
        record={'id':'3','description':'complete text ending','provenance':{'browser':'authorized-browser-a','method':'rendered_dom_text','captured_at':'now'},'quality_evidence':{'end_verified':True,'end_marker':'ending','truncation_flags':[]}}
        self.assertEqual(validate_quality(record)['status'],'PASS')
        record['quality_evidence']['end_verified']=False
        self.assertEqual(validate_quality(record)['status'],'BLOCKED')
    def test_quality_hashes_are_bound_to_description_and_evidence(self):
        first={'id':'5','description':'first complete ending','provenance':{'browser':'authorized-browser-a','method':'rendered_dom_text','captured_at':'now'},'quality_evidence':{'end_verified':True,'end_marker':'ending','truncation_flags':[]}}
        second={**first,'description':'second complete ending'}
        a=validate_quality(first);b=validate_quality(second)
        self.assertNotEqual(a['description_sha256'],b['description_sha256'])
        self.assertNotEqual(a['quality_input_sha256'],b['quality_input_sha256'])
        self.assertNotEqual(a['quality_result_sha256'],b['quality_result_sha256'])

if __name__=='__main__': unittest.main()
