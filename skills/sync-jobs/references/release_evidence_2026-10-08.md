# Sync-jobs candidate remediation evidence — 2026-10-08

This receipt covers local code remediation and synthetic validation. It does
not establish live source availability, authenticated browser readiness,
installation, or authorization to change a real tracker.

## Changes and checks

- Tracker operations use the wrapper; the external-intake helper is no longer
  directly executable.
- Expected read failures, rejected API destinations and excessive JSON structure remain per-URL failures;
  later selected postings receive independent acquisition budgets.
- Posting deadlines interrupt slow header/body reads. DNS waiting and its
  outstanding daemon workers are bounded; expired system lookups may remain
  in one of two slots until the system call returns.
- Worklist, diff and report outputs are private and create-only. Staged
  workbooks and full backups use private run directories and file modes.
- First-difference previews use a bounded linear scan; full-body classifications
  and hashes retain their equality/substantive-difference meaning.
- Generic newer profile output columns coexist with legacy columns. Synthetic
  integration verifies zero values, assess-only state, discarded reasons and
  links, profile binding, write re-derivation and explicit backup-parent routing.
- Isolated Python 3.12 with openpyxl 3.1.5: 140 unittest cases passed, with zero
  failures, errors or skips. Skill quick validation, Python syntax validation
  and the Git whitespace/error check passed.
- A GPT-6-Luna xhigh review found no demonstrated blockers. A subsequent
  Claude Opus 5.5 medium review found an API safety-rejection regression that
  aborted the batch. The local correction restores per-URL failure retention;
  a synthetic batch regression covers private DNS answers and localhost
  redirects, including successful acquisition of a later posting. Opus reviewed
  the preceding snapshot, not the corrected candidate.

## Remaining coverage and limits

The independent review observed scorer-created JSON and preview files with
ordinary umask permissions. This pre-existing profile-owned behavior remains
outside the five fixes. Keep those files in private run directories; the engine
does not claim that every profile-produced artifact is mode 0600.
Workflow examples now use a unique private temporary directory.

Opus also identified, from code reading only, that TLS handshakes can overrun
the nominal posting deadline by up to the socket inactivity timeout (15 seconds
by default). The handshake remains bounded by that timeout; a live slow TLS
server was not tested.

Only synthetic profiles and disposable workbooks were used. The public package
still contains only the synthetic example profile; production profiles remain
installation-local. This candidate has not been installed.
No external extraction dependency was added.

The public canaries in the [September receipt](release_evidence_2026-09-13.md)
are historical. Current authenticated posting/index capture, browser fallback,
live tracker behavior and promotion/installation remain unqualified here.

## Follow-up: score output symlink protection

The score wrapper now supplies isolated staging paths to the selected policy
instead of the caller's result and preview paths. It validates staged regular
files, adds profile metadata, then publishes to fresh destinations without
following output symlinks. Existing and dangling links, duplicate outputs,
worklist aliases and destinations introduced during scoring are refused.
Resolved destination directory descriptors remain pinned during publication.
The result and preview use the existing mode-0600 publication helper; the
earlier scorer-file permission observation above describes the prior snapshot.

The focused profile module passed 9 tests. The complete isolated Python 3.12
suite with openpyxl 3.1.5 passed 146 tests, with zero failures, errors or skips.
Synthetic cases preserve linked target bytes, cover output option forms and
abbreviations, validate staging cleanup and retain normal legacy/newer scoring,
profile binding, reports and tracker-write checks. Skill quick validation and
the Git whitespace/error check passed. Directory replacement and the final
publication-race interval were inspected in code rather than directly injected
in tests. This follow-up does not change refresh journals or installation-local
profiles and has not been installed.
