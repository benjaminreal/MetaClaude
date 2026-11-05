import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch
import books_api as b

class FakeResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.calls=[]
    def tearDown(self): self.tmp.cleanup()
    def client(self,raw,settings=None):
        def opener(req,timeout):
            self.calls.append(req)
            if isinstance(raw,Exception): raise raw
            return FakeResponse(raw if isinstance(raw,bytes) else json.dumps(raw).encode())
        return b.Client(settings or {},self.root/'state',opener)
    def test_isbn_checksum_and_conversion(self):
        self.assertEqual(b.canonical_isbn('0-7432-7356-7'),'9780743273565')
        for invalid in ['9780743273566','0743273568','0000000000000','http://internal']:
            with self.assertRaises(ValueError): b.canonical_isbn(invalid)
    def test_missing_key_never_requests_network(self):
        out=self.client({}).search('google_books',isbn='9780743273565')
        self.assertEqual(out['status'],'unconfigured')
        self.assertEqual(self.calls,[])
        self.assertFalse((self.root/'state').exists())
    def test_credentials_header_only_and_not_in_cache(self):
        key='synthetic-not-a-real-secret'
        client=self.client({'totalItems':0}, {'google_books_api_key':key})
        out=client.search('google_books',title='The Great Gatsby',author='F. Scott Fitzgerald')
        self.assertEqual(out['status'],'no_result')
        self.assertNotIn(key,self.calls[0].full_url)
        self.assertEqual(self.calls[0].get_header('X-goog-api-key'),key)
        from urllib.parse import parse_qs,urlsplit
        query=parse_qs(urlsplit(self.calls[0].full_url).query)['q'][0]
        self.assertEqual(query,'"The Great Gatsby" "F. Scott Fitzgerald"')
        self.assertNotIn(key,json.dumps(out))
        self.assertNotIn(key.encode(),(self.root/'state/state.sqlite3').read_bytes())
    def test_cache_shared_by_independent_client_instances(self):
        raw={'numFound':1,'docs':[{'key':'/works/OL1W','title':'Gatsby','author_name':['Fitzgerald']}]}
        one=self.client(raw).search('open_library',title='Gatsby')
        two=self.client(raw).search('open_library',title='Gatsby')
        self.assertFalse(one['cache_hit'])
        self.assertTrue(two['cache_hit'])
        self.assertEqual(one['retrieved_at'],two['retrieved_at'])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(two['candidates'][0]['record_type'],'work')
        self.assertNotIn('pages',two['candidates'][0])
    def test_exact_isbn_requires_listed_edition_isbn(self):
        raw={'docs':[{'key':'/works/OL1W','title':'Gatsby','editions':{'docs':[{'key':'/books/OL1M','title':'Gatsby','isbn':['0743273567']}]}}, {'key':'/works/OL2W','title':'Other work'}]}
        out=self.client(raw).search('open_library',isbn='9780743273565')
        self.assertTrue(out['candidates'][0]['exact_isbn'])
        self.assertFalse(out['candidates'][1]['exact_isbn'])
        self.assertNotIn('publisher',out['candidates'][1])
    def test_google_conflicting_isbn_not_exact(self):
        raw={'items':[{'id':'abc','volumeInfo':{'title':'Gatsby','industryIdentifiers':[{'type':'ISBN_13','identifier':'9780141182636'}]}}]}
        out=self.client(raw,{'google_books_api_key':'synthetic'}).search('google_books',isbn='9780743273565')
        self.assertFalse(out['candidates'][0]['exact_isbn'])
    def test_errors_are_distinct_and_not_retried(self):
        for code,status in [(403,'denied'),(429,'rate_limited'),(404,'no_result'),(503,'unavailable'),(302,'unavailable')]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                count=[]
                def fail(req,timeout):
                    count.append(1)
                    raise urllib.error.HTTPError(req.full_url,code,'test',{},None)
                out=b.Client({},Path(tmp)/'state',fail).search('open_library',title='Gatsby')
                self.assertEqual(out['status'],status)
                self.assertEqual(len(count),1)
    def test_bad_and_oversized_responses(self):
        for raw in [b'<html>',b'[]',b'x'*(b.MAX_BYTES+1),{'error':'not a catalog'}, {'docs':'not a list'}]:
            with self.subTest(raw=str(raw)[:30]),tempfile.TemporaryDirectory() as tmp:
                client=b.Client({},Path(tmp)/'state',lambda req,timeout:FakeResponse(raw if isinstance(raw,bytes) else json.dumps(raw).encode()))
                self.assertEqual(client.search('open_library',title='Gatsby')['status'],'invalid_response')
    def test_no_arbitrary_urls_or_control_character_queries(self):
        client=self.client({})
        for provider,record_id in [('open_library','https://localhost/secret'),('open_library','/books/../../private'),('google_books','a?key=secret')]:
            with self.assertRaises(ValueError): client.get_record(provider,record_id)
        with self.assertRaises(ValueError): client.search('open_library',title='Gatsby\nInjected')
        with self.assertRaises(ValueError): client.search('open_library',title='Gatsby',limit=True)
        self.assertEqual(self.calls,[])
    def test_config_permissions_and_symlinks(self):
        f=self.root/'config.json'
        f.write_text('{"google_books_api_key":"synthetic"}')
        f.chmod(0o644)
        with self.assertRaises(ValueError):b.config(f)
        f.chmod(0o600)
        self.assertEqual(b.config(f)['google_books_api_key'],'synthetic')
        link=self.root/'linked.json';link.symlink_to(f)
        with self.assertRaises(ValueError):b.config(link)
    def test_no_network_status_and_strict_tool_args(self):
        client=self.client({})
        self.assertEqual(b.call_tool(client,'books_status',{})['google_books']['state'],'unconfigured')
        with self.assertRaises(ValueError):b.call_tool(client,'books_status',{'url':'https://localhost'})
        self.assertEqual(self.calls,[])
    def test_mcp_real_subprocess_handshake_no_network(self):
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'test','version':'1'}}}, {'jsonrpc':'2.0','method':'notifications/initialized'}, {'jsonrpc':'2.0','id':2,'method':'tools/list'}, {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'books_status','arguments':{}}}, {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'books_get_record','arguments':{'provider':'open_library','record_id':'http://localhost'}}}]
        run=subprocess.run([sys.executable,str(Path(b.__file__)), '--config',str(self.root/'absent.json'),'--state-dir',str(self.root/'state'),'serve'],input='\n'.join(json.dumps(x) for x in requests)+'\n',capture_output=True,text=True,timeout=10,check=True)
        replies=[json.loads(x) for x in run.stdout.splitlines()]
        self.assertEqual([x['id'] for x in replies],[1,2,3,4])
        self.assertEqual(replies[0]['result']['protocolVersion'],'2025-06-18')
        self.assertEqual(len(replies[1]['result']['tools']),3)
        self.assertFalse(replies[2]['result']['isError'])
        self.assertTrue(replies[3]['result']['isError'])
        self.assertEqual(run.stderr,'')
        self.assertFalse((self.root/'state').exists())
    def test_concurrent_processes_share_rate_limit(self):
        runner="""import sys,time,json
from pathlib import Path
import books_api as b
class R:
 def __enter__(self): return self
 def __exit__(self,*a): pass
 def read(self,n): return b'{"docs":[]}'
def opener(req,timeout):
 print(time.time(),flush=True)
 return R()
b.Client({},Path(sys.argv[1]),opener).search('open_library',title=sys.argv[2])
"""
        procs=[subprocess.Popen([sys.executable,'-c',runner,str(self.root/'shared'),str(i)],cwd=Path(b.__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
        starts=[]
        for p in procs:
            out,err=p.communicate(timeout=10)
            self.assertEqual(p.returncode,0,err)
            starts.append(float(out.strip()))
        self.assertGreaterEqual(abs(starts[0]-starts[1]),1.0)

if __name__=='__main__':unittest.main(verbosity=2)
