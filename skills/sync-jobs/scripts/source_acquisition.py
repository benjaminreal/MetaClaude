#!/usr/bin/env python3
"""Acquire owner-selected public job URLs without opening the tracker.

The module intentionally uses the Python standard library.  It handles public
ATS JSON, schema.org JobPosting JSON-LD and bounded static HTML.  LinkedIn and
pages that need an authenticated or rendered browser return a structured
fallback requirement; this module never transfers browser credentials or calls
private endpoints.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import hashlib
import http.client
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import zlib

from acquisition_quality import validate_quality

# Keep generic query parameters unless they are unambiguously advertising
# trackers.  Fields such as ``source``, ``ref`` and ``locale`` can carry job
# identity on an unfamiliar board and are therefore preserved.
TRACKING_KEYS = {"fbclid", "gclid"}
ALLOWED_CONTENT_TYPES = {
    "application/json", "application/ld+json", "text/html", "application/xhtml+xml"
}
JOB_CONTAINER = re.compile(
    r"(?:^|[-_\s])(job[-_\s]?(?:description|details|content)|posting[-_\s]?description|description)(?:$|[-_\s])",
    re.I,
)
JOB_CONTAINER_NORMALIZED = re.compile(
    r"\b(?:job description(?: text)?|job details|job content|posting description|description)\b",
    re.I,
)
SECRET_QUERY_KEY = re.compile(
    r"(?:^|[_-])(?:access[_-]?token|auth(?:orization)?|api[_-]?key|client[_-]?secret|"
    r"credential|jwt|password|passwd|secret|signature|sig|token)(?:$|[_-])",
    re.I,
)
EXPLICIT_TRUNCATION = re.compile(
    r"(?:\.\.\.|…)(?:\s*$|\s*(?:read|show|see|continue)\s+more\b)|"
    r"\b(?:read|show|see|continue)\s+more\b|\b(?:content|description|text)\s+(?:was\s+)?(?:clipped|truncated)\b",
    re.I,
)
BLOCKED_TEXT = {
    "captcha": ("captcha", "verify you are human", "unusual traffic"),
    "login_required": ("sign in to continue", "log in to continue", "login required"),
    "bot_challenge": ("just a moment", "checking your browser", "attention required"),
}
EXPIRED_TEXT = (
    "job is no longer available", "job no longer available", "position has been filled",
    "posting has expired", "vacancy is no longer available",
)
SUPPORTED_ATS = {"greenhouse", "lever", "smartrecruiters"}
RECORD_FIELDS = {
    "schema", "request_id", "supplied_url", "final_url", "canonical_url", "url",
    "provider", "ats", "provider_job_id", "requisition_id", "source_identity",
    "cross_source_match", "title", "company", "location", "employmentType",
    "listedAt", "status", "description", "authentication_state", "provenance",
    "quality_evidence", "source_evidence", "attempts", "description_sha256",
    "quality", "source_record_sha256",
}
FAILURE_FIELDS = {"request_id", "supplied_url", "final_url", "provider", "ats", "failure_kind", "reason", "attempts", "next_action"}
ATTEMPT_FIELDS = {"method", "url", "status", "http_status", "final_url", "response_sha256", "reason"}
BUNDLE_FIELDS = {"schema", "version", "created_at", "selected_requests", "records", "failures", "complete", "quality_complete", "claims", "bundle_sha256"}
PROVENANCE_FIELDS = {"browser", "method", "captured_at", "complete_text", "completion_evidence", "status_certain", "status_uncertainty"}
SOURCE_EVIDENCE_FIELDS = {"response_sha256", "capture_sha256", "artifact_sha256", "content_type", "redirect_chain"}


def canonical_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_posting_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("posting URL must be absolute HTTP(S)")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("posting URL must not contain credentials")
    host = parsed.hostname.lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("posting URL has an invalid port") from exc
    if port is not None and port not in {80, 443}:
        raise ValueError("posting URL uses a disallowed port")
    netloc = host
    if ":" in host:
        netloc = f"[{host}]"
    if port is not None and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
        netloc += f":{port}"
    query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        lower = key.casefold()
        if SECRET_QUERY_KEY.search(lower):
            raise ValueError("posting URL must not contain credential or secret query parameters")
        if lower.startswith("utm_") or lower in TRACKING_KEYS:
            continue
        query.append((key, val))
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", urlencode(query), ""))


def redact_url(value: str) -> str:
    """Return a persistence-safe URL-shaped value without changing fetch input."""
    raw = str(value)
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "redacted-invalid-url-" + sha256_bytes(raw.encode("utf-8"))[:20]
    host = parsed.hostname or "invalid"
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        host += f":{port}"
    query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "[REDACTED]" if SECRET_QUERY_KEY.search(key.casefold()) else val))
    safe = urlunsplit((parsed.scheme, host, parsed.path, urlencode(query), ""))
    return safe or ("redacted-invalid-url-" + sha256_bytes(raw.encode("utf-8"))[:20])


def request_id(url: str) -> str:
    return "req-" + sha256_bytes(canonical_posting_url(url).encode("utf-8"))[:20]


def _public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
    )


def validate_public_url(value: str, *, resolve: bool = True) -> str:
    canonical = canonical_posting_url(value)
    parsed = urlsplit(canonical)
    host = parsed.hostname or ""
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise ValueError("localhost destinations are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not _public_ip(str(literal)):
        raise ValueError("private or non-routable destinations are not allowed")
    if resolve and literal is None:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise ValueError(f"destination DNS resolution failed: {exc}") from exc
        if not addresses or any(not _public_ip(address) for address in addresses):
            raise ValueError("destination resolves to a private or non-routable address")
    return canonical


class AcquisitionError(Exception):
    def __init__(self, kind: str, reason: str, *, status: int | None = None, final_url: str | None = None):
        super().__init__(reason)
        self.kind = kind
        self.reason = reason
        self.status = status
        self.final_url = final_url


@dataclass(frozen=True)
class FetchResponse:
    requested_url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes
    redirects: tuple[str, ...] = ()

    @property
    def response_sha256(self) -> str:
        return sha256_bytes(self.body)


class BoundedFetcher:
    """HTTP reader with DNS, redirect, byte, timeout and content controls."""

    def __init__(self, timeout: float = 15.0, max_bytes: int = 3_000_000, max_redirects: int = 5):
        if timeout <= 0 or max_bytes < 1024 or not 0 <= max_redirects <= 10:
            raise ValueError("invalid fetch limits")
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        verify_paths = ssl.get_default_verify_paths()
        system_bundle = Path("/etc/ssl/cert.pem")
        if verify_paths.cafile is None and system_bundle.is_file():
            # Some python.org macOS builds have no populated framework-local
            # trust file even though macOS exposes a maintained PEM bundle.
            # Use that bundle rather than weakening certificate verification
            # or adding a dependency solely for CA discovery.
            context = ssl.create_default_context(cafile=str(system_bundle))
        else:
            context = ssl.create_default_context()
        self.ssl_context = context

    def _resolve(self, url: str) -> tuple[str, list[tuple]]:
        canonical = validate_public_url(url, resolve=False)
        parsed = urlsplit(canonical)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise AcquisitionError("network_error", f"destination DNS resolution failed: {exc}", final_url=canonical) from exc
        if not addresses or any(not _public_ip(item[4][0]) for item in addresses):
            raise ValueError("destination resolves to a private or non-routable address")
        return canonical, addresses

    def _open_validated(self, url: str, addresses: list[tuple]):
        """Connect only to a prevalidated sockaddr; hostname remains Host/SNI."""
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        last_error = None
        for family, socktype, proto, _canonname, sockaddr in addresses:
            sock = socket.socket(family, socktype, proto)
            try:
                sock.settimeout(self.timeout)
                sock.connect(sockaddr)
                if parsed.scheme == "https":
                    sock = self.ssl_context.wrap_socket(sock, server_hostname=host)
                conn = http.client.HTTPConnection(host, port, timeout=self.timeout)
                conn.sock = sock
                path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
                conn.request("GET", path, headers={
                    "Host": host if parsed.port is None else parsed.netloc,
                    "User-Agent": "sync-jobs/2.5 public-posting-capture",
                    "Accept": "application/json, application/ld+json, text/html;q=0.9",
                    "Accept-Encoding": "gzip, deflate, identity",
                    "Connection": "close",
                })
                return conn, conn.getresponse()
            except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
                last_error = exc
                sock.close()
        raise AcquisitionError("network_error", f"public request failed: {last_error}", final_url=url)

    def _read_bounded(self, response, encoding: str) -> bytes:
        encoding = encoding.casefold().strip()
        if encoding not in {"", "identity", "gzip", "deflate"}:
            raise AcquisitionError("unsupported_content_encoding", f"unsupported content encoding {encoding!r}")
        decoder = None
        if encoding == "gzip":
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif encoding == "deflate":
            decoder = zlib.decompressobj(zlib.MAX_WBITS)
        output = bytearray()
        encoded_total = 0
        encoded_limit = max(self.max_bytes * 2, self.max_bytes + 65536)
        try:
            while True:
                chunk = response.read(min(65536, self.max_bytes + 1))
                if not chunk:
                    break
                encoded_total += len(chunk)
                if encoded_total > encoded_limit:
                    raise AcquisitionError("response_too_large", "encoded response exceeds the bounded transport limit")
                if decoder is None:
                    piece = chunk
                else:
                    piece = decoder.decompress(chunk, self.max_bytes + 1 - len(output))
                output.extend(piece)
                if len(output) > self.max_bytes or (decoder is not None and decoder.unconsumed_tail):
                    raise AcquisitionError("response_too_large", "decompressed response exceeds the configured byte limit")
            if decoder is not None:
                output.extend(decoder.flush(self.max_bytes + 1 - len(output)))
                if not decoder.eof:
                    raise AcquisitionError("invalid_content_encoding", f"truncated {encoding} response")
            if len(output) > self.max_bytes:
                raise AcquisitionError("response_too_large", "decompressed response exceeds the configured byte limit")
        except zlib.error as exc:
            raise AcquisitionError("invalid_content_encoding", f"invalid {encoding} response") from exc
        return bytes(output)

    def fetch(self, url: str) -> FetchResponse:
        requested = validate_public_url(url, resolve=False)
        current = requested
        redirects: list[str] = []
        for hop in range(self.max_redirects + 1):
            current, addresses = self._resolve(current)
            conn = None
            try:
                conn, response = self._open_validated(current, addresses)
            except (AcquisitionError, ValueError):
                raise
            except (TimeoutError, OSError) as exc:
                raise AcquisitionError("network_error", f"public request failed: {exc}", final_url=current) from exc
            status = int(response.status)
            headers = {key.casefold(): value for key, value in response.getheaders()}
            if status in {301, 302, 303, 307, 308}:
                if conn:
                    conn.close()
                location = headers.get("location")
                if not location:
                    raise AcquisitionError("invalid_redirect", "redirect response omitted Location", status=status, final_url=current)
                if hop >= self.max_redirects:
                    raise AcquisitionError("redirect_limit", "redirect limit exceeded", status=status, final_url=current)
                current = validate_public_url(urljoin(current, location), resolve=False)
                redirects.append(current)
                continue
            try:
                body = self._read_bounded(response, headers.get("content-encoding", ""))
            finally:
                if conn:
                    conn.close()
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().casefold()
            if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                raise AcquisitionError("unsupported_content_type", f"unsupported content type {content_type!r}", status=status, final_url=current)
            return FetchResponse(requested, current, status, headers, body, tuple(redirects))
        raise AcquisitionError("redirect_limit", "redirect limit exceeded", final_url=current)


def decode_body(response: FetchResponse) -> str:
    content_type = response.headers.get("content-type", "")
    match = re.search(r"charset=([\w._-]+)", content_type, re.I)
    encoding = match.group(1) if match else "utf-8"
    try:
        return response.body.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        return response.body.decode("utf-8", errors="replace")


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        elif not self.skip and tag in {"p", "div", "li", "br", "h1", "h2", "h3", "section"}:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1
        elif not self.skip and tag in {"p", "div", "li", "h1", "h2", "h3", "section"}:
            self.text.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def html_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(value)
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.text).splitlines()]
    return "\n".join(line for line in lines if line)


class _JobPageParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.skip_depth = 0
        self.title_depth: int | None = None
        self.h1_depth: int | None = None
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self.json_depth: int | None = None
        self.json_parts: list[str] = []
        self.containers: list[dict] = []
        self.active_container: int | None = None

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        attrs = {str(k).casefold(): str(v or "") for k, v in attrs}
        if tag in {"style", "noscript", "svg"}:
            self.skip_depth += 1
        if tag == "script":
            if attrs.get("type", "").split(";", 1)[0].strip().casefold() == "application/ld+json":
                self.json_depth = self.depth
                self.json_parts = []
            else:
                self.skip_depth += 1
        if tag == "title":
            self.title_depth = self.depth
        if tag == "h1" and self.h1_depth is None:
            self.h1_depth = self.depth
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").casefold()
            if key and attrs.get("content"):
                self.meta[key] = attrs["content"].strip()
        identity = " ".join((attrs.get("id", ""), attrs.get("class", "")))
        normalized_identity = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", identity)
        normalized_identity = re.sub(r"[^A-Za-z0-9]+", " ", normalized_identity)
        if self.active_container is None and (
            JOB_CONTAINER.search(identity) or JOB_CONTAINER_NORMALIZED.search(normalized_identity)
            or (tag == "article" and attrs.get("data-job-id"))
        ):
            self.containers.append({"depth": self.depth, "parts": [], "closed": False})
            self.active_container = len(self.containers) - 1
        if self.active_container is not None and tag in {"p", "div", "li", "br", "h2", "h3", "section"}:
            self.containers[self.active_container]["parts"].append("\n")
        if tag in self.VOID_TAGS:
            self.depth = max(0, self.depth - 1)

    def handle_startendtag(self, tag, attrs):
        # ``handle_starttag`` already accounts for void-element depth.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self.active_container is not None:
            current = self.containers[self.active_container]
            if self.depth == current["depth"]:
                current["closed"] = True
                self.active_container = None
            elif tag in {"p", "div", "li", "h2", "h3", "section"}:
                current["parts"].append("\n")
        if self.json_depth == self.depth and tag == "script":
            self.json_ld.append("".join(self.json_parts))
            self.json_depth = None
            self.json_parts = []
        elif tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        if self.title_depth == self.depth and tag == "title":
            self.title_depth = None
        if self.h1_depth == self.depth and tag == "h1":
            self.h1_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.json_depth is not None:
            self.json_parts.append(data)
            return
        if self.skip_depth:
            return
        if self.title_depth is not None:
            self.title_parts.append(data)
        if self.h1_depth is not None:
            self.h1_parts.append(data)
        if self.active_container is not None:
            self.containers[self.active_container]["parts"].append(data)


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _job_postings(parser: _JobPageParser) -> list[dict]:
    found = []
    for raw in parser.json_ld:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _walk_json(payload):
            types = item.get("@type")
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list) and any(str(t).casefold() == "jobposting" for t in types):
                found.append(item)
    return found


def _organization_name(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _location(value) -> str:
    if isinstance(value, list):
        return "; ".join(filter(None, (_location(item) for item in value)))
    if not isinstance(value, dict):
        return str(value or "").strip()
    address = value.get("address", value)
    if isinstance(address, str):
        return address.strip()
    if not isinstance(address, dict):
        return ""
    parts = [address.get(key) for key in ("addressLocality", "addressRegion", "addressCountry")]
    if not any(parts):
        parts = [address.get(key) for key in ("city", "region", "country")]
    return ", ".join(str(part).strip() for part in parts if str(part or "").strip())


def _identifier(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("name")
    if isinstance(value, (str, int)) and str(value).strip():
        return str(value).strip()
    return None


def recognize(url: str) -> dict:
    parsed = urlsplit(canonical_posting_url(url))
    host = parsed.hostname or ""
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"linkedin.com", "www.linkedin.com"}:
        return {"provider": "linkedin", "ats": None, "kind": "browser_only"}
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and len(parts) >= 3 and parts[-2] == "jobs":
        return {"provider": "greenhouse", "ats": "greenhouse", "kind": "official_api", "board": parts[0], "job_id": parts[-1]}
    if host == "jobs.lever.co" and len(parts) >= 2:
        return {"provider": "lever", "ats": "lever", "kind": "official_api", "site": parts[0], "job_id": parts[1]}
    if host == "jobs.smartrecruiters.com" and len(parts) >= 2:
        job_id = parts[1].split("-", 1)[0]
        return {"provider": "smartrecruiters", "ats": "smartrecruiters", "kind": "official_api", "company": parts[0], "job_id": job_id}
    if "indeed." in host or host.endswith("indeed.com"):
        return {"provider": "indeed", "ats": None, "kind": "public_page"}
    return {"provider": host, "ats": None, "kind": "public_page"}


def api_url(adapter: dict) -> str:
    if adapter["provider"] == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{adapter['board']}/jobs/{adapter['job_id']}"
    if adapter["provider"] == "lever":
        return f"https://api.lever.co/v0/postings/{adapter['site']}/{adapter['job_id']}"
    if adapter["provider"] == "smartrecruiters":
        return f"https://api.smartrecruiters.com/v1/companies/{adapter['company']}/postings/{adapter['job_id']}"
    raise ValueError("adapter has no official API")


def source_record_hash(record: dict) -> str:
    source = {key: value for key, value in record.items() if key not in {"id", "source_id", "description_sha256", "source_record_sha256", "quality"}}
    return sha256_bytes(canonical_json(source))


def _end_marker(description: str) -> str:
    normalized = re.sub(r"\s+", " ", description).strip()
    return normalized[-min(160, len(normalized)):]


def _truncation_flags(description: str) -> list[str]:
    flags = []
    if EXPLICIT_TRUNCATION.search(description):
        flags.append("EXPLICIT_CLIPPED_OR_READ_MORE_SIGNAL")
    return flags


def _quality_evidence(description: str, method: str, response: FetchResponse,
                      structural_identity: str, extra: dict | None = None) -> dict:
    normalized = re.sub(r"\s+", " ", description).strip()
    flags = _truncation_flags(normalized)
    evidence = {
        "end_verified": not flags,
        "end_marker": _end_marker(normalized),
        "truncation_flags": flags,
        "description_length": len(description),
        "truncation_scan_sha256": sha256_bytes(canonical_json({
            "method": method, "description": description, "flags": flags,
        })),
        "structural_identity": structural_identity,
        "http_status": response.status,
        "response_sha256": response.response_sha256,
        "single_job_bound": True,
    }
    evidence.update(extra or {})
    return evidence


def _make_record(*, supplied_url: str, final_url: str, canonical_url: str, adapter: dict,
                 method: str, title: str, company: str, location: str, description: str,
                 response: FetchResponse, provider_job_id: str | None = None,
                 requisition_id: str | None = None, employment_type=None, posting_date=None,
                 completion_evidence: str, structural_identity: str,
                 quality_extra: dict | None = None,
                 attempts: list[dict] | None = None) -> dict:
    required = {"title": title, "company": company, "location": location, "description": description}
    missing = [key for key, value in required.items() if not isinstance(value, str) or not value.strip()]
    if missing:
        raise AcquisitionError("missing_required_fields", f"capture omitted required fields: {', '.join(missing)}", final_url=final_url)
    description = description.strip()
    evidence = _quality_evidence(description, method, response, structural_identity, quality_extra)
    record = {
        "schema": "SourceNeutralPostingV2",
        "request_id": request_id(supplied_url),
        "supplied_url": supplied_url,
        "final_url": final_url,
        "canonical_url": canonical_url,
        "url": canonical_url,
        "provider": adapter["provider"],
        "ats": adapter.get("ats"),
        "provider_job_id": provider_job_id,
        "requisition_id": requisition_id,
        "source_identity": {
            "kind": "provider_job_id" if provider_job_id else "canonical_url",
            "provider": adapter["provider"],
            "provider_job_id": provider_job_id,
            "canonical_url": canonical_url,
        },
        "cross_source_match": {
            "status": "review_candidate_only",
            "fingerprint_sha256": sha256_bytes(canonical_json({
                "company": company.casefold().strip(), "title": title.casefold().strip(),
                "location": location.casefold().strip(), "requisition_id": requisition_id,
                "description_sha256": sha256_bytes(description.encode("utf-8")),
            })),
        },
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "employmentType": employment_type,
        "listedAt": posting_date,
        "status": "Saved",
        "description": description,
        "authentication_state": "anonymous",
        "provenance": {
            "browser": "none",
            "method": method,
            "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "complete_text": True,
            "completion_evidence": completion_evidence,
            "status_certain": False,
            "status_uncertainty": "Acquisition does not establish saved-board membership or application state.",
        },
        "quality_evidence": evidence,
        "source_evidence": {
            "response_sha256": response.response_sha256,
            "content_type": response.headers.get("content-type", ""),
            "redirect_chain": list(response.redirects),
        },
        "attempts": attempts or [],
    }
    record["description_sha256"] = sha256_bytes(description.encode("utf-8"))
    record["quality"] = validate_quality(record)
    if not record["quality"]["eligible_for_ingest"]:
        raise AcquisitionError("quality_blocked", ", ".join(record["quality"]["unresolved_flags"]), final_url=final_url)
    record["source_record_sha256"] = source_record_hash(record)
    return record


def _json_record(payload: dict, adapter: dict, supplied_url: str, response: FetchResponse, attempts: list[dict]) -> dict:
    provider = adapter["provider"]
    expected = str(adapter["job_id"])
    if provider == "greenhouse":
        actual = str(payload.get("id") or "")
        title = payload.get("title")
        company = payload.get("company_name")
        if not company and isinstance(payload.get("company"), dict):
            company = payload["company"].get("name")
        location = (payload.get("location") or {}).get("name") if isinstance(payload.get("location"), dict) else payload.get("location")
        description = html_text(str(payload.get("content") or ""))
        canonical = payload.get("absolute_url") or supplied_url
        requisition = _identifier(payload.get("requisition_id"))
        employment = payload.get("employment_type")
        posted = payload.get("updated_at")
        structural_identity = "greenhouse:content"
    elif provider == "lever":
        actual = str(payload.get("id") or "")
        title = payload.get("text")
        company = payload.get("company") or payload.get("companyName")
        categories = payload.get("categories") or {}
        location = categories.get("location") if isinstance(categories, dict) else ""
        chunks = [payload.get("descriptionPlain") or html_text(str(payload.get("description") or ""))]
        for item in payload.get("lists") or []:
            if isinstance(item, dict):
                chunks.extend((str(item.get("text") or ""), html_text(str(item.get("content") or ""))))
        chunks.append(payload.get("additionalPlain") or html_text(str(payload.get("additional") or "")))
        description = "\n".join(chunk.strip() for chunk in chunks if isinstance(chunk, str) and chunk.strip())
        canonical = payload.get("hostedUrl") or supplied_url
        requisition = _identifier(payload.get("requisition"))
        employment = categories.get("commitment") if isinstance(categories, dict) else None
        posted = payload.get("createdAt")
        structural_identity = "lever:description+lists+additional"
    else:
        actual = str(payload.get("id") or "")
        title = payload.get("name") or payload.get("title")
        company = _organization_name(payload.get("company")) or adapter.get("company")
        location = _location(payload.get("location"))
        sections = payload.get("jobAd", {}).get("sections", {}) if isinstance(payload.get("jobAd"), dict) else {}
        description = "\n".join(html_text(str(sections.get(key, {}).get("text") or "")) for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation") if isinstance(sections.get(key), dict))
        canonical = payload.get("ref") or payload.get("applyUrl") or supplied_url
        requisition = _identifier(payload.get("refNumber"))
        employment = (payload.get("typeOfEmployment") or {}).get("label") if isinstance(payload.get("typeOfEmployment"), dict) else payload.get("typeOfEmployment")
        posted = payload.get("releasedDate")
        structural_identity = "smartrecruiters:jobAd.sections"
    if actual != expected:
        raise AcquisitionError("identity_mismatch", f"official API returned job ID {actual!r}, expected {expected!r}", final_url=response.final_url)
    canonical = canonical_posting_url(str(canonical))
    return _make_record(
        supplied_url=supplied_url, final_url=response.final_url, canonical_url=canonical,
        adapter=adapter, method="official_api", title=str(title or ""), company=str(company or ""),
        location=str(location or ""), description=description, response=response,
        provider_job_id=actual, requisition_id=requisition, employment_type=employment,
        posting_date=posted, completion_evidence="Official public ATS response supplied one complete description field.",
        structural_identity=structural_identity,
        quality_extra={"endpoint": response.final_url, "provider_job_id": actual}, attempts=attempts,
    )


def _select_json_ld(items: list[dict], supplied_url: str, final_url: str) -> dict:
    if not items:
        raise AcquisitionError("structured_data_missing", "no schema.org JobPosting object was found", final_url=final_url)
    targets = {canonical_posting_url(supplied_url), canonical_posting_url(final_url)}
    bound = []
    for item in items:
        candidate = item.get("url")
        if isinstance(candidate, str):
            try:
                if canonical_posting_url(candidate) in targets:
                    bound.append(item)
            except ValueError:
                pass
    if len(bound) == 1:
        return bound[0]
    if len(items) == 1:
        if not isinstance(items[0].get("url"), str):
            return items[0]
        raise AcquisitionError("identity_mismatch", "singleton JobPosting URL did not match the supplied or final page URL", final_url=final_url)
    raise AcquisitionError("multiple_postings", "page contains multiple JobPosting objects without one exact URL binding", final_url=final_url)


def _page_record(supplied_url: str, response: FetchResponse, adapter: dict, attempts: list[dict]) -> dict:
    if response.status != 200:
        kind = f"http_{response.status}"
        if response.status in {404, 410}:
            kind = "source_unavailable"
        elif response.status in {401, 403}:
            kind = "authentication_or_access_required"
        elif response.status == 429:
            kind = "rate_limited"
        raise AcquisitionError(kind, f"public page returned HTTP {response.status}", status=response.status, final_url=response.final_url)
    text = decode_body(response)
    parser = _JobPageParser()
    parser.feed(text)
    visible_head = " ".join(("".join(parser.title_parts), html_text(text)[:2500])).casefold()
    for kind, markers in BLOCKED_TEXT.items():
        if any(marker in visible_head for marker in markers):
            raise AcquisitionError(kind, f"page matched {kind.replace('_', ' ')} evidence", final_url=response.final_url)
    if any(marker in visible_head for marker in EXPIRED_TEXT):
        raise AcquisitionError("source_unavailable", "page states that the posting is unavailable or expired", final_url=response.final_url)
    items = _job_postings(parser)
    if items:
        item = _select_json_ld(items, supplied_url, response.final_url)
        canonical = canonical_posting_url(str(item.get("url") or response.final_url))
        description = html_text(str(item.get("description") or ""))
        job_id = _identifier(item.get("identifier"))
        return _make_record(
            supplied_url=supplied_url, final_url=response.final_url, canonical_url=canonical,
            adapter=adapter, method="public_json_ld", title=str(item.get("title") or item.get("name") or ""),
            company=str(_organization_name(item.get("hiringOrganization")) or ""),
            location=_location(item.get("jobLocation") or item.get("applicantLocationRequirements") or item.get("jobLocationType")),
            description=description, response=response, provider_job_id=job_id,
            requisition_id=_identifier(item.get("identifier")), employment_type=item.get("employmentType"),
            posting_date=item.get("datePosted"),
            completion_evidence="One schema.org JobPosting object was bound to the posting URL and its complete description value was parsed.",
            structural_identity="schema.org:JobPosting.description",
            quality_extra={"structured_type": "JobPosting", "container_count": len(items)}, attempts=attempts,
        )
    usable = [container for container in parser.containers if container["closed"]]
    if len(usable) != 1:
        kind = "javascript_render_required" if not usable else "multiple_postings"
        raise AcquisitionError(kind, f"expected one closed posting-description container, found {len(usable)}", final_url=response.final_url)
    description = html_text("".join(usable[0]["parts"]))
    title = parser.meta.get("og:title") or re.sub(r"\s+", " ", "".join(parser.h1_parts)).strip()
    company = parser.meta.get("job:company") or parser.meta.get("company") or parser.meta.get("og:site_name")
    location = parser.meta.get("job:location") or parser.meta.get("location")
    return _make_record(
        supplied_url=supplied_url, final_url=response.final_url,
        canonical_url=canonical_posting_url(response.final_url), adapter=adapter, method="public_html",
        title=str(title or ""), company=str(company or ""), location=str(location or ""),
        description=description, response=response,
        completion_evidence="One closed posting-description container was bound to this page and read through its structural end boundary.",
        structural_identity="html:closed-job-description-container",
        quality_extra={"container_count": 1, "container_closed": True}, attempts=attempts,
    )


def _attempt(method: str, url: str, status: str, *, response: FetchResponse | None = None, reason: str | None = None) -> dict:
    result = {"method": method, "url": redact_url(url), "status": status}
    if response is not None:
        result.update({"http_status": response.status, "final_url": redact_url(response.final_url), "response_sha256": response.response_sha256})
    if reason:
        result["reason"] = reason
    return result


def _redacted_attempt(attempt: dict) -> dict:
    result = dict(attempt)
    for key in ("url", "final_url"):
        if key in result:
            result[key] = redact_url(result[key])
    return result


def acquire_one(supplied_url: str, fetch: Callable[[str], FetchResponse]) -> tuple[dict | None, dict | None]:
    try:
        supplied = canonical_posting_url(supplied_url)
        validate_public_url(supplied, resolve=False)
    except ValueError as exc:
        raw_id = "req-" + sha256_bytes(str(supplied_url).encode("utf-8"))[:20]
        return None, {"request_id": raw_id, "supplied_url": redact_url(str(supplied_url)), "failure_kind": "unsafe_url", "reason": str(exc), "attempts": [], "next_action": "correct_or_replace_url"}
    rid = request_id(supplied)
    adapter = recognize(supplied)
    attempts: list[dict] = []
    if adapter["kind"] == "browser_only":
        attempts.append(_attempt("policy_check", supplied, "skipped", reason="LinkedIn automated public scraping is not an authorized acquisition method."))
        return None, {"request_id": rid, "supplied_url": supplied, "provider": "linkedin", "failure_kind": "browser_required", "reason": "Use a permitted user-visible browser capture; authenticated board state stays inside that browser.", "attempts": attempts, "next_action": "browser_fallback"}
    if adapter["kind"] == "official_api":
        endpoint = api_url(adapter)
        try:
            response = fetch(endpoint)
            attempts.append(_attempt("official_api", endpoint, "received", response=response))
            if response.status == 200:
                payload = json.loads(decode_body(response))
                if not isinstance(payload, dict):
                    raise AcquisitionError("invalid_api_payload", "official API response must be a JSON object", final_url=response.final_url)
                record = _json_record(payload, adapter, supplied, response, attempts)
                attempts[-1]["status"] = "accepted"
                record["attempts"] = attempts
                record["source_record_sha256"] = source_record_hash(record)
                return record, None
            attempts[-1].update({"status": "rejected", "reason": f"HTTP {response.status}"})
        except (AcquisitionError, ValueError, json.JSONDecodeError) as exc:
            reason = exc.reason if isinstance(exc, AcquisitionError) else str(exc)
            attempts.append(_attempt("official_api_parse", endpoint, "rejected", reason=reason))
    try:
        response = fetch(supplied)
        attempts.append(_attempt("anonymous_http", supplied, "received", response=response))
        record = _page_record(supplied, response, adapter, attempts)
        attempts[-1]["status"] = "accepted"
        record["attempts"] = attempts
        record["source_record_sha256"] = source_record_hash(record)
        return record, None
    except (AcquisitionError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, AcquisitionError):
            kind, reason, final_url = exc.kind, exc.reason, exc.final_url
        else:
            kind, reason, final_url = "parse_error", str(exc), None
        attempts.append(_attempt("anonymous_http_or_parse", supplied, "rejected", reason=reason))
        next_action = "manual_artifact_or_stop" if kind == "source_unavailable" else "browser_fallback"
        return None, {
            "request_id": rid, "supplied_url": supplied, "final_url": redact_url(final_url) if final_url else None,
            "provider": adapter["provider"], "ats": adapter.get("ats"),
            "failure_kind": kind, "reason": reason, "attempts": attempts,
            "next_action": next_action,
        }


def validate_bundle(payload: dict, *, require_hash: bool = True) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != "SourcePostingAcquisitionV2":
        raise ValueError("source acquisition bundle requires schema SourcePostingAcquisitionV2")
    unknown_bundle = set(payload) - BUNDLE_FIELDS
    if unknown_bundle:
        raise ValueError(f"bundle contains unsupported fields: {sorted(unknown_bundle)}")
    selected = payload.get("selected_requests")
    records = payload.get("records")
    failures = payload.get("failures")
    if not isinstance(selected, list) or not selected or not isinstance(records, list) or not isinstance(failures, list):
        raise ValueError("bundle requires nonempty selected_requests plus records[] and failures[]")
    if any(not isinstance(item, dict) or set(item) != {"request_id", "supplied_url"} for item in selected):
        raise ValueError("selected_requests items require only request_id and supplied_url")
    request_ids = [item.get("request_id") for item in selected]
    if len(request_ids) != len(selected) or any(not isinstance(item, str) or not item.startswith("req-") for item in request_ids) or len(set(request_ids)) != len(request_ids):
        raise ValueError("selected request IDs must be unique")
    covered = [item.get("request_id") for item in records + failures if isinstance(item, dict)]
    if len(covered) != len(records) + len(failures) or len(set(covered)) != len(covered) or set(covered) != set(request_ids):
        raise ValueError("every selected URL must occur exactly once as a record or failure")
    selected_by_id = {item["request_id"]: item["supplied_url"] for item in selected}
    if any(redact_url(item["supplied_url"]) != item["supplied_url"] for item in selected):
        raise ValueError("selected request URL contains unredacted credentials or secrets")
    for record in records:
        if set(record) - RECORD_FIELDS:
            raise ValueError(f"source record contains unsupported fields: {sorted(set(record) - RECORD_FIELDS)}")
        for key in ("request_id", "supplied_url", "final_url", "canonical_url", "url", "title", "company", "location", "description", "provenance", "quality_evidence", "source_identity"):
            if key not in record:
                raise ValueError(f"acquisition record omitted {key}")
        if record["supplied_url"] != canonical_posting_url(selected_by_id[record["request_id"]]):
            raise ValueError("record supplied URL does not match its selected request")
        for key in ("final_url", "canonical_url", "url"):
            validate_public_url(record[key], resolve=False)
        if record["url"] != record["canonical_url"]:
            raise ValueError("record URL must equal canonical posting URL")
        provenance = record["provenance"]
        if not isinstance(provenance, dict) or set(provenance) - PROVENANCE_FIELDS:
            raise ValueError("source record provenance contains unsupported fields")
        method = provenance.get("method")
        if method not in {"official_api", "public_json_ld", "public_html", "rendered_dom_text", "owner_provided_artifact"}:
            raise ValueError("source acquisition record has unsupported provenance method")
        if provenance.get("complete_text") is not True or not isinstance(provenance.get("captured_at"), str):
            raise ValueError("source record provenance is incomplete")
        evidence = record.get("source_evidence")
        if not isinstance(evidence, dict) or set(evidence) - SOURCE_EVIDENCE_FIELDS:
            raise ValueError("source record evidence contains unsupported fields")
        redirects = evidence.get("redirect_chain")
        if not isinstance(redirects, list):
            raise ValueError("source record redirect chain must be a list")
        for redirect in redirects:
            validate_public_url(redirect, resolve=False)
            if redact_url(redirect) != redirect:
                raise ValueError("source record redirect contains unredacted credentials or secrets")
        expected_auth = {
            "official_api": "anonymous", "public_json_ld": "anonymous", "public_html": "anonymous",
            "rendered_dom_text": "authorized_user_visible_browser",
            "owner_provided_artifact": "owner_provided_artifact",
        }[method]
        if record.get("authentication_state") != expected_auth:
            raise ValueError("source acquisition authentication state does not match its method")
        if method in {"official_api", "public_json_ld", "public_html"}:
            if evidence.get("response_sha256") != record["quality_evidence"].get("response_sha256"):
                raise ValueError("public response evidence hashes disagree")
        elif not isinstance(evidence.get("capture_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", evidence["capture_sha256"]):
            raise ValueError("fallback capture evidence hash is missing")
        if method == "owner_provided_artifact" and evidence.get("artifact_sha256") != record["quality_evidence"].get("artifact_sha256"):
            raise ValueError("owner artifact evidence hashes disagree")
        _validate_attempts(record.get("attempts"))
        identity = record["source_identity"]
        if not isinstance(identity, dict) or set(identity) != {"kind", "provider", "provider_job_id", "canonical_url"}:
            raise ValueError("source identity has unsupported fields")
        if identity["canonical_url"] != record["canonical_url"] or identity["provider"] != record.get("provider"):
            raise ValueError("source identity does not match record")
        if record.get("description_sha256") != sha256_bytes(record["description"].encode("utf-8")):
            raise ValueError("description hash mismatch")
        if record.get("source_record_sha256") != source_record_hash(record):
            raise ValueError("source record hash mismatch")
        recomputed = validate_quality(record)
        if record.get("quality") != recomputed or not recomputed["eligible_for_ingest"]:
            raise ValueError("source record quality is stale, fabricated or blocked")
    for failure in failures:
        if set(failure) - FAILURE_FIELDS:
            raise ValueError(f"failure contains unsupported fields: {sorted(set(failure) - FAILURE_FIELDS)}")
        selected_url = selected_by_id[failure["request_id"]]
        if failure.get("failure_kind") == "unsafe_url":
            if failure.get("supplied_url") != selected_url:
                raise ValueError("unsafe failure URL does not match its selected request")
        elif failure.get("supplied_url") != canonical_posting_url(selected_url):
            raise ValueError("failure supplied URL does not match its selected request")
        if failure.get("final_url") is not None and redact_url(failure["final_url"]) != failure["final_url"]:
            raise ValueError("failure final URL contains unredacted credentials or secrets")
        if not isinstance(failure.get("reason"), str) or not failure["reason"].strip():
            raise ValueError("failure requires a reason")
        _validate_attempts(failure.get("attempts"))
    complete = not failures and len(records) == len(selected)
    if payload.get("complete") is not complete or payload.get("quality_complete") is not complete:
        raise ValueError("bundle completion claims do not match coverage and failures")
    if require_hash:
        supplied_hash = payload.get("bundle_sha256")
        unhashed = {key: value for key, value in payload.items() if key != "bundle_sha256"}
        if supplied_hash != sha256_bytes(canonical_json(unhashed)):
            raise ValueError("bundle hash mismatch")
    return payload


def _fallback_record(raw: dict, selected: dict, prior_attempts: list[dict]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("replacement record must be an object")
    required = {"request_id", "url", "title", "company", "location", "description", "provenance", "quality_evidence"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"replacement record omitted fields: {sorted(missing)}")
    if raw["request_id"] != selected["request_id"]:
        raise ValueError("replacement record request_id does not match its selected request")
    supplied = selected["supplied_url"]
    canonical = canonical_posting_url(raw["url"])
    final_url = canonical_posting_url(raw.get("final_url") or canonical)
    provenance = dict(raw["provenance"])
    method = provenance.get("method")
    if method not in {"rendered_dom_text", "owner_provided_artifact"}:
        raise ValueError("replacement method must be rendered_dom_text or owner_provided_artifact")
    if provenance.get("complete_text") is not True or not isinstance(provenance.get("captured_at"), str):
        raise ValueError("replacement provenance must attest captured_at and complete_text")
    if method == "rendered_dom_text":
        if not isinstance(provenance.get("browser"), str) or provenance["browser"].strip().casefold() in {"", "none"}:
            raise ValueError("rendered_dom_text replacement requires the user-visible browser name")
        authentication_state = "authorized_user_visible_browser"
        structural_identity = "rendered:description-only-dom"
    else:
        authentication_state = "owner_provided_artifact"
        structural_identity = "owner:hashed-artifact"
    description = str(raw["description"]).strip()
    evidence = dict(raw["quality_evidence"])
    flags = _truncation_flags(description)
    evidence.update({
        "end_verified": evidence.get("end_verified") is True and not flags,
        "truncation_flags": flags,
        "description_length": len(description),
        "truncation_scan_sha256": sha256_bytes(canonical_json({
            "method": method, "description": description, "flags": flags,
        })),
        "structural_identity": structural_identity,
    })
    provider = str(raw.get("provider") or recognize(canonical)["provider"])
    provider_job_id = _identifier(raw.get("provider_job_id"))
    attempts = [_redacted_attempt(item) for item in list(prior_attempts) + list(raw.get("attempts") or [])]
    attempts.append(_attempt(method, canonical, "accepted", reason="validated fallback replacement"))
    record = {
        "schema": "SourceNeutralPostingV2", "request_id": selected["request_id"],
        "supplied_url": supplied, "final_url": final_url, "canonical_url": canonical, "url": canonical,
        "provider": provider, "ats": raw.get("ats"), "provider_job_id": provider_job_id,
        "requisition_id": _identifier(raw.get("requisition_id")),
        "source_identity": {
            "kind": "provider_job_id" if provider_job_id else "canonical_url", "provider": provider,
            "provider_job_id": provider_job_id, "canonical_url": canonical,
        },
        "cross_source_match": {"status": "review_candidate_only", "fingerprint_sha256": sha256_bytes(canonical_json({
            "company": str(raw["company"]).casefold().strip(), "title": str(raw["title"]).casefold().strip(),
            "location": str(raw["location"]).casefold().strip(),
            "requisition_id": _identifier(raw.get("requisition_id")),
            "description_sha256": sha256_bytes(description.encode("utf-8")),
        }))},
        "title": str(raw["title"]).strip(), "company": str(raw["company"]).strip(),
        "location": str(raw["location"]).strip(), "employmentType": raw.get("employmentType"),
        "listedAt": raw.get("listedAt"), "status": "Saved", "description": description,
        "authentication_state": authentication_state, "provenance": provenance,
        "quality_evidence": evidence,
        "source_evidence": {
            "capture_sha256": sha256_bytes(canonical_json({
                "request_id": selected["request_id"], "url": canonical, "provenance": provenance,
                "description": description, "quality_evidence": evidence,
            })),
            "artifact_sha256": evidence.get("artifact_sha256"),
            "content_type": str(raw.get("content_type") or "text/plain"), "redirect_chain": [],
        },
        "attempts": attempts,
    }
    record["description_sha256"] = sha256_bytes(description.encode("utf-8"))
    record["quality"] = validate_quality(record)
    if not record["quality"]["eligible_for_ingest"]:
        raise ValueError("replacement record quality is blocked: " + ", ".join(record["quality"]["unresolved_flags"]))
    record["source_record_sha256"] = source_record_hash(record)
    return record


def resume_bundle(original: dict, replacements: dict) -> dict:
    """Replace only failed requests in an incomplete V2 bundle."""
    validate_bundle(original)
    if original.get("complete") or not original.get("failures"):
        raise ValueError("resume requires an incomplete SourcePostingAcquisitionV2 bundle")
    if not isinstance(replacements, dict) or replacements.get("schema") != "SourcePostingFallbackV2":
        raise ValueError("replacements require schema SourcePostingFallbackV2")
    outcomes = replacements.get("outcomes")
    if not isinstance(outcomes, list):
        raise ValueError("fallback outcomes must be a list")
    ids = [item.get("request_id") for item in outcomes if isinstance(item, dict)]
    failed_by_id = {item["request_id"]: item for item in original["failures"]}
    if len(ids) != len(outcomes) or len(set(ids)) != len(ids):
        raise ValueError("fallback outcome request IDs must be present and unique")
    if set(ids) != set(failed_by_id):
        raise ValueError("fallback outcomes must cover exactly the original failed request IDs")
    selected_by_id = {item["request_id"]: item for item in original["selected_requests"]}
    records = list(original["records"])
    failures = []
    for outcome in outcomes:
        if set(outcome) not in ({"request_id", "record"}, {"request_id", "failure"}):
            raise ValueError("each fallback outcome must contain request_id and exactly one record or failure")
        prior = failed_by_id[outcome["request_id"]]
        if "record" in outcome:
            if prior.get("failure_kind") == "unsafe_url":
                raise ValueError("unsafe URL failures require a newly selected acquisition URL")
            replacement = dict(outcome["record"])
            replacement["request_id"] = outcome["request_id"]
            records.append(_fallback_record(replacement, selected_by_id[outcome["request_id"]], prior["attempts"]))
        else:
            failure = dict(prior)
            update = outcome["failure"]
            if not isinstance(update, dict) or not isinstance(update.get("reason"), str):
                raise ValueError("unresolved fallback failure requires a reason")
            extra_attempts = update.get("attempts") or []
            _validate_attempts(extra_attempts)
            failure["attempts"] = [_redacted_attempt(item) for item in list(prior["attempts"]) + list(extra_attempts)]
            failure["reason"] = update["reason"]
            failure["failure_kind"] = str(update.get("failure_kind") or prior["failure_kind"])
            failure["next_action"] = str(update.get("next_action") or prior["next_action"])
            failures.append(failure)
    records.sort(key=lambda item: [x["request_id"] for x in original["selected_requests"]].index(item["request_id"]))
    result = {
        **{key: value for key, value in original.items() if key not in {"records", "failures", "complete", "quality_complete", "bundle_sha256", "created_at"}},
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "records": records, "failures": failures,
        "complete": not failures, "quality_complete": not failures,
        "claims": {**original.get("claims", {}), "browser_fallback_executed": any(
            item.get("record", {}).get("provenance", {}).get("method") == "rendered_dom_text" for item in outcomes
        ), "authenticated_state_accessed": (
            original.get("claims", {}).get("authenticated_state_accessed", False)
            or any(item.get("record", {}).get("provenance", {}).get("method") == "rendered_dom_text" for item in outcomes)
        )},
    }
    result["bundle_sha256"] = sha256_bytes(canonical_json(result))
    return validate_bundle(result)


def _validate_attempts(attempts) -> None:
    if not isinstance(attempts, list):
        raise ValueError("attempt ledger must be a list")
    for attempt in attempts:
        if not isinstance(attempt, dict) or set(attempt) - ATTEMPT_FIELDS:
            raise ValueError("attempt ledger contains unsupported fields")
        for key in ("method", "url", "status"):
            if not isinstance(attempt.get(key), str) or not attempt[key].strip():
                raise ValueError(f"attempt ledger requires {key}")
        for key in ("url", "final_url"):
            if key in attempt and redact_url(attempt[key]) != attempt[key]:
                raise ValueError("attempt ledger URL contains unredacted credentials or secrets")


def acquire_urls(urls: list[str], fetch: Callable[[str], FetchResponse] | None = None) -> dict:
    if not urls:
        raise ValueError("at least one --url is required")
    selected = []
    seen = set()
    for url in urls:
        try:
            rid = request_id(url)
            persisted_url = canonical_posting_url(url)
        except ValueError:
            rid = "req-" + sha256_bytes(str(url).encode("utf-8"))[:20]
            persisted_url = redact_url(str(url))
        if rid in seen:
            raise ValueError("duplicate supplied URL identity")
        seen.add(rid)
        selected.append({"request_id": rid, "supplied_url": persisted_url})
    if fetch is None:
        fetch = BoundedFetcher().fetch
    records, failures = [], []
    for item, raw_url in zip(selected, urls):
        # Validate/fetch the original input.  A redacted persistence value is
        # never reinterpreted as an authorized destination.
        record, failure = acquire_one(raw_url, fetch)
        (records if record else failures).append(record or failure)
    payload = {
        "schema": "SourcePostingAcquisitionV2",
        "version": "2.0",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "selected_requests": selected,
        "records": records,
        "failures": failures,
        "complete": not failures and len(records) == len(selected),
        "quality_complete": not failures and len(records) == len(selected),
        "claims": {
            "tracker_opened": False, "tracker_written": False, "external_site_mutated": False,
            "authenticated_state_accessed": False, "browser_fallback_executed": False,
        },
    }
    payload["bundle_sha256"] = sha256_bytes(canonical_json(payload))
    return validate_bundle(payload)


def atomic_write_json(path: Path, payload: dict) -> str:
    if path.exists():
        raise ValueError("output already exists; choose a new evidence path")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(name, path)
        except FileExistsError as exc:
            raise ValueError("output was created concurrently; choose a new evidence path") from exc
        os.unlink(name)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    if json.loads(path.read_text(encoding="utf-8")) != payload:
        raise RuntimeError("acquisition bundle exact readback mismatch")
    return sha256_bytes(path.read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", required=True, help="Owner-selected job posting URL; repeat for a bounded batch")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-bytes", type=int, default=3_000_000)
    parser.add_argument("--max-redirects", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        fetcher = BoundedFetcher(args.timeout, args.max_bytes, args.max_redirects)
        payload = acquire_urls(args.url, fetcher.fetch)
        file_hash = atomic_write_json(Path(args.out).expanduser().resolve(), payload)
    except (ValueError, AcquisitionError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "status": "ACQUIRED" if payload["complete"] else "INCOMPLETE_BROWSER_OR_MANUAL_FALLBACK_REQUIRED",
        "path": str(Path(args.out).expanduser().resolve()), "sha256": file_hash,
        "record_count": len(payload["records"]), "failure_count": len(payload["failures"]),
        "complete": payload["complete"],
    }, indent=2))
    return 0


def resume_main(argv=None):
    parser = argparse.ArgumentParser(description="Merge browser/manual fallback outcomes into an incomplete source-neutral acquisition bundle.")
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--replacements", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        original = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
        replacements = json.loads(Path(args.replacements).read_text(encoding="utf-8"))
        payload = resume_bundle(original, replacements)
        file_hash = atomic_write_json(Path(args.out).expanduser().resolve(), payload)
    except (OSError, json.JSONDecodeError, ValueError, AcquisitionError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "status": "ACQUIRED" if payload["complete"] else "INCOMPLETE_BROWSER_OR_MANUAL_FALLBACK_REQUIRED",
        "path": str(Path(args.out).expanduser().resolve()), "sha256": file_hash,
        "record_count": len(payload["records"]), "failure_count": len(payload["failures"]),
        "complete": payload["complete"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
