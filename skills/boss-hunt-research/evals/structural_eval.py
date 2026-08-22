#!/usr/bin/env python3
"""Complete deterministic structural and behavioral eval for Boss Hunt V3."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures"
CANDIDATE_VERSION = "1.2.9"
CLAUDE_LOADER = ROOT / "skills" / "boss-hunt-research" / "SKILL.md"
INSTALL_METADATA = ROOT / "INSTALL-METADATA.json"
REQUIRED_FILES = [
    ROOT / "SKILL.md", ROOT / "README.md", ROOT / "BACKLOG.md", ROOT / "agents" / "openai.yaml",
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / "HANDOFF.md", ROOT / "COLLEAGUE-ONBOARDING.md", ROOT / "TRANSFERABILITY-STATEMENT.md",
    ROOT / "references" / "process.md", ROOT / "references" / "source-policy.md",
    ROOT / "references" / "authoring-guide.md", ROOT / "references" / "dossier-contract.md", ROOT / "references" / "hook-exhaustion.md",
    ROOT / "references" / "dependency-capability-contract.md",
    ROOT / "references" / "harness-tool-discovery.md",
    ROOT / "references" / "bosshunt_target_v2.schema.json",
    ROOT / "references" / "bosshunt_dossier_v2.schema.json",
    ROOT / "references" / "bosshunt_dossier_v3.schema.json",
    ROOT / "scripts" / "build_search_plan.py", ROOT / "scripts" / "validate_dossier.py",
    ROOT / "scripts" / "init_dossier.py", ROOT / "scripts" / "hash_evidence.py", ROOT / "scripts" / "intent_fingerprint.py", ROOT / "scripts" / "review_record.py", ROOT / "scripts" / "check_session_tools.py", ROOT / "scripts" / "build_harness_install.py", ROOT / "scripts" / "release_privacy_scan.py",
    ROOT / "references" / "release-privacy.md",
    ROOT / "evals" / "behavioral_fixtures.py", FIXTURES / "target.json",
    FIXTURES / "valid_dossier.json", FIXTURES / "invalid_apex_dossier.json",
    ROOT / "transferability" / "BASELINE-2026-08-21.md",
    ROOT / "transferability" / "STAGE-1-DELTA-CAPTURE.md",
    ROOT / "transferability" / "STAGE-1-INITIAL-COLD-READ.md",
    ROOT / "transferability" / "STAGE-2-GAP-REGISTER.md",
    ROOT / "transferability" / "STAGE-2-INDEPENDENT-TEST-EVIDENCE.md",
    ROOT / "transferability" / "STAGE-3-TRANSFERABILITY-ASSESSMENT.md",
    ROOT / "transferability" / "STAGE-3-HANDOFF-CHECKPOINT-SUPERSEDED.md",
    ROOT / "transferability" / "STAGE-4-WEAKEST-SECTION-TEST.md",
    ROOT / "transferability" / "STAGE-5-DOCUMENTATION-AUDIT.md",
    ROOT / "transferability" / "STAGE-5-NOVEL-EDGE-CASE.md",
    ROOT / "transferability" / "FINAL-VERIFICATION-2026-08-21.md",
    ROOT / "transferability" / "DEFECT-DISPOSITIONS-R1-R13.md",
]

CERTIFIED_RUNTIME_DOCS = [
    ROOT / "SKILL.md",
    ROOT / "README.md",
    ROOT / "HANDOFF.md",
    ROOT / "COLLEAGUE-ONBOARDING.md",
    ROOT / "TRANSFERABILITY-STATEMENT.md",
    ROOT / "references" / "process.md",
    ROOT / "references" / "authoring-guide.md",
]
FORBIDDEN_RUNTIME_PATH_FRAGMENTS = tuple("/" + value for value in ("Users/", "home/", "Volumes/", "private/tmp"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def codes(validator, dossier) -> set[str]:
    return {issue.code for issue in validator.validate(dossier)}


def expect_code(failures: list[str], validator, name: str, dossier: dict, code: str) -> None:
    observed = codes(validator, dossier)
    if code not in observed:
        failures.append(f"{name}: expected {code}, observed {sorted(observed)}")


def main() -> int:
    failures: list[str] = []
    tree_kind = "SOURCE"
    install_metadata: dict[str, object] | None = None
    if INSTALL_METADATA.is_file():
        try:
            install_metadata = json.loads(INSTALL_METADATA.read_text(encoding="utf-8"))
            tree_kind = str(install_metadata.get("harness"))
            if install_metadata.get("schema_version") != "BossHuntHarnessInstallMetadataV1":
                failures.append(f"install metadata schema drift: {install_metadata}")
            if tree_kind not in {"CODEX", "CLAUDE_CODE"}:
                failures.append(f"install metadata harness drift: {install_metadata}")
        except Exception as exc:
            failures.append(f"install metadata parse failed: {exc}")
            tree_kind = "INVALID_INSTALL"
    required_files = list(REQUIRED_FILES)
    if tree_kind in {"SOURCE", "CLAUDE_CODE"}:
        required_files.append(CLAUDE_LOADER)
    for path in required_files:
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            failures.append(f"missing or empty required file: {path.relative_to(ROOT)}")

    skill_entries = sorted(str(path.relative_to(ROOT)) for path in ROOT.rglob("SKILL.md"))
    if tree_kind == "CODEX":
        if skill_entries != ["SKILL.md"]:
            failures.append(f"Codex install must expose exactly one canonical skill: {skill_entries}")
        if not (ROOT / "agents" / "openai.yaml").is_file():
            failures.append("Codex install lacks canonical agents/openai.yaml")
    elif tree_kind in {"SOURCE", "CLAUDE_CODE"}:
        expected_entries = ["SKILL.md", "skills/boss-hunt-research/SKILL.md"]
        if skill_entries != expected_entries:
            failures.append(f"source/Claude tree skill entries drift: {skill_entries}")

    for path in CERTIFIED_RUNTIME_DOCS:
        content = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_RUNTIME_PATH_FRAGMENTS:
            if fragment in content:
                failures.append(f"owner/platform-specific path in certified runtime documentation: {path.relative_to(ROOT)} contains {fragment}")
        if "quick_validate.py" in content:
            failures.append(f"harness-specific validator leaked into certified runtime documentation: {path.relative_to(ROOT)}")

    try:
        privacy = load_module("boss_hunt_release_privacy_scan", ROOT / "scripts" / "release_privacy_scan.py")
        privacy_findings = privacy.scan_tree(ROOT)
        if privacy_findings:
            failures.append(f"release privacy scan failed: {privacy_findings}")
        privacy_mutants = (
            ("owner-local path", "/" + "Users/release-test/private/file.json", "OWNER_LOCAL_PATH"),
            ("private key", "-" * 5 + "BEGIN PRIVATE KEY" + "-" * 5, "PRIVATE_KEY"),
            ("non-synthetic email", "person" + "@" + "company.test", "NON_SYNTHETIC_EMAIL"),
        )
        for name, payload, expected in privacy_mutants:
            observed = {item["code"] for item in privacy.scan_text(Path("synthetic-mutant.txt"), payload)}
            if expected not in observed:
                failures.append(f"privacy mutant {name}: expected {expected}, observed {sorted(observed)}")
        allowed = privacy.scan_text(Path("synthetic-allowed.txt"), "jordan@example.com")
        if allowed:
            failures.append(f"reserved synthetic email rejected by privacy scan: {allowed}")
    except Exception as exc:
        failures.append(f"release privacy scan suite failed: {exc}")

    for schema_name, title in (("bosshunt_target_v2.schema.json", "BossHuntTargetV2"),
                               ("bosshunt_dossier_v2.schema.json", "BossHuntResearchDossierV2"),
                               ("bosshunt_dossier_v3.schema.json", "BossHuntResearchDossierV3")):
        try:
            schema = json.loads((ROOT / "references" / schema_name).read_text(encoding="utf-8"))
            if schema.get("title") != title:
                failures.append(f"{schema_name}: title drift")
        except Exception as exc:
            failures.append(f"{schema_name}: parse failed: {exc}")

    try:
        claude_manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if claude_manifest.get("name") != "boss-hunt-research" or claude_manifest.get("version") != CANDIDATE_VERSION:
            failures.append(f"Claude Code plugin identity/version drift: {claude_manifest}")
        if tree_kind in {"SOURCE", "CLAUDE_CODE"}:
            claude_loader = CLAUDE_LOADER.read_text(encoding="utf-8")
            if "../../SKILL.md" not in claude_loader or "only Boss Hunt Research contract" not in claude_loader:
                failures.append("Claude Code skills-dir loader does not delegate to the canonical root skill")
    except Exception as exc:
        failures.append(f"Claude Code plugin manifest parse failed: {exc}")

    try:
        tool_check = load_module("boss_hunt_check_session_tools", ROOT / "scripts" / "check_session_tools.py")
        full_inventory = {
            "schema_version": tool_check.INPUT_VERSION,
            "observed_at": "2026-08-21T17:30:00-06:00",
            "inventory_source": "synthetic harness inventory",
            "harness": "CODEX",
            "inventory_available": True,
            "tools": [
                "mcp__codex_apps__hunter_get_account_details",
                "mcp__codex_apps__hunter_email_finder",
                "mcp__codex_apps__hunter_domain_search",
                tool_check.CODEX_CHROME_TOOL,
            ],
            "skills": ["chrome:control-chrome", "browser:control-in-app-browser"],
        }
        full = tool_check.classify(full_inventory)
        if any(item["state"] != "EXPOSED" for item in full["surfaces"].values()):
            failures.append(f"preferred tool exposure not recognized: {full}")
        if full["surfaces"]["authenticated_profile_preferred"]["provider"] != "EXTERNAL_CHROME":
            failures.append(f"Codex AUTO did not prefer existing Chrome: {full}")
        if full["schema_version"] != "BossHuntSessionToolAvailabilityV2":
            failures.append(f"session tool output contract drift: {full['schema_version']}")
        if full["external_calls_made"] != 0 or full["credits_used"] != 0:
            failures.append("tool discovery claimed an external call or credit")
        partial_inventory = deepcopy(full_inventory)
        partial_inventory["tools"].remove("mcp__codex_apps__hunter_email_finder")
        partial = tool_check.classify(partial_inventory)
        if partial["surfaces"]["hunter_preferred"]["state"] != "PARTIAL":
            failures.append(f"partial Hunter exposure not preserved: {partial}")
        unavailable_inventory = deepcopy(full_inventory)
        unavailable_inventory.update({"inventory_available": False, "tools": [], "skills": []})
        unavailable = tool_check.classify(unavailable_inventory)
        if any(item["state"] != "INVENTORY_UNAVAILABLE" for item in unavailable["surfaces"].values()):
            failures.append(f"unavailable inventory not fail-closed: {unavailable}")

        claude_inventory = {
            "schema_version": tool_check.INPUT_VERSION,
            "observed_at": "2026-08-21T17:31:00-06:00",
            "inventory_source": "synthetic Claude Code inventory",
            "harness": "CLAUDE_CODE",
            "inventory_available": True,
            "tools": [
                "mcp__Claude_in_Chrome__list_connected_browsers",
                "mcp__hunter__get_account_details",
                "mcp__hunter__email_finder",
                "mcp__hunter__domain_search",
            ],
            "skills": [],
        }
        claude = tool_check.classify(claude_inventory)
        if claude["surfaces"]["authenticated_profile_external_chrome"]["state"] != "EXPOSED":
            failures.append(f"Claude Code Chrome tool family not recognized: {claude}")
        if claude["surfaces"]["hunter_preferred"]["state"] != "EXPOSED":
            failures.append(f"Claude Code Hunter operation aliases not recognized: {claude}")
        if claude["surfaces"]["authenticated_profile_preferred"]["provider"] != "EXTERNAL_CHROME":
            failures.append(f"Claude Code AUTO did not select exposed Chrome: {claude}")

        false_hunter = deepcopy(claude_inventory)
        false_hunter["tools"] = [
            "mcp__other_provider__get_account_details",
            "mcp__other_provider__email_finder",
            "mcp__other_provider__domain_search",
        ]
        false_hunter_result = tool_check.classify(false_hunter)
        if false_hunter_result["surfaces"]["hunter_preferred"]["state"] != "NOT_EXPOSED":
            failures.append(f"non-Hunter operation collision was accepted: {false_hunter_result}")

        internal_inventory = {
            "schema_version": tool_check.INPUT_VERSION,
            "observed_at": "2026-08-21T17:32:00-06:00",
            "inventory_source": "synthetic harness-internal browser inventory",
            "harness": "CLAUDE_CODE",
            "inventory_available": True,
            "profile_surface_preference": "AUTO",
            "tools": ["mcp__internal_browser__list_tabs"],
            "skills": [],
        }
        internal = tool_check.classify(internal_inventory)
        if internal["surfaces"]["authenticated_profile_internal_browser"]["state"] != "EXPOSED":
            failures.append(f"harness internal-browser alternative not recognized: {internal}")
        selected = internal["surfaces"]["authenticated_profile_preferred"]
        if selected["provider"] != "HARNESS_INTERNAL_BROWSER" or selected["state"] != "EXPOSED":
            failures.append(f"AUTO did not fall back to the harness internal browser: {internal}")

        explicit_inventory = deepcopy(internal_inventory)
        explicit_inventory["profile_surface_preference"] = "EXTERNAL_CHROME"
        explicit = tool_check.classify(explicit_inventory)
        selected = explicit["surfaces"]["authenticated_profile_preferred"]
        if selected["provider"] != "EXTERNAL_CHROME" or selected["state"] != "NOT_EXPOSED":
            failures.append(f"explicit Chrome preference was silently substituted: {explicit}")
        agent_yaml = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        for dependency in ('value: "codex_apps"', 'value: "node_repl"'):
            if dependency not in agent_yaml:
                failures.append(f"preferred session dependency missing from agents/openai.yaml: {dependency}")
    except Exception as exc:
        failures.append(f"session tool discovery suite failed: {exc}")

    try:
        planner = load_module("boss_hunt_build_search_plan_v2", ROOT / "scripts" / "build_search_plan.py")
        target = json.loads((FIXTURES / "target.json").read_text(encoding="utf-8"))
        first, second = planner.build_plan(target), planner.build_plan(target)
        if first != second:
            failures.append("planner is not deterministic")
        stages = first["stage_order"]
        required_order = ["GLOBAL_GUARDS", "ADJACENT_ROUTES", "AUTHENTICATED_CURRENTNESS", "HOOK_ARTIFACT", "HOOK_GATE", "EMAIL_DISCOVERY_FIRST_PARTY", "HUNTER_DISCOVERY"]
        if [stages.index(stage) for stage in required_order] != sorted(stages.index(stage) for stage in required_order):
            failures.append("Hunter ordering gate is not monotonic")
        if len(first.get("hunter_preconditions", [])) < 6:
            failures.append("Hunter preconditions are incomplete")
        for state, expected in (("UNAVAILABLE", "NO_HUNTER / CONTINUE_WITH_DOCUMENTED_FALLBACK"),
                                ("UNAUTHENTICATED", "NO_HUNTER / CONTINUE_WITH_DOCUMENTED_FALLBACK"),
                                ("WRONG_SCOPE", "NO_HUNTER / CONTINUE_WITH_DOCUMENTED_FALLBACK")):
            mutant = deepcopy(target)
            mutant["capabilities"]["hunter_email_finder"]["state"] = state
            if planner.build_plan(mutant)["capability_map"]["hunter_email_finder"]["required_result"] != expected:
                failures.append(f"Hunter {state} did not produce named zero-credit fallback")
        missing_id = deepcopy(target)
        missing_id.pop("target_id")
        try:
            planner.build_plan(missing_id)
            failures.append("missing target identity was accepted")
        except planner.TargetError as exc:
            if not str(exc).startswith("TARGET_REQUIRED target_id:"):
                failures.append(f"missing target identity error was not actionable: {exc}")
        missing_authority = deepcopy(target)
        missing_authority["authority_sources"] = []
        try:
            planner.build_plan(missing_authority)
            failures.append("missing authority was accepted")
        except planner.TargetError as exc:
            if not str(exc).startswith("TARGET_AUTHORITY authority_sources:"):
                failures.append(f"missing authority error was not actionable: {exc}")
    except Exception as exc:
        failures.append(f"planner suite failed: {exc}")

    try:
        validator = load_module("boss_hunt_validate_dossier_v3", ROOT / "scripts" / "validate_dossier.py")
        fixtures = load_module("boss_hunt_behavioral_fixtures", ROOT / "evals" / "behavioral_fixtures.py")
        valid = json.loads((FIXTURES / "valid_dossier.json").read_text(encoding="utf-8"))
        if validator.validate(valid):
            failures.append("valid fixture rejected: " + ", ".join(sorted(codes(validator, valid))))
        for name, factory in fixtures.NAMED_FIXTURES.items():
            observed = validator.validate(factory(validator))
            if observed:
                failures.append(f"behavioral fixture {name} rejected: {[item.code for item in observed]}")

        no_channel = deepcopy(valid)
        no_channel["channel"] = {"kind": "NONE", "address": None, "state": "UNAVAILABLE", "basis": "NONE", "source_url": None,
                                 "hunter_usage": {"account_snapshot_at": None, "account_receipt_ref": None, "method": "NONE", "result": "NOT_USED", "domain_search_limit": None, "discovery_connector_calls": 0, "search_credits_used": 0, "verification_credits_used": 0}}
        no_channel["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(no_channel)
        expect_code(failures, validator, "draft-ready without channel", no_channel, "READY_CHANNEL")

        hunter_verified = deepcopy(valid)
        for capability in ("hunter_account_details", "hunter_email_finder"):
            hunter_verified["capabilities"][capability]["state"] = "AVAILABLE"
        hunter_verified["query_access_limitations"] = [item for item in hunter_verified["query_access_limitations"] if item["capability"] not in {"hunter_account_details", "hunter_email_finder"}]
        hunter_verified["search"]["queries_run"][-1].update({"outcome": "MISS", "result_url": None})
        hunter_verified["search"]["queries_run"].append({"stage": "HUNTER_DISCOVERY", "surface": "synthetic-hunter", "query": "Email Finder", "observed_at": "2026-08-21T09:32:00-06:00", "outcome": "HIT", "result_url": "https://hunter.example/results/jordan", "run_id": valid["run_id"], "note": "Synthetic; no live call."})
        hunter_verified["channel"].update({"state": "VERIFIED", "basis": "HUNTER_EMAIL_FINDER", "source_url": "https://hunter.example/results/jordan",
                                            "hunter_usage": {"account_snapshot_at": "2026-08-21T09:00:00-06:00", "account_receipt_ref": "receipt:hunter-account", "method": "EMAIL_FINDER", "result": "HIT", "domain_search_limit": None, "discovery_connector_calls": 1, "search_credits_used": 1, "verification_credits_used": 0}})
        hunter_verified["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(hunter_verified)
        expect_code(failures, validator, "Hunter-derived VERIFIED channel", hunter_verified, "CHANNEL_NOT_VERIFIED")

        hunter_valid = deepcopy(hunter_verified)
        hunter_valid["channel"]["state"] = "VERIFY_CHANNEL"
        hunter_valid["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(hunter_valid)
        if validator.validate(hunter_valid):
            failures.append(f"valid synthetic Hunter branch rejected: {sorted(codes(validator, hunter_valid))}")
        hunter_premature = deepcopy(hunter_valid)
        hunter_trace = hunter_premature["search"]["queries_run"].pop()
        auth_index = next(index for index, item in enumerate(hunter_premature["search"]["queries_run"]) if item["stage"] == "AUTHENTICATED_CURRENTNESS")
        hunter_premature["search"]["queries_run"].insert(auth_index, hunter_trace)
        hunter_premature["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(hunter_premature)
        expect_code(failures, validator, "Hunter before currentness/hook/first-party gates", hunter_premature, "HUNTER_PREMATURE")

        hook_mismatch = deepcopy(valid)
        hook_mismatch["hook"]["evidence_binding"]["result_url"] = "https://example.com/insights/different-artifact"
        hook_mismatch["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(hook_mismatch)
        expect_code(failures, validator, "hook evidence mismatch", hook_mismatch, "HOOK_EVIDENCE_MISMATCH")

        duplicate = deepcopy(valid)
        dup_intent = deepcopy(duplicate["hook_search"]["intents"][0])
        dup_intent.update({"intent_id": "same-intent-rephrased", "query_or_action": "find Jordan's operating model writing with different words", "supports_selected_hook": False})
        duplicate["hook_search"]["intents"].append(dup_intent)
        duplicate["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(duplicate)
        expect_code(failures, validator, "rephrased duplicate intent", duplicate, "HOOK_INTENT_DUPLICATE_FINGERPRINT")

        stale_guard = deepcopy(valid)
        stale_guard["guards"]["receipts"][0]["observed_at"] = "2026-08-01T09:00:00-06:00"
        stale_guard["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(stale_guard)
        expect_code(failures, validator, "CLEAR without current guard evidence", stale_guard, "GUARD_RECEIPT_STALE")

        pending_review = deepcopy(valid)
        pending_review["quality_review"].update({"verdict": "PENDING", "reviewed_at": None})
        for check in pending_review["quality_review"]["checks"]:
            check.update({"verdict": "PENDING", "evidence_refs": ["PENDING"]})
        pending_codes = codes(validator, pending_review)
        if pending_codes != {"REVIEW_PENDING"}:
            failures.append(f"pending review diagnostic drift: {sorted(pending_codes)}")

        failed_review = deepcopy(valid)
        failed_review["quality_review"]["verdict"] = "FAIL"
        expect_code(failures, validator, "completed failed review", failed_review, "REVIEW_FAILED")

        failed_check = deepcopy(valid)
        failed_check["quality_review"]["checks"][0]["verdict"] = "FAIL"
        failed_check_codes = codes(validator, failed_check)
        for expected_code in {"REVIEW_CHECK_FAILED", "REVIEW_VERDICT_DRIFT"}:
            if expected_code not in failed_check_codes:
                failures.append(f"PASS review with failed check: expected {expected_code}, observed {sorted(failed_check_codes)}")

        not_evaluated_ready = deepcopy(valid)
        not_evaluated_ready["candidate_proof"] = {"claim": None, "source_ref": None, "source_kind": None,
                                                    "evidence_sha256": None, "run_id": valid["run_id"],
                                                    "support_state": "NOT_EVALUATED",
                                                    "not_evaluated_reason": "Earlier gate stopped proof evaluation."}
        not_evaluated_ready["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(not_evaluated_ready)
        expect_code(failures, validator, "NOT_EVALUATED proof at draft readiness", not_evaluated_ready, "PROOF_NOT_EVALUATED_READY")

        not_evaluated_with_evidence = deepcopy(fixtures.stale_person(validator))
        not_evaluated_with_evidence["candidate_proof"]["claim"] = "This claim must not coexist with NOT_EVALUATED."
        not_evaluated_with_evidence["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(not_evaluated_with_evidence)
        expect_code(failures, validator, "NOT_EVALUATED proof carrying evidence", not_evaluated_with_evidence, "PROOF_NOT_EVALUATED_EVIDENCE")

        evaluated_missing_fields = deepcopy(valid)
        evaluated_missing_fields["candidate_proof"]["claim"] = None
        evaluated_missing_fields["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(evaluated_missing_fields)
        expect_code(failures, validator, "evaluated proof missing evidence fields", evaluated_missing_fields, "PROOF_EVALUATED_FIELDS")

        auth_unbound = deepcopy(valid)
        auth_unbound["search"]["authenticated_currentness"]["capability_receipt_ref"] = "receipt:other-profile"
        auth_unbound["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(auth_unbound)
        expect_code(failures, validator, "currentness without bound capability", auth_unbound, "AUTH_CAPABILITY_BINDING")

        auth_stale = deepcopy(valid)
        auth_stale["search"]["authenticated_currentness"]["fresh_until"] = "2026-08-21T09:30:00-06:00"
        auth_stale["quality_review"]["review_subject_sha256"] = validator.review_subject_hash(auth_stale)
        expect_code(failures, validator, "stale authenticated currentness", auth_stale, "AUTH_FRESHNESS")

        unknown = deepcopy(valid)
        unknown["invented_field"] = True
        observed = validator.validate(unknown)
        if not observed or observed[0].code != "STRUCT_UNKNOWN" or any(not item.code.startswith("STRUCT_") for item in observed):
            failures.append(f"unknown property did not fail structurally first: {[item.code for item in observed]}")

        malformed = deepcopy(valid)
        malformed["hook_search"]["intents"][0] = []
        observed = validator.validate(malformed)
        if not observed or observed[0].code != "STRUCT_TYPE" or any(not item.code.startswith("STRUCT_") for item in observed):
            failures.append(f"malformed nested object did not fail structurally first: {[item.code for item in observed]}")

        review_unbound = deepcopy(valid)
        review_unbound["quality_review"]["review_subject_sha256"] = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        expect_code(failures, validator, "review not bound to dossier", review_unbound, "REVIEW_HASH_MISMATCH")

        legacy = json.loads((FIXTURES / "invalid_apex_dossier.json").read_text(encoding="utf-8"))
        expect_code(failures, validator, "frozen V2 refusal", legacy, "LEGACY_SCHEMA_REFUSED")
    except Exception as exc:
        failures.append(f"validator suite failed: {exc}")

    valid_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_dossier.py"), str(FIXTURES / "valid_dossier.json")], capture_output=True, text=True)
    invalid_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_dossier.py"), str(FIXTURES / "invalid_apex_dossier.json")], capture_output=True, text=True)
    planner_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_search_plan.py"), str(FIXTURES / "target.json")], capture_output=True, text=True)
    if valid_cli.returncode != 0:
        failures.append(f"valid CLI failed: {valid_cli.stdout}{valid_cli.stderr}")
    if invalid_cli.returncode != 1:
        failures.append(f"invalid CLI expected 1, got {invalid_cli.returncode}")
    if planner_cli.returncode != 0:
        failures.append(f"documented target planner CLI failed: {planner_cli.stdout}{planner_cli.stderr}")

    with tempfile.TemporaryDirectory(prefix="bosshunt-eval-") as temp_dir:
        temp_root = Path(temp_dir)
        if tree_kind == "SOURCE":
            codex_install = temp_root / "codex-install"
            claude_install = temp_root / "claude-install"
            build_codex = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_harness_install.py"), "--harness", "CODEX", "--output", str(codex_install)],
                capture_output=True,
                text=True,
            )
            build_claude = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_harness_install.py"), "--harness", "CLAUDE_CODE", "--output", str(claude_install)],
                capture_output=True,
                text=True,
            )
            if build_codex.returncode != 0:
                failures.append(f"Codex install build failed: {build_codex.stdout}{build_codex.stderr}")
            else:
                codex_manifest = json.loads(build_codex.stdout)
                if codex_manifest["skill_entries"] != ["SKILL.md"]:
                    failures.append(f"Codex install exposes duplicate skills: {codex_manifest}")
                if codex_manifest["excluded_files"] != ["skills/boss-hunt-research/SKILL.md"]:
                    failures.append(f"Codex install exclusion drift: {codex_manifest}")
                codex_metadata = json.loads((codex_install / "INSTALL-METADATA.json").read_text(encoding="utf-8"))
                if codex_metadata.get("harness") != "CODEX":
                    failures.append(f"Codex install metadata drift: {codex_metadata}")
                if not (codex_install / "agents" / "openai.yaml").is_file():
                    failures.append("Codex install lost canonical agents/openai.yaml")
            if build_claude.returncode != 0:
                failures.append(f"Claude Code install build failed: {build_claude.stdout}{build_claude.stderr}")
            else:
                claude_manifest = json.loads(build_claude.stdout)
                if "skills/boss-hunt-research/SKILL.md" not in claude_manifest["skill_entries"]:
                    failures.append(f"Claude Code install lost nested loader: {claude_manifest}")
                claude_metadata = json.loads((claude_install / "INSTALL-METADATA.json").read_text(encoding="utf-8"))
                if claude_metadata.get("harness") != "CLAUDE_CODE":
                    failures.append(f"Claude Code install metadata drift: {claude_metadata}")
                resolved = (claude_install / "skills" / "boss-hunt-research" / ".." / ".." / "SKILL.md").resolve()
                if resolved != (claude_install / "SKILL.md").resolve():
                    failures.append("Claude Code loader no longer resolves to canonical root SKILL.md")

            existing_manifest = temp_root / "existing-manifest.json"
            existing_manifest.write_text("{}\n", encoding="utf-8")
            refused_output = temp_root / "refused-existing-manifest"
            existing_manifest_cli = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_harness_install.py"), "--harness", "CODEX", "--output", str(refused_output), "--manifest-output", str(existing_manifest)],
                capture_output=True,
                text=True,
            )
            if existing_manifest_cli.returncode != 1 or refused_output.exists():
                failures.append("existing manifest refusal left a finalized install tree")

            embedded_output = temp_root / "refused-embedded-manifest"
            embedded_manifest_cli = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_harness_install.py"), "--harness", "CODEX", "--output", str(embedded_output), "--manifest-output", str(embedded_output / "manifest.json")],
                capture_output=True,
                text=True,
            )
            if embedded_manifest_cli.returncode != 1 or embedded_output.exists():
                failures.append("embedded manifest was accepted or left a finalized install tree")

            derived_output = temp_root / "refused-derived-build"
            derived_build_cli = subprocess.run(
                [sys.executable, str(codex_install / "scripts" / "build_harness_install.py"), "--harness", "CLAUDE_CODE", "--output", str(derived_output)],
                capture_output=True,
                text=True,
            )
            if derived_build_cli.returncode != 1 or derived_output.exists():
                failures.append("derived install was accepted as a canonical build source")
        elif install_metadata and install_metadata.get("candidate_version") != CANDIDATE_VERSION:
            failures.append(f"installed-tree candidate version drift: {install_metadata}")
        initialized = temp_root / "dossier.json"
        review_request = temp_root / "review.json"
        pending_bound = temp_root / "dossier-review-pending.json"
        init_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "init_dossier.py"), str(FIXTURES / "target.json"), "--run-id", "run-eval-init", "--researcher-id", "researcher-eval", "--output", str(initialized)], capture_output=True, text=True)
        review_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_record.py"), "prepare", str(FIXTURES / "valid_dossier.json"), "--reviewer-id", "reviewer-eval", "--output", str(review_request)], capture_output=True, text=True)
        hash_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "hash_evidence.py"), str(ROOT / "evals" / "cold_handoff" / "SYNTHETIC_EVIDENCE.md")], capture_output=True, text=True)
        fingerprint_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "intent_fingerprint.py"), "--subject", "jordan example", "--claim", "authored operating model artifact", "--surface-family", "employer authored content"], capture_output=True, text=True)
        if init_cli.returncode != 0 or not initialized.is_file():
            failures.append(f"dossier initializer failed: {init_cli.stdout}{init_cli.stderr}")
        if review_cli.returncode != 0 or not review_request.is_file():
            failures.append(f"review request preparation failed: {review_cli.stdout}{review_cli.stderr}")
        bind_cli = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_record.py"), "bind-pending", str(FIXTURES / "valid_dossier.json"), str(review_request), "--output", str(pending_bound)], capture_output=True, text=True)
        if bind_cli.returncode != 0 or not pending_bound.is_file():
            failures.append(f"pending review binding failed: {bind_cli.stdout}{bind_cli.stderr}")
        elif codes(validator, json.loads(pending_bound.read_text(encoding="utf-8"))) != {"REVIEW_PENDING"}:
            failures.append("bound pending dossier did not produce exactly REVIEW_PENDING")
        pending_attach = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_record.py"), "attach", str(pending_bound), str(review_request), "--output", str(temp_root / "pending-reviewed.json")], capture_output=True, text=True)
        if pending_attach.returncode == 0 or "still PENDING" not in (pending_attach.stdout + pending_attach.stderr):
            failures.append(f"pending review attachment was not refused: {pending_attach.stdout}{pending_attach.stderr}")
        if hash_cli.returncode != 0 or not hash_cli.stdout.startswith("sha256:"):
            failures.append(f"evidence hash helper failed: {hash_cli.stdout}{hash_cli.stderr}")
        if fingerprint_cli.returncode != 0 or fingerprint_cli.stdout.strip() != "sha256:1cb4d73c923c38671f7dfdb7e8d3d978223aaf673f5e03e829349be04423907e":
            failures.append(f"intent fingerprint helper failed: {fingerprint_cli.stdout}{fingerprint_cli.stderr}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        print(f"\n{len(failures)} failure(s)")
        return 1
    print(f"PASS: {len(required_files)} required files; tree_kind={tree_kind}; harness-aware install checks; release privacy scan; portable runtime docs; no-call Codex/Claude Code tool discovery; external Chrome/internal-browser selection; canonical target; structural-first validation; 6 behavioral fixtures; 21 one-defect mutants; Hunter fail-closed states; authoring/review helpers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
