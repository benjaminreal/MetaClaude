import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
FIXTURES = SKILL / "tests/fixtures/source_acquisition"
sys.path.insert(0, str(SKILL / "scripts"))

from acquisition_quality import validate_quality
from source_acquisition import (
    AcquisitionError, BoundedFetcher, FetchResponse, acquire_urls, canonical_json,
    canonical_posting_url, recognize, request_id, sha256_bytes, source_record_hash,
    validate_bundle, validate_public_url,
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
        self._status=status;self._body=body;self.headers=headers or {}
    def getcode(self): return self._status
    def read(self, size): return self._body[:size]


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
        fetcher.opener=mock.Mock()
        fetcher.opener.open.return_value=HTTPStub(302,headers={"Location":"http://127.0.0.1/private"})
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(None,None,None,None,("93.184.216.34",443))]):
            with self.assertRaises(ValueError):
                fetcher.fetch("https://public.example/job")
        fetcher.opener.open.return_value=HTTPStub(200,b"x"*1025,{"Content-Type":"text/html"})
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(None,None,None,None,("93.184.216.34",443))]):
            with self.assertRaises(AcquisitionError) as too_large:
                fetcher.fetch("https://public.example/job")
        self.assertEqual(too_large.exception.kind,"response_too_large")
        fetcher.opener.open.return_value=HTTPStub(200,b"binary",{"Content-Type":"application/octet-stream"})
        with mock.patch("source_acquisition.socket.getaddrinfo", return_value=[(None,None,None,None,("93.184.216.34",443))]):
            with self.assertRaises(AcquisitionError) as content:
                fetcher.fetch("https://public.example/job")
        self.assertEqual(content.exception.kind,"unsupported_content_type")

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


if __name__ == "__main__":
    unittest.main()
