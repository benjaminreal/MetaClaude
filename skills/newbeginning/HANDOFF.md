# newbeginning 2.0.7 — candidate handoff

**Status:** candidate. This file does not certify the package. Phase 4
behavioral validation passed on 2.0.5 (six fresh sessions in Claude Code and
Codex, English and Spanish). The independent transferability record for this
exact package is kept outside the package, bound to its version and tree hash,
in the repository's `skills/_shared/validation/phase4_5/`. Production promotion
is a separate decision.

## Prerequisites

- An agent that can read the whole skill folder and converse with the owner.
- Python 3 and shell access for the bundled CLI, which uses only the standard
  library. Follow workspace runner instructions when present.
- One intended project root with continuity files, or an owner-confirmed
  location for approved bootstrap.
- Optional Git, a compatible Tasks MCP SQL connector scoped by the owner's
  project instructions, and Open Brain tools. No credentials are bundled.

Install the entire folder, including scripts and references (for example into
`~/.claude/skills/newbeginning` or `~/.codex/skills/newbeginning`), and start a
fresh agent session. Authoritative tasks require a compatible `task_urgency`
view.

## Normal use

Invoke newbeginning (`/newbeginning` in Claude Code, `$newbeginning` in Codex)
at the project root. The agent snapshots bounded continuity evidence, reads
each project or ancestor instruction file the snapshot lists, reads current
Tasks rows when available, and validates a scratch envelope. It replies in the
owner's language with at most 250 words: project state, the last `Next:`, top
tasks only with a current receipt, flags and gaps, one hand-off question with
three options (a fourth for pending learnings when applicable), and a final
evidence line. Then it stops.

Useful CLI entry points:

```text
python /path/to/newbeginning/scripts/runtime_cli.py snapshot /path/to/project
python /path/to/newbeginning/scripts/runtime_cli.py fingerprint-rows /scratch/rows.json
python /path/to/newbeginning/scripts/runtime_cli.py validate /scratch/envelope.json
python /path/to/newbeginning/scripts/runtime_cli.py count-words /scratch/brief.md
```

Pass `-` instead of a JSON or text path to read it from stdin. Read
references/runtime_contract.md to assemble an envelope; executable validators
are in scripts/schemas.py. Keep scratch evidence outside the project.
Validation checks consistency, not the authenticity of supplied rows.

## Degraded and recovery use

- Tasks absent, unauthorized, or scoped elsewhere: name the exact state, treat
  the Markdown mirror as possibly stale, and make no current-task claim.
- Rows that cannot be fingerprinted: label any task list "unverified".
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
Phase 4 covered fresh model behavior in two harnesses, English and Spanish
only. Not validated: working external writes, nested or recursive conflict
discovery, ambiguous filenames, and other languages.
