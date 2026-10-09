# Workflow and stage contracts

Set `SKILL` to the installed skill directory and `ROOT` to the chosen project directory. Use a unique private run directory for intermediate files and previews. Stage the saved-list and acquisition inputs there before running these commands. These commands do not require the old project scripts.

```bash
PROFILE_ID="<profile-id>"
SYNC_RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sync-jobs-run.XXXXXX")"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" diff --saved-json "$SYNC_RUN_DIR/saved.json" "$SYNC_RUN_DIR/in_progress.json" --out "$SYNC_RUN_DIR/new.json"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" ingest --jobs-json "$SYNC_RUN_DIR/acquisition.json" --saved-json "$SYNC_RUN_DIR/saved.json" "$SYNC_RUN_DIR/in_progress.json"
# After inspecting the rehearsal, commit an authorized sync:
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" --commit ingest --jobs-json "$SYNC_RUN_DIR/acquisition.json" --saved-json "$SYNC_RUN_DIR/saved.json" "$SYNC_RUN_DIR/in_progress.json"
# Always available, including zero-new runs; does not write the tracker:
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" reconcile --saved-json "$SYNC_RUN_DIR/saved.json" "$SYNC_RUN_DIR/in_progress.json" --out-dir "$SYNC_RUN_DIR/reconciliation"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" worklist --out "$SYNC_RUN_DIR/worklist.json"
# Select this batch's Tracker IDs, read the JDs, then fill judgment blocks.
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" score --worklist "$SYNC_RUN_DIR/worklist.json" --out "$SYNC_RUN_DIR/results.json" --preview "$SYNC_RUN_DIR/preview.txt"
# Check the report before committing: it enforces discarded reasons and posting links.
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" report --worklist "$SYNC_RUN_DIR/worklist.json" --results "$SYNC_RUN_DIR/results.json" --out "$SYNC_RUN_DIR/report.md"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" write --results "$SYNC_RUN_DIR/results.json" --worklist "$SYNC_RUN_DIR/worklist.json"
# Add --commit before write only after checking the dry-run.

# Owner-selected direct employer or organization URLs use a separate source-neutral ingest.
python3 "$SKILL/scripts/sync_jobs.py" acquire-url \
  --url "https://employer.example/jobs/123" --out "$SYNC_RUN_DIR/source_acquisition.json"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" external-ingest --records-json "$SYNC_RUN_DIR/source_acquisition.json"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" --commit external-ingest --records-json "$SYNC_RUN_DIR/source_acquisition.json"
```

| Stage | Input | Output |
|---|---|---|
| Acquire | Authenticated session, saved and in-progress tabs | Complete index JSON and new-job description JSON; errors listed |
| Acquire selected IDs | Explicit owner-selected IDs and authenticated browser text | Hashed evidence bundle with recomputed quality results; no official-new-ID or sync claim |
| Acquire selected URLs | Explicit owner-selected public URLs | `SourcePostingAcquisitionV2`; every URL is one passing record or retained failure; no tracker access |
| Diff | Index JSON, tracker and archived posting source IDs | New IDs; no writes to workspace |
| Ingest | Complete acquisition bundle, saved indexes | New posting Markdown, appended rows, compensation evidence sidecars, sync log; default dry-run writes only temporary files |
| Reconcile | Complete board index and tracker | Cleanup/FYI report; no board changes |
| Worklist | Pending tracker rows and JD locations | Rows with blank judgments; selector may include older pending work |
| Judge | Profile facts/rules, JDs, explicit current evidence | Human/agent-filled judgment fields |
| Score | Judgments and selected profile policy | Header-keyed verdicts and decision reasons |
| Report check | Worklist and verdicts | Review table, including links and plain-English reasons for discarded roles |
| Write | Checked verdicts | Backup, limited tracker changes, append-only audit comments |

The score result is bound to the explicitly selected profile ID, version and
policy hash. It also records the exact worklist/result scope. The write command
re-derives each result from that worklist and selected policy before writing.
Both legacy triage columns and the newer generic profile columns are supported;
only requested columns need to exist in the selected tracker. See
[profile compatibility and migration](profile_compatibility.md) before carrying
an installation-local profile across an engine update.

Score result and preview paths must be distinct, fresh destinations under
existing directories and must not alias the worklist. The wrapper stages both
outputs privately and publishes them create-only; existing files or symlinks,
including dangling links, cause scoring to stop without replacing their targets.

Unless `--report-name` is supplied, scoring creates a unique project-relative
report-batch path. The final report uses that path when `--out` is omitted. The
pre-write report check above uses a separate staging path. Report files are
private mode 0600 and create-only: choose a new staging or published path for
each report. If you choose a custom final `--out`, use the same value as
`--report-name` during scoring so the tracker pointer names the report that was
published.

Input saved-list shape: `{count,total,error,jobs:[{id,company,role,location,status,url}]}`. Capture full descriptions with `acquire-save` using [capture quality](acquisition_quality.md), then pass its `SelectedPostingAcquisitionV1` output directly to `ingest`. Backfill missing company/title from the corresponding index record before capture validation, not by inference. An incomplete or failed index is not a reconciliation input.

Ingest recomputes the capture and quality contracts for every description it would write. A new job or tracker-only recovery cannot use a legacy bare list, `jobs` wrapper or hand-made record to bypass URL/ID binding, provenance, ordered native nodes, verified ending, truncation flags or independent resolution. An archive-only recovery reuses existing archive bytes without falsely certifying them as a fresh capture; an already-canonical tracker/archive pair is skipped idempotently.

The tracker and archive are checked separately. Diff reports recovery IDs; archive-only records can supply metadata for a missing row without rewriting their bytes. Tracker-only records retain their Tracker ID, status and other cells when the missing JD is restored. A blank JD link may be repaired. Ambiguous sources or conflict with a preserved compensation-source binding stop the batch before writes. Recovery of records outside the input batch is reported explicitly, not silently treated as complete. Empty-input runs cannot claim consistency when mismatches remain.

Saved indexes require count, total, error and jobs. Count mismatches or
incomplete pagination block diff, ingest and reconciliation. Ingest checks the
index before any writes.

Triage preflights every result ID and requested header before changing cells, rejects missing/duplicate IDs, saves to a temporary workbook, verifies the saved cells and checks the original workbook has not changed before replacing it. Formula targets are protected; an intended replacement of a formula blocks the write instead of reporting partial success.
# Eligibility evidence

New or recovered-description ingest writes a hash-bound eligibility sidecar alongside compensation. Worklists reference it without filling `Sponsor Status`; missing historical evidence stays non-blocking. See [eligibility evidence](eligibility_evidence.md). Authorized description refresh uses an explicit three-file V2 transaction, while legacy V1 authorization remains two-file only.
