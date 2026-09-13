#!/usr/bin/env python3
"""write_tracker.py — the safe writer for triage results.

STEP 4 of the chain. Takes the results JSON from score_triage.py and writes the
triage cells into the live tracker. Safety contract (all enforced here):

  1. BACKUP FIRST — copy the tracker to a timestamped /tmp backup before any
     mutation. Nothing is written until the backup exists.
  2. Load with FORMULAS INTACT (NOT data_only) so we never replace a formula
     with its cached value when saving.
  3. Match the target row by `Tracker ID` (stable key). Fail loudly on 0 or >1
     matches for a given ID.
  4. Write ONLY the provided cells, located BY HEADER NAME (never by Excel
     letter). Columns not in the results are never touched.
  5. REFUSE to overwrite a formula cell (warn + skip) — protects any future
     computed column.
  6. IDEMPOTENT — if the live cell already equals the target value, skip it. A
     second run with the same results is a no-op (zero changes).
  7. Preserve the JobsTable object and its range.
  8. COMMIT LIVE by default (backup-first). --dry-run writes to a /tmp copy
     instead of the live file and is NOT the default.

`Comentarios` is special-cased: read-modify-write APPEND (never clobber). A
dated, batch-tagged line is appended once; re-running with the same batch tag is
a no-op so existing audit notes are preserved and not duplicated.

Any result may carry an `append` block beside
`cells`. It shares one implementation with apply_bosshunt_delta.py through
`_cell_append.py`, so the two writers no longer diverge:

    {"J-000001": {"cells":  {"Estatus": "Rejected"},
                  "append": {"Next Action": "Also chase the referral."}}}

Appends join with a blank line, are idempotent (a note already present is a
no-op), and are allowed only on Next Action, Triage Summary, Decision Driver,
Primary Risk / Blocker, Key Uplifts. A column in both `cells` and `append`, or
an append onto a controlled column, is a hard error and nothing is saved.
`Comentarios` is NOT in that allowlist: it keeps its batch-tag path, so a
results file cannot drive it through two mechanisms at once. Results files
written before this change are unaffected.

Usage:
    write_tracker.py --results /tmp/triage_results_YYYY-MM-DD.json \
                     --tracker /path/to/jobs.xlsx
    write_tracker.py --results ... --tracker ... --dry-run   # writes a /tmp copy
"""
import argparse
import datetime as _dt
import json
import os
import shutil
import sys
import unicodedata

from pathlib import Path
import hashlib
import tempfile
import openpyxl

SHEET = "Jobs"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cell_append import (SEP_LINE, SEP_PARAGRAPH, AppendError,  # noqa: E402
                          append_value, validate_append_block)

COMMENTS_HEADER = "Comentarios"

# BossHunt state is owned by the dedicated, selector-bound successor pipeline.
# This generic Jobs-sheet writer must never project that state.  Normalize case,
# whitespace, and common hyphen characters so spelling variants cannot bypass
# the boundary.  There is intentionally no override flag or environment escape.
CONTROLLED_BOSSHUNT_TOKEN = "bosshunt"
HYPHEN_CHARS = frozenset("-‐‑‒–—―")

# Free-text Jobs columns that may be appended to via an explicit `append` block.
# Controlled columns (Estatus, dates, IDs, scores, links) are excluded: an
# append would stop them parsing as what they are. `Comentarios` keeps its own
# batch-tag path below and is deliberately NOT listed here, so a results file
# cannot drive it through two mechanisms at once.
APPEND_OK = {"Next Action", "Triage Summary", "Decision Driver",
             "Primary Risk / Blocker", "Key Uplifts"}

# These come from score_triage.py; we additionally allow Comentarios appends.
# write_tracker does not re-derive — it only writes what the results provide.


def header_index(ws):
    return {
        str(cell.value).strip(): idx
        for idx, cell in enumerate(ws[1])
        if cell.value is not None and str(cell.value).strip() != ""
    }


def is_formula(value):
    return isinstance(value, str) and value.startswith("=")


def normalize_controlled_header(header):
    """Return the comparison token used only for controlled-header rejection."""
    text = unicodedata.normalize("NFKC", str(header)).casefold()
    return "".join(char for char in text
                   if not char.isspace() and char not in HYPHEN_CHARS)


def validate_no_bosshunt_writes(results):
    """Reject generic BossHunt writes before backup or workbook access."""
    violations = []
    for tid, result in results.items():
        for block_name in ("cells", "append"):
            block = result.get(block_name, {}) or {}
            if not isinstance(block, dict):
                continue
            for header in block:
                if normalize_controlled_header(header) == CONTROLLED_BOSSHUNT_TOKEN:
                    violations.append(f"{tid}:{block_name}:{header}")
    if violations:
        joined = ", ".join(sorted(violations))
        sys.exit(
            "ERROR: BOSSHUNT_CONTROLLED_FIELD_REJECTED: "
            f"generic Jobs writer cannot mutate Boss-Hunt ({joined}). "
            "Use the dedicated selector-bound successor projection path."
        )


