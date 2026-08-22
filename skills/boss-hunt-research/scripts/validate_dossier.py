#!/usr/bin/env python3
"""Dependency-free structural-then-policy validator for BossHuntResearchDossierV3.

V2 records are preserved historical inputs. This validator refuses to reinterpret
them; create a new V3 record from newly observed evidence instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "references" / "bosshunt_dossier_v3.schema.json"
VERSION = "BossHuntResearchDossierV3"
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
REQUIRED_GUARDS = {"NO_BYPASS", "TERMINAL_OUTREACH", "OWNER_CLOSED", "COMPANY_COLLISION", "DISCONFIRMATION"}
REQUIRED_STAGES = {"EMPLOYER_CONTEXT", "LITERAL_SEAT", "REPORTING_ALTERNATIVES", "REQUISITION_AND_SEARCH_OWNER", "ADJACENT_ROUTES", "AUTHENTICATED_CURRENTNESS", "HOOK_ARTIFACT", "EMAIL_DISCOVERY_FIRST_PARTY"}
REQUIRED_REVIEW = {"RESOURCE_COVERAGE", "ROUTE_HONESTY", "CURRENT_ROLE", "HOOK_ATTRIBUTION", "CHANNEL_SEPARATION", "COLLISION_LIFECYCLE"}
PERSON_ROUTES = {"CONFIRMED_HM", "LIKELY_HM", "RECRUITER_JOB_POSTER", "RECRUITER_OWNER_CHECK", "SPONSOR_AUTHORITY", "POTENTIAL_COWORKER", "WARM_CONNECTOR", "APEX_CONTEXT"}
NON_DRAFT_ROUTES = {"APEX_CONTEXT", "NOT_PUBLIC", "NO_SAFE_ROUTE", "DISCONFIRMED", "UNRESOLVED"}
ROUTE_RESPONSES = {
    "CONFIRMED_HM": {"CONVERSATION"}, "LIKELY_HM": {"CONVERSATION", "ROUTE"},
    "RECRUITER_JOB_POSTER": {"RECRUITER_ASSESSMENT", "PROCESS_CLARIFICATION", "ROUTE"},
    "RECRUITER_OWNER_CHECK": {"PROCESS_CLARIFICATION", "ROUTE"},
    "SPONSOR_AUTHORITY": {"ROUTE", "CONVERSATION"},
    "POTENTIAL_COWORKER": {"INFORMATIONAL_GUIDANCE", "ROUTE"},
    "WARM_CONNECTOR": {"INFORMATIONAL_GUIDANCE", "ROUTE"},
    "APEX_CONTEXT": {"ROUTE", "PROCESS_CLARIFICATION"},
    "NOT_PUBLIC": {"NONE"}, "NO_SAFE_ROUTE": {"NONE"}, "DISCONFIRMED": {"NONE"}, "UNRESOLVED": {"NONE"},
}
RECIPIENT_FAMILIES = {"RECIPIENT_AUTHORED", "RECIPIENT_SPEAKING", "EMPLOYER_PERSON_ATTRIBUTION"}


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def review_subject_hash(dossier: Mapping[str, Any]) -> str:
    return sha256_value({key: value for key, value in dossier.items() if key != "quality_review"})


def intent_fingerprint(signature: Mapping[str, Any]) -> str:
    normalized = {key: " ".join(str(signature[key]).lower().split()) for key in ("subject", "claim", "surface_family")}
    return sha256_value(normalized)


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def exact_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and parsed.path not in {"", "/"}


def resolve_ref(schema: Mapping[str, Any], root: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith("#/"):
        return schema
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def type_ok(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(expected, True)


def validate_structure(value: Any, schema: Mapping[str, Any], root: Mapping[str, Any], path: str = "$", issues: list[Issue] | None = None) -> list[Issue]:
    """Small Draft-2020-12 subset used by the bundled schemas."""
    if issues is None:
        issues = []
    schema = resolve_ref(schema, root)
    if "oneOf" in schema:
        branch_results = []
        for branch in schema["oneOf"]:
            branch_results.append(validate_structure(value, branch, root, path, []))
        if not any(not result for result in branch_results):
            issues.append(Issue("STRUCT_ONE_OF", path, "does not match any permitted shape"))
            return issues
    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected] if isinstance(expected, str) else []
    if expected_types and not any(type_ok(value, item) for item in expected_types):
        issues.append(Issue("STRUCT_TYPE", path, f"expected {expected_types}"))
        return issues
    if "const" in schema and value != schema["const"]:
        issues.append(Issue("STRUCT_CONST", path, f"must equal {schema['const']!r}"))
    if "enum" in schema and value not in schema["enum"]:
        issues.append(Issue("STRUCT_ENUM", path, f"value {value!r} is not permitted"))
    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            issues.append(Issue("STRUCT_MIN_LENGTH", path, "string is too short"))
        if isinstance(schema.get("pattern"), str) and re.fullmatch(schema["pattern"], value) is None:
            issues.append(Issue("STRUCT_PATTERN", path, "string does not match the required pattern"))
        if schema.get("format") == "date-time" and parse_dt(value) is None:
            issues.append(Issue("STRUCT_DATETIME", path, "must be an ISO 8601 date-time with timezone"))
    if isinstance(value, Mapping):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                issues.append(Issue("STRUCT_REQUIRED", f"{path}.{key}", "required field is missing"))
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    issues.append(Issue("STRUCT_UNKNOWN", f"{path}.{key}", "unknown field is forbidden"))
        for key, child in value.items():
            if key in properties:
                validate_structure(child, properties[key], root, f"{path}.{key}", issues)
    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            issues.append(Issue("STRUCT_MIN_ITEMS", path, "array has too few items"))
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            issues.append(Issue("STRUCT_MAX_ITEMS", path, "array has too many items"))
        if schema.get("uniqueItems") is True:
            rendered = [canonical_json(item) for item in value]
            if len(rendered) != len(set(rendered)):
                issues.append(Issue("STRUCT_UNIQUE", path, "array items must be unique"))
        if isinstance(schema.get("items"), Mapping):
            for index, child in enumerate(value):
                validate_structure(child, schema["items"], root, f"{path}[{index}]", issues)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(Issue("STRUCT_MINIMUM", path, f"must be >= {schema['minimum']}"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(Issue("STRUCT_MAXIMUM", path, f"must be <= {schema['maximum']}"))
    return issues


def policy_validate(dossier: Mapping[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    run_id = dossier["run_id"]
    researcher_id = dossier["researcher_id"]
    role, capabilities, guards, search = dossier["role"], dossier["capabilities"], dossier["guards"], dossier["search"]
    recipient, hook, hook_search = dossier["recipient"], dossier["hook"], dossier["hook_search"]
    proof, channel, decision, review = dossier["candidate_proof"], dossier["channel"], dossier["decision"], dossier["quality_review"]
    review_time = parse_dt(review["reviewed_at"])
    review_pending = review["verdict"] == "PENDING"

    if review_pending:
        issues.append(Issue("REVIEW_PENDING", "quality_review.verdict", "independent review has not been completed"))
        if review["reviewed_at"] is not None:
            issues.append(Issue("REVIEW_PENDING_TIME", "quality_review.reviewed_at", "pending review must not have a completion time"))
    elif review_time is None:
        issues.append(Issue("REVIEW_TIME_MISSING", "quality_review.reviewed_at", "completed review requires a valid completion time"))
    if review["verdict"] == "FAIL":
        issues.append(Issue("REVIEW_FAILED", "quality_review.verdict", "independent review did not pass"))

    # Run binding and guard receipts.
    guard_names, guard_results = [], {}
    for index, receipt in enumerate(guards["receipts"]):
        guard_names.append(receipt["guard"])
        guard_results[receipt["guard"]] = receipt["result"]
        if receipt["run_id"] != run_id:
            issues.append(Issue("GUARD_FOREIGN_RUN", f"guards.receipts[{index}].run_id", "must match dossier run_id"))
        guard_time = parse_dt(receipt["observed_at"])
        if review_time and not review_pending and not (0 <= (review_time - guard_time).total_seconds() <= 86400):
            issues.append(Issue("GUARD_RECEIPT_STALE", f"guards.receipts[{index}].observed_at", "guard receipt must be observed no more than 24 hours before review"))
    missing_guards = REQUIRED_GUARDS - set(guard_names)
    duplicate_guards = {name for name in guard_names if guard_names.count(name) > 1}
    if missing_guards:
        issues.append(Issue("GUARD_RECEIPT_MISSING", "guards.receipts", f"missing {sorted(missing_guards)}"))
    if duplicate_guards:
        issues.append(Issue("GUARD_RECEIPT_DUPLICATE", "guards.receipts", f"duplicate {sorted(duplicate_guards)}"))
    guards_clear = REQUIRED_GUARDS <= set(guard_names) and all(guard_results[name] in {"CLEAR", "CONSOLIDATED"} for name in REQUIRED_GUARDS)
    if guards["overall_state"] in {"CLEAR", "CONSOLIDATED"} and not guards_clear:
        issues.append(Issue("GUARD_CLEAR_UNSUPPORTED", "guards.overall_state", "CLEAR/CONSOLIDATED requires a current clear receipt for every guard"))
    blocking_guard = guards["overall_state"] not in {"CLEAR", "CONSOLIDATED"} or any(value in {"TRIGGERED", "UNKNOWN"} for value in guard_results.values())

    # Query ordering and run binding.
    stages = []
    accessible = set()
    for index, query in enumerate(search["queries_run"]):
        stages.append(query["stage"])
        if query["run_id"] != run_id:
            issues.append(Issue("QUERY_FOREIGN_RUN", f"search.queries_run[{index}].run_id", "must match dossier run_id"))
        if query["outcome"] in {"HIT", "MISS"}:
            accessible.add(query["stage"])
        if query["outcome"] == "HIT" and not exact_url(query["result_url"]):
            issues.append(Issue("QUERY_HIT_RESULT", f"search.queries_run[{index}].result_url", "HIT requires an exact URL"))
    if "HUNTER_DISCOVERY" in stages:
        hunter_index = stages.index("HUNTER_DISCOVERY")
        prerequisites = ["AUTHENTICATED_CURRENTNESS", "HOOK_ARTIFACT", "EMAIL_DISCOVERY_FIRST_PARTY"]
        for stage in prerequisites:
            if stage not in stages[:hunter_index]:
                issues.append(Issue("HUNTER_PREMATURE", "search.queries_run", f"Hunter requires earlier {stage}"))

    # Capability-backed authenticated currentness.
    auth_cap = capabilities["authenticated_profile"]
    auth = search["authenticated_currentness"]
    if auth["capability_receipt_ref"] != auth_cap["receipt_ref"]:
        issues.append(Issue("AUTH_CAPABILITY_BINDING", "search.authenticated_currentness.capability_receipt_ref", "must bind the current authenticated-profile capability receipt"))
    if auth["run_id"] != run_id:
        issues.append(Issue("AUTH_FOREIGN_RUN", "search.authenticated_currentness.run_id", "must match dossier run_id"))
    binding = auth["identity_binding"]
    if recipient["name"] is not None and binding["recipient_name"] != recipient["name"]:
        issues.append(Issue("AUTH_IDENTITY_MISMATCH", "search.authenticated_currentness.identity_binding.recipient_name", "must match selected recipient"))
    if recipient["profile_url"] is not None and binding["profile_url"] != recipient["profile_url"]:
        issues.append(Issue("AUTH_IDENTITY_MISMATCH", "search.authenticated_currentness.identity_binding.profile_url", "must match selected recipient profile"))
    if binding["company"] != role["company"] or binding["target_id"] != role["target_id"]:
        issues.append(Issue("AUTH_SCOPE_MISMATCH", "search.authenticated_currentness.identity_binding", "must bind company and target"))
    fresh_until = parse_dt(auth["fresh_until"])
    observed_at = parse_dt(auth["observed_at"])
    auth_window_valid = bool(observed_at and fresh_until and observed_at <= fresh_until)
    auth_fresh = bool(auth_window_valid and (review_pending or (review_time and review_time <= fresh_until)))
    auth_pass = auth_cap["state"] == "AVAILABLE" and auth["result"] == "CONFIRMED" and auth_fresh
    if auth["result"] == "CONFIRMED" and auth_cap["state"] != "AVAILABLE":
        issues.append(Issue("AUTH_CAPABILITY_UNAVAILABLE", "capabilities.authenticated_profile.state", "CONFIRMED currentness requires AVAILABLE capability"))
    if auth["result"] == "CONFIRMED" and not auth_fresh:
        issues.append(Issue("AUTH_FRESHNESS", "search.authenticated_currentness.fresh_until", "currentness must remain fresh through review"))

    # Current-title source independence.
    supported_keys = set()
    for index, source in enumerate(recipient["currentness_sources"]):
        if source["run_id"] != run_id:
            issues.append(Issue("CURRENTNESS_FOREIGN_RUN", f"recipient.currentness_sources[{index}].run_id", "must match dossier run_id"))
        if source["supports"] == "CURRENT_TITLE_AND_EMPLOYER" and source["source_family"] != "AGGREGATOR":
            supported_keys.add(source["independence_key"])

    # Hook fingerprints and exact evidence binding.
    fingerprints, intents_by_id = [], {}
    accessible_family = {}
    selected = []
    for index, intent in enumerate(hook_search["intents"]):
        expected = intent_fingerprint(intent["signature"])
        if intent["canonical_fingerprint"] != expected:
            issues.append(Issue("HOOK_INTENT_FINGERPRINT", f"hook_search.intents[{index}].canonical_fingerprint", "must equal the fingerprint of the structured signature"))
        fingerprints.append(intent["canonical_fingerprint"])
        intents_by_id[intent["intent_id"]] = intent
        if intent["run_id"] != run_id:
            issues.append(Issue("HOOK_INTENT_FOREIGN_RUN", f"hook_search.intents[{index}].run_id", "must match dossier run_id"))
        if intent["outcome"] in {"HIT", "MISS"}:
            accessible_family[intent["family"]] = accessible_family.get(intent["family"], 0) + 1
        if intent["supports_selected_hook"]:
            selected.append(intent)
    if len(fingerprints) != len(set(fingerprints)):
        issues.append(Issue("HOOK_INTENT_DUPLICATE_FINGERPRINT", "hook_search.intents", "rephrased or duplicate structured intents cannot manufacture exhaustion"))
    hook_supported = hook["support_state"] == "SUPPORTED"
    binding_ok = False
    if hook_supported and isinstance(hook["evidence_binding"], Mapping):
        bound = intents_by_id.get(hook["evidence_binding"]["intent_id"])
        binding_ok = bool(bound and bound["supports_selected_hook"] and bound["outcome"] == "HIT" and
                          bound["result_url"] == hook["artifact_url"] == hook["evidence_binding"]["result_url"] and
                          bound["content_sha256"] == hook["evidence_binding"]["content_sha256"] and
                          bound["run_id"] == hook["evidence_binding"]["run_id"] == hook["run_id"] == run_id)
        if not binding_ok:
            issues.append(Issue("HOOK_EVIDENCE_MISMATCH", "hook.evidence_binding", "intent, URL, content hash, and run ID must match exact selected evidence"))
    elif hook_supported:
        issues.append(Issue("HOOK_EVIDENCE_MISMATCH", "hook.evidence_binding", "supported hook requires exact evidence binding"))
    recipient_success = hook_search["fallback_kind"] == "RECIPIENT_SPECIFIC" and hook["attribution"] == "PERSON" and binding_ok and any(item["family"] in RECIPIENT_FAMILIES for item in selected) and accessible_family.get("ATTRIBUTION_REFUTATION", 0) >= 1
    generic_minimums = {"RECIPIENT_AUTHORED": 2, "RECIPIENT_SPEAKING": 1, "EMPLOYER_PERSON_ATTRIBUTION": 1, "COMPANY_MANDATE": 1, "ATTRIBUTION_REFUTATION": 1}
    if role["intake_mode"] != "PROACTIVE_COMPANY":
        generic_minimums["JD_CONTEXT"] = 1
    generic_counts = all(accessible_family.get(name, 0) >= count for name, count in generic_minimums.items())
    generic_kind = hook_search["fallback_kind"] in {"GENERIC_COMPANY", "GENERIC_JD"}
    generic_attribution = ((hook_search["fallback_kind"] == "GENERIC_COMPANY" and hook["attribution"] == "COMPANY" and any(item["family"] == "COMPANY_MANDATE" for item in selected)) or
                           (hook_search["fallback_kind"] == "GENERIC_JD" and hook["attribution"] == "JD" and any(item["family"] == "JD_CONTEXT" for item in selected)))
    generic_complete = generic_kind and binding_ok and generic_counts and generic_attribution and not any(item["family"] in RECIPIENT_FAMILIES for item in selected)
    hook_complete = recipient_success or generic_complete
    derived_coverage = "COMPLETE" if hook_complete else "INCOMPLETE"
    if hook_search["coverage_claim"] != derived_coverage:
        issues.append(Issue("HOOK_COVERAGE_DRIFT", "hook_search.coverage_claim", f"derived {derived_coverage}"))

    # Candidate proof.
    proof_state = proof["support_state"]
    proof_hash = proof["evidence_sha256"]
    proof_ok = proof_state == "SUPPORTED" and proof["run_id"] == run_id and isinstance(proof_hash, str) and bool(SHA_RE.fullmatch(proof_hash))
    if proof["run_id"] != run_id:
        issues.append(Issue("PROOF_FOREIGN_RUN", "candidate_proof.run_id", "must match dossier run_id"))
    proof_evidence_fields = (proof["claim"], proof["source_ref"], proof["source_kind"], proof["evidence_sha256"])
    not_evaluated_reason = proof.get("not_evaluated_reason")
    if proof_state == "NOT_EVALUATED":
        if any(value is not None for value in proof_evidence_fields):
            issues.append(Issue("PROOF_NOT_EVALUATED_EVIDENCE", "candidate_proof", "NOT_EVALUATED requires null claim, source, kind, and evidence hash"))
        if not isinstance(not_evaluated_reason, str) or not not_evaluated_reason.strip():
            issues.append(Issue("PROOF_NOT_EVALUATED_REASON", "candidate_proof.not_evaluated_reason", "NOT_EVALUATED requires a non-empty stop reason"))
        if decision["readiness"] == "DRAFT_READY_VERIFY_CHANNEL":
            issues.append(Issue("PROOF_NOT_EVALUATED_READY", "candidate_proof.support_state", "NOT_EVALUATED is permitted only for non-draft readiness"))
    else:
        if any(value is None for value in proof_evidence_fields):
            issues.append(Issue("PROOF_EVALUATED_FIELDS", "candidate_proof", "evaluated proof states require claim, source, kind, and evidence hash"))
        if not_evaluated_reason is not None:
            issues.append(Issue("PROOF_REASON_STATE_MISMATCH", "candidate_proof.not_evaluated_reason", "only NOT_EVALUATED may carry a not-evaluated reason"))

    # Channel cross-field and Hunter capability/budget contract.
    kind, basis, state, address = channel["kind"], channel["basis"], channel["state"], channel["address"]
    email_bases = {"PUBLISHED_FIRST_PARTY", "PATTERN_CONCRETE_COLLEAGUE", "HUNTER_EMAIL_FINDER", "HUNTER_DOMAIN_SEARCH"}
    if kind == "NONE" and not (address is None and basis == "NONE" and state == "UNAVAILABLE"):
        issues.append(Issue("CHANNEL_NONE_INCONSISTENT", "channel", "NONE requires null address, NONE basis, and UNAVAILABLE state"))
    if kind == "EMAIL" and not (isinstance(address, str) and EMAIL_RE.fullmatch(address) and basis in email_bases and state in {"VERIFIED", "VERIFY_CHANNEL"}):
        issues.append(Issue("CHANNEL_EMAIL_INCONSISTENT", "channel", "EMAIL requires syntactic address, email basis, and VERIFIED/VERIFY_CHANNEL state"))
    if kind == "PROFESSIONAL_PLATFORM" and not (exact_url(address) and basis == "PROFESSIONAL_PLATFORM" and state == "VERIFY_CHANNEL"):
        issues.append(Issue("CHANNEL_PLATFORM_INCONSISTENT", "channel", "professional platform requires exact profile URL and matching basis/state"))
    if kind == "RECRUITER_ROUTE" and not (isinstance(address, str) and address.strip() and basis == "RECRUITER_ROUTE" and state == "VERIFY_CHANNEL"):
        issues.append(Issue("CHANNEL_RECRUITER_INCONSISTENT", "channel", "recruiter route requires a route reference and matching basis/state"))
    if basis in {"PATTERN_CONCRETE_COLLEAGUE", "HUNTER_EMAIL_FINDER", "HUNTER_DOMAIN_SEARCH"} and state == "VERIFIED":
        issues.append(Issue("CHANNEL_NOT_VERIFIED", "channel.state", "pattern/Hunter discovery cannot verify a channel"))
    hunter = channel["hunter_usage"]
    hunter_method = hunter["method"]
    hunter_capability = "hunter_email_finder" if hunter_method == "EMAIL_FINDER" else "hunter_domain_search" if hunter_method == "DOMAIN_SEARCH" else None
    if hunter_method == "NONE":
        if any([hunter["discovery_connector_calls"] != 0, hunter["search_credits_used"] != 0, hunter["verification_credits_used"] != 0, hunter["result"] != "NOT_USED"]):
            issues.append(Issue("HUNTER_NOT_USED_DRIFT", "channel.hunter_usage", "NONE requires zero credits/calls and NOT_USED"))
    else:
        if capabilities["hunter_account_details"]["state"] != "AVAILABLE" or capabilities[hunter_capability]["state"] != "AVAILABLE":
            issues.append(Issue("HUNTER_CAPABILITY_BLOCK", "capabilities", "Hunter use requires AVAILABLE account-details and selected discovery capabilities"))
        if hunter["discovery_connector_calls"] != 1 or hunter["verification_credits_used"] != 0 or hunter["search_credits_used"] > 1:
            issues.append(Issue("HUNTER_BUDGET", "channel.hunter_usage", "one discovery call/search credit maximum and zero verification credits"))
    if hunter["verification_credits_used"] != 0:
        issues.append(Issue("HUNTER_VERIFICATION_FORBIDDEN", "channel.hunter_usage.verification_credits_used", "must remain zero"))

    limitations = dossier["query_access_limitations"]
    limitations_by_capability = {item["capability"]: item for item in limitations}
    for name, receipt in capabilities.items():
        if receipt["state"] != "AVAILABLE":
            limitation = limitations_by_capability.get(name)
            if not limitation or limitation["state"] != receipt["state"] or limitation["receipt_ref"] != receipt["receipt_ref"]:
                issues.append(Issue("CAPABILITY_LIMIT_UNRECORDED", "query_access_limitations", f"{name} {receipt['state']} requires a matching limitation record"))

    # Hash-bound independent review with per-check evidence.
    expected_hash = review_subject_hash(dossier)
    if review["review_subject_sha256"] != expected_hash:
        issues.append(Issue("REVIEW_HASH_MISMATCH", "quality_review.review_subject_sha256", "must equal canonical dossier hash excluding quality_review"))
    if review["reviewer_id"] == researcher_id:
        issues.append(Issue("REVIEW_NOT_INDEPENDENT", "quality_review.reviewer_id", "must differ from researcher"))
    check_names = [item["name"] for item in review["checks"]]
    if set(check_names) != REQUIRED_REVIEW or len(check_names) != len(set(check_names)):
        issues.append(Issue("REVIEW_CHECK_SET", "quality_review.checks", "requires each named check exactly once"))
    completed_failed_checks = [item["name"] for item in review["checks"] if not review_pending and item["verdict"] != "PASS"]
    if completed_failed_checks:
        issues.append(Issue("REVIEW_CHECK_FAILED", "quality_review.checks", f"non-passing completed checks: {sorted(completed_failed_checks)}"))
    if review["verdict"] == "PASS" and completed_failed_checks:
        issues.append(Issue("REVIEW_VERDICT_DRIFT", "quality_review.verdict", "PASS requires every named check to pass"))
    review_pass = review["verdict"] == "PASS" and all(item["verdict"] == "PASS" and item["evidence_refs"] for item in review["checks"]) and review["reviewer_id"] != researcher_id and review["review_subject_sha256"] == expected_hash

    route, readiness, response = recipient["route_class"], decision["readiness"], decision["permitted_response"]
    if route in ROUTE_RESPONSES and response not in ROUTE_RESPONSES[route]:
        issues.append(Issue("ROUTE_RESPONSE_MISMATCH", "decision.permitted_response", f"{response} is not permitted for {route}"))
    if route == "CONFIRMED_HM" and recipient["requisition_linkage"] != "EXPLICIT":
        issues.append(Issue("HM_LINKAGE", "recipient.requisition_linkage", "CONFIRMED_HM requires EXPLICIT linkage"))
    if route in {"CONFIRMED_HM", "LIKELY_HM"} and search["literal_seat_result"] != "HIT":
        issues.append(Issue("HM_WITHOUT_LITERAL_HIT", "search.literal_seat_result", "HM routes require literal-seat HIT"))
    if route == "APEX_CONTEXT" and readiness not in {"OWNER_DECISION", "BLOCKED"}:
        issues.append(Issue("APEX_REQUIRES_DECISION", "decision.readiness", "APEX_CONTEXT requires OWNER_DECISION or BLOCKED"))
    if route in {"NO_SAFE_ROUTE", "DISCONFIRMED"} and readiness != "BLOCKED":
        issues.append(Issue("BLOCKING_ROUTE", "decision.readiness", f"{route} requires BLOCKED"))
    if blocking_guard and readiness not in {"BLOCKED", "OWNER_DECISION", "RESEARCH_MORE"}:
        issues.append(Issue("BLOCKING_GUARD", "decision.readiness", "unresolved or blocking guard fails closed"))
    if route in PERSON_ROUTES and not auth_pass and readiness != "PROFILE_CHECK" and not blocking_guard:
        issues.append(Issue("AUTH_PROFILE_GATE", "decision.readiness", "named route without current capability-backed fresh observation requires PROFILE_CHECK"))

    if readiness == "DRAFT_READY_VERIFY_CHANNEL":
        requirements = {
            "READY_GUARDS": guards_clear and not blocking_guard,
            "READY_ROUTE": route not in NON_DRAFT_ROUTES,
            "READY_AUTH": auth_pass,
            "READY_CURRENTNESS_SOURCES": len(supported_keys) >= 2,
            "READY_HOOK": hook_supported and binding_ok and hook_complete,
            "READY_PROOF": proof_ok,
            "READY_RESOURCE_COVERAGE": REQUIRED_STAGES <= accessible,
            "READY_CHANNEL": kind != "NONE" and address is not None and state in {"VERIFIED", "VERIFY_CHANNEL"},
            "READY_RESPONSE": response != "NONE",
            "READY_REVIEW": review_pending or review_pass,
        }
        for code, passed in requirements.items():
            if not passed:
                issues.append(Issue(code, "decision.readiness", "draft-ready requirement is not satisfied"))
    return issues


def validate(dossier: Mapping[str, Any]) -> list[Issue]:
    if dossier.get("schema_version") == "BossHuntResearchDossierV2":
        return [Issue("LEGACY_SCHEMA_REFUSED", "schema_version", "V2 is frozen history; create a new V3 dossier from newly observed evidence")]
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Issue("SCHEMA_UNAVAILABLE", str(SCHEMA_PATH), str(exc))]
    structural = validate_structure(dossier, schema, schema)
    if structural:
        return structural
    return policy_validate(dossier)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dossier", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        dossier = json.loads(args.dossier.read_text(encoding="utf-8"))
        if not isinstance(dossier, dict):
            raise ValueError("dossier JSON must be an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    issues = validate(dossier)
    if args.json:
        print(json.dumps([issue.__dict__ for issue in issues], indent=2, sort_keys=True))
    elif issues:
        for issue in issues:
            print(f"{issue.code} {issue.path}: {issue.message}")
        print(f"FAIL: {len(issues)} issue(s)")
    else:
        print(f"PASS: {args.dossier}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
