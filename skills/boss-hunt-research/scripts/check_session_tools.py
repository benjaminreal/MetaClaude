#!/usr/bin/env python3
"""Classify preferred BossHunt tools from a supplied no-call session inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


INPUT_VERSION = "BossHuntSessionInventoryV1"
OUTPUT_VERSION = "BossHuntSessionToolAvailabilityV2"
HUNTER_OPERATIONS = {
    "hunter_get_account_details": ("hunter_get_account_details", "get_account_details"),
    "hunter_email_finder": ("hunter_email_finder", "email_finder"),
    "hunter_domain_search": ("hunter_domain_search", "domain_search"),
}
CODEX_CHROME_TOOL = "mcp__node_repl__js"
CODEX_CHROME_SKILLS = ("chrome:control-chrome", "control-chrome")
CLAUDE_CHROME_PREFIX = "mcp__claude_in_chrome__"
INTERNAL_BROWSER_SKILLS = ("browser:control-in-app-browser", "control-in-app-browser")
INTERNAL_BROWSER_PREFIXES = (
    "mcp__internal_browser__",
    "mcp__in_app_browser__",
    "mcp__harness_browser__",
)
PROFILE_PREFERENCES = {"AUTO", "EXTERNAL_CHROME", "HARNESS_INTERNAL_BROWSER"}


class InventoryError(ValueError):
    """Invalid supplied session inventory."""


def _strings(value: Any, label: str) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise InventoryError(f"INVENTORY {label}: expected a list of non-empty strings")
    return {item.strip() for item in value}


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _operation_tool(tools: set[str], aliases: tuple[str, ...]) -> str | None:
    normalized_aliases = tuple(_normalized(alias) for alias in aliases)
    for tool in sorted(tools):
        normalized = _normalized(tool)
        if "hunter" not in normalized:
            continue
        if any(normalized.endswith(alias) for alias in normalized_aliases):
            return tool
    return None


def _exact_or_suffix_tool(tools: set[str], preferred: str) -> str | None:
    suffix = preferred.removeprefix("mcp__")
    return next(
        (item for item in sorted(tools) if item == preferred or item.removeprefix("mcp__").endswith(suffix)),
        None,
    )


def _prefix_tools(tools: set[str], prefixes: tuple[str, ...]) -> list[str]:
    lowered = tuple(prefix.lower() for prefix in prefixes)
    return [item for item in sorted(tools) if item.lower().startswith(lowered)]


def _state(present: int, required: int, inventory_available: bool) -> str:
    if not inventory_available:
        return "INVENTORY_UNAVAILABLE"
    if present == required:
        return "EXPOSED"
    if present:
        return "PARTIAL"
    return "NOT_EXPOSED"


def _surface(provider: str, state: str, required: list[str], exposed: list[str]) -> dict[str, Any]:
    return {
        "provider": provider,
        "state": state,
        "required": required,
        "exposed": exposed,
        "missing": [] if state == "EXPOSED" else [item for item in required if item not in exposed],
    }


def _profile_surfaces(tools: set[str], skills: set[str], inventory_available: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    node_tool = _exact_or_suffix_tool(tools, CODEX_CHROME_TOOL)
    chrome_skill = next((item for item in CODEX_CHROME_SKILLS if item in skills), None)
    claude_chrome_tools = _prefix_tools(tools, (CLAUDE_CHROME_PREFIX,))
    if claude_chrome_tools:
        external = _surface(
            "EXTERNAL_CHROME",
            _state(1, 1, inventory_available),
            ["authenticated Chrome connector/tool family"],
            claude_chrome_tools,
        )
    else:
        exposed = ([node_tool] if node_tool else []) + ([chrome_skill] if chrome_skill else [])
        required = [CODEX_CHROME_TOOL, "chrome:control-chrome"]
        external = _surface("EXTERNAL_CHROME", _state(len(exposed), len(required), inventory_available), required, exposed)

    internal_tools = _prefix_tools(tools, INTERNAL_BROWSER_PREFIXES)
    internal_skill = next((item for item in INTERNAL_BROWSER_SKILLS if item in skills), None)
    if internal_tools:
        internal = _surface(
            "HARNESS_INTERNAL_BROWSER",
            _state(1, 1, inventory_available),
            ["harness internal-browser connector/tool family"],
            internal_tools,
        )
    else:
        exposed = ([node_tool] if node_tool else []) + ([internal_skill] if internal_skill else [])
        required = [CODEX_CHROME_TOOL, "browser:control-in-app-browser"]
        internal = _surface(
            "HARNESS_INTERNAL_BROWSER",
            _state(len(exposed), len(required), inventory_available),
            required,
            exposed,
        )
    return external, internal


def _select_profile_surface(
    preference: str,
    external: dict[str, Any],
    internal: dict[str, Any],
    inventory_available: bool,
) -> dict[str, Any]:
    candidates = {"EXTERNAL_CHROME": external, "HARNESS_INTERNAL_BROWSER": internal}
    if preference != "AUTO":
        selected = candidates[preference]
        basis = "EXPLICIT_REQUEST_NO_SILENT_SUBSTITUTION"
    elif external["state"] == "EXPOSED":
        selected = external
        basis = "AUTO_EXTERNAL_CHROME_FIRST"
    elif internal["state"] == "EXPOSED":
        selected = internal
        basis = "AUTO_INTERNAL_BROWSER_FALLBACK"
    elif external["state"] == "PARTIAL":
        selected = external
        basis = "AUTO_PARTIAL_EXTERNAL_CHROME"
    elif internal["state"] == "PARTIAL":
        selected = internal
        basis = "AUTO_PARTIAL_INTERNAL_BROWSER"
    else:
        selected = external
        basis = "AUTO_NO_EXPOSED_PROFILE_SURFACE"
    state = "INVENTORY_UNAVAILABLE" if not inventory_available else selected["state"]
    return {
        "provider": selected["provider"],
        "state": state,
        "preference": preference,
        "selection_basis": basis,
        "alternatives_exposed": [name for name, item in candidates.items() if item["state"] == "EXPOSED"],
        "boundary": "SELECTION_IS_NOT_AUTHENTICATION_OR_PERMISSION_AND_MUST_NOT_BYPASS_ACCESS_CONTROLS",
    }


def classify(inventory: dict[str, Any]) -> dict[str, Any]:
    if inventory.get("schema_version") != INPUT_VERSION:
        raise InventoryError(f"INVENTORY schema_version: must equal {INPUT_VERSION}")
    for field in ("observed_at", "inventory_source"):
        if not isinstance(inventory.get(field), str) or not inventory[field].strip():
            raise InventoryError(f"INVENTORY {field}: supply a non-empty string")
    inventory_available = inventory.get("inventory_available")
    if not isinstance(inventory_available, bool):
        raise InventoryError("INVENTORY inventory_available: supply true or false")
    harness = inventory.get("harness", "UNSPECIFIED")
    if not isinstance(harness, str) or not harness.strip():
        raise InventoryError("INVENTORY harness: when supplied, use a non-empty string")
    preference = inventory.get("profile_surface_preference", "AUTO")
    if preference not in PROFILE_PREFERENCES:
        raise InventoryError(f"INVENTORY profile_surface_preference: use one of {sorted(PROFILE_PREFERENCES)}")
    tools = _strings(inventory.get("tools", []), "tools")
    skills = _strings(inventory.get("skills", []), "skills")

    hunter_matches = {
        operation: _operation_tool(tools, aliases)
        for operation, aliases in HUNTER_OPERATIONS.items()
    }
    hunter_exposed = [tool for tool in hunter_matches.values() if tool]
    hunter_required = list(HUNTER_OPERATIONS)
    external, internal = _profile_surfaces(tools, skills, inventory_available)
    selected = _select_profile_surface(preference, external, internal, inventory_available)

    return {
        "schema_version": OUTPUT_VERSION,
        "observed_at": inventory["observed_at"],
        "inventory_source": inventory["inventory_source"],
        "harness": harness.strip(),
        "external_calls_made": 0,
        "credits_used": 0,
        "surfaces": {
            "authenticated_profile_external_chrome": external,
            "authenticated_profile_internal_browser": internal,
            "authenticated_profile_preferred": selected,
            "hunter_preferred": {
                "provider": "HUNTER_CONNECTOR",
                "state": _state(len(hunter_exposed), len(hunter_required), inventory_available),
                "required": hunter_required,
                "exposed": hunter_exposed,
                "missing": [operation for operation, tool in hunter_matches.items() if not tool],
            },
        },
        "boundary": "EXPOSED_IS_NOT_AUTHENTICATED_SCOPED_AUTHORIZED_OR_AVAILABLE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        if not isinstance(inventory, dict):
            raise InventoryError("INVENTORY root: expected an object")
        result = classify(inventory)
    except (OSError, json.JSONDecodeError, InventoryError) as exc:
        print(str(exc))
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists():
            print(f"INVENTORY output exists; refusing to overwrite: {args.output}")
            return 1
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
