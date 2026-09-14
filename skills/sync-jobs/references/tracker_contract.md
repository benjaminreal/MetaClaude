# Excel adapter contract

Supported workbook: a `Jobs` sheet, header-driven columns, and optional `JobsTable`. Default filename is supplied by the selected profile; `--tracker` can override it within the selected workspace. Postings and reports use `JobPostings/postings` and `JobPostings/_meta` under that workspace.

Ingest requires Tracker ID, Previous Row, Puesto, Empresa, Pais, Estatus, Next Action, JD File, Link puesto linkedin and Comentarios. Allocate monotonically increasing J-###### IDs. Append raw Saved/In-progress rows, link archived JDs, extend the table, and preserve existing row values. No title-derived fit score.

Triage writes only the existing writer's allowlisted columns; match by Tracker ID rather than row number. Preserve identity, application date and existing advanced lifecycle state. Append audit comments rather than replacing them. Candidate decision rules belong in the selected profile; header spellings and table layout belong in this adapter.

Before commit, check the Excel lock and inspect a dry-run. After commit, verify row counts, unique IDs, archive links, intended header changes and output presence. Run reports and posting artifacts are project data, never skill resources.

A historical row with Estatus=Duplicate remains intact. It can be excluded from the active LinkedIn-ID map only when its Comentarios explicitly names one `DUPLICATE of J-...` keeper and that unique non-Duplicate keeper carries the same LinkedIn ID. This keeper requirement applies only to actual same-LinkedIn-ID collisions. Unique LinkedIn IDs marked Duplicate remain ingested historical rows even without keeper annotations. Missing or conflicting keeper links on collisions still stop sync. Duplicate Tracker IDs always remain an error.
