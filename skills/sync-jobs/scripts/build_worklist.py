#!/usr/bin/env python3
"""build_worklist.py — select rows needing triage and emit a hand-off worklist.

STEP 1 of the reactive-triage chain. This script is pure plumbing: it reads the
tracker (read-only), selects the rows that need triage, and writes a JSON
worklist keyed by Tracker ID. Each entry carries the identity fields a human/
agent needs to judge fit, plus BLANK operator-judgment fields for them to fill.

It NEVER scores, NEVER decides a verdict, and NEVER writes the tracker.

Selector:
    Estatus == 'Saved'  AND  Next Action == 'Triage'
This deliberately does NOT use "empty Triage Date", because terminal rows
(Rejected/Unavailable) and prior-pass Saved rows carry stale/empty Triage Date
and would be over-captured. 'Saved' + 'Triage' is the clean new-triage target.

A row whose JD File (col 18) is blank is still emitted, but flagged
missing_jd=True so the judgment step (and the operator) can pull the JD first
rather than crashing or guessing from the title.

Usage:
    build_worklist.py --tracker /path/to/jobs.xlsx \
                      --out /tmp/triage_worklist_YYYY-MM-DD.json
    build_worklist.py            # defaults: live tracker -> /tmp worklist

Output JSON shape:
    {
      "generated": "<ISO timestamp>",
      "tracker": "<abs path>",
      "selector": "Estatus=Saved AND Next Action=Triage",
      "project_root": "<abs project root>",
      "count": <int>,
      "rows": [
        {
          "tracker_id": "J-000001",
          "puesto": "...", "empresa": "...", "pais": "...", "track_existing": "...",
            "linkedin_url": "https://www.linkedin.com/jobs/view/.../",
            "employer_url": "https://employer.example/jobs/...",
            "job_url": "<employer_url when present, otherwise linkedin_url>",
          "jd_file": "JobPostings/postings/....md",
          "jd_abs": "<project_root>/JobPostings/postings/....md" | null,
          "missing_jd": false,
          "judgment": { ... }      # blank selected-profile template
        }, ...
      ]
    }
"""
import argparse
import datetime as _dt
import json
import os
import sys

import openpyxl
import hashlib
from pathlib import Path
import posting_eligibility

PROJECT_ROOT = os.environ.get("SYNC_JOBS_ROOT", "")
DEFAULT_TRACKER = os.path.join(PROJECT_ROOT, "jobs.xlsx")
SHEET = "Jobs"
JUDGMENT_TEMPLATE = {}

# Advanced lifecycle states whose rows must NOT be regressed by a re-triage
# When such a row is included via
# --include-statuses, it is triaged ASSESS-ONLY: scores/summary refresh, but
# Estatus and Next Action are preserved. score_triage enforces this.
ADVANCED = {"applied", "in-progress", "interview", "offer"}


def header_index(ws):
    """Map header name -> 0-based column index. Header-driven, never by letter."""
    return {
        str(cell.value).strip(): idx
        for idx, cell in enumerate(ws[1])
        if cell.value is not None and str(cell.value).strip() != ""
    }

def eligibility_evidence(tracker_id, jd_abs, source_url):
    path = os.path.join(PROJECT_ROOT, "JobPostings", "_meta", "eligibility", f"{tracker_id}_PostingEligibilityV1.json")
    result = {"path": os.path.relpath(path, PROJECT_ROOT), "absolute_path": path, "availability": "missing",
              "posting_sha256": None, "schema": None, "status": None, "display_status": None,
              "mentions": [], "unclassified_candidate_spans": [], "limitation": None,
              "relocation_mentions": [], "sponsorship_mentions": []}
    if not os.path.exists(path): return result
    try:
        value=json.loads(Path(path).read_text(encoding="utf-8"))
        # Validate the sidecar structure before comparing it with the current
        # archive. A well-formed sidecar bound to older bytes is stale, not
        # malformed, and its quotations must not be exposed as current.
        posting_eligibility.validate(value, verify_file=False)
        expected_rel=os.path.relpath(jd_abs, PROJECT_ROOT) if jd_abs else None
        if value.get("tracker_id") != str(tracker_id) or value.get("posting",{}).get("path") != expected_rel or value.get("posting",{}).get("source_url") != source_url:
            raise ValueError("eligibility identity/path/source URL binding mismatch")
        result.update({"schema": value["schema"], "status": value["status"], "display_status": value["display_status"],
                       "posting_sha256": value["posting"]["sha256"],
                       "limitation": value["detection_limitation"]})
        if not jd_abs or not os.path.isfile(jd_abs) or hashlib.sha256(Path(jd_abs).read_bytes()).hexdigest()!=value["posting"]["sha256"]:
            result["availability"]="stale"
        else:
            posting_eligibility.validate(value, source_text=Path(jd_abs).read_text(encoding="utf-8"))
            result["availability"]="valid"
            result["mentions"]=value["mentions"]
            result["unclassified_candidate_spans"]=value["unclassified_candidate_spans"]
            result["relocation_mentions"]=[m for m in value["mentions"] if "relocation_support" in m["categories"]]
            result["sponsorship_mentions"]=[m for m in value["mentions"] if "employer_sponsorship_willingness" in m["categories"]]
    except Exception as exc:
        result["availability"]="invalid"; result["error"]=str(exc)
    return result


