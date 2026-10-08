# Local permission diagnosis — 2026-10-08

**Cause identified; no model call made.** Claude Code checks file-writing paths
against `Edit(path)` rules, including calls to the Write tool. It accepts but
does not consult `Write(path)` rules. The prepared scratch grant used
`Write(//<scratch-directory>/**)`, so it did not approve envelope creation.
With `dontAsk`, the resulting request was denied. The configured project-path
deny rule also used `Write(path)` and therefore was not an effective path rule;
the outer before/after hashes still confirm no project mutations in the retest.

This behavior is documented in Anthropic's
[Read and Edit permission rules](https://code.claude.com/docs/en/permissions#read-and-edit)
and confirmed by the embedded permission guidance in the installed Claude Code
2.1.295 executable. This identifies a harness configuration error, not a defect
in the candidate envelope validator.

The local corrected preparation replaces both path-based Write rules with
Edit rules:

```text
allow: Edit(//<unique-external-scratch-directory>/**)
deny:  Edit(//<disposable-fixture-directory>/**)
```

The exposed tools remain Bash, Glob, Grep, Read, Skill and Write. The Edit tool
is not exposed merely because its name is used in the permission rule. Existing
Read restrictions, isolated project skill discovery, absent connectors,
explicit `python3 -I -B`, subscription authentication and no-fallback limits
are preserved. Historical run receipts and configurations were not rewritten.

Static checks passed: the corrected allow and deny use Edit, no path-based
Write rule remains, only Write is exposed for file creation, and the prepared
launcher parses. A launch guard requires recorded specific owner approval.
No model request or native Write permission decision was exercised by these
local checks. The owner subsequently approved the prepared corrected run.
That 65.70-second preflight observed the scratch Write succeed, envelope
validation return `valid: true`, and complete outer fixture hashes remain
unchanged. See `preflight_review.md` and `preflight_execution.json`. The
configuration correction is verified for this scoped opening, without changing
the candidate packages or global configuration.

Candidate packages and their frozen hashes are unchanged. The earlier Claude
runs remain incomplete evidence; the new pass comes from the approved corrected
run. The integration matrix and independent certification remain NOT RUN.
