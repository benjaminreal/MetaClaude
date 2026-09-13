#!/usr/bin/env python3
"""sync_ingest.py — the deterministic half of the saved-jobs SYNC pipeline.

Authenticated index and description capture remain in an authorized browser
session. Browser credentials cannot move into this script. The script owns
deterministic diffing, archive creation, tracker append and reconciliation.

    diff    (read-only)  saved-IDs JSON  ->  the new-ID set to fetch
    ingest  (writes)     per-job JSON    ->  .md files + Excel rows + report

The ingest path reuses write_tracker.py's safety contract verbatim:
  1. BACKUP FIRST — timestamped /tmp copy before any tracker mutation.
  2. Load with FORMULAS INTACT (not data_only); the tracker has no formula
     columns today, but appended rows never fabricate one.
  3. Tracker ID is the stable key; new IDs = max existing J-NNNNNN + 1.
  4. Write BY HEADER NAME, never by Excel letter (header-driven schema).
  5. IDEMPOTENT / crash-safe — re-reads canon from disk and skips any board ID
     already archived, so a re-run (or a resumed run) never double-writes.
  6. Extend the JobsTable ref to cover the appended rows (the one structural
     change sync is ALLOWED to make; write_tracker forbids it for triage).
  7. Writes a hash-bound PostingCompensationV1 sidecar before tracker append;
     structured API pay fields and verbatim source text are preserved without
     conversion, annualization, or estimation.
  8. NEVER touches the job board, existing rows, or triage fields. New rows are
     Estatus=Saved / Next Action=Triage so build_worklist.py picks them up.
  9. COMMIT LIVE by default (backup-first). --dry-run stages to /tmp instead.

Usage:
    sync_ingest.py diff   --saved-json saved_SAVED.json saved_INPROGRESS.json \
                          --out /tmp/sync_new_YYYY-MM-DD.json
    sync_ingest.py ingest --jobs-json /tmp/jobs_full_YYYY-MM-DD.json \
                          [--saved-json saved_*.json]   # enables reconciliation
                          [--dry-run]

Input shapes (tolerant to field-name variants):
    saved-json : the browser index output -> {"jobs": [{id, company, role,
                 location, status, url}, ...]}  (a bare list is also accepted)
    jobs-json  : the per-job output  -> [{id, title|role, company,
                 location, description|descriptionText, type|employmentType,
                 listedAt(epoch ms)|posted("YYYY-MM"), url, status}, ...]
"""
import argparse
import datetime as _dt
import glob
import json
import os
from pathlib import Path
import re
import shutil
import sys

import hashlib
import tempfile
import openpyxl

import posting_compensation
import posting_eligibility
from excel_literal import write_literal_text
from record_fields import description_value, normalize_description
from acquisition_capture import RECORD_FIELDS, validate_record
from acquisition_quality import validate_quality
from sync_integrity import saved_records, surfaces, archived_record

# --- paths (portable: resolved from this file, never hard-coded per machine) ---
PROJECT_ROOT = os.environ.get("SYNC_JOBS_ROOT", "")
DEFAULT_TRACKER = os.path.join(PROJECT_ROOT, "jobs.xlsx")
POSTINGS_DIR = os.path.join(PROJECT_ROOT, "JobPostings", "postings")
JOBPOSTINGS_TREE = os.path.join(PROJECT_ROOT, "JobPostings")
META_DIR = os.path.join(PROJECT_ROOT, "JobPostings", "_meta")
SHEET = "Jobs"

JOBVIEW_RE = re.compile(r"/jobs/view/(\d+)")

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def header_index(ws):
    """header name -> 1-based column index (header-driven, never by letter)."""
    return {
        str(c.value).strip(): i
        for i, c in enumerate(ws[1], start=1)
        if c.value is not None and str(c.value).strip() != ""
    }


def country_from_location(location):
    """Return only an explicitly supplied two-letter country token.

    Free-form city-to-country inference is intentionally outside the public
    engine because a corpus-derived location map can leak private search
    history and silently misclassify unfamiliar locations.
    """
    if not location:
        return None
    parts = [part.strip() for part in re.split(r"[,;/|]", str(location))]
    for part in reversed(parts):
        match = re.fullmatch(r"(?:country\s*:\s*)?([A-Za-z]{2})", part)
        if match:
            return match.group(1).upper()
    return None


