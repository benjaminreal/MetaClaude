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
                  [--out JobPostings/_meta/triage_YYYY-MM-DD.md] \
                  [--project-root <abs path>]
"""
import argparse
import datetime as _dt
import json
import os

PROJECT_ROOT = os.environ.get("SYNC_JOBS_ROOT", "")
VERDICT_ORDER = ["Pursue", "Maybe", "Discarded", "Saved"]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def md_cell(value):
    """Render a single-line Markdown table cell without changing its meaning."""
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def main(argv=None):
    today = _dt.date.today().isoformat()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worklist", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--project-root", default=PROJECT_ROOT)
    ap.add_argument("--out", default=None,
                    help="output md path (default: <root>/JobPostings/_meta/triage_<today>.md)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.project_root)
    out = args.out or os.path.join(root, "JobPostings", "_meta", f"triage_{today}.md")
    if not os.path.isabs(out):
        out = os.path.join(root, out)

    wl = load(args.worklist)
    rs = load(args.results)
    results = rs.get("results", {})
    by_id = {r["tracker_id"]: r for r in wl.get("rows", [])}

    # A Discarded verdict creates an owner-review obligation. The detailed
    # framework trace remains in the per-role section, but the review table must
    # use a direct, plain-English reason and the exact posting URL. Fail closed:
    # do not emit a cleanup-ready report with either field missing.
    discarded_review = []
    for tid, res in results.items():
        if res.get("verdict") != "Discarded":
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
    for tid, res in results.items():
        verdict_counts[res["verdict"]] = verdict_counts.get(res["verdict"], 0) + 1
        tr = (by_id.get(tid, {}).get("judgment", {}) or {}).get("track") \
            or res.get("cells", {}).get("Track") or "—"
        track_counts[tr] = track_counts.get(tr, 0) + 1

    L = []
    L.append(f"# Triage — New Saved Postings — {today}")
    L.append("")
    L.append("**Framework:** the explicitly selected profile and its hash-bound "
             "policy. Candidate-specific rules remain in the private profile overlay.")
    L.append(f"**Source worklist:** `{os.path.basename(args.worklist)}` "
             f"(selector: {wl.get('selector')}).")
    L.append(f"**Rows triaged:** {len(results)}.")
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
    L.append("**Track distribution:** " +
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
            L.append(f"- **Track:** {j.get('track') or cells.get('Track') or '—'}")
            score = j.get("raw_fit_score")
            L.append(f"- **Best-fit score:** {score if score is not None else 'N/A'}"
                     f"  ·  **Band:** {res.get('band')}")
            if j.get("uplifts"):
                L.append(f"- **Why-pursue uplifts ({j.get('uplift_count')}):** "
                         + "; ".join(str(u) for u in j['uplifts']))
            sp = cells.get("Sponsor Status")
            if sp:
                L.append(f"- **Sponsor Status:** {sp}")
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
            L.append(f"- **Next Action:** {cells.get('Next Action') or '—'}")
            L.append(f"- **Verdict:** **{res['verdict'].upper()}** · "
                     f"Estatus **{cells.get('Estatus', row.get('estatus_existing') or 'Saved')}**")
            L.append("")

    # ----- self-check -----
    L.append("---")
    L.append("")
    L.append("### Self-check")
    triaged = sum(1 for r in results.values() if not r.get("missing_jd"))
    held = sum(1 for r in results.values() if r.get("missing_jd"))
    L.append(f"- Rows in worklist: {len(results)}; completed triage: {triaged}; "
             f"held for missing JD/evidence: {held}.")
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

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    rel = os.path.relpath(out, root)
    print(f"gen_report: wrote {out}")
    print(f"  (project-relative: {rel})")
    return 0


if __name__ == "__main__":
    raise SystemExit("Use scripts/sync_jobs.py with an explicit --project-root and --profile")

    raise SystemExit(main())
