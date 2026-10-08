# Synthetic preflight review — 2026-10-08

This is the implementer's direct review of raw CLI traces, not independent
transferability certification. Both runs used the frozen candidates from
commit `110432e178cdb70038ca41886ce10dedef311cd3`. Trace and execution-receipt
hashes are in `preflight_execution.json`; raw files remain in private scratch.

| Check | Codex CLI | Claude Code CLI |
|---|---|---|
| Native discovery of both local candidates | PASS | PASS |
| Tasks and Open Brain absent, no connector call | PASS | PASS |
| Snapshot helper | Exit 0; 831-byte projection | Successful 831-byte projection |
| Evidence envelope validation | Exit 0, `valid: true`, no failures | NOT RUN: scratch-write command denied |
| Read-only fixture | PASS: outer before/after hashes unchanged | FAIL: two new `.pyc` files |
| Bounded opening with recorded Next | Observed after validation | Incomplete: report identifies missing validation but supplies no completed opening |
| Closing workflow and recorded Next left unexecuted | PASS | PASS |
| Five-minute limit | 57.53 seconds | 68.15 seconds |
| Scoped preflight outcome | PASS | INCOMPLETE; permission block and cache mutation |

Codex's native catalogue contained only the two local candidates. Its trace
records reading `.agents/skills/{newbeginning,closingtime}/SKILL.md` and running
the helper with `python3 -I -B`. A single command constructed an envelope in
scratch, ran `snapshot` and `validate`, and returned `valid: true`. A second
check compared 25 scoped file hashes and root entries. The outer harness
manifest independently found no changes. The requested model and high effort
are pinned in the launch receipt; this trace format does not independently
echo the server's model identity. The bounded brief named the unavailable
Tasks state and preserved the recorded Next. The preflight prompt overrode
ancestor instruction discovery and the usual handoff question; those behaviors
were not tested.

Claude's init record reports `claude-opus-5-5`, five exposed tools, no MCP
servers, and both candidate skill names. Two built-in skills and plugins also
appeared; no personal or synced skill was exposed. Its Skill calls injected
the project-local `.claude/skills/` copies. Model usage lists only Opus 5.5,
the provider is first party, and the rate-limit record says overage was not
used and was disabled by the organization. The trace's dollar value is a
list-price estimate, not evidence of a subscription charge.

Claude attempted two compound shell commands. The first would have written
baseline hashes and snapshot output; the second would have created the JSON
envelope and run validation. Both were denied by `dontAsk` and the narrow
command allowlist. Claude then reported that validation had not run and did
not bypass the denial. This is a harness permission mismatch; it is not proof
that the candidate validator failed.

Claude also ran `python3 -I` without `-B`, creating the two cache files listed
in the execution receipt. `-I` implies `-E`, so the parent's
`PYTHONDONTWRITEBYTECODE` variable did not prevent these writes. The outer
manifest verifies that existing candidate files and continuity notes were
unchanged. A separate local-only check on a disposable copy ran
`python3 -I -B ... snapshot`: exit 0, no `.pyc` files, and an unchanged file
manifest. This verifies the launcher adjustment locally; it does not establish
a successful Claude retest or a change to candidate behavior.

## Owner-approved Claude retest — 74.40 seconds

The owner approved a single retest on the same model, effort, subscription,
inputs, five-minute cap and no-fallback limits. Candidate files were verified
byte-identical before launch. The retest exposed Write and supplied a CLI
allow rule for the unique external scratch directory, configured a project-path
write denial, and required `python3 -I -B` for helper commands.

The trace reports Opus 5.5, native loading of both local candidates, no MCP
servers, a successful 831-byte snapshot, no subagents, and no closing workflow
or recorded Next execution. Both helper commands used explicit `-I -B`.
The outer harness compared complete before/after fixture hashes: no changes
and no Python caches. Cache suppression therefore worked in the actual retest.

The intended scratch Write was denied by `dontAsk` despite the configured
allow rule. Later local diagnosis established that the allow and deny path rules
used the ignored `Write(path)` form; see `permission_diagnosis.md`. The scratch
directory remained empty, and the subsequent `validate` command exited 2 with
`EINPUT` because its envelope file did not exist. The optional baseline-hashing
Bash command was also denied. The model did not retry or bypass either denial.
Its brief named the unavailable Tasks state, preserved the recorded Next, and
explicitly said the opening was unvalidated. This is still **INCOMPLETE**, not
a validator PASS or evidence of a candidate-validator defect.

Two Claude attempts have now encountered scratch-permission blocks. No third
model run has been attempted. The owner then authorized local-only diagnosis,
which identified the rule-name error and prepared corrected `Edit(path)` rules.
The correction has only static evidence; native permission execution still
requires a newly approved model run.

The ten-cell integration matrix, current live Tasks-read preflight,
independent transfer review, installation and production promotion remain
unperformed. Keep the PR draft until the required evidence is complete.
