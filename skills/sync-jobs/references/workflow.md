# Workflow and stage contracts

Set `SKILL` to the installed skill directory and `ROOT` to the chosen project directory. Use a unique run directory under /tmp for intermediate files and previews. These commands do not require the old project scripts.

```bash
PROFILE_ID="<profile-id>"
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" diff --saved-json /tmp/run/saved.json /tmp/run/in_progress.json --out /tmp/run/new.json
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" ingest --jobs-json /tmp/run/acquisition.json --saved-json /tmp/run/saved.json /tmp/run/in_progress.json
# After inspecting the rehearsal, commit an authorized sync:
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" --commit ingest --jobs-json /tmp/run/acquisition.json --saved-json /tmp/run/saved.json /tmp/run/in_progress.json
# Always available, including zero-new runs; does not write the tracker:
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" reconcile --saved-json /tmp/run/saved.json /tmp/run/in_progress.json --out-dir /tmp/run/reconciliation
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" worklist --out /tmp/run/worklist.json
# Select this batch's Tracker IDs, read the JDs, then fill judgment blocks.
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" score --worklist /tmp/run/worklist.json --out /tmp/run/results.json --preview /tmp/run/preview.txt
# Check the report before committing: it enforces discarded reasons and posting links.
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" report --worklist /tmp/run/worklist.json --results /tmp/run/results.json --out /tmp/run/report.md
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" write --results /tmp/run/results.json --worklist /tmp/run/worklist.json
# Add --commit before write only after checking the dry-run.

# Owner-selected direct employer or organization URLs use a separate source-neutral ingest.
python3 "$SKILL/scripts/sync_jobs.py" acquire-url \
  --url "https://employer.example/jobs/123" --out /tmp/run/source_acquisition.json
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" external-ingest --records-json /tmp/run/source_acquisition.json
python3 "$SKILL/scripts/sync_jobs.py" --project-root "$ROOT" --profile "$PROFILE_ID" --commit external-ingest --records-json /tmp/run/source_acquisition.json
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

Input saved-list shape: `{count,total,error,jobs:[{id,company,role,location,status,url}]}`. Capture full descriptions with `acquire-save` using [capture quality](acquisition_quality.md), then pass its `SelectedPostingAcquisitionV1` output directly to `ingest`. Backfill missing company/title from the corresponding index record before capture validation, not by inference. An incomplete or failed index is not a reconciliation input.

Ingest recomputes the capture and quality contracts for every description it would write. A new job or tracker-only recovery cannot use a legacy bare list, `jobs` wrapper or hand-made record to bypass URL/ID binding, provenance, ordered native nodes, verified ending, truncation flags or independent resolution. An archive-only recovery reuses existing archive bytes without falsely certifying them as a fresh capture; an already-canonical tracker/archive pair is skipped idempotently.

The tracker and archive are checked separately. Diff reports recovery IDs; archive-only records can supply metadata for a missing row without rewriting their bytes. Tracker-only records retain their Tracker ID, status and other cells when the missing JD is restored. A blank JD link may be repaired. Ambiguous sources or conflict with a preserved compensation-source binding stop the batch before writes. Recovery of records outside the input batch is reported explicitly, not silently treated as complete. Empty-input runs cannot claim consistency when mismatches remain.

Saved indexes require count, total, error and jobs. Count mismatches or
incomplete pagination block diff, ingest and reconciliation. Ingest checks the
index before any writes.

Triage preflights every result ID and requested header before changing cells, rejects missing/duplicate IDs, saves to a temporary workbook, verifies the saved cells and checks the original workbook has not changed before replacing it. Formula targets are protected; an intended replacement of a formula blocks the write instead of reporting partial success.
# Eligibility evidence

New or recovered-description ingest writes a hash-bound eligibility sidecar alongside compensation. Worklists reference it without filling `Sponsor Status`; missing historical evidence stays non-blocking. See [eligibility evidence](eligibility_evidence.md). Authorized description refresh uses an explicit three-file V2 transaction, while legacy V1 authorization remains two-file only.
