#!/usr/bin/env python3
"""Synthetic explicit-verdict policy used only by public package tests.

This file demonstrates the private-profile interface. It is not a recommended
candidate policy and contains no real facts, preferences, targets or scoring
thresholds.
"""
import argparse
import datetime as dt
import json
import os


VERDICTS = {"Pursue", "Maybe", "Discarded", "Saved"}
DEFAULT_ACTIONS = {
    "Pursue": "Review",
    "Maybe": "Hold",
    "Discarded": "Review discard",
    "Saved": "Triage",
}
ADVANCED = {"applied", "in-progress", "interview", "offer"}


def derive(entry, today, batch_path):
    """Return tracker cells from an explicit synthetic judgment."""
    tracker_id = entry["tracker_id"]
    judgment = entry.get("judgment") or {}
    existing_status = str(entry.get("estatus_existing") or "").strip()
    assess_only = bool(entry.get("assess_only")) or existing_status.casefold() in ADVANCED
    flags = []

    if entry.get("missing_jd"):
        cells = {"Triage Batch": batch_path}
        if not assess_only:
            cells["Next Action"] = "Pull JD"
        return {
            "tracker_id": tracker_id,
            "verdict": existing_status or "Saved",
            "band": None,
            "demoted": False,
            "reasons": ["JD file missing; no synthetic verdict applied"],
            "missing_jd": True,
            "flags": flags,
            "cells": cells,
        }

    verdict = str(judgment.get("verdict") or "").strip().title()
    reasons = []
    if judgment.get("failed_hard_gate") is True:
        verdict = "Discarded"
        reasons.append("Explicit synthetic hard gate")
    if judgment.get("fatal_red_flag") is True:
        verdict = "Discarded"
        reasons.append("Explicit synthetic fatal flag")
    if verdict not in VERDICTS:
        return {
            "tracker_id": tracker_id,
            "verdict": "Saved",
            "band": None,
            "demoted": False,
            "reasons": ["Explicit verdict missing from synthetic judgment"],
            "missing_jd": False,
            "flags": ["SYNTHETIC_PROFILE_REQUIRES_EXPLICIT_VERDICT"],
            "cells": {},
        }

    cells = {"Triage Date": today, "Triage Batch": batch_path}
    if not assess_only:
        cells["Estatus"] = verdict
        cells["Next Action"] = judgment.get("next_action") or DEFAULT_ACTIONS[verdict]
    else:
        flags.append("ASSESS_ONLY_LIFECYCLE_PRESERVED")
    if judgment.get("track"):
        cells["Track"] = judgment["track"]
    if isinstance(judgment.get("raw_fit_score"), (int, float)):
        cells["Fit Score"] = judgment["raw_fit_score"]
    for source_key, header in (
        ("triage_summary", "Triage Summary"),
        ("decision_driver", "Decision Driver"),
        ("primary_risk", "Primary Risk / Blocker"),
    ):
        if judgment.get(source_key):
            cells[header] = judgment[source_key]

    comment = judgment.get("comment_note") or f"Synthetic example: {verdict}"
    return {
        "tracker_id": tracker_id,
        "verdict": verdict,
        "band": "explicit-synthetic",
        "demoted": False,
        "reasons": reasons,
        "missing_jd": False,
        "flags": flags,
        "cells": cells,
        "comment_note": comment,
    }


def main(argv=None):
    today = dt.date.today().isoformat()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worklist", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--report-name")
    args = parser.parse_args(argv)

    with open(args.worklist, encoding="utf-8") as handle:
        worklist = json.load(handle)
    batch_path = args.report_name or f"JobPostings/_meta/triage_{today}.md"
    results = {
        entry["tracker_id"]: derive(entry, today, batch_path)
        for entry in worklist.get("rows", [])
    }
    payload = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "framework": "synthetic-explicit-verdict-example",
        "report_batch": batch_path,
        "source_worklist": os.path.abspath(args.worklist),
        "results": results,
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    with open(args.preview, "w", encoding="utf-8") as handle:
        for tracker_id, result in results.items():
            handle.write(f"{tracker_id} {result['verdict']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit("Use the sync-jobs launcher with --profile example")
