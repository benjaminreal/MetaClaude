# Structural Eval — research-triangulation

Deterministic checks on the skill's own source files and golden-output fixtures.
Runs in seconds, exits non-zero on any failure.

## How to run

From the skill root:

```bash
python evals/structural_eval.py
```

Or from anywhere:

```bash
python /path/to/skills/multi-platform-research/evals/structural_eval.py
```

No dependencies beyond the Python 3.10+ standard library.

## What this covers

Six checks:

1. **Parameter Dictionary completeness.** Every `{{VAR}}` referenced in
   `references/phase1-templates.md` appears in the Parameter Dictionary, and
   every entry in the dictionary is actually used somewhere in the templates.
   Catches renames that miss one side and dead parameters that no template uses.
2. **Reference-file integrity.** Every file listed in SKILL.md's "Reference
   Files" table exists on disk and is non-empty.
3. **Pass-type consistency.** The "Valid pass types per platform" table in
   `references/phase1-templates.md` matches the contract hard-coded in
   `structural_eval.py` (`EXPECTED_VALID_PASS_TYPES`), and every example
   filename throughout the templates file uses only pass types the table
   declares valid for that platform.
4. **Metadata schema consistency.** The YAML header spec in the Metadata Header
   subsection of `references/phase1-templates.md` declares exactly the keys
   the script considers required (`REQUIRED_METADATA_KEYS`). Catches silent
   divergence between the template's schema and any downstream tool that
   depends on it.
5. **Fixture filenames.** Every `.md` file under `fixtures/` matches the
   prompt-file pattern or the report-file pattern declared in the File Naming
   Convention table, and the embedded platform + pass combination is valid.
6. **Fixture metadata headers.** Every report-style fixture (named
   `{{PLATFORM}}-{{PASS}}_{{SLUG}}_{{DATE}}.md`) begins with a YAML
   front-matter block containing all required metadata keys. Prompt-style
   fixtures are exempt — prompts don't carry metadata headers; the reports
   they produce do.

## What this does NOT cover

- **Research quality.** Whether a report is actually good, well-sourced, free
  of hallucinations, covers the research questions — that's what the Tier 1
  and Tier 2 quality rubrics in `references/quality-rubric.md` are for.
- **Skill triggering.** Whether the skill description is good enough that a
  model decides to consult it on realistic prompts. That's a separate,
  non-deterministic question handled by `skill-creator`'s description-
  optimization loop.
- **Behavioral regression.** Whether a model, invoked with this skill and a
  real research prompt, actually produces outputs that conform to the
  structural conventions. That would require the full skill-creator eval
  loop with subagents running research-like tasks against every template
  revision. This script only verifies that the skill's own rules are
  internally consistent and that the reference fixtures comply.

The structural eval is a complement to those other tools, not a substitute.
It's cheap enough to run on every edit; they're not.

## When to run it

- After any edit to `SKILL.md`, `references/phase1-templates.md`, or
  `references/consolidation-template.md`.
- After renaming a parameter, adding a parameter, or removing a parameter.
- After changing the File Naming Convention or the Metadata Header schema.
- Before cutting a new version of the skill.

A useful pattern: run it right before committing. If it passes, the skill's
structural contracts are intact. If it fails, the output tells you exactly
which contract broke.

## Layout

```
evals/
├── README.md              (this file)
├── structural_eval.py     (the checks)
└── fixtures/
    ├── prompt_Claude-DR_sample-topic.md          (prompt-file fixture)
    └── Claude-DR_sample-topic_2026-04-15.md      (report-file fixture)
```

Fixtures are synthetic by design. They exist to exercise the structural lane,
not to illustrate what good research looks like. When the File Naming
Convention or Metadata Header schema changes, update the fixtures alongside
the templates — otherwise this eval will (correctly) start failing.

## Extending it

The script is ~350 lines of Python stdlib. New checks go in as functions that
return a list of issue strings (empty list = pass), then get added to the
`CHECKS` list at the bottom. Good candidates, if you decide to add them:

- Changelog coverage: every file path mentioned in the v1.x changelog exists
  on disk. (Doesn't verify content is what's claimed — but catches deletions.)
- Cross-file link integrity: every `references/<file>` backtick-mention in
  any markdown file resolves.
- Single-brace placeholder detection in `phase1-templates.md`: the v1.1 upgrade
  switched this file to `{{VAR}}` double-brace. A stray single-brace `{VAR}`
  is almost always a regression. (Note: `references/consolidation-template.md`
  still uses single-brace pending the BACKLOG.md conversion item — if you
  add this check, scope it to phase1-templates.md only until consolidation
  is converted.)
