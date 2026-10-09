#!/usr/bin/env python3
"""Generate a dated triage audit report.

STEP 5 (final) of the chain. Reads the results JSON from score_triage.py and the
filled worklist (for identity and rationale fields) and writes a Markdown report:

  header (framework + source) -> batch summary table by verdict ->
  discarded-review table -> track distribution -> per-role sections ->
  self-check -> tracker confirmation.

The run date comes from the system date at runtime (never hardcoded), and the
output path / Triage Batch pointer use the FULL project-relative convention.

Usage:
    gen_report.py --worklist /tmp/triage_worklist_YYYY-MM-DD.json \
                  --results  /tmp/triage_results_YYYY-MM-DD.json \
                  [--out <unique-report-path>] \
                  [--project-root <abs path>]
"""
import argparse
import datetime as _dt
import json
import os
import sys

PROJECT_ROOT = os.environ.get("SYNC_JOBS_ROOT", "")
VERDICT_ORDER = ["Pursue", "Maybe", "Discarded", "Saved"]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from private_files import publish_private_file  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def md_cell(value):
    """Render a single-line Markdown table cell without changing its meaning."""
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def value_text(value):
    """Keep meaningful zero/false values visible and distinguish blanks."""
    if value is None:
        return "NOT RECORDED"
    if isinstance(value, str) and not value.strip():
        return "(blank)"
    return str(value)


def cell_field(cells, key, label):
    if key not in cells:
        return None
    return f"**{label}:** {md_cell(value_text(cells[key]))}"


