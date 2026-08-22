#!/usr/bin/env python3
"""Prepare or attach a separate hash-bound V3 independent-review record."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHECK_REFS = {
    "RESOURCE_COVERAGE": ["search.queries_run"],
    "ROUTE_HONESTY": ["recipient", "search.literal_seat_result"],
    "CURRENT_ROLE": ["search.authenticated_currentness", "recipient.currentness_sources"],
    "HOOK_ATTRIBUTION": ["hook.evidence_binding", "hook_search.intents"],
    "CHANNEL_SEPARATION": ["channel", "capabilities"],
    "COLLISION_LIFECYCLE": ["guards.receipts", "disconfirmers"],
}


def validator_module():
    path = ROOT / "scripts" / "validate_dossier.py"
    spec = importlib.util.spec_from_file_location("boss_hunt_review_validator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepare(dossier: dict, reviewer_id: str) -> dict:
    if reviewer_id == dossier.get("researcher_id"):
        raise ValueError("reviewer_id must differ from researcher_id")
    validator = validator_module()
    return {"review_schema": "BossHuntIndependentReviewV2", "reviewer_id": reviewer_id,
            "review_subject_sha256": validator.review_subject_hash(dossier), "verdict": "PENDING",
            "checks": [{"name": name, "verdict": "PENDING", "evidence_refs": refs} for name, refs in CHECK_REFS.items()],
            "reviewed_at": None, "note": "Independent reviewer must inspect the frozen subject and replace PENDING values."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("dossier", type=Path)
    prepare_parser.add_argument("--reviewer-id", required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    bind_parser = sub.add_parser("bind-pending")
    bind_parser.add_argument("dossier", type=Path)
    bind_parser.add_argument("review", type=Path)
    bind_parser.add_argument("--output", type=Path, required=True)
    attach_parser = sub.add_parser("attach")
    attach_parser.add_argument("dossier", type=Path)
    attach_parser.add_argument("review", type=Path)
    attach_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dossier = json.loads(args.dossier.read_text(encoding="utf-8"))
    if args.command == "prepare":
        record = prepare(dossier, args.reviewer_id)
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"REVIEW_REQUEST: {args.output}")
        return 0
    review = json.loads(args.review.read_text(encoding="utf-8"))
    validator = validator_module()
    if args.command == "bind-pending":
        if review.get("verdict") != "PENDING" or review.get("reviewed_at") is not None:
            raise ValueError("bind-pending requires a PENDING review with reviewed_at=null")
        if review.get("review_subject_sha256") != validator.review_subject_hash(dossier):
            raise ValueError("review record hash does not match the dossier subject")
        if review.get("reviewer_id") == dossier.get("researcher_id"):
            raise ValueError("reviewer must differ from researcher")
        dossier["quality_review"] = review
        args.output.write_text(json.dumps(dossier, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"REVIEW_PENDING_BOUND: {args.output}")
        return 0
    if review.get("verdict") == "PENDING":
        raise ValueError("review record is still PENDING; obtain a completed independent review before attach")
    if review.get("review_subject_sha256") != validator.review_subject_hash(dossier):
        raise ValueError("review record hash does not match the dossier subject")
    if review.get("reviewer_id") == dossier.get("researcher_id"):
        raise ValueError("reviewer must differ from researcher")
    dossier["quality_review"] = review
    args.output.write_text(json.dumps(dossier, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"REVIEW_ATTACHED: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