def posted_yyyymm(rec):
    """Derive 'YYYY-MM'. Prefer an explicit 'posted' field; else listedAt ms."""
    p = rec.get("posted") or rec.get("postedDate")
    if p and re.match(r"^\d{4}-\d{2}", str(p)):
        return str(p)[:7]
    ms = rec.get("listedAt")
    if ms:
        try:
            return _dt.datetime.fromtimestamp(
                int(ms) / 1000, _dt.timezone.utc).strftime("%Y-%m")
        except (ValueError, TypeError, OverflowError):
            pass
    return _dt.date.today().strftime("%Y-%m")


def sanitize(text, maxlen=80):
    """Filename-safe token: spaces -> hyphens, drop special chars."""
    t = re.sub(r"[^\w\s-]", "", str(text or ""), flags=re.U).strip()
    t = re.sub(r"\s+", "-", t)
    return t[:maxlen].strip("-") or "Unknown"


def get(rec, *names, default=None):
    """First present field among aliases."""
    for n in names:
        if rec.get(n) not in (None, ""):
            return rec[n]
    return default


def load_jobs(paths):
    """Read one or more description inputs.

    Validated acquisition bundles are accepted directly through their
    ``records`` list.  A bundle with retained failures is deliberately not a
    partial-success input: ingest has no owner-approved subset mechanism, so it
    fails closed before any workspace write.  Legacy lists and ``jobs``
    wrappers remain parseable only for compatibility; each description that
    would be written must still pass ``validate_record`` and
    ``validate_quality(require_pass=True)`` below.
    """
    out = []
    for p in paths or []:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "records" in data:
            if data.get("schema") != "SelectedPostingAcquisitionV1":
                raise ValueError(
                    "records envelopes require schema SelectedPostingAcquisitionV1"
                )
            records = data.get("records")
            if not isinstance(records, list):
                raise ValueError("Acquisition bundle records must be a list")
            failures = data.get("failures")
            if failures is None:
                failures = []
            if not isinstance(failures, list):
                raise ValueError("Acquisition bundle failures must be a list")
            if failures:
                ids = sorted({str(item.get("id") or "?") for item in failures
                              if isinstance(item, dict)})
                raise ValueError(
                    f"Acquisition bundle retains blocked failure(s) {ids}; "
                    "ingest requires a complete batch"
                )
            if data.get("complete") is False:
                raise ValueError("Acquisition bundle is incomplete; no ingestion performed")
            selected = data.get("selected_ids")
            if (not isinstance(selected, list) or not selected
                    or any(not re.fullmatch(r"\d+", str(jid)) for jid in selected)
                    or len({str(jid) for jid in selected}) != len(selected)):
                raise ValueError(
                    "SelectedPostingAcquisitionV1 selected_ids must be unique numeric IDs"
                )
            record_ids = [str(rec.get("id", "")) for rec in records
                          if isinstance(rec, dict)]
            if (len(record_ids) != len(records)
                    or len(set(record_ids)) != len(record_ids)
                    or set(record_ids) != {str(jid) for jid in selected}):
                raise ValueError(
                    "SelectedPostingAcquisitionV1 records must cover selected_ids exactly"
                )
            if data.get("complete") is not True:
                raise ValueError(
                    "SelectedPostingAcquisitionV1 complete must be explicitly true"
                )
            if data.get("quality_complete") is not True:
                raise ValueError(
                    "SelectedPostingAcquisitionV1 quality_complete must be explicitly true"
                )
            out.extend(records)
        elif isinstance(data, dict) and "jobs" in data:
            out.extend(data["jobs"])
        elif isinstance(data, list):
            out.extend(data)
        elif isinstance(data, dict):
            out.append(data)
    return out


def rec_id(rec):
    """Numeric LinkedIn job id from a record (id field or any URL it carries)."""
    if rec.get("id"):
        return re.sub(r"\D", "", str(rec["id"])) or None
    for k in ("url", "applyUrl", "source", "Source"):
        if rec.get(k):
            m = JOBVIEW_RE.search(str(rec[k]))
            if m:
                return m.group(1)
    return None


