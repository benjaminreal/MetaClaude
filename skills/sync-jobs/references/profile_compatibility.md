# Profile compatibility and migration

The public package contains the synthetic `example` profile only. Keep real
profiles, policy code, judgment templates and candidate data in the installation
that owns them. Updating this engine does not select, copy, rewrite or promote a
profile. Continue to pass its ID explicitly with `--profile`.

The generic writer accepts both the legacy output columns (`Track`, `Fit Score`,
`Priority` and the existing triage fields) and the newer profile columns
(`Lane`, `Market Tier`, `Eligibility`, `Priority Score`, and `Match`). Each
selected profile may emit the subset its tracker supports. A result containing
an unrecognized column is rejected before tracker access; the writer also
requires every requested header to exist in the selected workbook. Numeric zero
and boolean false remain data and are shown in reports.

When carrying an existing installation-local profile across an engine update,
keep its ID and policy intact, select it explicitly, and confirm the tracker has
the headers its results request. Scoring binds the result file to the selected
profile ID, version and policy SHA-256. A changed policy or selection requires
fresh scoring before report or write; the write gate also checks that results
still derive from the supplied worklist. No thresholds or personal preferences
are supplied by the public package.

Legacy result fields remain reportable. When newer generic fields are present,
the report labels `Fit Score` and `Priority` as legacy references so they do not
look like the active eligibility or priority outputs. Held and assess-only rows
remain in the report with their lifecycle state shown. A discarded result
requires both a plain-English reason and a posting URL before the report can be
published or a write can proceed.

Scoring assigns a unique project-relative report batch path unless
`--report-name` is supplied. The profile policy must accept `--report-name` as
part of the score command interface. A final report published without `--out`
uses that exact batch path. Reports are create-only mode-0600 files: an existing
destination is never replaced. For a staging review, pass a new path such as
`/tmp/run/report.md`; for another published batch, score again or provide a new
batch name and use that same path when reporting.

The score wrapper gives the selected profile private staging paths for its
result and preview, adds the profile binding to the staged result, then
publishes both as mode-0600 create-only files. Choose distinct fresh paths under
existing directories, separate from the source worklist; existing files and
symlinks, including dangling links, are refused. Resolved destination directories
are pinned for the scoring run, and a changed parent or a destination that
appears during scoring stops publication.

`write` rehearses by default and produces a private dry-run workbook. Use
`--commit` only after reviewing the rehearsal for an authorized tracker update.
