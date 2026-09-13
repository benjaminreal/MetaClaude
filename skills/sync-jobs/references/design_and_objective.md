# Design and objective

Make acquisition, sync and optional triage usable without importing retired
project machinery. Keep reusable operations separate from private candidate
decisions and changing evidence.

| Layer | Owns | Does not own |
|---|---|---|
| Engine | Diff, source identity, archive creation, evidence sidecars, protected workbook writes, reconciliation and reports | Candidate suitability, salary targets, preferred countries or browser preferences |
| Adapters | Provider record shapes, public acquisition and the supported workbook schema | Candidate preferences or credentials |
| Private profile overlay | Candidate facts, targets, decision policy, thresholds and operating preferences | Live tracker state, new source evidence or browser credentials |
| Workspace | Tracker, postings, current evidence and run outputs | Executable skill code |

The public package includes `profiles/example` only to exercise the profile
interface. It contains no real candidate facts, targets, thresholds, geography
rules or browser preferences. A real user supplies a separately reviewed
installation-local profile overlay. Adding or changing that overlay does not
require changing ingestion or workbook-safety code.

Private profiles may reference separate facts, preferences and policy files.
They must not be copied into a public branch, test fixture, release receipt or
source-provenance manifest. Promotion of a public engine release and promotion
of a private profile are separate reviews.

Time-sensitive eligibility research is supplied per run, not embedded as a
universal engine rule. Exact-job decisions remain workspace evidence and must
not silently become standing policy. Engine changes are tested against storage,
evidence and workflow invariants using synthetic inputs.

The workbook adapter supports the documented Jobs-table schema rather than
arbitrary spreadsheets. Its column labels are storage-format details. The
LinkedIn adapter is provider-specific, not person-specific.

No Apply Pack orchestrator, application renderer, console or registration
machinery is included. Compensation parsing is limited to source observations
for intake evidence. Historical migration inputs and their local paths are not
runtime dependencies or public-package provenance.
