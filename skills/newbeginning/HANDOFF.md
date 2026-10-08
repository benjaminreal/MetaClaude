# newbeginning 2.0.2 — candidate handoff

**Status:** Independent transferability review NOT RUN for this candidate.
The July certificate applied to an earlier version; it does not certify this
package. Local tests and real usage are different kinds of evidence.

## Prerequisites

- An agent that can read the whole skill folder and converse with the owner.
- Python 3 and shell access for the bundled CLI, which uses only the standard
  library. Follow workspace runner instructions when present.
- One intended project root with continuity files, or an owner-confirmed
  location for approved bootstrap.
- Optional Git, a compatible Tasks MCP SQL connector scoped by the owner's
  project instructions, and Open Brain tools. No credentials are bundled.

Install the entire folder, including scripts and references, and start a fresh
agent session. Authoritative tasks require a compatible task_urgency view.

## Normal use

Invoke $newbeginning at the project root. The agent resolves project/ancestor
instructions, snapshots bounded continuity evidence, reads current Tasks rows
when available, and validates a scratch envelope. It emits at most 250 words
with the last Next: and one handoff question, then stops.

Useful CLI entry points:

```text
python /path/to/newbeginning/scripts/runtime_cli.py snapshot /path/to/project
python /path/to/newbeginning/scripts/runtime_cli.py fingerprint-rows /scratch/rows.json
python /path/to/newbeginning/scripts/runtime_cli.py validate /scratch/envelope.json
```

Read references/runtime_contract.md to assemble an envelope; executable
validators are in scripts/schemas.py. Keep scratch evidence outside the
project. Validation checks consistency, not the authenticity of supplied rows.

## Degraded and recovery use

- Tasks absent, unauthorized, or scoped elsewhere: name the exact state, treat
  the Markdown mirror as possibly stale, and make no current-task claim.
- Python unavailable: name the missing helper and unperformed checks.
- Index absent: draft reconstruction/bootstrap, obtain approval, read back the
  saved index, and recapture before briefing.
- Source contradiction or root-level sync conflict: stop and name it; separate
  approval is required for reconciliation.
- Open Brain unavailable: leave pending-learning content unread and defer
  review. Ordinary opening does not require Open Brain.

## Authority and limits

Routine opening writes nothing to the project or external systems. Approved
post-brief task creation reserves its UUID before writing and reads that same
UUID after an uncertain outcome. Task updates, completion, parking, and
cancellation are outside opening scope.

Local fixtures cover contracts, helper failure paths, packaging, and structure.
They do not prove fresh model behavior, working external writes, third-language
quality, recursive conflict discovery, or independent transferability.
Current hashes and validation gates are recorded in the repository's
skills/_shared/validation/README.md; normal invocation does not need that
maintainer evidence. Production promotion remains a separate decision.
