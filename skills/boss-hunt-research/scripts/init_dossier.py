#!/usr/bin/env python3
"""Initialize an explicitly incomplete V3 dossier from BossHuntTargetV2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_search_plan import validate_target


CHECKS = ["RESOURCE_COVERAGE", "ROUTE_HONESTY", "CURRENT_ROLE", "HOOK_ATTRIBUTION", "CHANNEL_SEPARATION", "COLLISION_LIFECYCLE"]


def initialize(target: dict, run_id: str, researcher_id: str) -> dict:
    validate_target(target)
    role_keys = ["target_id", "source_tracker_id", "intake_mode", "company", "company_domain", "role_title", "job_url", "jd_source", "posting_status", "geography", "function", "explicit_boss_titles", "authority_sources", "owner_scope"]
    limitations = [{"capability": name, "surface": name, "state": receipt["state"], "reason": "REPLACE_WITH_OBSERVED_LIMITATION", "observed_at": receipt["observed_at"], "receipt_ref": receipt["receipt_ref"]}
                   for name, receipt in target["capabilities"].items() if receipt["state"] != "AVAILABLE"]
    return {
        "schema_version": "BossHuntResearchDossierV3", "run_id": run_id, "researcher_id": researcher_id,
        "role": {key: target.get(key) for key in role_keys}, "capabilities": target["capabilities"],
        "guards": {"overall_state": "UNKNOWN", "receipts": []},
        "search": {"reporting_hypotheses": target["reporting_hypotheses"], "literal_seat_result": "BLOCKED", "queries_run": [],
                   "authenticated_currentness": {"capability_receipt_ref": target["capabilities"]["authenticated_profile"]["receipt_ref"], "surface": "REPLACE_WITH_OBSERVED_SURFACE", "identity_binding": {"recipient_name": "REPLACE_WITH_RECIPIENT", "profile_url": "https://invalid.example/replace", "company": target["company"], "target_id": target["target_id"]}, "observed_at": target["capabilities"]["authenticated_profile"]["observed_at"], "fresh_until": target["capabilities"]["authenticated_profile"]["observed_at"], "result": "BLOCKED", "evidence_ref": "REPLACE_WITH_EVIDENCE_REF", "evidence_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000", "run_id": run_id}},
        "recipient": {"name": None, "current_title": None, "route_class": "UNRESOLVED", "requisition_linkage": "NONE", "profile_url": None, "currentness_sources": []},
        "hook": {"text": None, "attribution": "NONE", "artifact_url": None, "artifact_date": None, "observed_at": None, "support_excerpt": None, "support_state": "ABSENT", "run_id": run_id, "evidence_binding": None},
        "hook_search": {"policy_version": "BossHuntHookSearchV2", "intents": [], "fallback_kind": "NONE", "coverage_claim": "INCOMPLETE"},
        "candidate_proof": {"claim": None, "source_ref": None, "source_kind": None, "evidence_sha256": None, "run_id": run_id, "support_state": "NOT_EVALUATED", "not_evaluated_reason": "Candidate proof has not been reached in this initialized dossier."},
        "channel": {"kind": "NONE", "address": None, "state": "UNAVAILABLE", "basis": "NONE", "source_url": None, "hunter_usage": {"account_snapshot_at": None, "account_receipt_ref": None, "method": "NONE", "result": "NOT_USED", "domain_search_limit": None, "discovery_connector_calls": 0, "search_credits_used": 0, "verification_credits_used": 0}},
        "decision": {"readiness": "BLOCKED", "permitted_response": "NONE", "requires_owner_decision": False, "reason": "Incomplete initialized dossier; replace every REPLACE field and collect required evidence.", "next_bounded_search": None},
        "disconfirmers": [],
        "quality_review": {"review_schema": "BossHuntIndependentReviewV2", "reviewer_id": "PENDING_INDEPENDENT_REVIEWER", "review_subject_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000", "verdict": "PENDING", "checks": [{"name": name, "verdict": "PENDING", "evidence_refs": ["PENDING"]} for name in CHECKS], "reviewed_at": None, "note": "Generate with review_record.py after evidence capture."},
        "query_access_limitations": limitations,
        "owner_summary": {"route_summary": "UNRESOLVED", "weakest_assumption": "Evidence capture incomplete.", "capability_limits": [item["reason"] for item in limitations] or ["No capability limitation recorded."], "next_action_or_stop": "Follow references/authoring-guide.md.", "authority_note": "Research only; no external action authority."},
        "notes": "Initializer output is deliberately non-promotable until every placeholder is replaced and review is attached."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--researcher-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = json.loads(args.target.read_text(encoding="utf-8"))
    dossier = initialize(target, args.run_id, args.researcher_id)
    args.output.write_text(json.dumps(dossier, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"INITIALIZED_INCOMPLETE: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
