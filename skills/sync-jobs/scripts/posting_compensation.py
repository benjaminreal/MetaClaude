#!/usr/bin/env python3
"""Lossless, deterministic compensation extraction from archived job postings.

The extractor deliberately separates observation from interpretation.  It keeps
the exact source text and character offsets, then records only mechanical tokens
(currency, amounts, cadence, pay basis, and qualifiers).  It does not annualize,
convert currencies, infer a market band, or create a candidate salary strategy.

CLI examples:

    posting_compensation.py extract --posting JobPostings/postings/example.md
    posting_compensation.py backfill --batch-manifest <batch.json> [--write]

``backfill`` is dry-run by default.  Live outputs are stable sidecars under
``JobPostings/_meta/compensation/<Tracker ID>_PostingCompensationV1.json``.
"""
from __future__ import annotations

import os
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable

import openpyxl


ROOT = Path(os.environ.get("SYNC_JOBS_ROOT", "."))
TRACKER = ROOT / "jobs.xlsx"
OUTPUT_DIR = ROOT / "JobPostings/_meta/compensation"
SCHEMA = "PostingCompensationV1"
PARSER_VERSION = "1.0.2"
STATUSES = {
    "STATED",
    "NOT STATED ON SOURCE",
    "AMBIGUOUS",
    "EXTRACTION FAILED",
}

CURRENCY_RE = re.compile(
    r"(?<![A-Z])(?:USD|CAD|GBP|EUR|MXN|COP|PEN|CHF|DKK|SEK|NOK|PLN|CZK|BRL|"
    r"CLP|ARS|AUD|NZD|JPY|INR)(?![A-Z])|[$€£¥₹]",
    re.I,
)
AMOUNT_RE = re.compile(
    r"(?<![\w])(?:(?:USD|CAD|GBP|EUR|MXN|COP|PEN|CHF|DKK|SEK|NOK|PLN|CZK|"
    r"BRL|CLP|ARS|AUD|NZD|JPY|INR)\s+|[$€£¥₹]\s*)?"
    r"(?:\d{1,3}(?:[,.\s]\d{3})+|\d{4,9}|\d{1,3})(?:[.,]\d+)?\s*(?:[kKmM])?"
    r"(?:\s*(?:USD|CAD|GBP|EUR|MXN|COP|PEN|CHF|DKK|SEK|NOK|PLN|CZK|BRL|"
    r"CLP|ARS|AUD|NZD|JPY|INR))?(?![\w%])"
)
RANGE_RE = re.compile(
    r"(?:[$€£¥₹]\s*)?\d[\d,.\s]*\s*[kKmM]?\s*"
    r"(?:[-–—]|\bto\b|\ba\b|\bhasta\b)\s*"
    r"(?:[$€£¥₹]\s*)?\d[\d,.\s]*\s*[kKmM]?",
    re.I,
)
COMP_KEYWORD_RE = re.compile(
    r"\b(?:salary|salaries|pay range|pay band|base pay|base salary|compensation|"
    r"remuneration|wage|wages|rate|day rate|hourly|annual pay|annual salary|OTE|"
    r"on[- ]target earnings|total (?:annual )?package|sueldo|salario|salarios|rango salarial|remuneraci[oó]n|"
    r"compensaci[oó]n|retribuci[oó]n)\b",
    re.I,
)
NON_NUMERIC_RE = re.compile(
    r"\b(?:competitive|market[- ]competitive|commensurate with experience|"
    r"depending on experience|negotiable|a convenir|competitiv[oa])\b",
    re.I,
)

