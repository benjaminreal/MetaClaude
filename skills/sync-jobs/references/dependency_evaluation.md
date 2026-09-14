# Acquisition dependency decision

Decision date: 2026-09-13. Runtime inspected: Python 3.13.7.

## Decision

The 2.4 acquisition core adds no external dependency. Python's standard
library covers bounded HTTP, redirect control, DNS/IP safety, JSON, JSON-LD,
HTML parsing, decompression limits, hashing, atomic output, and the initial ATS
adapters. Fixture tests demonstrate those contracts without network access.

The inspected python.org macOS runtime did not expose a populated default CA
file, while the host-maintained `/etc/ssl/cert.pem` bundle was present. The
transport now selects that system bundle only when Python has no default CA
file. Certificate verification remains enabled; there is no unverified TLS
mode or bundled third-party CA dependency. A bounded public canary confirmed
verified HTTPS after this fallback was added.

`openpyxl==3.1.5` remains the sole declared dependency for tracker operations.
It was present at the pinned version and exercised by the inherited tracker
suite. The early `acquire-url` route does not import tracker modules or require
`openpyxl`.

## Candidates considered

| Candidate | Host availability | Decision |
|---|---:|---|
| `httpx` | Present | Deferred; no demonstrated fidelity or control gain over the bounded standard-library transport. |
| `extruct` | Absent | Deferred; the focused JSON-LD parser passes current multi-object and URL-binding fixtures. |
| `trafilatura` | Absent | Deferred; broad article extraction could confuse landing pages with one posting without stronger bindings. |
| Beautiful Soup | Present, undeclared | Deferred; the focused parser currently has a smaller dependency and attack surface. |
| `lxml` | Present, undeclared | Deferred; native components and packaging weight have not earned inclusion. |
| Playwright | Absent | Rejected as a core dependency; authorized interactive browser surfaces provide the intended authenticated fallback without credential export. |
| JobSpy | Absent | Rejected as a core/LinkedIn path; it is search-oriented, unofficial scraping and does not satisfy the selected-URL provenance contract. |

Host availability is not a portability guarantee. No candidate was installed,
downloaded, or exercised against authenticated state during this decision.

## Reconsideration gate

Reconsider one dependency only after a sanitized failing fixture and a bounded
public canary demonstrate a specific gap. Compare exact description fidelity,
end-boundary evidence, redirect/timeout/size behavior, Python compatibility,
license, maintenance, transitive risk, and clean-environment installation.
Keep it optional unless core behavior cannot be implemented safely without it.

The clean-environment dependency installation gate remains unverified for this
branch because no new dependency was proposed and network installation was not
needed. Before promotion, run the full suite in an isolated environment with
the pinned `requirements.txt` and record the result.
