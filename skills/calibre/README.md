# calibre

> Convert ebook formats and manage ebook metadata from the command line, powered by Calibre's headless CLI.

## Why this skill?

Calibre ships ~20 command-line tools with hundreds of options — most are GUI-only or destructive to a managed library. Point a model at them cold and it picks the wrong tool, converts over the original, or edits a library it shouldn't touch.

**calibre** scopes the surface to the two things you actually want from the CLI — **convert a file** and **fix a file's metadata** — hard-separates read-only from mutating commands, and defaults to non-destructive behavior: conversions never overwrite the input, in-place metadata edits are confirmed first, and library writes are out of scope.

**Version:** 1.0.0

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/calibre ~/.claude/skills/calibre

# Project-scoped (available only in this project)
cp -r skills/calibre .claude/skills/calibre
```

**Cowork:** Import the `.skill` file from the [GitHub Releases](https://github.com/benjaminreal/MetaClaude/releases) page.

> If this is the first skill you install and `~/.claude/skills/` didn't exist before, restart Claude Code so it picks up the new directory.

---

## Requirements

- **Calibre** installed, with its CLI on `PATH`. On macOS the binaries live in `/Applications/calibre.app/Contents/MacOS/`; symlink the automation tools (`ebook-convert`, `ebook-meta`, `fetch-ebook-metadata`, `calibredb`, …) into a directory on `PATH` (e.g. `/opt/homebrew/bin`). Verify with `ebook-convert --version`.
- **Bash.**
- **Network** — only for online metadata lookup (`fetch-ebook-metadata`); everything else works offline.

---

## How to Use

Say what you want in plain language:

> `convert this book to epub` · `convert my-book.epub to mobi` · `fix the metadata on this file` · `set the author and title on book.azw3` · `fetch metadata for this ISBN` · `what's the metadata on this epub?`

The skill runs a quick pre-flight (CLI present, inputs exist, read-only vs. mutating), then executes the matching workflow and reports the result.

### What it does

1. **Converts formats** — `ebook-convert` between EPUB, MOBI, AZW3, PDF, DOCX, HTML, TXT, FB2, and more. Always writes a **new** file; never overwrites your original.
2. **Reads metadata** — title, authors, tags, series, publisher, ISBN, cover.
3. **Writes metadata in place** — after confirming the file and exact fields with you.
4. **Fetches online metadata** — by ISBN or title+author, optionally a cover, for you to review before applying.
5. **Inspects a library (read-only)** — `calibredb list`/`search`/`show_metadata`.

### What it won't do

- Modify a managed Calibre library (`calibredb add`/`remove`/`set_metadata` stay prompt-gated and out of scope)
- Launch any GUI tool (`calibre`, `ebook-edit`, `ebook-viewer`)
- Send to devices/email, run the content server, or manage plugins
- Remove DRM
- Overwrite or delete your original files

---

## How It Works (Under the Hood)

An 8-section skill:

| Section | What it covers |
|---|---|
| 1. Purpose & Scope | The two primary flows and the hard scope boundary |
| 2. Pre-flight Checklist | CLI on PATH, inputs exist, operation class, output collisions, bulk/Dropbox |
| 3. Core Workflow | Convert (A), metadata read/write (B), online fetch (C), library read (D) |
| 4. Command Reference | The scoped tool surface, read-only vs. mutating |
| 5. Decision Rules | Overwrites, in-place confirms, batch failures, DRM, GUI requests |
| 6. Harness Adaptations | Bash + Calibre CLI required; network/read/allowlist optional |
| 7. Eval Criteria | Workflow correctness, safety, output quality |
| 8. Version & Changelog | Release history |

### Safety model

- **Conversions are non-destructive** — new output file, input untouched; identical-format requests write `<stem>.converted.<ext>`.
- **In-place edits are gated** — `ebook-meta --field` and `ebook-polish` modify the file, so the skill names the file and fields and confirms first.
- **Library writes are out of scope** — read-only `calibredb` only; anything mutating is handed back to you.
- **Bulk writes warn about Dropbox** per the workspace sync rules.

---

## Evals

Structural checks (deterministic, no Calibre required):

```bash
python skills/calibre/evals/structural_eval.py
```

Validates frontmatter, the 8-section structure, trigger-phrase consistency, the workflow/command/decision tables, and the read-only vs. mutating boundary language.

---

_Part of [MetaClaude](https://github.com/benjaminreal/MetaClaude) — a personal skills workspace._
