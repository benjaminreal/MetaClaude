# On-demand source verification and refresh

Use this mode only when the owner asks to recheck already archived postings or update an identified difference set. Normal sync and triage do not run these operations. A recheck request authorizes comparison; it does not automatically authorize refreshing every difference.

## Freeze, capture, compare

Invoke the skill entrypoint with `--project-root ROOT --profile PROFILE` before the command. Use a new durable output directory for each phase. Read each phase's `--help` for the exact accepted arguments.

1. `audit-existing prepare --selected-id ID --out-dir SELECTION_DIR` freezes the selected numeric LinkedIn IDs, canonical tracker identities, archive paths and hashes before browser acquisition. Repeat `--selected-id` or use `--latest-n N`. Latest selection uses trustworthy consistently covered evidence when available; otherwise descending numeric Tracker ID is explicitly labelled `tracker_id_order_fallback`, not actual download chronology. Filesystem times and physical worksheet order are not authority.
2. Capture those exact IDs after the selection timestamp. Use the browser procedure below and `acquire-save` to retain the normalized capture bundle and its save/readback evidence. Keep failed attempts. Neither the comparison CLI nor a hash claims to have browsed.
3. `audit-existing compare --selection SELECTION --capture-bundle BUNDLE --out-dir AUDIT_DIR` validates and compares. Read the per-ID classifications and raw evidence, not only totals. A partial capture set must remain partial.

`audit-existing local-check --selection SELECTION --out-dir LOCAL_DIR` is a separate local-artifact inspection. Its `LOCAL_ARTIFACT_VALIDATION_ONLY` output does not verify the current source and cannot authorize refresh.

Each selected ID has one classification: `exact_match`, `match_whitespace_or_ui`, `substantive_difference`, `source_unavailable`, `capture_failed`, `unvisited`, or `identity_mismatch`. Missing visits are unvisited. Browser failures and incomplete expansion are capture failures. Unavailable requires an observed, fresh, ID-bound invalid/removed posting page. Full title/company mismatches stop automatic body refresh; retain pipe-containing titles intact.

Complete text requires independently observed ending evidence, source identity and recomputed hashes/quality. These gates validate supplied browser evidence and known failure patterns; they cannot manufacture evidence or prove an unseen source ending. A substantive current difference has `historical_cause: unresolved`: it does not prove whether the old capture was incomplete or the employer later edited it.

Preserve raw widget text, inline labels and URLs even when recognized UI content is excluded from comparison. Only whitespace and narrowly evidenced interface boundaries may normalize away. Employer benefits, salary, punctuation, case and added/removed sentences remain meaningful even when a separately identified interface widget is excluded.

## Browser procedure

Use only documented capabilities actually available on an authorized selected
surface. A private installation-local profile may express browser preferences;
the public skill defines no fixed order. Do not use
cookies/tokens, fetch/XHR, hidden endpoints, private-endpoint scripts or the
retired project pipeline for this workflow.

For each attempt confirm visible canonical URL/ID, full title and company; expand the actual description and wait for expansion to settle. Read the complete body through an independently observed final section. Preserve inline link labels and URLs and source/widget metadata. Native captures use ordered JD-only `role=text|link` nodes with `native_scope=job_description_only`; retain URLs in the capture evidence fields described by the command contract.

Allow one initial attempt and one corrective retry per surface unless the
active private profile supplies another bound, then fall back or report the
blocker. Following a tab/browser crash, re-read current UI state and rebind
before retrying. Preserve attempts and uncertainty. Every surface must stop on
uncertain identity or text binding. An exact 512-character native node remains
blocked unless a distinct complete fresh capture resolves it under the existing
capture-quality contract.

Save the capture through `acquire-save`, inspect its readback, and use its normalized output for comparison. Do not hand-mark incomplete captures complete to satisfy a schema. Freshness includes any independent capture used to resolve a quality suspicion.

## Capture evidence fields

Keep optional raw metadata under `source_evidence`, separate from the strict `quality_evidence` object. Use `inline_links: [{"label": "Company careers", "url": "https://example.com/careers"}]`, `inline_urls`, `widget_text`, `raw_text`, `observed_sections` and `boundary_notes` as applicable. Do not invent missing links or boundaries. A declared `capture_path`/`capture_sha256` pair must refer to a retained file whose bytes match; the description hash and bundle hash are different evidence and must not be relabelled as that file's hash.

Use failure `failure_kind: "capture_failed"` for an unsuccessful attempt and `"source_unavailable"` only for an observed removed/invalid page. Retain `reason`, `attempts` and `status_uncertainty`. Unavailable `evidence` must be a structured object with the exact selected numeric `id`, exact canonical URL `https://www.linkedin.com/jobs/view/{id}/`, nonempty `browser`, supported `method` (`rendered_dom_text` or `native_text`), timezone-bearing `captured_at`, and `status` equal to one of `invalid`, `removed` or `unavailable`. The status is an enum, not a substring search over notes or page text; an open page with an unrelated `closed` word remains a capture failure. Missing attempts stay unvisited. Follow the validator's precise accepted fields; do not add invented completion booleans to bypass a failure.

## Preview and refresh

`refresh-existing --audit AUDIT --selected-id ID --out-dir REFRESH_DIR` creates a preview only. Select the exact owner-authorized substantive differences. Use `--approve-all-substantive` only when the owner requested the whole difference set. Matching, unavailable, failed, unvisited, identity-mismatched and local-only results cannot refresh.

Review the emitted preview manifest and diff. Apply that exact manifest using the entrypoint's global `--commit` **before** `refresh-existing --preview-manifest MANIFEST`. Existing explicit owner authorization is sufficient; do not ask for redundant confirmation. A recheck-only request still needs owner authorization for the proposed updates.

Refresh preserves the existing Markdown header bytes and path, replaces only the description body, and regenerates compensation evidence from the exact proposed bytes through the installed source-only parser. Missing or identity-conflicting prior sidecars block refresh; separate repair requires its own scope. No salary estimation, currency conversion, triage, tracker status or workbook write is included.

All targets and source inputs are revalidated and staged before writes. History remains in the durable run's before copies, manifest, audit and journal. Replacement is atomic per file, not for a posting/sidecar pair or whole batch. Each replacement rechecks expected old bytes. Rollback restores only bytes still matching this run's replacement; concurrent edits remain intact and produce an explicit partial-recovery conflict. Read the final receipt before reporting success. A replay succeeds as `already_applied` only when the recorded after hashes still match; other drift requires a new preview/audit as reported by the command.

If the process exits during a commit, rerun the same preview manifest to invoke journal recovery before normal stale-input checks. Recovery returns a rolled-back or partial-recovery receipt; it does not silently resume the write batch. Inspect that receipt and create a new preview/run for another authorized attempt. Concurrent additions or edits remain intact and prevent a clean-success claim. A successful replay also rechecks the tracker and posting population.
# Eligibility during refresh

Selection baselines may record the canonical eligibility path and optional hash. Missing evidence does not invalidate description comparison. A V2 refresh regenerates compensation and eligibility from the same staged Markdown bytes; capture time is retained only from the validated audit bundle. Legacy V1 refresh authorization never creates eligibility evidence. See [eligibility evidence](eligibility_evidence.md).
