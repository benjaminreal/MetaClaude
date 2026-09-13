#!/usr/bin/env python3
"""Lossless source-only eligibility evidence extraction for archived postings."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

ROOT = Path(os.environ.get("SYNC_JOBS_ROOT", "."))
OUTPUT_DIR = ROOT / "JobPostings/_meta/eligibility"
SCHEMA = "PostingEligibilityV1"
VERSION = "1.0"
PARSER_VERSION = "1.0.0"
STATUSES = {"EVIDENCE_FOUND", "NO_MATCHES_DETECTED", "AMBIGUOUS", "EXTRACTION_FAILED"}
CATEGORIES = {
    "employer_sponsorship_willingness", "work_authorization_requirement",
    "relocation_support", "citizenship_restriction", "security_restriction",
}
LIMITATION = (
    "Automated candidate-span detection found no supported wording. This is not proof "
    "of source-wide absence, does not mean no sponsorship, and does not replace reading the whole JD."
)
REVIEW_OBLIGATION = "Read the complete archived JD before making any candidate eligibility judgment."

SIGNALS = {
    "employer_sponsorship_willingness": re.compile(
        r"\b(?:visas?\s+sponsor\w*|sponsor\w*\s+(?:a\s+)?visas?|(?:visa|immigration)\s+sponsorship|sponsorship\s+(?:for\s+)?(?:visa|immigration)|patrocin\w*\s+(?:de\s+)?visad\w*|"
        r"visad\w*\s+patrocin\w*|parrainage\s+(?:de\s+)?visa|visa[- ]?sponsoring)\b", re.I),
    "work_authorization_requirement": re.compile(
        r"\b(?:authori[sz](?:ed|ation)\s+to\s+work|work\s+authori[sz]ation|right\s+to\s+work|work\s+permit|"
        r"permiso\s+de\s+trabajo|autorisation\s+de\s+travail|droit\s+de\s+travailler|Arbeitserlaubnis|"
        r"Arbeitsberechtigung|visado\s+de\s+trabajo|visa\s+de\s+travail|work\s+visa)\b", re.I),
    "relocation_support": re.compile(
        r"\b(?:(?:relocat\w*|reubicaci[oó]n|relocalisation)\s+(?:assistance|support|package|paid|disponible|offerte)|(?:assistance|support|package)\s+(?:for\s+)?relocat\w*|Umzug(?:shilfe|skosten)|Umzugsunterst[uü]tzung)\b", re.I),
    "citizenship_restriction": re.compile(
        r"\b(?:citizen(?:ship)?\s+(?:is\s+)?required|must\s+be\s+(?:a\s+)?(?:US|U\.S\.)\s+citizen|"
        r"nationality\s+(?:is\s+)?required|ciudadan[ií]a\s+(?:requerida|obligatoria)|"
        r"nationalit[eé]\s+(?:requise|obligatoire)|Staatsangeh[oö]rigkeit\s+(?:erforderlich|vorausgesetzt))\b", re.I),
    "security_restriction": re.compile(
        r"\b(?:security\s+clearance|cleared\s+(?:candidate|personnel)|habilitaci[oó]n\s+de\s+seguridad|"
        r"habilitation\s+de\s+s[eé]curit[eé]|Sicherheits[uü]berpr[uü]fung|Sicherheitsfreigabe)\b", re.I),
}
BROAD = re.compile(
    r"\b(?:visa|visado|visum|sponsor\w*|patrocin\w*|parrainage|work\s+right|work\s+authori[sz]|authori[sz](?:ed|ation)\s+to\s+work|"
    r"work\s+permit|permiso\s+de\s+trabajo|autorisation\s+de\s+travail|Arbeitserlaubnis|"
    r"relocat\w*|reubicaci[oó]n|relocalisation|Umzug\w*|citizen\w*|ciudadan[ií]a|nationalit\w*|"
    r"clearance|habilitaci[oó]n\s+de\s+seguridad|Sicherheits\w*)\b", re.I)
FALSE_POSITIVE = re.compile(r"\bsponsor(?:ing|ed|s)?\s+(?:stakeholder|executive|community|event|workshop|session)s?\b", re.I)
EEO = re.compile(
    r"(?:equal\s+(?:employment\s+)?opportunit|without\s+regard\s+to|no\s+discriminaci[oó]n|"
    r"ind[eé]pendamment\s+de).{0,180}\b(?:national\s+origin|citizenship|nationality|origen\s+nacional)\b", re.I | re.S)
STRUCTURED_KEY = re.compile(
    r"(?:visa|sponsor|work.?authori[sz]|work.?permit|relocat|citizen|nationality|clearance|"
    r"visado|patrocin|permiso.?de.?trabajo|autorisation.?de.?travail|Arbeitserlaubnis)", re.I)

def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rel(path: Path) -> str:
    try: return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError: return str(path.resolve())

def atomic_write(path: Path, content: str) -> str:
    data = content.encode("utf-8")
    if path.exists() and path.read_bytes() == data: return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as h:
        tmp = Path(h.name); h.write(data); h.flush(); os.fsync(h.fileno())
    try: tmp.replace(path)
    finally: tmp.unlink(missing_ok=True)
    return "written"

def validated_capture(captured_at: str | None, provenance: dict[str, Any] | None) -> dict[str, Any]:
    if captured_at is None:
        return {"captured_at": None, "reason": "not_available_from_archived_source", "provenance": None}
    if not isinstance(provenance, dict): raise ValueError("capture provenance is required")
    if provenance.get("captured_at") != captured_at: raise ValueError("capture timestamp/provenance mismatch")
    digest = provenance.get("record_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("capture provenance sha256 is required")
    try: parsed = dt.datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc: raise ValueError("captured_at must be ISO-8601") from exc
    if parsed.tzinfo is None: raise ValueError("captured_at must include timezone")
    required = ("source_url", "description_sha256")
    if any(not isinstance(provenance.get(key), str) or not provenance[key] for key in required):
        raise ValueError("capture provenance identity and description binding are required")
    linkedin_id = provenance.get("linkedin_id")
    source_id = provenance.get("source_id")
    if bool(linkedin_id) == bool(source_id):
        raise ValueError("capture provenance requires exactly one linkedin_id or source_id")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance["description_sha256"]):
        raise ValueError("capture description sha256 is invalid")
    identity = {"linkedin_id": linkedin_id} if linkedin_id else {"source_id": source_id}
    return {"captured_at": captured_at, "reason": None, "provenance": {
        "captured_at": captured_at, "record_sha256": digest,
        **identity, "source_url": provenance["source_url"],
        "description_sha256": provenance["description_sha256"],
        "kind": provenance.get("kind") or "validated_acquisition_evidence"}}

def structured_eligibility_fields(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    def walk(value: Any, path: str, depth: int) -> None:
        if depth > 5: return
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if STRUCTURED_KEY.search(str(key)) and child not in (None, "", [], {}): out.append({"field_path": child_path, "value": child})
                elif isinstance(child, (dict, list)): walk(child, child_path, depth + 1)
        elif isinstance(value, list):
            for i, child in enumerate(value): walk(child, f"{path}[{i}]", depth + 1)
    walk(record or {}, "", 0); return out

def _line(text: str, offset: int) -> int: return text.count("\n", 0, offset) + 1

def _segments(text: str) -> list[tuple[int, int]]:
    marker = re.search(r"^## About the Job\s*\r?\n", text, re.M)
    body_start = marker.end() if marker else 0
    cuts = [body_start] + [body_start + m.end() for m in re.finditer(r"\n\s*\n|(?<=[.!?])(?:[ \t]+)(?=[A-ZÀ-Þ])", text[body_start:])] + [len(text)]
    out = []
    for start, end in zip(cuts, cuts[1:]):
        while start < end and text[start].isspace(): start += 1
        while end > start and text[end-1].isspace(): end -= 1
        if start < end and BROAD.search(text[start:end]): out.append((start, end))
    return out

def extract_text(text: str, *, posting_path: Path, tracker_id: str | None = None,
                 source_url: str | None = None, linkedin_id: str | None = None,
                 source_id: str | None = None,
                 structured_fields: list[dict[str, Any]] | None = None,
                 extracted_at: str | None = None, captured_at: str | None = None,
                 capture_provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    mentions, unclassified = [], []
    for start, end in _segments(text):
        raw = text[start:end]
        if FALSE_POSITIVE.search(raw) and not any(p.search(raw) for p in SIGNALS.values()): continue
        cats = sorted(c for c, pattern in SIGNALS.items() if pattern.search(raw))
        if EEO.search(raw) and not cats: continue
        item = {"raw_text": raw, "source_locator": {"line_start": _line(text,start), "line_end": _line(text,max(start,end-1)), "character_start": start, "character_end": end}, "source_url": source_url, "posting_sha256": digest}
        if cats: mentions.append({**item, "categories": cats})
        else: unclassified.append(item)
    structured = structured_fields or []
    status = "EVIDENCE_FOUND" if mentions or structured else ("AMBIGUOUS" if unclassified else "NO_MATCHES_DETECTED")
    result = {"schema": SCHEMA, "version": VERSION, "parser_version": PARSER_VERSION,
              "extracted_at": extracted_at or dt.datetime.now(dt.timezone.utc).isoformat(), "tracker_id": tracker_id,
              "posting": {"path": rel(posting_path), "sha256": digest, "source_url": source_url, "linkedin_id": linkedin_id, "source_id": source_id},
              "source_capture": validated_capture(captured_at, capture_provenance), "status": status,
              "display_status": "NOT STATED ON SOURCE" if status == "NO_MATCHES_DETECTED" else status.replace("_", " "),
              "review": {"method": "automated_candidate_span_scan", "complete": False, "requirement": REVIEW_OBLIGATION},
              "mentions": mentions, "structured_source_fields": structured, "unclassified_candidate_spans": unclassified,
              "detection_limitation": LIMITATION if status == "NO_MATCHES_DETECTED" else "Candidate spans are source quotations, not a legal or candidate eligibility conclusion.",
              "interpretation_boundary": "Source observations only; no sponsorship, work-right, relocation, citizenship, security, or candidate verdict was inferred."}
    validate(result, source_text=text); return result

def extract_file(posting_path: Path, **kwargs: Any) -> dict[str, Any]:
    raw = posting_path.read_bytes(); text = raw.decode("utf-8")
    if kwargs.get("source_url") is None:
        m = re.search(r"^Source:\s*(\S+)", text, re.M); kwargs["source_url"] = m.group(1) if m else None
    kwargs.pop("structured_record", None)
    kwargs.setdefault("structured_fields", [])
    return extract_text(text, posting_path=posting_path, **kwargs)

def validate(value: dict[str, Any], *, verify_file: bool = False, source_text: str | None = None) -> None:
    if value.get("schema") != SCHEMA or value.get("version") != VERSION: raise ValueError("unsupported eligibility schema/version")
    if value.get("parser_version") != PARSER_VERSION: raise ValueError("unsupported parser version")
    if value.get("status") not in STATUSES: raise ValueError("unsupported status")
    try: extracted = dt.datetime.fromisoformat(str(value.get("extracted_at")).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc: raise ValueError("extracted_at must be ISO-8601") from exc
    if extracted.tzinfo is None: raise ValueError("extracted_at must include timezone")
    if value.get("review") != {"method": "automated_candidate_span_scan", "complete": False, "requirement": REVIEW_OBLIGATION}:
        raise ValueError("invalid review contract")
    posting = value.get("posting", {}); digest = posting.get("sha256")
    if not posting.get("path") or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest): raise ValueError("valid posting binding required")
    capture = value.get("source_capture", {})
    validated = validated_capture(capture.get("captured_at"), capture.get("provenance"))
    if validated["captured_at"] is not None:
        provenance = validated["provenance"]
        identity_matches = (provenance.get("linkedin_id") == posting.get("linkedin_id") if provenance.get("linkedin_id") else provenance.get("source_id") == posting.get("source_id"))
        if not identity_matches or provenance["source_url"] != posting.get("source_url"):
            raise ValueError("capture identity does not match posting")
    ordered = []
    for collection in ("mentions", "unclassified_candidate_spans"):
        if not isinstance(value.get(collection), list): raise ValueError(f"{collection} must be a list")
        collection_positions=[]
        for item in value[collection]:
            loc = item.get("source_locator", {}); start, end = loc.get("character_start"), loc.get("character_end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start: raise ValueError("invalid source locator")
            if item.get("posting_sha256") != digest or item.get("source_url") != posting.get("source_url"): raise ValueError("mention provenance mismatch")
            if collection == "mentions" and (not item.get("categories") or set(item["categories"]) - CATEGORIES): raise ValueError("invalid mention categories")
            ordered.append((start, end, item, collection))
            collection_positions.append((start,end))
        if collection_positions != sorted(collection_positions): raise ValueError(f"{collection} must be source ordered")
    positions=sorted(ordered,key=lambda row:(row[0],row[1]))
    if any(left[1] > right[0] for left, right in zip(positions, positions[1:])):
        raise ValueError("candidate spans must be ordered and non-overlapping")
    structured = value.get("structured_source_fields")
    if structured != []: raise ValueError("structured eligibility fields are not supported by this release")
    if value["status"] == "NO_MATCHES_DETECTED":
        if value["mentions"] or value["unclassified_candidate_spans"] or value.get("display_status") != "NOT STATED ON SOURCE" or value.get("detection_limitation") != LIMITATION: raise ValueError("invalid empty-scan contract")
    elif value["status"] == "EVIDENCE_FOUND" and not (value["mentions"] or structured): raise ValueError("evidence status requires categorized evidence")
    elif value["status"] == "AMBIGUOUS" and (not value["unclassified_candidate_spans"] or value["mentions"] or structured): raise ValueError("ambiguous status requires only unclassified spans")
    elif value["status"] == "EXTRACTION_FAILED": raise ValueError("ordinary extraction cannot claim failure")
    if verify_file:
        relpath = Path(posting["path"])
        if relpath.is_absolute() or ".." in relpath.parts: raise ValueError("posting path must be project-relative")
        lexical = ROOT / relpath
        if any(part.is_symlink() for part in [lexical, *lexical.parents] if part != ROOT.parent): raise ValueError("posting path contains symlink")
        path = lexical.resolve()
        if not path.is_relative_to(ROOT.resolve()): raise ValueError("posting path escapes root")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest: raise ValueError("posting file/hash mismatch")
        source_text = raw.decode("utf-8")
    if source_text is not None:
        if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != digest: raise ValueError("supplied source/hash mismatch")
        for start, end, item, _collection in ordered:
            loc=item["source_locator"]
            if source_text[start:end] != item["raw_text"]: raise ValueError("source locator slice mismatch")
            if loc["line_start"] != _line(source_text,start) or loc["line_end"] != _line(source_text,max(start,end-1)):
                raise ValueError("source locator line mismatch")
        header=re.search(r"^Source:\s*(\S+)",source_text,re.M)
        if header and header.group(1) != posting.get("source_url"): raise ValueError("posting source URL/header mismatch")
        if posting.get("linkedin_id") and header:
            found=re.search(r"/jobs/view/(\d+)/?",header.group(1))
            if not found or found.group(1) != posting["linkedin_id"]: raise ValueError("posting LinkedIn ID/header mismatch")
        if posting.get("source_id"):
            provenance=validated.get("provenance") or {}
            if provenance.get("source_id") != posting["source_id"]: raise ValueError("posting source ID/capture mismatch")
        if validated["captured_at"] is not None:
            marker=re.search(r"^## About the Job\s*\r?\n",source_text,re.M)
            if not marker: raise ValueError("captured posting has no JD body marker")
            description=source_text[marker.end():].strip()
            if hashlib.sha256(description.encode("utf-8")).hexdigest() != validated["provenance"]["description_sha256"]:
                raise ValueError("capture description hash does not bind archived JD body")

def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="command",required=True); ex=sub.add_parser("extract")
    ex.add_argument("--posting",required=True); ex.add_argument("--tracker-id"); ex.add_argument("--source-url"); ex.add_argument("--linkedin-id"); ex.add_argument("--source-id")
    args=ap.parse_args(argv); result=extract_file(Path(args.posting).resolve(),tracker_id=args.tracker_id,source_url=args.source_url,linkedin_id=args.linkedin_id,source_id=args.source_id)
    sys.stdout.write(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n"); return 0

if __name__ == "__main__": raise SystemExit(main())
