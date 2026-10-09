# Sync-jobs 2.6.0 evidence — 2026-10-09

This receipt covers local code changes and synthetic validation. It does not
establish installation, live LinkedIn capture or authorization to change a
real tracker.

## Changes

- Duplicate lifecycle lock. `build_worklist` marks rows whose Estatus is
  Duplicate as assess-only, the example profile honours it, and the writer
  aborts the whole batch before saving if any result would change Estatus or
  Next Action on a Duplicate row, or append to them. Other cells on the row may
  still refresh. This guard holds whatever the selected profile returns.
- SAVED reported-total surplus. A saved index whose LinkedIn SAVED total
  exceeds the unique jobs retrieved is accepted only with `card` SAVED,
  `pagination_complete` true and `termination` `total_reached` or
  `empty_page`; the gap is logged. IN_PROGRESS, incomplete pagination, a
  retrieved count above the total and acquisition errors still block. Ported
  from the 20 September 2026 installation-local correction, which postdated
  the imported 2.3.0 baseline.

## Checks

- Isolated Python 3.12.13 with openpyxl 3.1.5: 147 unittest cases passed.
- Both new tests (`test_writer_never_changes_duplicate_lifecycle`,
  `test_saved_reported_total_surplus_requires_completion`) fail against the
  2.5.0 scripts and pass against 2.6.0.
- Git whitespace check passed.

Only synthetic profiles and disposable workbooks were used. This candidate
has not been installed.
