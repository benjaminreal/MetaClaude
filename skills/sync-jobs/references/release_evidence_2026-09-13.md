# Sync-jobs 2.5 release evidence — 2026-09-13

This is dated evidence for the public engine branch. It is not evidence that
the skill was installed, promoted, used against an authenticated account, or
allowed to write a live tracker.

## Deterministic evidence

- The pre-feature v2.3.0 engine baseline passed 80 tests.
- The source-acquisition implementation passed 99 tests before the public
  privacy remediation.
- The cohesive post-review suite passed 120 tests after the nine confirmed
  findings were covered.
- Skill validation and Python compilation passed.
- Fixtures cover supported public ATS APIs, JSON-LD, bounded static HTML,
  multiple postings, JavaScript shells, login walls, CAPTCHA, expiration,
  exact JSON-LD URL binding, camelCase description containers, explicit
  truncation rejection, single-resolution socket pinning, redirect and secret
  URL guards, streaming compression boundaries, fallback resume/merge,
  stable-provider identity aliases, Excel literal-text round trips,
  temporary-workspace V2 ingestion, tamper rejection, and package triggers.

## Bounded public canaries

No tracker write, browser automation, credential access or authenticated
request occurred.

| Selected source category | Observed result |
|---|---|
| Greenhouse public posting | `official_api`, complete `PASS` record |
| Lever public posting | incomplete API attempt retained, then `public_json_ld`, complete `PASS` record |
| SmartRecruiters public posting | `official_api`, complete `PASS` record |
| LinkedIn public detail URL | no HTTP request; retained `browser_required` handoff |
| Indeed public detail URL | HTTP 401 retained as `authentication_or_access_required`; browser fallback required |
| Generic employer page A | HTTP 200 extraction retained, but a required field was missing; browser fallback required |
| Generic employer page B | HTTP 403 retained as `authentication_or_access_required`; browser fallback required |

Transient canary paths, individual posting identifiers and local environment
paths are intentionally excluded from this public receipt.

## Dependency decision

No acquisition dependency was added. The standard library met the bounded
transport and parsing contracts. `httpx`, `extruct`, `trafilatura`, Beautiful
Soup and `lxml` remain deferred. Playwright and JobSpy were not accepted as
core acquisition dependencies. The pinned spreadsheet dependency remains
limited to tracker operations. See
[dependency evaluation](dependency_evaluation.md).

## Privacy boundary

- The public package contains only `profiles/example`, a synthetic interface
  fixture with no real facts, targets, thresholds or preferences.
- Production profiles are private installation-local overlays and require a
  separate promotion review.
- The feature branch must be rewritten or squashed onto the public base before
  publication; deleting a private profile in a later commit is not sufficient.

## Outstanding supervised gates

- Qualify each authorized browser surface that will actually be used.
- Run explicitly authorized LinkedIn detail and Saved/In Progress checks.
- Complete one live owner-selected end-to-end ingestion dry run.
- Test the pinned tracker dependency in a clean isolated environment.
- Forward-test realistic prompts with a private profile only in an authorized
  non-public workspace.
- Repeat public canaries after review; deterministic transport tests do not
  prove every provider remains anonymously accessible.

Promotion or installation requires separate approval. Fixture or public-canary
success does not authorize tracker mutation.
