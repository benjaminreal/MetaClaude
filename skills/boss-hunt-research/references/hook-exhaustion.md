# Hook Exhaustion and Evidence Binding — V2

## Structured intent identity

One intent is a structured evidence hypothesis, not a query string. Record:

- `subject`: person, company, or JD target;
- `claim`: the evidence proposition being tested;
- `surface_family`: the source family on which it is tested.

The validator normalizes these three fields and recomputes `canonical_fingerprint`. Rewording `query_or_action`, changing Boolean syntax, or reaching the same hypothesis through another search engine cannot create another intent. Duplicate fingerprints fail with `HOOK_INTENT_DUPLICATE_FINGERPRINT`. A blocked surface does not satisfy an accessible minimum.

## Families and minimums

| Family | Accessible minimum before generic fallback |
|---|---:|
| `RECIPIENT_AUTHORED` | 2 |
| `RECIPIENT_SPEAKING` | 1 |
| `EMPLOYER_PERSON_ATTRIBUTION` | 1 |
| `COMPANY_MANDATE` | 1 |
| `JD_CONTEXT` | 1 for live/post-application; not required for proactive-company |
| `ATTRIBUTION_REFUTATION` | 1 |

Accessible means `HIT` or `MISS`. `BLOCKED` and `NOT_APPLICABLE` do not count.

## Recipient-specific early success

Stop the content ladder early only when an exact recipient-specific artifact is supported, attributed to the person, bound to the current run, selected by one recipient-family intent, and survives at least one accessible attribution-refutation intent. Route/currentness, candidate-proof, guard, channel, and independent-review gates still apply.

## Generic fallback

`GENERIC_COMPANY` or `GENERIC_JD` is allowed only after all relevant minimums pass, none of the four recipient-specific intents supplies the selected hook, and the selected company/JD intent exactly matches the hook evidence binding. Generic means exact supported company/JD context with honest attribution, never an unsupported compliment.

## Exact evidence binding

For a supported hook, `hook.evidence_binding` and the selected intent must match on:

- intent ID;
- exact artifact/result URL;
- content SHA-256;
- run ID.

Any mismatch fails. When a surface cannot expose stable content bytes, store the hash of the canonical captured representation used for review and name that representation in the evidence reference; do not invent a page-content hash.

## Independent review

Automatic research promotion requires the six named review checks, each with its own verdict and evidence references, inside a separate record bound to the dossier subject hash. Reviewer-ID inequality alone is insufficient.
