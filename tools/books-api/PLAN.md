# Approval scope — local book API candidate

Owner selected: Codex/T3 Code and Claude Code on this Mac first.
Task: 71fd8e61-20f3-4373-9a4e-603e860988c1 (P0, due 2026-10-03).

## Proposed installation

Run `python3 install.py` from this candidate directory after owner approval.
Reviewable implementation: books_api.py. Installer: install.py.

The installer runs tests, aborts on existing code destinations/name collisions,
backs up both user configuration files, creates canonical source and a local
runtime, preserves the owner's already saved settings byte-for-byte (or
initializes country MX if absent), and registers `books-api`
for both harnesses. It does not alter existing server entries intentionally.
It validates the two new command/argument registrations and writes an install
receipt. If one registration fails, report partial installation and inspect
the backups rather than calling the batch complete or rerunning blindly.

Exact registration commands, using the resolved current Python path and
installed absolute runtime path:

```sh
codex mcp add books-api -- /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 '/Users/benjaminre/Library/Application Support/MetaClaude/books-api/books_api.py' serve
claude mcp add --scope user --transport stdio books-api -- /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 '/Users/benjaminre/Library/Application Support/MetaClaude/books-api/books_api.py' serve
```

No existing CaptureBooks credential is reused by installation. A separate
decision is needed to create/configure a dedicated Google Books key or approve
reuse of only GOOGLE_BOOKS_API_KEY from the existing CaptureBooks PoC file.
OPENROUTER_API_KEY is outside scope and must never be copied or invoked.

## Acceptance after installation

1. Verify canonical/runtime hashes and two new server entries.
2. Direct MCP subprocess initialize, tool list, and books_status without network.
3. Public Open Library ISBN and title/author lookups with provenance/cache checks.
4. After key approval/setup, public Google Books ISBN and title/author lookups.
5. Fresh Codex/T3 Code and Claude Code sessions discover the tools and can call
   both providers. Configuration alone is not proof of session availability.
6. Keep the task open until this agreed coverage is verified. Other devices,
   hosted/web sessions, and project-specific catalog mutation remain separate.

## Current evidence

Installation approved and completed on 2026-10-02 (Mexico City). The owner
entered a key separately in the local config; the installer preserved it. Both
APIs passed live Dorian Gray title/author searches and record retrieval through
the installed MCP process. Claude CLI reports Connected; Codex registration and
both configured command handshakes passed. All 13 offline tests passed. Existing
settings were preserved, including restoration of an empty node_repl.args entry
omitted by Codex CLI serialization. Fresh model-session discovery remains
unverified. No other AI model session, deployment, or task change occurred.
See VERIFICATION.json and DORIAN_GRAY_*_RECEIPTS.json for bounded evidence.
