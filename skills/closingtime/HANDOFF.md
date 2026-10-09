# closingtime 3.0.4 — candidate handoff

**Status:** Independent transferability review NOT RUN for this candidate.
The July certificate applied to an earlier version; it does not certify this
package. Local tests and real usage are different kinds of evidence.

## Prerequisites

- An agent with project read/write access and owner conversation.
- Python 3 and shell access for the bundled CLI, which uses only the standard
  library. Follow workspace runner instructions when present.
- One intended project root; continuity files may be absent for a first close.
- Optional Git, compatible Tasks MCP SQL access scoped by the owner's project
  instructions, Open Brain, and bounded transcript access. No credentials are
  bundled. Tasks and Open Brain have separate authorization boundaries.

Install the complete folder and start a fresh session. The helper owns session
appends; a direct write is not the normal fallback.

## Normal use

Invoke $closingtime with verified outcomes and a concrete next step. The agent
snapshots current files, obtains current Tasks evidence or a named unavailable
receipt, and validates a scratch envelope. It shows the complete session/index/
task proposal before requesting approval of the exact mutation scope.

After approval, it validates a fresh envelope, appends through the helper,
reads back index/task changes, and audits the journal. Learning review follows
verified persistence: save candidates before presentation and obtain separate
approval for capture.

Useful CLI entry points:

```text
python /path/to/closingtime/scripts/runtime_cli.py snapshot /path/to/project
python /path/to/closingtime/scripts/runtime_cli.py validate /scratch/envelope.json
python /path/to/closingtime/scripts/runtime_cli.py append /scratch/envelope.json /scratch/entry.md
python /path/to/closingtime/scripts/runtime_cli.py audit /path/to/project
```

See references/runtime_contract.md and scripts/schemas.py for envelope fields.
Keep envelopes and entry drafts outside the project. Validation checks
consistency, not the authenticity of supplied MCP rows.

## Degraded, skip, and interruption use

- Tasks non-working: preserve task changes as pending and leave the mirror
  untouched. Approved local closeout can proceed.
- Open Brain non-working: retain candidates for later review; do not capture.
- Python unavailable: provide a draft for manual save and say no helper append
  or audit ran.
- Changed tail or root-level sync conflict: stop before the affected mutation.
  A local advisory lock cannot protect another machine; the tail hash is the
  cross-device check.
- Skips remain independent: skipping index does not skip tasks; skipping capture
  does not skip extraction.
- Interruption: distinguish verified, attempted, and pending actions and retain
  Next:. Never emit false completion checkmarks.

## Authority and limits

Write only the approved scope. Git operations and external captures need their
own authority. Historical exceptions remain unverified; they are not journal
receipts.

Local fixtures cover envelope rejection, changed-tail refusal, journal audit,
skip/interruption policy, packaging, and structure. They do not prove fresh
model behavior, working external writes, third-language quality, recursive
conflict discovery, or independent transferability.
Current hashes and validation gates are recorded in the repository's
skills/_shared/validation/README.md; normal invocation does not need that
maintainer evidence. Production promotion remains a separate decision.