def canon_ids(tracker):
    """Union of every LinkedIn id already in canon: Excel 'Link puesto linkedin'
    column UNION every JobPostings/**/*.md 'Source:' line. Same definition as the
    runbook Phase 2 so diff/ingest agree."""
    ids = set()
    # Excel
    wb = openpyxl.load_workbook(tracker, read_only=True, data_only=True)
    ws = wb["Jobs"]
    hdr = header_index(ws)
    lcol = hdr.get("Link puesto linkedin")
    if lcol:
        for (v,) in ws.iter_rows(min_row=2, min_col=lcol, max_col=lcol,
                                 values_only=True):
            if v:
                m = JOBVIEW_RE.search(str(v))
                if m:
                    ids.add(m.group(1))
    wb.close()
    # .md archive (posting evidence only). Meta reports also contain LinkedIn
    # links, but those are not archived JDs and must not block ingestion.
    for path in glob.glob(os.path.join(POSTINGS_DIR, "*.md")):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if not line.startswith("Source:"):
                        continue
                    for m in JOBVIEW_RE.finditer(line):
                        ids.add(m.group(1))
        except OSError:
            continue
    return ids


def canon_estatus(tracker):
    """id -> (Estatus, Puesto, Empresa) for reconciliation."""
    wb = openpyxl.load_workbook(tracker, read_only=True, data_only=True)
    ws = wb["Jobs"]
    hdr = header_index(ws)
    need = ["Puesto", "Empresa", "Estatus", "Link puesto linkedin"]
    if any(h not in hdr for h in need):
        wb.close()
        return {}
    out = {}
    # Some legacy rows have no instantiated cells in the trailing link columns.
    # In read-only mode openpyxl can therefore yield a shorter tuple unless the
    # required width is explicit, even though the header row extends farther.
    max_needed_col = max(hdr[h] for h in need)
    for r in ws.iter_rows(min_row=2, max_col=max_needed_col,
                          values_only=True):
        link = r[hdr["Link puesto linkedin"] - 1]
        if not link:
            continue
        m = JOBVIEW_RE.search(str(link))
        if m:
            out[m.group(1)] = (
                r[hdr["Estatus"] - 1],
                r[hdr["Puesto"] - 1],
                r[hdr["Empresa"] - 1],
            )
    wb.close()
    return out


# --------------------------------------------------------------------------- #
# subcommand: diff
# --------------------------------------------------------------------------- #
def cmd_diff(args):
    today = _dt.date.today().isoformat()
    saved = saved_records(args.saved_json)
    board = {}
    for rec in saved:
        jid = rec_id(rec)
        if not jid:
            continue
        board[jid] = {
            "id": jid,
            "company": get(rec, "company", "empresa"),
            "role": get(rec, "role", "title", "puesto"),
            "location": get(rec, "location"),
            "status": get(rec, "status", default="Saved"),
            "url": get(rec, "url", default=f"https://www.linkedin.com/jobs/view/{jid}/"),
        }
    tracker_rows, archives = surfaces(args.tracker, PROJECT_ROOT, POSTINGS_DIR)
    canon = set(tracker_rows) & set(archives)
    new_ids = [j for j in board if j not in canon]
    recovery_ids = sorted(set(tracker_rows) ^ set(archives))
    payload = {
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "tracker": os.path.abspath(args.tracker),
        "board_count": len(board),
        "canon_count": len(canon),
        "recovery_ids": recovery_ids,
        "new_count": len(new_ids),
        "new_ids": new_ids,
        "new_jobs": [board[j] for j in new_ids],
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"sync_ingest diff: board={len(board)}  canon={len(canon)}  "
          f"NEW={len(new_ids)}")
    for j in new_ids:
        b = board[j]
        print(f"  + {j} · {b['company']} · {b['role']}  [{b['status']}]")
    print(f"  -> {args.out}")
    if recovery_ids:
        print("RECOVERY REQUIRED: tracker/archive mismatches:", recovery_ids)
    if not new_ids and not recovery_ids:
        print("  Archive up to date — nothing to fetch. (reconciliation still "
              "runs in `ingest --saved-json ...`)")
    return 0


