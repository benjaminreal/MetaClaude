# Eligibility evidence

`PostingEligibilityV1` lives at `JobPostings/_meta/eligibility/<Tracker ID>_PostingEligibilityV1.json`. It binds exact archived Markdown bytes, source identity, exact quotation offsets, and provenance-bound capture time when validated acquisition evidence supplies one. Extraction time and capture time are different facts; local inspection has a null capture time.

The automated scan records source topics: employer visa sponsorship wording, work-authorization requirements, relocation support, citizenship restrictions, and security restrictions. It preserves negation, conflicts, region conditions, and unfamiliar candidate spans. These observations are not legal conclusions or candidate verdicts. Read the complete JD and the selected profile before filling judgment fields. Keep relocation separate from sponsorship.

`NO_MATCHES_DETECTED` has the user-facing label `NOT STATED ON SOURCE`. It states only that supported automated signals did not select a span. It is not proof of source-wide absence and never means that the employer will not sponsor. A missing historical sidecar is a separate non-blocking `missing` availability state.

New ingestion creates eligibility only when it writes new or recovered description bytes. Archive-only recovery and canonical old rows do not fabricate evidence. Worklist generation is read-only. An authorized substantive refresh uses a V2 three-file manifest for archive, compensation, and eligibility; a missing sidecar is an explicit atomic create. Legacy V1 refresh manifests remain limited to their original archive and compensation targets.
