# `_shared` — session-skill contracts and tests

Shared machinery for the sibling skills [`newbeginning`](../newbeginning/) and
[`closingtime`](../closingtime/). Not a skill itself — nothing here is invoked
by a model at runtime. It is the executable form of their lifecycle contract,
plus the deterministic tests that keep both skills honest.

## Files

| File | What it is |
|---|---|
| `schemas.py` | The four data contracts as validators: capability profile, MCP receipt, evidence envelope, journal record. No filesystem access, no MCP calls, no credentials. |
| `mapping.py` | The frozen-to-vNext checklist mapping — 71 behavioral checks, each dispositioned `retained` / `mapped` / `retired`, with the counts self-checked. |
| `fixtures.py` | Deterministic envelope fixtures and one-defect mutants. |
| `helpers.py` | Phase 2 local snapshot, compare-and-swap append/journal, audit, and deployment-hash helpers. No network client or credentials. |
| `helper_fixtures.py` | Real-filesystem fixtures, isolated under temporary directories. |
| `run_helper_tests.py` | Focused Phase 2 helper gate. |
| `runtime_cli.py` | CLI bridge used by the packaged skill runtimes. |
| `workflow.py` | Deterministic archive, skip, and interruption policies. |
| `workflow_fixtures.py` | Phase 3 trace and package-parity fixtures. |
| `candidate_quality_fixtures.py` | English/Spanish quality fixture catalog; semantic expectations need independent scoring. |
| `runtime_contract.md` | Progressive-disclosure envelope and helper reference. |
| `task_operations.md` | Progressive-disclosure Tasks DB queries and receipt rules. |
| `task_operations_newbeginning.md` | Opening-specific task reads and retry-safe creation; no task updates. |
| `sync_runtime_copies.py` | Regenerates identical deployable runtime copies in both skill folders. |
| `lifecycle_contract.md` | Approved normative lifecycle/test contract, relocated for implementation. |
| `run_contract_tests.py` | Runs the public deterministic contract and local-helper gates. |
| `validation/` | Frozen candidate identities, current local results, and pending forward-review gates. |

```bash
python skills/_shared/run_contract_tests.py
```

## The two ideas worth knowing

**Receipts are recomputed, not trusted.** A receipt asserting current database
state carries a `row_fingerprint`. The validator recomputes that fingerprint
from the returned rows rather than believing the asserted value. This does not
make fabrication impossible — rows and their hash could be fabricated together —
but it makes *drift between a claim and its cited evidence* mechanically
detectable, which is the failure mode actually observed in behavioral scoring.

**Retired checks leave both sides of the fraction.** When a check is withdrawn
with sign-off, it is excluded from the numerator *and* the denominator. Leaving
it in the denominator would make a correct run read as a regression, since a run
that follows the new rules fails the retired check by design. The counts
(`retained` / `mapped` / `retired`) are published with every score so the
adjustment is always visible.

## What this suite does not cover

It reports its own gaps on every run rather than implying full coverage:

- **All 15 fixture families** now have deterministic contract, helper, or
  workflow coverage. Phase 4 still supplies fresh controlled model runs; these
  fixtures do not impersonate behavioral evidence.
- **The historical-corpus scorer self-test** depends on a private evaluation
  ledger and lives alongside it. A green run here is not a full pass.

## Phase 2 enforcement boundary

`append_session_entry` validates the envelope, acquires a same-host advisory
lock, rechecks the observed tail hash, appends exactly one allocated session,
reads it back, and writes its journal record before releasing the lock. The tail
hash is the cross-device control; the lock cannot observe a Dropbox write from
another machine. `audit_session_log` detects direct writes after the fact and
grandfathers only the ceiling recorded once at Phase 2 start.

The bounded projection cap is **16,384 bytes**. It was selected from the largest
of the current project and three documented-maximum prototypes, with 25%
headroom rounded to a 4 KiB boundary. See the private Phase 2 measurement report.

`helpers.py`, `schemas.py`, `runtime_cli.py`, `workflow.py`, and the two runtime
references are the shared editable sources. Run `sync_runtime_copies.py` after
changing one; the Phase 3 package fixture fails if either deployable skill copy
drifts.

The task reference is deliberately different between the skills. The generator
uses `task_operations_newbeginning.md` for the opening package and
`task_operations.md` for closeout. Both copies remain generated and checked;
regeneration must not expand opening authority or remove reserved-ID retry
protection.

## Mutant discipline

Each mutant removes exactly one thing — a receipt, an approval, a readback, or a
required warning — and declares the failure code it must produce. A mutant that
fails a *different* code is a defect in the validator, not a pass. Sensitivity
was verified by weakening the validator: disabling the fingerprint recomputation
leaves exactly the fingerprint mutant alive, and disabling the approval gate
leaves exactly its two. One defect, one detector.

The valid-fixture check exists so the degenerate "reject everything" validator
cannot pass the mutant suite.

## Fixtures carry no real identifiers

Project refs, task IDs, and commit SHAs in fixtures are synthetic
(`proj-ref-placeholder`, `task-aaaa`, `0000000`). Tests assert by pattern, never
by literal private strings — a check that names what it forbids publishes it.