def main(argv=None):
    today = _dt.date.today().isoformat()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tracker", default=DEFAULT_TRACKER,
                    help="path to the selected tracker")
    ap.add_argument("--out", default=f"/tmp/triage_worklist_{today}.json",
                    help="output worklist JSON path")
    ap.add_argument("--include-statuses", default="",
                    help="comma-separated Estatus values to ALSO select regardless "
                         "of Next Action (e.g. 'In-progress'). Advanced states are "
                         "marked assess_only so the scorer preserves their lifecycle.")
    args = ap.parse_args(argv)
    include_statuses = {s.strip() for s in args.include_statuses.split(",") if s.strip()}

    if not os.path.exists(args.tracker):
        sys.exit(f"ERROR: tracker not found: {args.tracker}")

    # read_only is fine here — we only READ. Values, not formulas, are needed.
    wb = openpyxl.load_workbook(args.tracker, read_only=True, data_only=True)
    if SHEET not in wb.sheetnames:
        sys.exit(f"ERROR: sheet {SHEET!r} not in {wb.sheetnames}")
    ws = wb[SHEET]
    hdr = header_index(ws)

    required = ["Tracker ID", "Puesto", "Empresa", "Pais", "Track",
                "Estatus", "Next Action", "JD File", "Link puesto linkedin",
                "Link puesto empresa"]
    missing = [h for h in required if h not in hdr]
    if missing:
        sys.exit(f"ERROR: tracker missing expected headers: {missing}")

    iTID = hdr["Tracker ID"]; iPue = hdr["Puesto"]; iEmp = hdr["Empresa"]
    iPais = hdr["Pais"]; iTrack = hdr["Track"]; iEst = hdr["Estatus"]
    iNA = hdr["Next Action"]; iJD = hdr["JD File"]
    iLinkedIn = hdr["Link puesto linkedin"]
    iEmployer = hdr["Link puesto empresa"]

    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        tid = r[iTID]
        if tid in (None, ""):
            continue
        estatus = (str(r[iEst]).strip() if r[iEst] is not None else "")
        next_action = (str(r[iNA]).strip() if r[iNA] is not None else "")
        # --- selector ---
        # Primary: the new-triage queue (Saved + Triage). Optionally ALSO select
        # rows whose Estatus is in --include-statuses (e.g. In-progress), for an
        # assess-only refresh; those carry estatus_existing so the scorer's
        # no-downgrade guard preserves their lifecycle.
        is_queue = (estatus == "Saved" and next_action == "Triage")
        is_extra = estatus in include_statuses
        if not (is_queue or is_extra):
            continue
        assess_only = estatus.lower() in ADVANCED

        jd_rel = r[iJD] if r[iJD] not in (None, "") else None
        jd_abs = None
        missing_jd = True
        if jd_rel:
            jd_abs = os.path.join(PROJECT_ROOT, str(jd_rel))
            missing_jd = not os.path.exists(jd_abs)

        linkedin_url = r[iLinkedIn]
        employer_url = r[iEmployer]
        rows.append({
            "tracker_id": str(tid),
            "puesto": r[iPue],
            "empresa": r[iEmp],
            "pais": r[iPais],
            "track_existing": r[iTrack],
            "linkedin_url": linkedin_url,
            "employer_url": employer_url,
            "job_url": employer_url or linkedin_url,
            "estatus_existing": estatus,
            "assess_only": assess_only,
            "jd_file": jd_rel,
            "jd_abs": jd_abs,
            "missing_jd": missing_jd,
            # Preserve existing LinkedIn bindings; direct-source rows leave
            # that column blank and bind evidence to the employer URL.
            "eligibility_evidence": eligibility_evidence(str(tid), jd_abs, linkedin_url or employer_url),
            "judgment": json.loads(json.dumps(JUDGMENT_TEMPLATE)),
        })

    selector = "Estatus=Saved AND Next Action=Triage"
    if include_statuses:
        selector += f"  OR Estatus in {sorted(include_statuses)} (assess-only)"
    payload = {
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "tracker": os.path.abspath(args.tracker),
        "selector": selector,
        "project_root": PROJECT_ROOT,
        "count": len(rows),
        "rows": rows,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    n_missing = sum(1 for x in rows if x["missing_jd"])
    n_assess = sum(1 for x in rows if x["assess_only"])
    print(f"build_worklist: {len(rows)} rows need triage "
          f"({n_missing} MISSING-JD, {n_assess} assess-only) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit("Use scripts/sync_jobs.py with an explicit --project-root and --profile")
