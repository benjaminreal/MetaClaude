# closingtime 3.0.10 — candidate handoff

**Status:** candidate. This file does not certify the package. Phase 4
behavioral validation passed on 3.0.6 (six fresh sessions in Claude Code and
Codex, English and Spanish) with targeted checks of 3.0.7 and 3.0.8. The
independent transferability record for this exact package is kept outside the
package, bound to its version and tree hash, in the repository's
`skills/_shared/validation/phase4_5/`. Production promotion is a separate
decision.

## Prerequisites

- An agent with project read/write access and owner conversation.
- Python 3 and shell access for the bundled CLI, which uses only the standard
  library. Follow workspace runner instructions when present.
- One intended project root; continuity files may be absent for a first close.
- Optional Git, compatible Tasks MCP SQL access scoped by the owner's project
  instructions, Open Brain, and bounded transcript access. No credentials are
  bundled. Tasks and Open Brain have separate authorization boundaries.

Install the complete folder (for example into `~/.claude/skills/closingtime`
or `~/.codex/skills/closingtime`) and start a fresh session. The helper owns
session appends; a direct write is not the normal fallback.

## Normal use

Invoke closingtime (`/closingtime` in Claude Code, `$closingtime` in Codex)
with verified outcomes and a concrete next step. The agent:

1. snapshots current files, obtains current Tasks evidence or a named
   unavailable receipt, and validates a scratch envelope;
2. drafts the session entry, index changes and task operations, runs
   `freeze-draft`, and shows the complete proposal with its exact mutation
   scope (no learning-candidate wording yet);
3. after explicit approval, runs `approve-draft`, validates the approved copy
   of the draft envelope (same snapshot), appends through the helper, applies
   and reads back index and task changes, and audits the journal;
4. writes learning candidates to `pending_learnings.md`, searches Open Brain
   for connections, and quotes the saved wording for review; capture needs
   separate approval;
5. closes with status lines, an evidence line, and the ritual line last.

The entry and index default to English; replies follow the owner's language.

Useful CLI entry points:

```text
python /path/to/closingtime/scripts/runtime_cli.py snapshot /path/to/project
python /path/to/closingtime/scripts/runtime_cli.py fingerprint-rows /scratch/rows.json
python /path/to/closingtime/scripts/runtime_cli.py validate /scratch/envelope.json
python /path/to/closingtime/scripts/runtime_cli.py freeze-draft /scratch/draft-envelope.json /scratch/entry.md
python /path/to/closingtime/scripts/runtime_cli.py approve-draft /scratch/draft-receipt.json "<exact scope>"
python /path/to/closingtime/scripts/runtime_cli.py append /scratch/approved-envelope.json /scratch/entry.md /scratch/approved-receipt.json
python /path/to/closingtime/scripts/runtime_cli.py audit /path/to/project
python /path/to/closingtime/scripts/runtime_cli.py render-mirror /scratch/rows.json <local-date>
python /path/to/closingtime/scripts/runtime_cli.py count-words /scratch/text.md
```

Pass `-` instead of a JSON or text path to read it from stdin. See
references/runtime_contract.md and scripts/schemas.py for envelope fields.
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
  cross-device check. A changed draft needs a new freeze and approval.
- Skips remain independent: skipping index does not skip tasks; skipping capture
  does not skip extraction or the Open Brain search.
- Interruption: distinguish verified, attempted, and pending actions and retain
  Next:. Never emit false completion checkmarks.

## Authority and limits

Write only the approved scope. Git operations and external captures need their
own authority. Historical exceptions remain unverified; they are not journal
receipts. The draft receipt guards against accidental rebasing, not deliberate
forgery.

Local fixtures cover envelope rejection, frozen-draft and chronology refusals,
changed-tail refusal, journal audit, skip/interruption policy, packaging, and
structure. Phase 4 covered fresh model behavior in two harnesses, English and
Spanish only. Not validated: working Tasks DB writes, live Open Brain capture,
nested or recursive conflict discovery, ambiguous filenames, and other
languages.
