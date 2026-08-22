"""Synthetic V3 behavioral fixtures; no real people, services, or identifiers."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def base() -> dict[str, Any]:
    return json.loads((ROOT / "evals" / "fixtures" / "valid_dossier.json").read_text(encoding="utf-8"))


def rebind_review(dossier: dict[str, Any], validator: Any) -> dict[str, Any]:
    dossier["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(dossier)
    return dossier


def mark_proof_not_evaluated(dossier: dict[str, Any], reason: str) -> None:
    dossier["candidate_proof"] = {"claim": None, "source_ref": None, "source_kind": None,
                                  "evidence_sha256": None, "run_id": dossier["run_id"],
                                  "support_state": "NOT_EVALUATED", "not_evaluated_reason": reason}


def literal_seat_hit(validator: Any) -> dict[str, Any]:
    return rebind_review(base(), validator)


def literal_seat_miss(validator: Any) -> dict[str, Any]:
    dossier = base()
    dossier["search"]["literal_seat_result"] = "MISS"
    dossier["recipient"].update({"route_class": "SPONSOR_AUTHORITY", "requisition_linkage": "ADJACENT"})
    dossier["decision"].update({"readiness": "OWNER_DECISION", "permitted_response": "ROUTE", "requires_owner_decision": True,
                                "reason": "Literal seat missed; sponsor posture requires owner judgment."})
    return rebind_review(dossier, validator)


def recruiter_route(validator: Any) -> dict[str, Any]:
    dossier = base()
    dossier["search"]["literal_seat_result"] = "MISS"
    dossier["recipient"].update({"current_title": "Senior Recruiter", "route_class": "RECRUITER_JOB_POSTER", "requisition_linkage": "EXPLICIT"})
    dossier["decision"].update({"readiness": "DRAFT_READY_VERIFY_CHANNEL", "permitted_response": "RECRUITER_ASSESSMENT",
                                "requires_owner_decision": False, "reason": "Synthetic current recruiter is explicitly linked to the requisition."})
    return rebind_review(dossier, validator)


def generic_fallback(validator: Any) -> dict[str, Any]:
    dossier = base()
    run_id = dossier["run_id"]
    when = "2026-08-21T09:25:00-06:00"

    def intent(intent_id: str, family: str, subject: str, claim: str, surface_family: str,
               outcome: str, result_url: str | None, content_sha256: str | None, selected: bool) -> dict[str, Any]:
        signature = {"subject": subject, "claim": claim, "surface_family": surface_family}
        return {"intent_id": intent_id, "family": family, "signature": signature,
                "canonical_fingerprint": validator.intent_fingerprint(signature), "hypothesis": claim,
                "surface": surface_family, "query_or_action": f"test {claim}", "observed_at": when,
                "run_id": run_id, "outcome": outcome, "result_url": result_url,
                "content_sha256": content_sha256, "supports_selected_hook": selected}

    artifact = "https://example.com/insights/company-operating-model"
    content_hash = "sha256:efefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefef"
    dossier["hook"].update({"text": "Example Company published a dated operating-model mandate.", "attribution": "COMPANY",
                             "artifact_url": artifact, "support_excerpt": "The company is changing its operating model.",
                             "evidence_binding": {"intent_id": "company-mandate", "result_url": artifact,
                                                  "content_sha256": content_hash, "run_id": run_id}})
    dossier["hook_search"] = {"policy_version": "BossHuntHookSearchV2", "fallback_kind": "GENERIC_COMPANY", "coverage_claim": "COMPLETE", "intents": [
        intent("authored-1", "RECIPIENT_AUTHORED", "jordan example", "authored operating model article", "public articles", "MISS", None, None, False),
        intent("authored-2", "RECIPIENT_AUTHORED", "jordan example", "authored product design post", "professional posts", "MISS", None, None, False),
        intent("speaking-1", "RECIPIENT_SPEAKING", "jordan example", "operating model talk or interview", "events and podcasts", "MISS", None, None, False),
        intent("employer-attribution-1", "EMPLOYER_PERSON_ATTRIBUTION", "jordan example", "employer attributed statement", "employer newsroom", "MISS", None, None, False),
        intent("company-mandate", "COMPANY_MANDATE", "example company", "dated operating model mandate", "employer insights", "HIT", artifact, content_hash, True),
        intent("jd-context", "JD_CONTEXT", "director product design role", "exact role objective", "job description", "HIT", "https://careers.example.com/jobs/director-product-design", "sha256:1212121212121212121212121212121212121212121212121212121212121212", False),
        intent("refute-company", "ATTRIBUTION_REFUTATION", "example company", "refute mandate freshness and attribution", "exact artifact readback", "HIT", artifact, content_hash, False)
    ]}
    return rebind_review(dossier, validator)


def stale_person(validator: Any) -> dict[str, Any]:
    dossier = base()
    dossier["guards"]["overall_state"] = "BLOCKED"
    for receipt in dossier["guards"]["receipts"]:
        if receipt["guard"] == "DISCONFIRMATION":
            receipt["result"] = "TRIGGERED"
    dossier["search"]["authenticated_currentness"]["result"] = "MISMATCH"
    dossier["recipient"].update({"route_class": "DISCONFIRMED", "requisition_linkage": "NONE"})
    dossier["channel"] = {"kind": "NONE", "address": None, "state": "UNAVAILABLE", "basis": "NONE", "source_url": None,
                          "hunter_usage": {"account_snapshot_at": None, "account_receipt_ref": None, "method": "NONE", "result": "NOT_USED", "domain_search_limit": None, "discovery_connector_calls": 0, "search_credits_used": 0, "verification_credits_used": 0}}
    dossier["decision"].update({"readiness": "BLOCKED", "permitted_response": "NONE", "requires_owner_decision": False,
                                "reason": "Currentness evidence disconfirms the person."})
    mark_proof_not_evaluated(dossier, "Disconfirmation guard stopped the workflow before candidate-proof evaluation.")
    return rebind_review(dossier, validator)


def company_collision(validator: Any) -> dict[str, Any]:
    dossier = base()
    dossier["guards"]["overall_state"] = "CONFLICT"
    for receipt in dossier["guards"]["receipts"]:
        if receipt["guard"] == "COMPANY_COLLISION":
            receipt["result"] = "TRIGGERED"
    dossier["decision"].update({"readiness": "BLOCKED", "requires_owner_decision": False,
                                "reason": "Company-level route collision must be reconciled before promotion."})
    mark_proof_not_evaluated(dossier, "Company-collision guard stopped the workflow before candidate-proof evaluation.")
    return rebind_review(dossier, validator)


NAMED_FIXTURES = {
    "valid_literal_seat_hit": literal_seat_hit,
    "literal_seat_miss": literal_seat_miss,
    "generic_fallback": generic_fallback,
    "recruiter_route": recruiter_route,
    "stale_person": stale_person,
    "company_collision": company_collision,
}