# --------------------------------------------------------------------------- #
# subcommand: ingest
# --------------------------------------------------------------------------- #
MD_TEMPLATE = """# {title}

Company: {company}
Location: {location}
Type: {jtype}
Posted: {posted}
Source: https://www.linkedin.com/jobs/view/{jid}/

## About the Job

{description}
"""


def render_md(rec, jid, posted):
    return MD_TEMPLATE.format(
        title=get(rec, "title", "role", "puesto", default="Unknown"),
        company=get(rec, "company", "empresa", default="Unknown"),
        location=get(rec, "location", default="Unknown"),
        jtype=get(rec, "type", "employmentType", "jtype", default="Unknown"),
        posted=posted,
        jid=jid,
        description=(get(rec, "description", "descriptionText", "about",
                         default="") or "").strip(),
    )


def write_md(rec, jid, posted, staging_dir):
    company = sanitize(get(rec, "company", "empresa", default="Unknown"))
    title = sanitize(get(rec, "title", "role", "puesto", default="Unknown"))
    fname = f"{company}_{title}_{posted}.md"
    path = os.path.join(staging_dir, fname)
    # collision with a DIFFERENT posting -> disambiguate by id
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            if f"/jobs/view/{jid}/" not in fh.read():
                fname = f"{company}_{title}_{posted}_{jid}.md"
                path = os.path.join(staging_dir, fname)
    body = render_md(rec, jid, posted)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return fname, path


