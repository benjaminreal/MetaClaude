# Focused closing smoke review — 2026-10-08

**PASS_SCOPED_CLOSING_SMOKE** for the frozen newbeginning 2.0.3 /
closingtime 3.0.4 package copies. This exercises closingtime, not a new opening
validation. See `closing_smoke_execution.json` for identities and receipts.

The owner approved OpenAI GPT-6.1-Sol/high through Codex CLI with ChatGPT
subscription authentication, synthetic inputs only, a five-minute aggregate
model-run limit, zero additional-cost budget, and no paid API or model fallback.

## Observed workflow

The first turn read the local closing package and instructions, verified a
three-item synthetic checklist, captured a 597-byte projection, validated its
observation envelope, displayed the full proposed entry/index/scope, and stopped.
The parent manifest proved all project bytes unchanged before approval.

The harness supplied exact-scope synthetic owner approval in the same session.
The model built and validated a fresh approved envelope, appended Session #1
through the bundled CLI, read back the entry and helper journal receipt, saved
and read back the approved index, and ran audit. Total CLI model-run time across
the two turns was 199.05 seconds; both model turns exited zero. Time spent by
the operator inspecting and correcting the launcher between turns is excluded
from that runtime total.

The implementer inspected both raw traces, their commands/results, and the
final claims. An additional outer readback and audit confirmed:

- one session and one exact matching journal receipt;
- zero unjournaled entries, orphan receipts, historical exemptions, or errors;
- saved session and index exactly match the approved draft;
- frozen Active TODOs block is byte-identical;
- only the session, index narrative, and one journal receipt changed;
- packages, instructions, and checklist unchanged; no bytecode or policy file;
- no external connector, network tool, or delegated model call observed.

The final output reported verified local saves and explicit skips for tasks,
learning, Open Brain, and ritual, and retained the concrete next action.

## Setup defects retained

A stale enabled-only MCP override rejected CLI startup in 0.12 seconds, before
any model request. Removing those overrides restored the previously successful
isolation configuration.

The draft turn could not save the scratch review copy because the launcher did
not allow that external directory. The model named the block and did not bypass
it. The exact structured proposal was retained from its raw tool output; only
the already-approved scratch directory was allowed for the second turn. The
same session continued within the remaining aggregate model-run budget.

These were harness setup repairs, not candidate package changes. Rejected
startup and first-turn evidence remain retained locally; public hashes bind the
records. The raw trace does not echo the serving model identity; the CLI request
was pinned to the approved model and effort.

## Scope of conclusion

This closes the focused local closing-workflow gap for candidate source merge.
It does not establish live Tasks/Open Brain behavior, unskipped learning quality,
all recovery/conflict paths, or independent transferability certification.
The broader production validation plan remains separate.
