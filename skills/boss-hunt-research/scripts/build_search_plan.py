#!/usr/bin/env python3
"""Build an offline, fail-closed Boss Hunt research plan from BossHuntTargetV2.

The plan is sequencing metadata only. It never fetches a page, uses Hunter,
authenticates to a profile surface, or establishes that evidence is true.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


TARGET_VERSION = "BossHuntTargetV2"
CAPABILITY_STATES = {"AVAILABLE", "UNAVAILABLE", "UNAUTHENTICATED", "WRONG_SCOPE", "BLOCKED", "NOT_APPLICABLE"}
CAPABILITIES = (
    "local_role_authority", "public_web", "authenticated_profile",
    "hunter_account_details", "hunter_email_finder", "hunter_domain_search",
    "local_python", "schema_validation",
)
TARGET_KEYS = {
    "schema_version", "target_id", "source_tracker_id", "company", "company_domain",
    "role_title", "intake_mode", "job_url", "jd_source", "posting_status",
    "geography", "function", "explicit_boss_titles", "reporting_hypotheses",
    "authority_sources", "owner_scope", "capabilities",
}


class TargetError(ValueError):
    """One actionable canonical-target error."""


def quoted(value: str) -> str:
    return '"' + value.replace('"', " ").strip() + '"'


def need_string(target: Mapping[str, Any], key: str) -> str:
    value = target.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TargetError(f"TARGET_REQUIRED {key}: supply a non-empty {key!r} in {TARGET_VERSION}")
    return value.strip()


def optional_string(target: Mapping[str, Any], key: str) -> str | None:
    value = target.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TargetError(f"TARGET_FIELD {key}: use null or a non-empty string")
    return value.strip()


def string_list(target: Mapping[str, Any], key: str) -> list[str]:
    value = target.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise TargetError(f"TARGET_FIELD {key}: supply an array of non-empty strings")
    values = [item.strip() for item in value]
    if len(values) != len(set(values)):
        raise TargetError(f"TARGET_FIELD {key}: remove duplicate values")
    return values


def validate_target(target: Mapping[str, Any]) -> None:
    if target.get("schema_version") != TARGET_VERSION:
        raise TargetError(f"TARGET_SCHEMA schema_version: must equal {TARGET_VERSION}")
    unknown = sorted(set(target) - TARGET_KEYS)
    if unknown:
        raise TargetError(f"TARGET_UNKNOWN {unknown[0]}: remove the unknown field or update the target schema")
    for key in ("target_id", "company", "role_title", "owner_scope"):
        need_string(target, key)
    if target.get("intake_mode") not in {"LIVE_REQUISITION", "POST_APPLICATION", "PROACTIVE_COMPANY"}:
        raise TargetError("TARGET_FIELD intake_mode: use LIVE_REQUISITION, POST_APPLICATION, or PROACTIVE_COMPANY")
    if target.get("posting_status") not in {"OPEN", "CLOSED", "UNKNOWN", "NOT_APPLICABLE"}:
        raise TargetError("TARGET_FIELD posting_status: use OPEN, CLOSED, UNKNOWN, or NOT_APPLICABLE")
    for key in ("source_tracker_id", "company_domain", "job_url", "jd_source", "geography", "function"):
        optional_string(target, key)
    string_list(target, "explicit_boss_titles")
    hypotheses = target.get("reporting_hypotheses")
    if not isinstance(hypotheses, list) or not 1 <= len(hypotheses) <= 4:
        raise TargetError("TARGET_FIELD reporting_hypotheses: supply 1 to 4 structured hypotheses")
    required_hypothesis = {"title", "basis", "would_support", "would_refute"}
    for index, hypothesis in enumerate(hypotheses):
        if not isinstance(hypothesis, Mapping) or set(hypothesis) != required_hypothesis:
            raise TargetError(f"TARGET_FIELD reporting_hypotheses[{index}]: use exactly title, basis, would_support, would_refute")
        for key in sorted(required_hypothesis):
            if not isinstance(hypothesis.get(key), str) or not hypothesis[key].strip():
                raise TargetError(f"TARGET_FIELD reporting_hypotheses[{index}].{key}: supply a non-empty string")
    authorities = target.get("authority_sources")
    if not isinstance(authorities, list) or not authorities:
        raise TargetError("TARGET_AUTHORITY authority_sources: supply at least one current local authority receipt")
    authority_keys = {"authority_type", "source_ref", "observed_at", "authority_scope", "evidence_sha256"}
    for index, receipt in enumerate(authorities):
        if not isinstance(receipt, Mapping) or set(receipt) != authority_keys:
            raise TargetError(f"TARGET_AUTHORITY authority_sources[{index}]: use exactly {sorted(authority_keys)}")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(receipt.get("evidence_sha256", ""))):
            raise TargetError(f"TARGET_AUTHORITY authority_sources[{index}].evidence_sha256: supply sha256:<64 lowercase hex>")
        for key in authority_keys - {"evidence_sha256"}:
            if not isinstance(receipt.get(key), str) or not receipt[key].strip():
                raise TargetError(f"TARGET_AUTHORITY authority_sources[{index}].{key}: supply a non-empty string")
    capabilities = target.get("capabilities")
    if not isinstance(capabilities, Mapping):
        raise TargetError("TARGET_CAPABILITY capabilities: supply the complete capability profile")
    missing = [name for name in CAPABILITIES if name not in capabilities]
    if missing:
        raise TargetError(f"TARGET_CAPABILITY capabilities.{missing[0]}: record its state and receipt")
    unknown_caps = sorted(set(capabilities) - set(CAPABILITIES))
    if unknown_caps:
        raise TargetError(f"TARGET_CAPABILITY capabilities.{unknown_caps[0]}: capability is not recognized")
    capability_keys = {"state", "observed_at", "scope", "receipt_ref", "evidence_sha256"}
    for name in CAPABILITIES:
        receipt = capabilities[name]
        if not isinstance(receipt, Mapping) or set(receipt) != capability_keys:
            raise TargetError(f"TARGET_CAPABILITY capabilities.{name}: use exactly {sorted(capability_keys)}")
        if receipt.get("state") not in CAPABILITY_STATES:
            raise TargetError(f"TARGET_CAPABILITY capabilities.{name}.state: use a named capability state")


def capability_result(name: str, state: str) -> str:
    if state == "AVAILABLE":
        return "CONTINUE"
    if name in {"local_role_authority", "local_python", "schema_validation"}:
        return "BLOCKED"
    if name == "public_web":
        return "RESEARCH_MORE" if state in {"UNAVAILABLE", "BLOCKED"} else "BLOCKED"
    if name == "authenticated_profile":
        return "PROFILE_CHECK"
    return "NO_HUNTER / CONTINUE_WITH_DOCUMENTED_FALLBACK"


def build_plan(target: Mapping[str, Any]) -> dict[str, Any]:
    validate_target(target)
    target_id = need_string(target, "target_id")
    company = need_string(target, "company")
    role_title = need_string(target, "role_title")
    geography = optional_string(target, "geography")
    company_domain = optional_string(target, "company_domain")
    explicit_titles = string_list(target, "explicit_boss_titles")
    hypotheses = target["reporting_hypotheses"]
    capabilities = target["capabilities"]
    company_q, role_q = quoted(company), quoted(role_title)
    geo_q = f" {quoted(geography)}" if geography else ""
    site_q = f"site:{company_domain} " if company_domain else ""
    stages: list[dict[str, Any]] = []

    def add(stage: str, gate: str, purpose: str, actions: list[str], stop: str) -> None:
        stages.append({"stage": stage, "entry_gate": gate, "purpose": purpose, "actions": actions,
                       "record_each_as": "HIT | MISS | BLOCKED | NOT_APPLICABLE", "stop_rule": stop})

    add("TARGET_AUTHORITY", "INVOCATION_START", "Validate canonical identity and local authority.",
        ["Validate BossHuntTargetV2", "Bind target ID, owner scope, and authority receipts"],
        "Missing identity or authority => BLOCKED; do not begin web research.")
    add("GLOBAL_GUARDS", "TARGET_AUTHORITY_PASS", "Resolve lifecycle, no-bypass, collision, and disconfirmation guards.",
        ["Create a current receipt for every guard", "Derive the guard state from receipts"],
        "Any triggered/unknown required guard => BLOCKED, OWNER_DECISION, or RESEARCH_MORE; Hunter is forbidden.")
    add("REPORTING_HYPOTHESES", "GLOBAL_GUARDS_PASS", "Freeze literal and alternative reporting hypotheses before names.",
        [f"Literal titles: {', '.join(explicit_titles) if explicit_titles else 'NOT STATED ON SOURCE'}",
         *[f"Hypothesis: {item['title']} — {item['basis']}" for item in hypotheses]],
        "Do not search an apex-only route or invent a reporting line.")
    add("EMPLOYER_CONTEXT", "REPORTING_HYPOTHESES_PASS", "Resolve employer, role, and current mandate.",
        [f"{site_q}{company_q} {role_q}".strip(), f"{company_q} {role_q} (job OR careers OR hiring)"],
        "Confidential/agency ownership or unresolved company identity => BLOCKED.")
    literal_queries = [f"{company_q} {quoted(title)}{geo_q}" for title in explicit_titles]
    if not literal_queries:
        literal_queries = [f"{company_q} {role_q} (reports to OR manager OR leadership){geo_q}"]
    add("LITERAL_SEAT", "EMPLOYER_CONTEXT_PASS", "Test the literal seat before adjacent routes.", literal_queries,
        "Record HIT/MISS/BLOCKED; a miss never authorizes apex substitution.")
    add("REPORTING_ALTERNATIVES", "LITERAL_SEAT_RECORDED", "Test only the predeclared alternatives.",
        [f"{company_q} {quoted(item['title'])}{geo_q}" for item in hypotheses], "Adjacency is not confirmation.")
    add("REQUISITION_AND_SEARCH_OWNER", "REPORTING_ALTERNATIVES_RECORDED", "Resolve explicit requisition or search ownership.",
        [f"{company_q} {role_q} (\"join my team\" OR \"we are hiring\" OR recruiter OR talent)"],
        "Do not route around an owner or confidential search.")
    add("ADJACENT_ROUTES", "SEARCH_OWNER_RECORDED", "Map recruiter, sponsor, colleague, and connector routes honestly.",
        [f"site:linkedin.com/in {company_q} {role_q}{geo_q}"],
        "A named route or documented Domain Search exception hypothesis is required before Hunter can be considered.")
    add("AUTHENTICATED_CURRENTNESS", "DEFENSIBLE_ROUTE_NAMED", "Observe current role on the bound authenticated surface.",
        ["Create a capability receipt", "Bind surface identity to the selected recipient", "Record result and freshness deadline"],
        "Unavailable/unauthenticated/wrong-scope/blocked => PROFILE_CHECK and zero Hunter credits.")
    add("HOOK_ARTIFACT", "AUTHENTICATED_CURRENTNESS_PASS", "Find an exact current-run hook artifact and candidate proof.",
        [f"{{candidate_name}} {company_q} (article OR interview OR talk OR podcast OR post)",
         f"{company_q} {role_q} (strategy OR transformation OR launch OR initiative)"],
        "No exact supported hook and proof => RESEARCH_MORE/BLOCKED; Hunter is forbidden.")
    add("HOOK_GATE", "HOOK_ARTIFACT_RECORDED", "Bind selected hook to one deduplicated intent and exact evidence.",
        ["Recompute structured intent fingerprints", "Match URL, content SHA-256, run ID, and intent ID"],
        "Mismatch, duplicate fingerprint, or incomplete exhaustion => RESEARCH_MORE/BLOCKED.")
    add("EMAIL_DISCOVERY_FIRST_PARTY", "HOOK_GATE_PASS", "Run the bounded first-party email lane.",
        ["Reuse one live first-party address, otherwise one exact query and one obvious first-party read"],
        "HIT => stop. MISS/BLOCKED may enter the Hunter gate.")
    add("HUNTER_DISCOVERY", "FIRST_PARTY_EMAIL_MISS_OR_BLOCKED_AND_HUNTER_CAPABILITY_PASS",
        "Consider at most one Hunter discovery method after every preceding gate.",
        [f"Email Finder for a resolved person at {company_domain or '{verified_company_domain}'}",
         "Domain Search instead of Finder only for a named, predeclared exception; limit <= 10; no pagination"],
        "Any Hunter capability failure => zero credits and documented fallback/blocker. Never call Verifier or mutations.")
    add("ADVERSARIAL_GATE", "CHANNEL_HYPOTHESIS_RECORDED", "Refute currentness, linkage, hook binding, collision, and channel separation.",
        ["Validate BossHuntResearchDossierV3 structurally, then apply policy", "Obtain hash-bound per-check independent review"],
        "Any unresolved contradiction fails closed.")
    add("HANDOFF", "ADVERSARIAL_GATE_PASS_OR_NAMED_STOP", "Return one readiness label and owner summary.",
        ["Return candidate-route evidence, CAN/CANNOT boundary, and one bounded next action or stop reason"],
        "No result authorizes drafting, channel verification, sending, registration, or mutation.")

    capability_map = {name: {"state": capabilities[name]["state"],
                             "required_result": capability_result(name, capabilities[name]["state"]),
                             "receipt_ref": capabilities[name]["receipt_ref"]} for name in CAPABILITIES}
    return {
        "schema_version": "BossHuntSearchPlanV2",
        "target": {key: target.get(key) for key in TARGET_KEYS if key != "capabilities"},
        "capability_map": capability_map,
        "stage_order": [stage["stage"] for stage in stages],
        "stages": stages,
        "hunter_preconditions": ["GLOBAL_GUARDS_PASS", "DEFENSIBLE_ROUTE_NAMED_OR_DOCUMENTED_DOMAIN_EXCEPTION",
                                 "AUTHENTICATED_CURRENTNESS_PASS", "HOOK_GATE_PASS",
                                 "FIRST_PARTY_EMAIL_MISS_OR_BLOCKED", "HUNTER_CAPABILITY_PASS"],
        "authority_note": "Offline plan only; no live call, truth claim, draft, authorization, or mutation.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        target = json.loads(args.target.read_text(encoding="utf-8"))
        if not isinstance(target, dict):
            raise TargetError("TARGET_SCHEMA root: target JSON must be an object")
        plan = build_plan(target)
    except (OSError, json.JSONDecodeError, TargetError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