def build_comment_line(today, batch, verdict, note, prefix="Triage v2"):
    """One audit line appended to Comentarios. Carries a stable batch tag so a
    re-run can detect 'already appended' and skip (idempotent append)."""
    tag = f"{prefix} {today} [{os.path.basename(batch)}]"
    bits = [tag]
    if verdict:
        bits.append(f"verdict={verdict}")
    if note:
        bits.append(str(note))
    return tag, ": ".join([bits[0], " ".join(bits[1:])]) if len(bits) > 1 else bits[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", required=True, help="results JSON from score_triage.py")
    ap.add_argument("--tracker", required=True, help="path to the selected tracker")
    ap.add_argument("--dry-run", action="store_true",
                    help="write to a /tmp copy instead of the live tracker (NOT default)")
    ap.add_argument("--backup-dir", default="/tmp", help="directory for the safety backup")
    args = ap.parse_args(argv)

    with open(args.results, encoding="utf-8") as fh:
        data = json.load(fh)
    results = data.get("results", {})
    validate_no_bosshunt_writes(results)

    if not os.path.exists(args.tracker):
        sys.exit(f"ERROR: tracker not found: {args.tracker}")

    initial_sha = hashlib.sha256(Path(args.tracker).read_bytes()).hexdigest()
    batch = data.get("report_batch", "")
    comment_prefix = data.get("comment_prefix", "Triage v2")
    today = _dt.date.today().isoformat()

    # ----- 1. BACKUP FIRST (before any mutation) -----
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    tracker_stem = Path(args.tracker).stem
    backup = os.path.join(args.backup_dir, f"{tracker_stem}.backup_{stamp}.xlsx")
    shutil.copy2(args.tracker, backup)
    print(f"write_tracker: backup -> {backup}")

    # Where do we actually save?  Live by default; /tmp copy on --dry-run.
    if args.dry_run:
        target = os.path.join(args.backup_dir, f"{tracker_stem}.dryrun_{stamp}.xlsx")
        shutil.copy2(args.tracker, target)
        print(f"write_tracker: DRY-RUN — writing to {target} (live tracker untouched)")
    else:
        target = args.tracker

    # ----- 2. Load with formulas intact (NOT data_only) -----
    wb = openpyxl.load_workbook(target)  # keep_vba default False; formulas kept
    if SHEET not in wb.sheetnames:
        sys.exit(f"ERROR: sheet {SHEET!r} not in {wb.sheetnames}")
    ws = wb[SHEET]
    hdr = header_index(ws)
    if "Tracker ID" not in hdr:
        sys.exit("ERROR: 'Tracker ID' header not found — cannot match rows.")
    tid_col0 = hdr["Tracker ID"]

    pre_table_ref = ws.tables["JobsTable"].ref if "JobsTable" in ws.tables else None
    pre_max_row = ws.max_row

    # ----- 3. Build Tracker ID -> row map; fail on dupes -----
    id_to_row = {}
    dupes = []
    for row_cells in ws.iter_rows(min_row=2):
        tid = row_cells[tid_col0].value
        if tid in (None, ""):
            continue
        tid = str(tid)
        if tid in id_to_row:
            dupes.append(tid)
        id_to_row[tid] = row_cells[0].row
    if dupes:
        sys.exit(f"ERROR: duplicate Tracker IDs in tracker: {sorted(set(dupes))}")

    missing = sorted(set(results)-set(id_to_row))
    if missing:
        sys.exit(f"ERROR: result IDs not found in tracker: {missing}; whole batch aborted without save")
    for tid,res in results.items():
        requested=set(res.get('cells',{})) | set(res.get('append',{}) or {})
        missing_headers=requested-set(hdr)
        if missing_headers:sys.exit(f"ERROR: missing target headers {sorted(missing_headers)}; batch aborted")
        for header,value in res.get('cells',{}).items():
            cell=ws.cell(id_to_row[tid],hdr[header]+1)
            if is_formula(cell.value) and cell.value!=value:
                sys.exit(f"ERROR: intended write targets protected formula {tid}/{header}; batch aborted")

    changes = []        # (tid, header, old, new)
    skipped_formula = []  # (tid, header)
    noop = 0
    missing_ids = []

    for tid, res in results.items():
        if tid not in id_to_row:
            missing_ids.append(tid)
            continue
        rownum = id_to_row[tid]
        cells = dict(res.get("cells", {}))
        appends = dict(res.get("append", {}) or {})
        if appends:
            try:
                validate_append_block(tid, cells.keys(), appends.keys(), APPEND_OK)
            except AppendError as exc:
                sys.exit(f"ERROR: {exc} Nothing was saved.")

        # ----- Comentarios: read-modify-write APPEND (never clobber) -----
        # Prefer the explicit per-row note from score_triage; fall back to any
        # Comentarios cell, then to a synthesized note.
        comment_note = (res.get("comment_note")
                        or res.get("cells", {}).get(COMMENTS_HEADER)
                        or _comment_note_from(res))
        if comment_note is not None and COMMENTS_HEADER in hdr:
            cells.pop(COMMENTS_HEADER, None)  # handled specially below
            ccol = hdr[COMMENTS_HEADER] + 1
            cell = ws.cell(row=rownum, column=ccol)
            existing = cell.value
            if is_formula(existing):
                skipped_formula.append((tid, COMMENTS_HEADER))
            else:
                tag, line = build_comment_line(
                    today, batch, res.get("verdict"), comment_note, comment_prefix)
                # Shared append mechanism, with this column's two specialisations:
                # one entry per LINE (not a blank-line-separated block), and
                # dedup on the dated batch TAG rather than the note text, so a
                # re-run with an edited note still refuses to add a second line.
                newval, changed = append_value(
                    existing, line, sep=SEP_LINE, dedup_marker=tag)
                if not changed:
                    noop += 1
                else:
                    changes.append((tid, COMMENTS_HEADER, existing, "<append> " + line))
                    cell.value = newval

        # ----- All other writable cells: header-name, formula-safe, idempotent -----
        for header, value in cells.items():
            if header not in hdr:
                print(f"  WARN {tid}: header {header!r} not in tracker — skipped")
                continue
            col = hdr[header] + 1
            cell = ws.cell(row=rownum, column=col)
            if is_formula(cell.value):
                skipped_formula.append((tid, header))   # rule 5: never clobber a formula
                continue
            if cell.value == value:
                noop += 1                                 # rule 6: idempotent
                continue
            changes.append((tid, header, cell.value, value))
            cell.value = value

        # ----- Explicit `append` block: add without clobbering -----
        for header, addition in appends.items():
            if header not in hdr:
                print(f"  WARN {tid}: header {header!r} not in tracker — skipped")
                continue
            cell = ws.cell(row=rownum, column=hdr[header] + 1)
            if is_formula(cell.value):
                skipped_formula.append((tid, header))
                continue
            newval, changed = append_value(cell.value, addition, sep=SEP_PARAGRAPH)
            if not changed:
                noop += 1
                continue
            changes.append((tid, header, cell.value, "<append> " + str(addition)))
            cell.value = newval

    # ----- 7. Verify structure preserved -----
    post_table_ref = ws.tables["JobsTable"].ref if "JobsTable" in ws.tables else None
    if pre_table_ref != post_table_ref:
        sys.exit(f"ERROR: JobsTable ref changed {pre_table_ref} -> {post_table_ref}; aborting without save.")
    if ws.max_row != pre_max_row:
        print(f"  WARN: max_row changed {pre_max_row} -> {ws.max_row}")

    # ----- 8. Save (live by default; /tmp copy on dry-run) -----
    expected={(tid,header):ws.cell(id_to_row[tid],col+1).value for tid in results for header,col in hdr.items()}
    fd,staged=tempfile.mkstemp(prefix='.sync-jobs-write-',suffix='.xlsx',dir=os.path.dirname(os.path.abspath(target)))
    os.close(fd)
    try:
        wb.save(staged)
        check=openpyxl.load_workbook(staged,data_only=False)
        for (tid,header),value in expected.items():
            actual=check[SHEET].cell(id_to_row[tid],hdr[header]+1).value
            if actual!=value and not (actual is None and value==''):
                raise ValueError(f'Post-save verification failed: {tid}/{header}')
        check.close()
        if hashlib.sha256(Path(args.tracker).read_bytes()).hexdigest()!=initial_sha:
            raise ValueError('Tracker changed during write; staged batch not committed')
        os.replace(staged,target)
    finally:
        if os.path.exists(staged):os.unlink(staged)

    # ----- Per-cell change summary -----
    print(f"write_tracker: {len(changes)} cell change(s), {noop} no-op(s), "
          f"{len(skipped_formula)} formula-skip(s).")
    for tid, header, old, new in changes:
        olds = "<blank>" if old in (None, "") else repr(old)
        print(f"  {tid}  {header}: {olds} -> {new!r}")
    if skipped_formula:
        print("  formula cells skipped (not overwritten):")
        for tid, header in skipped_formula:
            print(f"    {tid}  {header}")
    if missing_ids:
        print("  WARN: result IDs not found in tracker (skipped):", missing_ids)
    print(f"  saved: {target}")
    print(f"  JobsTable ref preserved: {post_table_ref}")
    return 0


def _comment_note_from(res):
    """Fallback Comentarios note when score_triage did not embed one: use the
    verdict + a couple of reasons so the audit trail is non-empty per batch."""
    if res.get("missing_jd"):
        return "JD missing — pulled to triage queue"
    reasons = res.get("reasons") or []
    return reasons[0] if reasons else None


if __name__ == "__main__":
    raise SystemExit("Use scripts/sync_jobs.py with an explicit --project-root and --profile")

    raise SystemExit(main())
