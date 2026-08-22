# Evals

Run from the skill root:

```bash
python3 evals/structural_eval.py
python3 scripts/release_privacy_scan.py
```

The suite validates the release privacy gate, canonical target, planner gate order,
both schema versions, structural-first enforcement, six named V3 behavioral
fixtures, one-defect mutants, Hunter unavailable/unauthenticated/wrong-scope
fallbacks, CLI behavior, and explicit V2 refusal.

`fixtures/valid_dossier.json` is synthetic V3 and must pass. `fixtures/invalid_apex_dossier.json` is the preserved historical V2 invalid fixture and must fail with `LEGACY_SCHEMA_REFUSED`; it is not rewritten as V3.

The suite makes no network call and spends no credits. It cannot establish live search quality, current profile access, source truth, channel deliverability, reply/screen efficacy, production readiness, installation, or release authorization.
