# MetaClaude

A personal workspace of [Claude](https://claude.ai) skills. Everything here is designed for my own use; it's published in case any of it is useful to someone else working through the same problems.

Nothing in this repository is endorsed by or affiliated with Anthropic.

## What's a skill?

A Claude skill is a folder with a `SKILL.md` file — frontmatter describing when the skill should trigger, followed by instructions the model reads before acting. Claude loads the description into its selection pool at session start and reads the full file only when a trigger matches. Skills let you pre-commit methodology, file conventions, and quality rubrics so Claude applies them consistently instead of reasoning them out each time.

Skills install as a folder under `~/.claude/skills/` (Claude Code) or via the **Save skill** button in Cowork mode when you open a `.skill` archive.

## Skills in this repo

| Skill | Latest | Status | One-liner |
|---|---|---|---|
| [`closingtime`](./skills/closingtime/) | v2.0 | Shipped | Session-closing capture — drafts a session entry, updates the project index, extracts Open Brain learning candidates, runs the close-out ritual. Pairs with `newbeginning`. |
| [`newbeginning`](./skills/newbeginning/) | v1.0 | Shipped | Session-opening brief — reads `project_index.md` and the last entries of `project_session.md`, surfaces pending learnings, briefs on state and "Next" items. Pairs with `closingtime`. |
| [`research-triangulation`](./skills/research-triangulation/) | v1.5 | Shipped | End-to-end methodology for running the same research across multiple AI platforms (Claude, Perplexity, Gemini, ChatGPT) and consolidating findings through convergence/divergence analysis. |

Each skill has its own `README.md`, `SKILL.md`, and (where relevant) `BACKLOG.md` with open items and closed-decision register, plus `evals/` for regression checks.

## Install

Two install methods, pick whichever suits your setup.

### Claude Code / CLI — git clone

```bash
mkdir -p ~/.claude/skills
git clone --depth 1 https://github.com/benjaminreal/MetaClaude.git /tmp/metaclaude
cp -r /tmp/metaclaude/skills/research-triangulation ~/.claude/skills/
rm -rf /tmp/metaclaude
```

Replace `research-triangulation` with `closingtime` (or any other) to install a different skill. To pin to a specific released version, add `--branch <tag>` to the clone — e.g. `--branch research-triangulation-v1.5`.

### Claude Code / CLI — `.skill` archive

Download the `.skill` bundle from the [Releases](../../releases) page, then:

```bash
mkdir -p ~/.claude/skills
unzip path/to/research-triangulation_v1.5.skill -d ~/.claude/skills/
```

### Cowork mode

Download the `.skill` file from the [Releases](../../releases) page, open it, and click **Save skill** in the prompt.

### Verify

Ask Claude something the skill should trigger on. If it doesn't trigger, the skill description wasn't selected — invoke it explicitly (`/skill-name` or `use the X skill`).

## Versioning

Each skill maintains its own changelog in its `SKILL.md`. Releases on GitHub are per-skill and carry the changelog entry as release notes. Tags follow the pattern `{skill-name}-v{version}`, e.g. `research-triangulation-v1.3.2`.

## Design notes

A few principles that apply across the skills here, extracted from what's worked:

- **Structural discipline over intelligence.** A skill earns its keep by pre-committing to a process — file naming, output rubrics, validation gates — that Claude wouldn't consistently produce unprompted. If the skill doesn't make the work *more uniform*, it's redundant.
- **Evals are structural, not behavioral, by default.** Deterministic lints on file shape, metadata, and references catch the regressions worth catching. Behavioral evals with LLM graders compete with existing quality rubrics rather than complementing them.
- **Closed decisions belong in the backlog.** When a validator surfaces something you've decided *not* to do, record the decision with rationale — otherwise the same item re-surfaces on every pass. `BACKLOG.md` has both open items and a closed-decisions register.
- **Aspiration is not demonstration.** Changelogs should reflect what shipped, not what was planned. This repo's version history reflects actual state.

## Contributing

I don't actively solicit contributions, but issues are welcome if you hit a bug or find a skill description ambiguous. Forks are fine; roundtripping may be slow since this repo uses release-based snapshots rather than a live commit history.

## License

MIT — see [LICENSE](./LICENSE).