def cmd_ingest(args):
    today = _dt.date.today().isoformat()
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    if args.saved_json:
        saved_records(args.saved_json)  # validate BEFORE any writes
    initial_sha = hashlib.sha256(Path(args.tracker).read_bytes()).hexdigest()
    jobs = [normalize_description(rec) if isinstance(rec, dict) else rec for rec in load_jobs(args.jobs_json)]
    if not jobs:
        rows,archives=surfaces(args.tracker,PROJECT_ROOT,POSTINGS_DIR)
        if set(rows)^set(archives):raise ValueError('Tracker/archive inconsistencies remain; supply recovery records')
        _reconcile_and_report(args, [], today, stamp)
        return 0

    # idempotent / crash-safe: re-read canon from disk, skip anything present.
    tracker_rows, archives = surfaces(args.tracker, PROJECT_ROOT, POSTINGS_DIR)
    canon = set(tracker_rows) & set(archives)
    pending, already = [], []
    seen_input = set()
    for rec in jobs:
        jid = rec_id(rec)
        if not jid:
            print(f"  WARN: record without a resolvable job id, skipped: "
                  f"{get(rec, 'title', 'role', default='?')}")
            continue
        if jid in seen_input:
            continue
        seen_input.add(jid)
        if jid in archives and jid not in tracker_rows:
            rec = archived_record(archives[jid], jid, get(rec, 'status', default='Saved'))
        if jid not in canon and not description_value(rec).strip():
            raise ValueError(f"Missing description for new job {jid}; no ingestion performed")
        complete = jid in canon and tracker_rows[jid].get('JD File') and (Path(PROJECT_ROOT)/str(tracker_rows[jid]['JD File'])).resolve() == archives[jid].resolve()
        # Require current acquisition-quality evidence only when this run would
        # write description bytes.  Archive-only recovery reuses the existing
        # archived bytes verbatim and therefore must not falsely certify old
        # evidence as a fresh capture.  Canonical rows remain read-only and
        # idempotent.  Tracker-only recovery and brand-new jobs both write a JD
        # and must pass the same quality gate.
        writes_description = jid not in archives
        if not complete and writes_description:
            # Re-run the acquisition contract as well as the quality checks.
            # Acquisition bundles contain derived fields, so retain only the
            # capture input fields when validating.  This prevents a hand-made
            # JSON record from bypassing URL/ID, provenance, complete-text, or
            # transferred-description hash validation.
            capture_input = {key: rec[key] for key in RECORD_FIELDS if key in rec}
            rec = validate_record(capture_input, {jid})
            # Recompute from source evidence.  An embedded ``quality`` result
            # is informative but never trusted as an ingest bypass.
            validate_quality(rec, require_pass=True)
        (already if complete else pending).append((jid, rec))
    if already:
        print(f"sync_ingest ingest: {len(already)} id(s) already in canon "
              f"(skipped, idempotent): {[j for j, _ in already]}")
    unhandled = (set(tracker_rows) ^ set(archives)) - seen_input
    if unhandled:
        print(f'OUTSTANDING RECOVERY outside this input batch: {sorted(unhandled)}')
        if not pending:raise ValueError('No batch work performed; tracker/archive inconsistencies remain')
    if not pending:
        print("sync_ingest ingest: nothing new to write. Archive and tracker agree.")
        _reconcile_and_report(args, [], today, stamp)
        return 0

    for jid,rec in pending:
        row=tracker_rows.get(jid)
        if row and row.get('JD File'):
            dest=(Path(PROJECT_ROOT)/str(row['JD File'])).resolve()
            if dest.exists() and (jid not in archives or dest!=archives[jid].resolve()):
                raise ValueError(f'JD File source mismatch for {jid}; entire batch stopped before writes')

    for jid,rec in pending:
        row=tracker_rows.get(jid)
        if row and jid not in archives:
            sidecar=Path(META_DIR)/'compensation'/f"{row['Tracker ID']}_PostingCompensationV1.json"
            if sidecar.exists():
                bound=json.loads(sidecar.read_text())
                digest=hashlib.sha256(render_md(rec,jid,posted_yyyymm(rec)).encode()).hexdigest()
                if bound.get('tracker_id')!=row['Tracker ID'] or bound.get('posting',{}).get('sha256')!=digest:
                    raise ValueError(f'Recovery source for {jid} differs from the preserved compensation binding; manual reconciliation required before writes')
            eligibility=Path(META_DIR)/'eligibility'/f"{row['Tracker ID']}_PostingEligibilityV1.json"
            if eligibility.exists():
                bound=json.loads(eligibility.read_text())
                digest=hashlib.sha256(render_md(rec,jid,posted_yyyymm(rec)).encode()).hexdigest()
                if bound.get('tracker_id')!=row['Tracker ID'] or bound.get('posting',{}).get('sha256')!=digest:
                    raise ValueError(f'Recovery source for {jid} differs from the preserved eligibility binding; manual reconciliation required before writes')

    # ---- staging dirs (dry-run keeps the live tree + tracker untouched) ----
    if args.dry_run:
        staging_md = os.path.join(args.backup_dir, f"sync_md_dryrun_{stamp}")
        os.makedirs(staging_md, exist_ok=True)
        # work on a /tmp copy of the tracker
        tracker_stem = Path(args.tracker).stem
        target = os.path.join(args.backup_dir, f"{tracker_stem}.dryrun_{stamp}.xlsx")
        shutil.copy2(args.tracker, target)
        print(f"sync_ingest: DRY-RUN — .md -> {staging_md}/ , Excel -> {target}")
    else:
        staging_md = POSTINGS_DIR
        os.makedirs(staging_md, exist_ok=True)
        target = args.tracker

    # ---- 1. BACKUP FIRST (always, before any tracker mutation) ----
    tracker_stem = Path(args.tracker).stem
    backup = os.path.join(args.backup_dir, f"{tracker_stem}.backup_{stamp}.xlsx")
    shutil.copy2(args.tracker, backup)
    print(f"sync_ingest: backup -> {backup}")

    # ---- 2. Load tracker with formulas intact ----
    wb = openpyxl.load_workbook(target)
    ws = wb[SHEET]
    hdr = header_index(ws)
    required = ["Tracker ID", "Previous Row", "Puesto", "Empresa", "Pais",
                "Estatus", "Next Action", "JD File", "Link puesto linkedin",
                "Comentarios"]
    miss = [h for h in required if h not in hdr]
    if miss:
        sys.exit(f"ERROR: tracker missing headers: {miss}")

    pre_ref = ws.tables["JobsTable"].ref if "JobsTable" in ws.tables else None
    base_max = _max_tracker_id(ws, hdr["Tracker ID"])

    # Keep every rehearsal's sidecars inside its unique staging tree. Shared
    # /tmp metadata would let an earlier dry-run collide with later fixtures.
    meta_dir = os.path.join(staging_md, "_meta") if args.dry_run else META_DIR
    os.makedirs(meta_dir, exist_ok=True)
    run_log = os.path.join(meta_dir, f"_sync_run_{today}.md")
    processed = os.path.join(args.backup_dir, f"processed_ids_{today}.txt")
    written = []

    appended = 0
    for n, (jid, rec) in enumerate(pending, start=1):
        posted = posted_yyyymm(rec)
        existing_row = tracker_rows.get(jid)
        if jid in archives:
            md_path = str(archives[jid])
            md_name = Path(md_path).name
            jd_link = str(Path(md_path).resolve().relative_to(Path(PROJECT_ROOT).resolve()))
        else:
            md_name, md_path = write_md(rec, jid, posted, staging_md)
            jd_link = f"JobPostings/postings/{md_name}"
            if existing_row and existing_row.get('JD File'):
                destination = (Path(PROJECT_ROOT)/str(existing_row['JD File'])).resolve()
                if destination.exists() and Path(md_path).resolve()!=destination:raise ValueError(f'Existing JD File for {jid} has mismatched source; stopped')
                jd_link = str(destination.relative_to(Path(PROJECT_ROOT).resolve()))
                if not args.dry_run:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    if Path(md_path).resolve()!=destination:
                        os.replace(md_path,destination)
                    md_path = str(destination)
                    md_name = destination.name
        if existing_row:
            tracker_id = str(existing_row['Tracker ID'])
            matches=[i for i in range(2,ws.max_row+1) if str(ws.cell(i,hdr['Tracker ID']).value)==tracker_id]
            if len(matches)!=1:raise ValueError(f'Nonunique recovery Tracker ID {tracker_id}')
            next_row=matches[0]
        else:
            appended += 1
            next_row = ws.max_row + 1
            tracker_id = f"J-{base_max + appended:06d}"
        status = get(rec, "status", default="Saved")
        estatus = "In-progress" if str(status).lower().startswith("in") else "Saved"
        country = country_from_location(
            get(rec, "countryCode", "country_code", "country")
            or get(rec, "location")
        )
        url = get(rec, "url", default=f"https://www.linkedin.com/jobs/view/{jid}/")

        # Preserve compensation evidence before triage or application-pack
        # composition.  The sidecar binds the exact archived posting bytes and
        # any structured pay fields present in the source record.  It never
        # annualizes, converts, or turns the observation into a salary strategy.
        comp_result = posting_compensation.extract_file(
            Path(md_path), tracker_id=tracker_id, source_url=url,
            structured_record=rec,
        )
        comp_dir = Path(meta_dir) / "compensation"
        comp_path = comp_dir / f"{tracker_id}_PostingCompensationV1.json"
        if comp_path.exists():
            previous=json.loads(comp_path.read_text())
            if previous.get('tracker_id') not in (None,tracker_id):raise ValueError('Compensation sidecar identity conflict')
        else:
            posting_compensation.atomic_write(
            comp_path,
            json.dumps(comp_result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

        capture = rec.get('provenance') if isinstance(rec, dict) else None
        capture_time = capture.get('captured_at') if isinstance(capture, dict) else None
        capture_binding = None
        if capture_time and rec.get('source_record_sha256'):
            capture_binding = {"captured_at": capture_time, "record_sha256": rec['source_record_sha256'],
                               "linkedin_id": jid, "source_url": url,
                               "description_sha256": rec['description_sha256'],
                               "kind": "validated_acquisition_record"}
        eligibility_result = {"status": "not_created_archive_only_recovery"}
        eligibility_path = Path(meta_dir) / "eligibility" / f"{tracker_id}_PostingEligibilityV1.json"
        if jid not in archives:
            eligibility_result = posting_eligibility.extract_file(
                Path(md_path), tracker_id=tracker_id, source_url=url, linkedin_id=jid,
                structured_record=rec, captured_at=capture_time if capture_binding else None,
                capture_provenance=capture_binding,
            )
            if eligibility_path.exists():
                previous = json.loads(eligibility_path.read_text())
                if previous.get('tracker_id') not in (None, tracker_id): raise ValueError('Eligibility sidecar identity conflict')
                if previous.get('posting', {}).get('sha256') != eligibility_result['posting']['sha256']: raise ValueError('Eligibility sidecar posting hash conflict')
            else:
                posting_eligibility.atomic_write(eligibility_path, json.dumps(eligibility_result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

        def setv(header, value):
            if existing_row and header != 'JD File':return
            cell=ws.cell(row=next_row, column=hdr[header])
            if isinstance(value,str):write_literal_text(cell,value)
            else:cell.value=value

        setv("Tracker ID", tracker_id)
        setv("Previous Row", next_row)
        setv("Puesto", get(rec, "title", "role", "puesto", default="Unknown"))
        setv("Empresa", get(rec, "company", "empresa", default="Unknown"))
        setv("Pais", country)
        setv("Estatus", estatus)
        setv("Next Action", "Triage")
        setv("JD File", jd_link)
        setv("Link puesto linkedin", url)
        setv("Comentarios", f"Saved-sync {today} via LinkedIn — pending triage")
        written.append((tracker_id, jid, estatus, md_name, get(rec, "company"),
                        get(rec, "title", "role"), comp_result["status"],
                        str(comp_path), eligibility_result["status"], str(eligibility_path)))

        # crash-safe checkpoint after each fully-written posting
        with open(processed, "a", encoding="utf-8") as fh:
            fh.write(jid + "\n")

    # ---- 6. extend the JobsTable ref to cover the new rows ----
    if pre_ref:
        m = re.match(r"([A-Z]+\d+):([A-Z]+)(\d+)", pre_ref)
        new_ref = f"{m.group(1)}:{m.group(2)}{ws.max_row}"
        jobs_table = ws.tables["JobsTable"]
        jobs_table.ref = new_ref
        # Keep the table's embedded AutoFilter aligned with the table range.
        # Updating only Table.ref leaves newly appended rows outside Excel's
        # filter controls even though they are visibly part of the table.
        if jobs_table.autoFilter is not None:
            jobs_table.autoFilter.ref = new_ref
    else:
        new_ref = None

    fd,staged=tempfile.mkstemp(prefix='.sync-jobs-ingest-',suffix='.xlsx',dir=os.path.dirname(os.path.abspath(target)))
    os.close(fd)
    try:
        wb.save(staged)
        check=openpyxl.load_workbook(staged,data_only=False)
        if check[SHEET].max_row!=ws.max_row:raise ValueError('Ingest row-count readback failed')
        for a,b in zip(ws.iter_rows(values_only=True),check[SHEET].iter_rows(values_only=True)):
            if tuple(None if x=='' else x for x in a)!=tuple(None if x=='' else x for x in b):raise ValueError('Ingest cell readback failed')
        check.close()
        if hashlib.sha256(Path(args.tracker).read_bytes()).hexdigest()!=initial_sha:raise ValueError('Tracker changed concurrently; new archive files require recovery, workbook not committed')
        os.replace(staged,target)
    finally:
        if os.path.exists(staged):os.unlink(staged)

    # ---- run log (human-readable) ----
    with open(run_log, "a", encoding="utf-8") as fh:
        fh.write(f"\n## Sync ingest {stamp}\n")
        fh.write(f"- backup: {backup}\n- tracker: {target}"
                 f"{'  (DRY-RUN)' if args.dry_run else ''}\n")
        fh.write(f"- rows appended: {appended}; recoveries: {len(written)-appended}  "
                 f"(JobsTable {pre_ref} -> {new_ref})\n")
        for tid, jid, est, md, co, role, comp_status, comp_path, eligibility_status, eligibility_path in written:
            fh.write(
                f"  - {tid} · {jid} · {co} · {role}  [{est}]  -> {md}; "
                f"compensation={comp_status} -> {comp_path}; eligibility={eligibility_status} -> {eligibility_path}\n"
            )

    print(f"sync_ingest ingest: appended {appended} row(s), restored {len(written)-appended} existing-row archive/link(s)  "
          f"(JobsTable {pre_ref} -> {new_ref})")
    for tid, jid, est, md, co, role, comp_status, comp_path, eligibility_status, eligibility_path in written:
        print(
            f"  + {tid}  {jid}  {co} · {role}  [{est}]  {md}  "
            f"compensation={comp_status} eligibility={eligibility_status}"
        )
    print(f"  tracker saved: {target}")
    print(f"  run log: {run_log}")

    _reconcile_and_report(args, written, today, stamp)
    return 0


def _max_tracker_id(ws, tcol):
    mx = 0
    for (v,) in ws.iter_rows(min_row=2, min_col=tcol, max_col=tcol,
                             values_only=True):
        m = re.match(r"J-(\d+)$", str(v or ""))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx


def _reconcile_and_report(args, written, today, stamp):
    """Phase 5 reconciliation (REPORT ONLY) + Phase 10 final report. Needs the
    board's saved list (--saved-json) to compare against canon Estatus; without
    it, the unsave/FYI sections are skipped with a note. NEVER mutates the board."""
    cleanup, fyi = [], []
    if args.saved_json:
        board = {}
        for rec in saved_records(args.saved_json):
            jid = rec_id(rec)
            if jid:
                board[jid] = rec
        canon = canon_estatus(args.tracker)
        UNSAVE = {"applied", "discarded", "unavailable", "rejected"}
        for jid in board:
            if jid in canon and str(canon[jid][0] or "").strip().lower() in UNSAVE:
                est, pue, emp = canon[jid]
                cleanup.append((emp, pue, jid, est))
        for jid, (est, pue, emp) in canon.items():
            if str(est or "").strip().lower() == "saved" and jid not in board:
                fyi.append((emp, pue, jid))

    meta_dir = args.backup_dir if args.dry_run else META_DIR
    os.makedirs(meta_dir, exist_ok=True)
    report = os.path.join(meta_dir, f"_sync_run_{today}.md")
    lines = [f"\n### Final report {stamp}",
             f"- New postings written this run: {len(written)}"]
    if args.saved_json:
        lines.append(f"- BOARD CLEANUP — unsave manually ({len(cleanup)}):")
        for emp, pue, jid, est in cleanup:
            lines.append(f"  - {emp} · {pue} · "
                         f"https://www.linkedin.com/jobs/view/{jid}/ · {est}")
        lines.append(f"- POSSIBLY UNSAVED ON BOARD (FYI, {len(fyi)}):")
        for emp, pue, jid in fyi[:50]:
            lines.append(f"  - {emp} · {pue} · {jid}")
    else:
        lines.append("- (reconciliation skipped — pass --saved-json to enable)")
    with open(report, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"\nRECONCILIATION (report only — board never mutated):")
    if args.saved_json:
        print(f"  unsave-manually: {len(cleanup)}   possibly-unsaved FYI: {len(fyi)}")
    else:
        print("  skipped (no --saved-json)")
    print(f"  appended this run: {len(written)}")


# --------------------------------------------------------------------------- #
def main(argv=None):
    today = _dt.date.today().isoformat()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracker", default=DEFAULT_TRACKER,
                    help="path to the selected tracker")
    ap.add_argument("--backup-dir", default="/tmp",
                    help="directory for backups / dry-run staging")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("diff", help="read-only: saved-IDs JSON -> new-ID set")
    d.add_argument("--saved-json", nargs="+", required=True,
                   help="one or more saved-list JSON files (SAVED, IN_PROGRESS)")
    d.add_argument("--out", default=f"/tmp/sync_new_{today}.json")
    d.set_defaults(func=cmd_diff)

    g = sub.add_parser("ingest", help="writes: per-job JSON -> .md + Excel rows")
    g.add_argument("--jobs-json", nargs="+", required=True,
                   help="per-job full-description JSON for the new IDs")
    g.add_argument("--saved-json", nargs="+", default=None,
                   help="optional saved list, to enable reconciliation")
    g.add_argument("--dry-run", action="store_true",
                   help="stage .md + Excel to /tmp; leave the live tree untouched")
    g.set_defaults(func=cmd_ingest)

    args = ap.parse_args(argv)
    if not os.path.exists(args.tracker):
        sys.exit(f"ERROR: tracker not found: {args.tracker}")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit("Use scripts/sync_jobs.py with an explicit --project-root and --profile")

    raise SystemExit(main())