def main(argv=None):
    today = _dt.date.today().isoformat()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worklist", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--project-root", default=PROJECT_ROOT)
    ap.add_argument("--out", default=None,
                    help="new output Markdown path (default: results report_batch path)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.project_root)
    wl = load(args.worklist)
    rs = load(args.results)
    results = rs.get("results", {})
    work_rows = wl.get("rows", [])
    if not isinstance(results, dict) or not isinstance(work_rows, list):
        raise SystemExit("ERROR: worklist rows and result records must be objects")
    work_ids = [row.get("tracker_id") for row in work_rows]
    if len(set(work_ids)) != len(work_ids) or set(work_ids) != set(results):
        raise SystemExit("ERROR: worklist/result IDs differ or contain duplicates")
    by_id = {row["tracker_id"]: row for row in work_rows}

    # A Discarded verdict creates an owner-review obligation. The detailed
    # framework trace remains in the per-role section, but the review table must
    # use a direct, plain-English reason and the exact posting URL. Fail closed:
    # do not emit a cleanup-ready report with either field missing.
    discarded_review = []
    for tid, res in results.items():
        if (res.get("verdict") != "Discarded" or res.get("assess_only")
                or res.get("missing_jd") or res.get("held") is True):
            continue
        row = by_id.get(tid, {})
        judgment = row.get("judgment", {}) or {}
        url = str(row.get("job_url") or row.get("employer_url") or
                  row.get("linkedin_url") or "").strip()
        reason = str(judgment.get("discard_reason_plain_english") or "").strip()
        if not url:
            raise SystemExit(
                f"ERROR: discarded review missing job posting URL for {tid}"
            )
        if not reason:
            raise SystemExit(
                f"ERROR: discarded review missing plain-English reason for {tid}; "
                "fill judgment.discard_reason_plain_english"
            )
        discarded_review.append((tid, row, url, reason))

    # ----- aggregate -----
    verdict_counts = {v: 0 for v in VERDICT_ORDER}
    track_counts = {}
    lane_counts = {}
    for tid, res in results.items():
        verdict_counts[res["verdict"]] = verdict_counts.get(res["verdict"], 0) + 1
        row = by_id[tid]
        cells = res.get("cells", {}) or {}
        tr = (row.get("judgment", {}) or {}).get("track")
        if tr is None:
            tr = cells.get("Track", "—")
        track_counts[tr] = track_counts.get(tr, 0) + 1
        if "Lane" in cells:
            lane = value_text(cells["Lane"])
            lane_counts[lane] = lane_counts.get(lane, 0) + 1

    L = []
    L.append(f"# Triage — New Saved Postings — {today}")
    L.append("")
    profile = rs.get("profile") or {}
    if profile:
        L.append("**Selected profile:** "
                 f"{md_cell(profile.get('id') or 'NOT RECORDED')} "
                 f"version {md_cell(profile.get('version') or 'NOT RECORDED')}; "
                 f"policy SHA-256 `{md_cell(profile.get('policy_sha256') or 'NOT RECORDED')}`.")
    else:
        L.append("**Selected profile:** legacy result without profile/hash metadata.")
    L.append("**Framework:** the selected profile policy supplied the recorded verdict "
             "and tracker fields. Profile policy remains installation-local.")
    L.append(f"**Source worklist:** `{os.path.basename(args.worklist)}` "
             f"(selector: {wl.get('selector')}).")
    L.append(f"**Rows in batch:** {len(results)}.")
    L.append("**Write mode:** Selected tracker, `Jobs` sheet, keyed by Tracker ID.")
    L.append("")
    L.append("## Batch summary")
    L.append("")
    L.append("| Verdict | Count |")
    L.append("|---|---|")
    for v in VERDICT_ORDER:
        if verdict_counts.get(v):
            L.append(f"| **{v}** | {verdict_counts[v]} |")
    L.append("")
    if lane_counts:
        L.append("**Lane distribution:** " +
                 (", ".join(f"{k}: {v}" for k, v in sorted(lane_counts.items())) or "—") + ".")
    L.append("**Legacy track distribution:** " +
             (", ".join(f"{k}: {v}" for k, v in sorted(track_counts.items())) or "—") + ".")
    L.append("")

    if discarded_review:
        L.append("## Discarded review")
        L.append("")
        L.append("**Review status:** Pending owner review. This table is evidence for a "
                 "decision; it does not authorize changing LinkedIn saved-job state.")
        L.append("")
        L.append("| Job posting | Job ID | Position | Company | Why discarded |")
        L.append("|---|---|---|---|---|")
        for tid, row, url, reason in sorted(discarded_review):
            L.append(
                f"| [Open posting]({url}) | `{md_cell(tid)}` | "
                f"{md_cell(row.get('puesto') or 'NOT STATED ON SOURCE')} | "
                f"{md_cell(row.get('empresa') or 'NOT STATED ON SOURCE')} | "
                f"{md_cell(reason)} |"
            )
        L.append("")
        L.append("Owner outcomes are recorded separately as: confirm discard; keep/reclassify; "
                 "or re-triage for missing or changed evidence. Only an explicit cleanup approval "
                 "authorizes unsaving confirmed discards on LinkedIn.")
        L.append("")

    L.append("---")
    L.append("")

    # ----- per-role sections, grouped by verdict in canonical order -----
    for v in VERDICT_ORDER:
        ids = [tid for tid, r in results.items() if r["verdict"] == v]
        if not ids:
            continue
        for tid in sorted(ids):
            res = results[tid]
            row = by_id.get(tid, {})
            j = row.get("judgment", {}) or {}
            cells = res.get("cells", {})
            puesto = row.get("puesto") or "(unknown role)"
            empresa = row.get("empresa") or "(unknown company)"
            L.append(f"#### {empresa} — {puesto}  ·  `{tid}`")
            L.append(f"- **File:** `{row.get('jd_file') or '(missing JD)'}`")
            L.append(f"- **Location / Pais:** {row.get('pais') or '—'}")
            v5_fields = [
                cell_field(cells, "Lane", "Lane"),
                cell_field(cells, "Market Tier", "Market tier"),
                cell_field(cells, "Eligibility", "Eligibility"),
                cell_field(cells, "Priority Score", "Priority score"),
                cell_field(cells, "Match", "Trial match"),
            ]
            v5_fields = [field for field in v5_fields if field is not None]
            if v5_fields:
                L.append("- " + " · ".join(v5_fields))

            legacy_fields = []
            track = j.get("track")
            if track is None and "Track" in cells:
                track = cells["Track"]
            if track is not None:
                legacy_fields.append(f"**Legacy track:** {md_cell(value_text(track))}")
            fit_score = j.get("raw_fit_score")
            if fit_score is None and "Fit Score" in cells:
                fit_score = cells["Fit Score"]
            if fit_score is not None or "Fit Score" in cells:
                label = "Legacy fit score (reference)" if v5_fields else "Fit score"
                legacy_fields.append(f"**{label}:** {md_cell(value_text(fit_score))}")
            if "Priority" in cells:
                label = "Legacy priority (reference)" if v5_fields else "Priority"
                legacy_fields.append(f"**{label}:** {md_cell(value_text(cells['Priority']))}")
            legacy = res.get("legacy") or {}
            if "verdict" in legacy:
                legacy_fields.append(f"**Legacy verdict (reference):** "
                                     f"{md_cell(value_text(legacy['verdict']))}")
            if legacy_fields:
                L.append("- " + " · ".join(legacy_fields))
            if res.get("band") is not None:
                L.append(f"- **Band:** {md_cell(value_text(res['band']))}")
            if res.get("assess_only"):
                L.append("- **Lifecycle:** assess-only; the existing tracker lifecycle is preserved.")
            if res.get("missing_jd"):
                L.append("- **Triage state:** held because the job description or required evidence is missing.")
            if res.get("held") is True:
                L.append("- **Triage state:** held by the selected profile.")
            if j.get("uplifts"):
                L.append(f"- **Why-pursue uplifts ({j.get('uplift_count')}):** "
                         + "; ".join(str(u) for u in j['uplifts']))
            sp = cell_field(cells, "Sponsor Status", "Sponsor Status")
            if sp:
                L.append(f"- {sp}")
            if j.get("triage_summary"):
                L.append(f"- **Triage Summary:** {j['triage_summary']}")
            if j.get("decision_driver"):
                L.append(f"- **Decision Driver:** {j['decision_driver']}")
            if j.get("primary_risk"):
                L.append(f"- **Primary Risk / Blocker:** {j['primary_risk']}")
            if res.get("reasons"):
                L.append("- **Gate/demoter trace:**")
                for rsn in res["reasons"]:
                    L.append(f"    - {rsn}")
            if res.get("flags"):
                L.append("- **Flags:** " + "; ".join(res["flags"]))
            next_action = cells.get("Next Action", "—")
            L.append(f"- **Next Action:** {md_cell(value_text(next_action))}")
            L.append(f"- **Verdict:** **{res['verdict'].upper()}** · "
                     f"Estatus **{md_cell(value_text(cells.get('Estatus', row.get('estatus_existing') or 'Saved')))}**")
            L.append("")

    # ----- self-check -----
    L.append("---")
    L.append("")
    L.append("### Self-check")
    held_ids = [tid for tid, result in results.items()
                if result.get("missing_jd") or result.get("assess_only")
                or result.get("held") is True]
    held = len(held_ids)
    triaged = len(results) - held
    L.append(f"- Rows in worklist: {len(results)}; completed triage: {triaged}; "
             f"held or assess-only: {held}.")
    if held_ids:
        L.append("- Held/assess-only rows retained in this report: "
                 + ", ".join(f"`{md_cell(tid)}`" for tid in sorted(held_ids)) + ".")
    L.append("- Verdict consistency is enforced by recomputing the selected "
             "profile policy before any tracker write.")
    allflags = [f"{t}: {fl}" for t, r in results.items() for fl in r.get("flags", [])]
    if allflags:
        L.append("- Flags raised:")
        for fl in allflags:
            L.append(f"    - {fl}")
    L.append("")
    L.append("### Tracker update confirmation")
    L.append(f"- Writer: `write_tracker.py` (backup-first; matched by Tracker ID; "
             f"header-name writes; formula-safe; idempotent).")
    L.append(f"- Triage Batch pointer written to rows: `{rs.get('report_batch')}`.")
    L.append("")

    if args.out:
        out = args.out
    elif rs.get("report_batch"):
        out = rs["report_batch"]
    else:
        stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
        out = os.path.join("JobPostings", "_meta", f"triage_{stamp}.md")
    if not os.path.isabs(out):
        out = os.path.join(root, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        publish_private_file(out, "\n".join(L))
    except FileExistsError as exc:
        raise SystemExit(
            f"ERROR: report output already exists; choose a new --out path or score a new batch. {exc}"
        )
    rel = os.path.relpath(out, root)
    print(f"gen_report: wrote {out}")
    print(f"  (project-relative: {rel})")
    return 0


if __name__ == "__main__":
    raise SystemExit("Use scripts/sync_jobs.py with an explicit --project-root and --profile")

    raise SystemExit(main())
