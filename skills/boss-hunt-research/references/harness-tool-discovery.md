# Harness Tool Discovery

Use this reference to perform the no-call preflight in Codex, Claude Code, or
another compatible harness. The portable skill consumes an inventory; it does not
install a connector, alter MCP configuration, open a browser, authenticate an
account, or call Hunter.

## Portable inventory

Create `BossHuntSessionInventoryV1` from the tools and skills already exposed by
the current session:

```json
{
  "schema_version": "BossHuntSessionInventoryV1",
  "observed_at": "2026-08-21T17:30:00-06:00",
  "inventory_source": "current harness tool and skill catalogs",
  "harness": "CODEX",
  "inventory_available": true,
  "profile_surface_preference": "AUTO",
  "tools": [],
  "skills": []
}
```

`harness` is descriptive and may be `CODEX`, `CLAUDE_CODE`, or another non-empty
label. `profile_surface_preference` is optional and defaults to `AUTO`; its allowed
values are `AUTO`, `EXTERNAL_CHROME`, and `HARNESS_INTERNAL_BROWSER`.

Run:

```bash
python3 scripts/check_session_tools.py <session-inventory.json> --output <new-session-report.json>
```

This creates `BossHuntSessionToolAvailabilityV2`. It must report zero external
calls and zero credits.

## Codex

`agents/openai.yaml` can request the `codex_apps` and `node_repl` providers when
Codex loads the skill. That metadata is a Codex convenience, not part of the
portable contract and not proof that a provider was granted.

Install Codex from the deterministic `CODEX` output of
`scripts/build_harness_install.py`, not by copying the full canonical source tree.
The derived tree excludes the Claude-only nested loader and must contain exactly
one discoverable `SKILL.md` at its root beside the canonical metadata. A duplicate
same-name root/loader catalog is a packaging defect, even when both files delegate
to identical instructions. The builder also writes `INSTALL-METADATA.json`, which
identifies the harness and canonical source hash so the portable evaluator can run
the correct installed-tree checks. Do not run the builder from a derived install.

The classifier recognizes:

- external Chrome: `chrome:control-chrome` plus `mcp__node_repl__js`;
- harness internal browser: `browser:control-in-app-browser` plus
  `mcp__node_repl__js`;
- Hunter: the account-details, Email Finder, and Domain Search operations exposed
  by the connector.

## Claude Code

Claude Code loads the plugin through `.claude-plugin/plugin.json`. Its global
`skills-dir` inventory discovers `skills/boss-hunt-research/SKILL.md`, a minimal
loader that delegates immediately to the canonical root `SKILL.md`. The portable
frontmatter uses only `name` and `description`. `agents/openai.yaml` is not a
Claude Code dependency mechanism and may be ignored there.

Install Claude Code from the deterministic `CLAUDE_CODE` output of
`scripts/build_harness_install.py`. That output preserves the full package and the
nested loader required by Claude Code's `skills-dir` inventory, plus generated
install metadata. External build manifests must remain outside the install tree.

The classifier recognizes the Claude in Chrome tool family
`mcp__Claude_in_Chrome__*` and harness-neutral Hunter operation suffixes such as
`mcp__hunter__get_account_details`, `mcp__hunter__email_finder`, and
`mcp__hunter__domain_search`. If a Claude Code environment exposes an explicitly
named internal-browser MCP family (`internal_browser`, `in_app_browser`, or
`harness_browser`), the classifier recognizes it as the internal alternative.

Claude Code does not gain Hunter or a browser merely by reading this skill. Those
tools must already be present through the user's Claude Code MCP/plugin
configuration. Do not invent an MCP server command, endpoint, or credential. If
the required provider is absent, record `NOT_EXPOSED`; configuration or plugin
installation is a separate owner-authorized setup action.

## Browser selection

For `AUTO`, choose exposed external Chrome first because it is the most likely
surface to contain the user's existing authenticated session. If external Chrome
is not exposed and the harness internal browser is, select the internal browser.
If the user explicitly selected either surface, do not silently substitute the
other one.

Selecting a surface means only that its tool family is exposed. Before writing
`authenticated_profile=AVAILABLE`, a permitted read must succeed in the current
invocation and be bound to the intended surface, account identity, target person,
evidence, and freshness window. Never switch browser surfaces to bypass login,
permissions, anti-automation controls, or an explicit block.

## Hunter aliases and limits

Hunter provider names vary by harness, so classification is based on the three
operation suffixes rather than the MCP server name. All three operations must be
exposed for `hunter_preferred=EXPOSED`; a subset is `PARTIAL`.

Exposure is still not permission, authentication, account scope, credit
availability, or method-specific `AVAILABLE`. The runtime Hunter gates and
one-call/one-search-credit ceiling remain unchanged.
