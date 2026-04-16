# Examples

Real outputs from past triangulations — Phase 1 prompts, platform reports, and
consolidations — kept here as quality references.

## Purpose (what this is not)

This directory is distinct from `evals/fixtures/`:

- **`evals/fixtures/`** — synthetic, minimal, structurally-conformant files used by
  `evals/structural_eval.py` to exercise the naming-convention and metadata-header
  checks. Their job is to pass lints, not to demonstrate research quality.
- **`examples/`** (this directory) — actual outputs from real triangulations that
  you want to preserve as quality anchors. Useful when debugging "what does a good
  Phase 1 prompt look like?" or "what does an acceptable consolidation produce?"
  without having to re-run a full cycle.

## What belongs here

Representative artifacts from a triangulation worth archiving. A complete example
bundle typically includes:

- the operator handoff file (`handoff_<topic>.md`)
- all Phase 1 prompt files (`prompt_<Platform>-<Pass>_<topic>.md`)
- all Phase 1 reports (`<Platform>-<Pass>_<topic>_<date>.md`)
- the consolidation prompt (`consolidation_<topic>.md`)
- the consolidated report (`consolidated_<topic>.md`)
- scorecards (`scorecard_*.json`)

Group a complete bundle into a subdirectory named after the topic:

```
examples/
├── README.md (this file)
├── <topic-slug>_<date>/
│   ├── handoff_<topic>.md
│   ├── prompt_Claude-DR_<topic>.md
│   ├── Claude-DR_<topic>_<date>.md
│   ├── ...
│   └── consolidated_<topic>.md
└── <another-topic-slug>_<date>/
    └── ...
```

## What does NOT belong here

- Synthetic fixtures — those live in `evals/fixtures/`.
- Incomplete bundles where key files were never collected — archive these
  elsewhere, or don't. An example with missing pieces is misleading to future
  readers who treat the directory as a reference.
- Anything containing confidential client material, personally identifying
  information, or vendor-confidential data without explicit review. Examples are
  archival but also readable — apply the same redaction standards you would to
  any shared work product.

## Curation principle

Not every triangulation needs to land here. Archive examples that are either
(a) unusually good and worth emulating, (b) unusually instructive about a specific
failure mode or platform behavior, or (c) topically important enough that
re-running them from scratch would be expensive. Noise accumulation defeats the
purpose; quality beats quantity.

## Current state

*Empty — pending first real triangulation. Populate when a run produces archival
material.*
