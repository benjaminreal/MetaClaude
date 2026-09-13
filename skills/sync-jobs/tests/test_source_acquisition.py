import copy
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "tests/fixtures/source_acquisition"
sys.path.insert(0, str(SKILL / "scripts"))

from acquisition_quality import validate_quality
from source_acquisition import (
    AcquisitionError, BoundedFetcher, FetchResponse, acquire_urls, canonical_json,
    canonical_posting_url, recognize, request_id, sha256_bytes, source_record_hash,
    resume_bundle, validate_bundle, validate_public_url,
)


def fixture(name):
    return (FIXTURES / name).read_bytes()


def response(url, body, status=200, content_type="text/html; charset=utf-8", redirects=()):
    return FetchResponse(url, url, status, {"content-type": content_type}, body, tuple(redirects))


class MappingFetcher:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        value = self.mapping[url]
        return value() if callable(value) else value


class HTTPStub:
    def __init__(self, status, body=b"", headers=None):
        self.status=status;self._body=body;self._offset=0;self._headers=headers or {}
    def getheaders(self): return list(self._headers.items())
    def read(self, size):
        value=self._body[self._offset:self._offset+size];self._offset+=len(value);return value

class ConnStub:
    def close(self): pass


class SourceAcquisition(unittest.TestCase):
    def test_provider_recognition_and_identity_parameters(self):
        self.assertEqual(recognize("https://boards.greenhouse.io/acme/jobs/123")["provider"], "greenhouse")
        self.assertEqual(recognize("https://jobs.lever.co/acme/abc")["provider"], "lever")
        self.assertEqual(recognize("https://jobs.smartrecruiters.com/Acme/xyz-role")["provider"], "smartrecruiters")
        value = canonical_posting_url("HTTPS://EXAMPLE.COM:443/job/1?source=req-9&utm_campaign=x#apply")
        self.assertEqual(value, "https://example.com/job/1?source=req-9")

    def test_url_safety_rejects_credentials_and_private_destinations(self):
        for value in (
            "file:///etc/passwd", "https://user:secret@example.com/job",
            "http://127.0.0.1/job", "http://[::1]/job", "http://169.254.169.254/latest",
            "http://10.2.3.4/job", "https://example.com:8443/job",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_public_url(value, resolve=False)

    def test_dns_redirect_size_and_content_guards(self):
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(None,None,None,None,("10.0.0.2",443))]):
            with self.assertRaises(ValueError):
                validate_public_url("https://dns-rebind.example/job")
        fetcher=BoundedFetcher(max_bytes=1024)
        fetcher._open_validated=mock.Mock(return_value=(ConnStub(),HTTPStub(302,headers={"Location":"http://127.0.0.1/private"})))
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(None,None,None,None,("93.184.216.34",443))]):
            with self.assertRaises(ValueError):
                fetcher.fetch("https://public.example/job")
        fetcher._open_validated=mock.Mock(return_value=(ConnStub(),HTTPStub(200,b"x"*1025,{"Content-Type":"text/html"})))
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(2,1,6,"",("93.184.216.34",443))]):
            with self.assertRaises(AcquisitionError) as too_large:
                fetcher.fetch("https://public.example/job")
        self.assertEqual(too_large.exception.kind,"response_too_large")
        fetcher._open_validated=mock.Mock(return_value=(ConnStub(),HTTPStub(200,b"binary",{"Content-Type":"application/octet-stream"})))
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(2,1,6,"",("93.184.216.34",443))]):
            with self.assertRaises(AcquisitionError) as content:
                fetcher.fetch("https://public.example/job")
        self.assertEqual(content.exception.kind,"unsupported_content_type")

    def test_transport_uses_single_validated_resolution_and_never_private_second_lookup(self):
        fetcher=BoundedFetcher(max_bytes=1024)
        fake_sock=mock.Mock()
        fake_sock.recv.return_value=b""
        fetcher.ssl_context.wrap_socket=mock.Mock(return_value=fake_sock)
        response_stub=HTTPStub(200,b"ok",{"Content-Type":"text/html"})
        with mock.patch("source_acquisition.socket.getaddrinfo", side_effect=[
            [(2,1,6,"",("93.184.216.34",443))],
            [(2,1,6,"",("10.0.0.7",443))],
        ]) as resolver, mock.patch("source_acquisition.socket.socket", return_value=fake_sock), \
             mock.patch("source_acquisition.http.client.HTTPConnection.getresponse", return_value=response_stub):
            result=fetcher.fetch("https://public.example/job")
        self.assertEqual(result.body,b"ok")
        self.assertEqual(resolver.call_count,1)
        fake_sock.connect.assert_called_once_with(("93.184.216.34",443))
        self.assertNotIn(mock.call(("10.0.0.7",443)),fake_sock.connect.call_args_list)
        fetcher.ssl_context.wrap_socket.assert_called_once_with(fake_sock,server_hostname="public.example")

    def test_streaming_content_decoding_boundaries_and_errors(self):
        fetcher=BoundedFetcher(max_bytes=1024)
        for encoding,encode in (("identity",lambda b:b),("gzip",gzip.compress),("deflate",zlib.compress)):
            with self.subTest(encoding=encoding):
                self.assertEqual(fetcher._read_bounded(HTTPStub(200,encode(b"x"*1024)),encoding),b"x"*1024)
                with self.assertRaises(AcquisitionError) as over:
                    fetcher._read_bounded(HTTPStub(200,encode(b"x"*1025)),encoding)
                self.assertEqual(over.exception.kind,"response_too_large")
        random_exact=os.urandom(1024)
        self.assertEqual(fetcher._read_bounded(HTTPStub(200,gzip.compress(random_exact)),"gzip"),random_exact)
        for encoding,body in (("gzip",gzip.compress(b"ok")[:-2]),("deflate",zlib.compress(b"ok")[:-2]),("gzip",b"bad")):
            with self.subTest(encoding=encoding,body=body),self.assertRaises(AcquisitionError) as bad:
                fetcher._read_bounded(HTTPStub(200,body),encoding)
            self.assertEqual(bad.exception.kind,"invalid_content_encoding")

    def test_greenhouse_official_api(self):
        page = "https://boards.greenhouse.io/example/jobs/12345"
        endpoint = "https://boards-api.greenhouse.io/v1/boards/example/jobs/12345"
        fetch = MappingFetcher({endpoint: response(endpoint, fixture("greenhouse.json"), content_type="application/json")})
        bundle = acquire_urls([page], fetch)
        self.assertTrue(bundle["complete"])
        record = bundle["records"][0]
        self.assertEqual(record["provenance"]["method"], "official_api")
        self.assertEqual(record["provider_job_id"], "12345")
        self.assertEqual(record["requisition_id"], "REQ-12345")
        self.assertEqual(fetch.calls, [endpoint])

    def test_lever_and_smartrecruiters_official_apis(self):
        lever = "https://jobs.lever.co/example/abc-123"
        smart = "https://jobs.smartrecruiters.com/Example/xyz123-example-role"
        lever_api = "https://api.lever.co/v0/postings/example/abc-123"
        smart_api = "https://api.smartrecruiters.com/v1/companies/Example/postings/xyz123"
        fetch = MappingFetcher({
            lever_api: response(lever_api, fixture("lever.json"), content_type="application/json"),
            smart_api: response(smart_api, fixture("smartrecruiters.json"), content_type="application/json"),
        })
        bundle = acquire_urls([lever, smart], fetch)
        self.assertTrue(bundle["complete"])
        self.assertEqual({r["provider"] for r in bundle["records"]}, {"lever", "smartrecruiters"})
        self.assertTrue(all(r["quality"]["status"] == "PASS" for r in bundle["records"]))

    def test_generic_json_ld_and_static_html(self):
        structured = "https://careers.unknown.example/openings/42"
        static = "https://static.example/jobs/77"
        fetch = MappingFetcher({
            structured: response(structured, fixture("generic_jsonld.html")),
            static: response(static, fixture("generic_html.html")),
        })
        bundle = acquire_urls([structured, static], fetch)
        self.assertTrue(bundle["complete"])
        methods = {record["provenance"]["method"] for record in bundle["records"]}
        self.assertEqual(methods, {"public_json_ld", "public_html"})
        self.assertIn("documented completion marker", bundle["records"][0]["description"])

    def test_json_ld_url_binding_rules(self):
        supplied="https://example.test/jobs/1";final="https://example.test/jobs/1"
        base={"@type":"JobPosting","title":"x","description":"x"}
        from source_acquisition import _select_json_ld
        with self.assertRaises(AcquisitionError) as mismatch:
            _select_json_ld([{**base,"url":"https://example.test/jobs/2"}],supplied,final)
        self.assertEqual(mismatch.exception.kind,"identity_mismatch")
        self.assertEqual(_select_json_ld([base],supplied,final),base)
        match={**base,"url":supplied}
        self.assertIs(_select_json_ld([match,{**base,"url":"https://example.test/jobs/2"}],supplied,final),match)

    def test_truncation_signals_block_all_public_methods(self):
        cases={
            "https://boards.greenhouse.io/example/jobs/12345":("https://boards-api.greenhouse.io/v1/boards/example/jobs/12345","greenhouse_truncated.json","application/json"),
            "https://json.example/jobs/1":("https://json.example/jobs/1","generic_jsonld_truncated.html","text/html"),
            "https://html.example/jobs/1":("https://html.example/jobs/1","generic_html_truncated.html","text/html"),
        }
        for supplied,(target,name,ctype) in cases.items():
            with self.subTest(name=name):
                mapping={target:response(target,fixture(name),content_type=ctype)}
                if target!=supplied:
                    mapping[supplied]=response(supplied,fixture("generic_html_truncated.html"))
                bundle=acquire_urls([supplied],MappingFetcher(mapping))
                self.assertFalse(bundle["complete"])
                self.assertEqual(bundle["failures"][0]["failure_kind"],"quality_blocked")

    def test_indeed_camelcase_description_container_is_narrowly_extracted(self):
        url="https://www.indeed.com/viewjob?jk=synthetic-42"
        bundle=acquire_urls([url],MappingFetcher({url:response(url,fixture("indeed_like.html"))}))
        self.assertTrue(bundle["complete"])
        self.assertIn("actual scoped description",bundle["records"][0]["description"])
        self.assertNotIn("unrelated navigation",bundle["records"][0]["description"])

    def test_secret_urls_are_redacted_and_never_fetched(self):
        secret="s3cr3t-value"
        urls=[f"https://user:{secret}@example.com/jobs/1",f"https://example.com/jobs/2?access_token={secret}&safe=1"]
        fetch=MappingFetcher({})
        bundle=acquire_urls(urls,fetch)
        serialized=json.dumps(bundle)
        self.assertNotIn(secret,serialized)
        self.assertEqual(fetch.calls,[])
        self.assertTrue(all(x["failure_kind"]=="unsafe_url" for x in bundle["failures"]))

    def test_resume_replaces_only_failures_and_recomputes_hashes(self):
        accepted="https://static.example/jobs/77";failed="https://www.linkedin.com/jobs/view/1234567890"
        original=acquire_urls([accepted,failed],MappingFetcher({accepted:response(accepted,fixture("generic_html.html"))}))
        frozen=copy.deepcopy(original["records"][0])
        rid=request_id(failed);description="Full synthetic fallback description with a verified final sentence."
        replacement={"schema":"SourcePostingFallbackV2","outcomes":[{"request_id":rid,"record":{
            "url":failed,"title":"Synthetic role","company":"Synthetic Corp","location":"Remote, US","description":description,
            "provider":"linkedin","provider_job_id":"1234567890",
            "provenance":{"browser":"authorized-browser-a","method":"rendered_dom_text","captured_at":"2030-01-01T00:00:00Z","complete_text":True,"completion_evidence":"Expanded and checked the final section.","status_certain":False,"status_uncertainty":"Saved state not asserted."},
            "quality_evidence":{"end_verified":True,"end_marker":"verified final sentence.","truncation_flags":[]},
        }}]}
        merged=resume_bundle(original,replacement)
        self.assertTrue(merged["complete"]);self.assertEqual(merged["records"][0],frozen)
        fallback=next(x for x in merged["records"] if x["request_id"]==rid)
        self.assertGreater(len(fallback["attempts"]),len(original["failures"][0]["attempts"]))
        validate_bundle(merged)
        unresolved=resume_bundle(original,{"schema":"SourcePostingFallbackV2","outcomes":[{"request_id":rid,"failure":{
            "reason":"Browser still unavailable.","failure_kind":"capability_missing","next_action":"manual_artifact_or_stop",
            "attempts":[{"method":"rendered_dom_text","url":failed,"status":"rejected","reason":"capability missing"}],
        }}]})
        self.assertFalse(unresolved["complete"]);self.assertEqual(len(unresolved["failures"][0]["attempts"]),len(original["failures"][0]["attempts"])+1)
        for bad_ids in ([],[rid,rid],[request_id(accepted)]):
            bad={"schema":"SourcePostingFallbackV2","outcomes":[{"request_id":x,"failure":{"reason":"still blocked","attempts":[]}} for x in bad_ids]}
            with self.assertRaises(ValueError):resume_bundle(original,bad)

    def test_owner_artifact_fallback_requires_artifact_evidence(self):
        url="https://www.linkedin.com/jobs/view/2233445566";original=acquire_urls([url],lambda _:self.fail("no fetch"));rid=request_id(url)
        base={"url":url,"title":"Synthetic role","company":"Example Corp","location":"Remote, US","description":"Complete owner supplied artifact with final line.","provider":"linkedin","provider_job_id":"2233445566",
              "provenance":{"browser":"none","method":"owner_provided_artifact","captured_at":"2030-01-01T00:00:00Z","complete_text":True,"completion_evidence":"Owner supplied a complete text artifact.","status_certain":False,"status_uncertainty":"Live availability not checked."},
              "quality_evidence":{"end_verified":True,"end_marker":"final line.","truncation_flags":[],"artifact_path":"owner/job.txt","availability_verified":False}}
        bad={"schema":"SourcePostingFallbackV2","outcomes":[{"request_id":rid,"record":base}]}
        with self.assertRaisesRegex(ValueError,"OWNER_ARTIFACT_HASH_MISSING"):resume_bundle(original,bad)
        base["quality_evidence"]["artifact_sha256"]=sha256_bytes(b"synthetic owner artifact")
        merged=resume_bundle(original,bad);self.assertTrue(merged["complete"])

    def test_multiple_jobs_js_shell_and_challenges_are_retained(self):
        cases = {
            "https://multi.example/careers": ("multiple_jobs.html", "multiple_postings"),
            "https://js.example/jobs/1": ("javascript_shell.html", "javascript_render_required"),
            "https://login.example/jobs/1": ("login_wall.html", "login_required"),
            "https://captcha.example/jobs/1": ("captcha.html", "captcha"),
            "https://expired.example/jobs/1": ("expired.html", "source_unavailable"),
        }
        fetch = MappingFetcher({url: response(url, fixture(name)) for url, (name, _) in cases.items()})
        bundle = acquire_urls(list(cases), fetch)
        self.assertFalse(bundle["complete"])
        self.assertEqual({failure["supplied_url"]: failure["failure_kind"] for failure in bundle["failures"]}, {url: kind for url, (_, kind) in cases.items()})
        self.assertTrue(all(failure["next_action"] in {"browser_fallback", "manual_artifact_or_stop"} for failure in bundle["failures"]))

    def test_http_failure_taxonomy(self):
        cases = {401: "authentication_or_access_required", 403: "authentication_or_access_required", 404: "source_unavailable", 410: "source_unavailable", 429: "rate_limited"}
        for status, expected in cases.items():
            with self.subTest(status=status):
                url = f"https://status.example/jobs/{status}"
                bundle = acquire_urls([url], MappingFetcher({url: response(url, b"error", status=status)}))
                self.assertEqual(bundle["failures"][0]["failure_kind"], expected)

    def test_linkedin_short_circuits_without_http(self):
        fetch = MappingFetcher({})
        bundle = acquire_urls(["https://www.linkedin.com/jobs/view/1234567890"], fetch)
        self.assertFalse(bundle["complete"])
        self.assertEqual(bundle["failures"][0]["failure_kind"], "browser_required")
        self.assertEqual(fetch.calls, [])

    def test_every_url_accounted_for_and_tamper_rejected(self):
        good = "https://static.example/jobs/77"
        linked = "https://www.linkedin.com/jobs/view/1234567890"
        bundle = acquire_urls([good, linked], MappingFetcher({good: response(good, fixture("generic_html.html"))}))
        self.assertEqual(len(bundle["records"]) + len(bundle["failures"]), 2)
        self.assertEqual({x["request_id"] for x in bundle["records"] + bundle["failures"]}, {request_id(good), request_id(linked)})
        tampered = copy.deepcopy(bundle)
        tampered["records"][0]["description"] += " changed"
        with self.assertRaises(ValueError):
            validate_bundle(tampered)
        injected = copy.deepcopy(bundle)
        injected["records"][0]["csrf_token"]="secret"
        injected["records"][0]["source_record_sha256"]=source_record_hash(injected["records"][0])
        injected["bundle_sha256"]=sha256_bytes(canonical_json({key:value for key,value in injected.items() if key!="bundle_sha256"}))
        with self.assertRaisesRegex(ValueError,"unsupported fields"):
            validate_bundle(injected)

    def test_method_specific_quality_cannot_borrow_browser_evidence(self):
        record = {
            "id": "x", "description": "Complete description ending.",
            "provenance": {"method": "official_api"},
            "quality_evidence": {"end_verified": True, "end_marker": "ending.", "truncation_flags": []},
        }
        quality = validate_quality(record)
        self.assertEqual(quality["status"], "BLOCKED")
        self.assertIn("OFFICIAL_API_RESPONSE_HASH_MISSING", quality["unresolved_flags"])

    def test_cli_runs_without_tracker_and_rejects_commit(self):
        with tempfile.TemporaryDirectory(prefix="source-acquire-cli-") as tmp:
            out = Path(tmp) / "capture.json"
            base = [sys.executable, str(SKILL / "scripts/sync_jobs.py")]
            result = subprocess.run(base + ["acquire-url", "--url", "https://www.linkedin.com/jobs/view/1234567890", "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(out.exists())
            self.assertFalse(json.loads(out.read_text())["complete"])
            blocked = subprocess.run(base + ["--commit", "acquire-url", "--url", "https://www.linkedin.com/jobs/view/1", "--out", str(Path(tmp) / "other.json")], capture_output=True, text=True)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("does not accept --commit", blocked.stderr)
            original=json.loads(out.read_text());rid=original["failures"][0]["request_id"]
            replacements=Path(tmp)/"fallback.json";merged=Path(tmp)/"merged.json"
            replacements.write_text(json.dumps({"schema":"SourcePostingFallbackV2","outcomes":[{"request_id":rid,"failure":{
                "reason":"No authorized browser surface.","attempts":[],"failure_kind":"capability_missing","next_action":"manual_artifact_or_stop"
            }}]}))
            resumed=subprocess.run(base+["resume-url","--bundle",str(out),"--replacements",str(replacements),"--out",str(merged)],capture_output=True,text=True)
            self.assertEqual(resumed.returncode,0,resumed.stdout+resumed.stderr);self.assertFalse(json.loads(merged.read_text())["complete"])


if __name__ == "__main__":
    unittest.main()