CADENCE_PATTERNS = {
    "annual": re.compile(r"\b(?:annual(?:ly)?|yearly|per year|a year|p\.?a\.?|anual(?:es)?)\b", re.I),
    "monthly": re.compile(r"\b(?:monthly|per month|a month|mensual(?:es)?)\b", re.I),
    "weekly": re.compile(r"\b(?:weekly|per week|a week|semanal(?:es)?)\b", re.I),
    "daily": re.compile(r"\b(?:daily|per day|a day|day rate|diari[oa]s?)\b", re.I),
    "hourly": re.compile(r"\b(?:hourly|per hour|an hour|por hora)\b", re.I),
}
PAY_BASIS_PATTERNS = {
    "total package": re.compile(r"\btotal\s+(?:annual\s+)?package\b", re.I),
    "base salary": re.compile(r"\b(?:base salary|base pay|salario base|sueldo base)\b", re.I),
    "total compensation": re.compile(r"\b(?:total compensation|total comp|compensaci[oó]n total)\b", re.I),
    "total cash": re.compile(r"\b(?:total cash|cash compensation)\b", re.I),
    "OTE": re.compile(r"\b(?:OTE|on[- ]target earnings)\b", re.I),
    "contract rate": re.compile(r"\b(?:day rate|hourly rate|contract rate|daily rate)\b", re.I),
}
QUALIFIER_PATTERNS = {
    "ceiling": re.compile(r"\b(?:up to|maximum(?: of)?|at most)\b", re.I),
    "bonus": re.compile(r"\b(?:bonus|bonuses|bono|bonos|annual incentive)\b", re.I),
    "commission": re.compile(r"\b(?:commission|commissions|comisi[oó]n|comisiones)\b", re.I),
    "equity": re.compile(r"\b(?:equity|stock|RSU|shares|acciones)\b", re.I),
    "benefits": re.compile(r"\b(?:benefits|beneficios|pension)\b", re.I),
    "location-limited": re.compile(
        r"\b(?:based in|for candidates in|for (?:US|UK|Canada|Europe|EMEA|LATAM)|"
        r"location|geograph|depending on where|varies by location)\b",
        re.I,
    ),
}
STRUCTURED_KEY_RE = re.compile(
    r"(?:salary|compensation|pay.?range|wage|remuneration|rate)", re.I
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def atomic_write(path: Path, content: str) -> str:
    encoded = content.encode("utf-8")
    if path.exists() and path.read_bytes() == encoded:
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return "written"


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(match.end() for match in re.finditer(r"\n", text))
    return starts


def _line_for_offset(starts: list[int], offset: int) -> int:
    lo, hi = 0, len(starts)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= offset:
            lo = mid
        else:
            hi = mid
    return lo + 1


def _candidate_spans(text: str) -> list[tuple[int, int]]:
    """Return exact paragraph/sentence spans that contain pay signals."""
    boundaries = [0]
    boundaries.extend(match.end() for match in re.finditer(r"\n\s*\n|(?<=[.!?])\s+(?=[A-ZÀ-Þ])", text))
    boundaries.append(len(text))
    spans: list[tuple[int, int]] = []
    for start, end in zip(boundaries, boundaries[1:]):
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start >= end:
            continue
        segment = text[start:end]
        has_keyword = COMP_KEYWORD_RE.search(segment) is not None
        has_currency_amount = (
            CURRENCY_RE.search(segment) is not None
            and AMOUNT_RE.search(segment) is not None
            and _has_range_expression(segment)
        )
        if has_keyword or has_currency_amount:
            spans.append((start, end))
    # Coalesce exact duplicate/contained spans without changing source bytes.
    unique: list[tuple[int, int]] = []
    for span in spans:
        if span not in unique:
            unique.append(span)
    return unique


def _amount_tokens(text: str) -> list[str]:
    values = []
    for match in AMOUNT_RE.finditer(text):
        token = match.group(0).strip()
        bare = re.sub(r"[^0-9]", "", token)
        # Years and tiny bare numbers are not compensation without currency/K/M.
        if not CURRENCY_RE.search(token) and not re.search(r"[kKmM]", token):
            if bare.isdigit() and (int(bare) < 1000 or 1900 <= int(bare) <= 2100):
                continue
        values.append(token)
    return values


def _has_range_expression(text: str) -> bool:
    matches = list(AMOUNT_RE.finditer(text))
    for left, right in zip(matches, matches[1:]):
        between = text[left.end():right.start()].strip()
        # A true range separator is local.  Long prose between unrelated
        # benefit amounts (or an ordinary hyphen in that prose) is not a band.
        currency = (
            r"(?:USD|CAD|GBP|EUR|MXN|COP|PEN|CHF|DKK|SEK|NOK|PLN|CZK|BRL|"
            r"CLP|ARS|AUD|NZD|JPY|INR|[$€£¥₹])"
        )
        if len(between) <= 24 and re.fullmatch(
            rf"(?:{currency}\s*)?(?:[-–—]|to|a|hasta)(?:\s*{currency})?",
            between,
            re.I,
        ):
            return True
    return False


def _has_numeric_pay_disclosure(text: str, amounts: list[str], currencies: list[str]) -> bool:
    if not amounts:
        return False
    # A currency-bearing range is independently strong.  A single figure must
    # be introduced as salary/pay/rate; this rejects revenue, benefit budgets,
    # home-office allowances, and other numbers that happen to sit nearby.
    if len(amounts) >= 2 and currencies and _has_range_expression(text):
        return True
    for match in AMOUNT_RE.finditer(text):
        prefix = text[max(0, match.start() - 120):match.start()]
        if re.search(
            r"\b(?:allowance|budget|voucher|coverage|reimbursement|revenue|funding)\b",
            prefix,
            re.I,
        ):
            continue
        if re.search(
            r"(?:salary(?:\s+range)?|base\s+pay(?:\s+range)?|pay\s+range|"
            r"compensation(?:\s+range)?|total\s+(?:annual\s+)?package|remuneration|OTE|on[- ]target earnings|"
            r"sueldo|salario(?:\s+base)?|rango\s+salarial|day\s+rate|hourly\s+rate)"
            r"[^.!?\n]{0,100}$",
            prefix,
            re.I,
        ):
            return True
    return False


def structured_compensation_fields(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Preserve pay-looking source fields returned by an upstream API."""
    found: list[dict[str, Any]] = []

    def walk(value: Any, path: str, depth: int) -> None:
        if depth > 5:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if STRUCTURED_KEY_RE.search(str(key)) and child not in (None, "", [], {}):
                    found.append({"field_path": child_path, "value": child})
                elif isinstance(child, (dict, list)):
                    walk(child, child_path, depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", depth + 1)

    walk(record or {}, "", 0)
    return found


def extract_text(
    text: str,
    *,
    posting_path: Path,
    tracker_id: str | None = None,
    source_url: str | None = None,
    structured_fields: list[dict[str, Any]] | None = None,
    extracted_at: str | None = None,
) -> dict[str, Any]:
    starts = _line_starts(text)
    mentions = []
    for start, end in _candidate_spans(text):
        raw = text[start:end]
        amounts = _amount_tokens(raw)
        currencies = list(dict.fromkeys(match.group(0) for match in CURRENCY_RE.finditer(raw)))
        cadences = [name for name, pattern in CADENCE_PATTERNS.items() if pattern.search(raw)]
        bases = [name for name, pattern in PAY_BASIS_PATTERNS.items() if pattern.search(raw)]
        qualifiers = [name for name, pattern in QUALIFIER_PATTERNS.items() if pattern.search(raw)]
        has_range = _has_range_expression(raw)
        mentions.append({
            "raw_text": raw,
            "source_locator": {
                "line_start": _line_for_offset(starts, start),
                "line_end": _line_for_offset(starts, max(start, end - 1)),
                "character_start": start,
                "character_end": end,
            },
            "currency_tokens": currencies,
            "amount_tokens": amounts,
            "cadence_tokens": cadences,
            "pay_basis_tokens": bases,
            "qualifiers": qualifiers,
            "has_range_expression": has_range,
            "has_numeric_pay_disclosure": _has_numeric_pay_disclosure(
                raw, amounts, currencies
            ),
            "has_non_numeric_statement": NON_NUMERIC_RE.search(raw) is not None and not amounts,
        })

    structured = structured_fields or []
    numeric = [mention for mention in mentions if mention["has_numeric_pay_disclosure"]]
    non_numeric = [mention for mention in mentions if mention["has_non_numeric_statement"]]
    if mentions or structured:
        status = "STATED"
    else:
        status = "NOT STATED ON SOURCE"
    ambiguous = any(
        mention["amount_tokens"]
        and not mention["currency_tokens"]
        and not mention["pay_basis_tokens"]
        and not mention["cadence_tokens"]
        for mention in mentions
    )
    if status == "STATED" and ambiguous and not structured:
        status = "AMBIGUOUS"

    result = {
        "schema": SCHEMA,
        "parser": {"name": Path(__file__).name, "version": PARSER_VERSION},
        "extracted_at": extracted_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "tracker_id": tracker_id,
        "posting": {
            "path": rel(posting_path),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_url": source_url,
        },
        "status": status,
        "structured_source_fields": structured,
        "mentions": mentions,
        "summary": {
            "mention_count": len(mentions),
            "structured_field_count": len(structured),
            "has_numeric_disclosure": bool(numeric or structured),
            "has_range_expression": any(m["has_range_expression"] for m in mentions),
            "has_non_numeric_statement": bool(non_numeric),
        },
        "interpretation_boundary": (
            "Mechanical source extraction only. No currency conversion, annualization, "
            "market estimate, forced single, negotiation anchor, or decision floor was inferred."
        ),
    }
    validate(result)
    return result


def extract_file(
    posting_path: Path,
    *,
    tracker_id: str | None = None,
    source_url: str | None = None,
    structured_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        text = posting_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {
            "schema": SCHEMA,
            "parser": {"name": Path(__file__).name, "version": PARSER_VERSION},
            "extracted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "tracker_id": tracker_id,
            "posting": {"path": rel(posting_path), "sha256": None, "source_url": source_url},
            "status": "EXTRACTION FAILED",
            "structured_source_fields": structured_compensation_fields(structured_record),
            "mentions": [],
            "summary": {
                "mention_count": 0,
                "structured_field_count": 0,
                "has_numeric_disclosure": False,
                "has_range_expression": False,
                "has_non_numeric_statement": False,
            },
            "failure": f"{type(exc).__name__}: {exc}",
            "interpretation_boundary": "Source extraction failed; no compensation inference was made.",
        }
    if source_url is None:
        match = re.search(r"^Source:\s*(\S+)", text, re.M)
        source_url = match.group(1) if match else None
    return extract_text(
        text,
        posting_path=posting_path,
        tracker_id=tracker_id,
        source_url=source_url,
        structured_fields=structured_compensation_fields(structured_record),
    )


def validate(value: dict[str, Any], *, verify_file: bool = False) -> None:
    if value.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if value.get("status") not in STATUSES:
        raise ValueError(f"unsupported status: {value.get('status')}")
    posting = value.get("posting")
    if not isinstance(posting, dict) or not posting.get("path"):
        raise ValueError("posting path is required")
    if value["status"] != "EXTRACTION FAILED":
        digest = posting.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("posting sha256 is required")
    if not isinstance(value.get("mentions"), list):
        raise ValueError("mentions must be a list")
    if verify_file and value["status"] != "EXTRACTION FAILED":
        path = ROOT / posting["path"]
        if not path.is_file() or sha256_file(path) != posting["sha256"]:
            raise ValueError("posting file/hash mismatch")


def _tracker_rows(tracker: Path) -> dict[str, dict[str, Any]]:
    workbook = openpyxl.load_workbook(tracker, read_only=True, data_only=True)
    sheet = workbook["Jobs"]
    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in sheet[1]]
    rows: dict[str, dict[str, Any]] = {}
    for values in sheet.iter_rows(min_row=2, max_col=len(headers), values_only=True):
        row = dict(zip(headers, values))
        job_id = str(row.get("Tracker ID") or "")
        if re.fullmatch(r"J-\d{6}", job_id):
            rows[job_id] = row
    workbook.close()
    return rows


def _batch_job_ids(batch_path: Path) -> list[str]:
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    ids = [str(item.get("job_id") or "") for item in batch.get("selected", [])]
    if not ids or any(not re.fullmatch(r"J-\d{6}", job_id) for job_id in ids):
        raise ValueError("batch manifest contains invalid or empty selected job IDs")
    if len(ids) != len(set(ids)):
        raise ValueError("batch manifest contains duplicate job IDs")
    return ids


def backfill(
    *, batch_manifest: Path, tracker: Path, output_dir: Path, write: bool
) -> dict[str, Any]:
    rows = _tracker_rows(tracker)
    records = []
    for job_id in _batch_job_ids(batch_manifest):
        row = rows.get(job_id)
        if row is None:
            records.append({"job_id": job_id, "status": "EXTRACTION FAILED", "error": "tracker row missing"})
            continue
        jd_value = str(row.get("JD File") or "").strip()
        if not jd_value:
            records.append({"job_id": job_id, "status": "EXTRACTION FAILED", "error": "JD File missing"})
            continue
        posting_path = (ROOT / jd_value).resolve()
        output = output_dir / f"{job_id}_PostingCompensationV1.json"
        result = None
        action = "dry-run"
        if write and output.is_file():
            try:
                current = json.loads(output.read_text(encoding="utf-8"))
                validate(current, verify_file=True)
                if (
                    current.get("tracker_id") == job_id
                    and current.get("parser", {}).get("version") == PARSER_VERSION
                ):
                    result = current
                    action = "unchanged"
            except (OSError, ValueError, json.JSONDecodeError):
                # Re-extract invalid, stale, or parser-old sidecars below.
                result = None
        if result is None:
            result = extract_file(
                posting_path,
                tracker_id=job_id,
                source_url=str(row.get("Link puesto linkedin") or "") or None,
            )
            if write:
                action = atomic_write(
                    output,
                    json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                )
        records.append({
            "job_id": job_id,
            "company": row.get("Empresa"),
            "role": row.get("Puesto"),
            "posting": rel(posting_path),
            "output": rel(output),
            "status": result["status"],
            "numeric": result["summary"]["has_numeric_disclosure"],
            "ranges": result["summary"]["has_range_expression"],
            "action": action,
        })
    return {
        "schema": "PostingCompensationBackfillReportV1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "batch_manifest": rel(batch_manifest),
        "batch_manifest_sha256": sha256_file(batch_manifest),
        "tracker": rel(tracker),
        "tracker_sha256": sha256_file(tracker),
        "write": write,
        "records": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("extract")
    one.add_argument("--posting", required=True)
    one.add_argument("--tracker-id")
    one.add_argument("--source-url")
    one.add_argument("--out")
    batch = sub.add_parser("backfill")
    batch.add_argument("--batch-manifest", required=True)
    batch.add_argument("--tracker", default=str(TRACKER))
    batch.add_argument("--output-dir", default=str(OUTPUT_DIR))
    batch.add_argument("--report")
    batch.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "extract":
        result = extract_file(
            Path(args.posting).resolve(), tracker_id=args.tracker_id, source_url=args.source_url
        )
        content = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.out:
            atomic_write(Path(args.out).resolve(), content)
        else:
            sys.stdout.write(content)
        return 0

    report = backfill(
        batch_manifest=Path(args.batch_manifest).resolve(),
        tracker=Path(args.tracker).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        write=args.write,
    )
    content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        atomic_write(Path(args.report).resolve(), content)
    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit("Use scripts/sync_jobs.py with an explicit --project-root and --profile")

    raise SystemExit(main())
