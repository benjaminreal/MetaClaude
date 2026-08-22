# Release Privacy and Publication Gate

Run this gate before publishing or installing a changed source tree:

```bash
python3 scripts/release_privacy_scan.py
```

After staging the exact Git release surface, also run:

```bash
python3 scripts/release_privacy_scan.py --require-git-tracked
```

The offline scanner covers every publishable UTF-8 skill file while excluding
runtime debris and generated install metadata. It rejects owner-specific home or
mounted-volume paths, non-synthetic email domains, private-key markers,
credential-like assignments, common high-signal token shapes, binary publication
files, and files absent from the Git index when tracking enforcement is requested.
Reserved `example.com`, `example.net`, `example.org`, and `example.invalid`
addresses are permitted only for synthetic fixtures.

A PASS is a bounded release control, not proof that no sensitive information can
exist. Maintainers must still review the staged diff, confirm that examples are
synthetic, run the generic skill validator when available, execute the complete
portable suite from a clean checkout, and keep live credentials and captured
research evidence outside the skill tree.
