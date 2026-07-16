---
name: calibre
description: "Convert ebook formats and manage ebook metadata from the command line via Calibre's CLI. MUST trigger on: 'convert ebook', 'convert this book', 'convert to epub', 'convert to mobi', 'convert to azw3', 'convert to pdf', 'ebook metadata', 'fix ebook metadata', 'set ebook metadata', 'fetch book metadata', 'calibre convert'. Do NOT trigger on: Calibre GUI/library-catalog questions, or destructive library-wide operations with no conversion or metadata intent."
version: 1.0.0
---

# calibre

Convert between ebook formats and read/write ebook metadata using Calibre's headless CLI (`ebook-convert`, `ebook-meta`, `fetch-ebook-metadata`, read-only `calibredb`). File-level operations only — it does not curate a managed Calibre library or run the GUI.

---

## 1. Purpose & Scope

**Purpose:** Turn "convert this book" and "fix this book's metadata" into safe, scripted CLI runs. Two primary flows — **format conversion** and **metadata management** — plus online metadata lookup, all against standalone ebook files.

**Why a skill?** The Calibre CLI has ~20 tools and hundreds of options; most are GUI-only or destructive to a managed library. Without guidance the model reaches for the wrong tool, converts destructively, or edits a library it shouldn't touch. This skill scopes the surface to the file-level convert + metadata flows, hard-separates read-only from mutating commands, and encodes the non-destructive defaults (never overwrite an input, warn before in-place edits, pause Dropbox for bulk runs).

**Does:**
- Convert a single file or a batch between formats via `ebook-convert` (EPUB, MOBI, AZW3, PDF, DOCX, HTML, TXT, FB2, …)
- Read metadata from a file (`ebook-meta <file>`)
- Write/fix metadata in place on a standalone file (`ebook-meta <file> --title …`)
- Fetch metadata (and optionally a cover) from online sources (`fetch-ebook-metadata`)
- Read-only inspection of an existing Calibre library (`calibredb list`/`search`/`show_metadata`)

**Does NOT:**
- Mutate a managed Calibre library — `calibredb add`/`remove`/`add_format`/`remove_format`/`set_metadata` stay prompt-gated and out of scope for autonomous runs
- Launch any GUI tool (`calibre`, `ebook-edit`, `ebook-viewer`, `lrfviewer`)
- Send books to devices/email (`calibre-smtp`), run the content server (`calibre-server`), or manage plugins (`calibre-customize`)
- DRM removal of any kind
- Overwrite or delete the user's original input files

---

## 2. Pre-flight Checklist

Before any conversion or metadata write, confirm:

1. **Calibre CLI on PATH.** Run `ebook-convert --version`. If not found, the binaries aren't linked — tell the user to run the PATH step from `calibre_cli_reference.md` (symlink `/Applications/calibre.app/Contents/MacOS/*` into a PATH dir) and stop. Record the reported version.
2. **Input files exist and are readable.** Resolve each input path; if a glob matches nothing, stop and report it rather than proceeding with zero files.
3. **Operation class.** Classify the request as **read-only** (metadata read, `calibredb list`/`search`/`show_metadata`, conversion to a *new* file) or **mutating** (in-place `ebook-meta` write, any `calibredb` write). Mutating-in-place needs the Section 5 confirmation.
4. **Output collision.** Determine each output path. If an output file already exists, do not overwrite silently — see Section 5.
5. **Bulk / heavy write.** If converting more than ~5 files or writing into a Dropbox-synced tree, issue the Dropbox sync warning (CLAUDE.md rule 3) before starting.
6. **Library operations are read-only.** If the request touches a Calibre library (`--library-path`/`--with-library`), confirm it's a read (`list`/`search`/`show_metadata`). Any library write is out of scope — hand back to the user.

---

## 3. Core Workflow

Pick the workflow that matches the request. Each is independent; a request may chain them (e.g. fetch metadata → apply → convert).

### Workflow A — Format conversion (`ebook-convert`)

Non-destructive by contract: `ebook-convert` reads the input and writes a **new** output file; it never modifies the input.

1. Resolve input path and target format. Derive the output path as `<input-stem>.<ext>` in the same directory unless the user specifies otherwise.
2. **Never overwrite the input**; if input and output paths would collide (same format requested), write to `<stem>.converted.<ext>` and note it.
3. Run:
   ```bash
   ebook-convert "<input>" "<output>" [options]
   ```
   Common options: `--authors "A & B"`, `--title "T"`, `--output-profile <profile>`, `--embed-all-fonts`, `--enable-heuristics`. Only add options the user asked for; defaults are sensible.
4. **Batch:** loop over inputs, converting each to its own output. Report per-file success/failure; one failure does not abort the batch.
5. Verify each output exists and is non-empty; report path + size. On non-zero exit, surface `ebook-convert`'s stderr and continue to the next file.

### Workflow B — Metadata read / write (`ebook-meta`)

**Read (always safe):**
```bash
ebook-meta "<file>"
```
Parse and present title, authors, tags, series/index, publisher, ISBN, language, and cover presence.

**Write (in-place — mutates the file):**
1. This edits the file in place. Apply the Section 5 in-place-write confirmation first.
2. Run only the fields the user specified:
   ```bash
   ebook-meta "<file>" --title "T" --authors "A & B" \
     --tags "t1,t2" --series "S" --index 1 \
     --publisher "P" --isbn "978…" --cover "cover.jpg"
   ```
3. Re-read (`ebook-meta "<file>"`) and confirm the fields changed as intended.

> Author separator is ` & `; tags are comma-separated. `--index` sets the series position.

### Workflow C — Fetch online metadata (`fetch-ebook-metadata`)

Network call; returns metadata (and optionally a cover) — it does **not** modify any file.

1. Query by the strongest identifier available (ISBN beats title+author):
   ```bash
   fetch-ebook-metadata --isbn "978…"                     # or
   fetch-ebook-metadata --title "T" --authors "A" --opf   # OPF to stdout
   fetch-ebook-metadata --title "T" --authors "A" --cover "cover.jpg"
   ```
2. Present the fetched fields to the user for confirmation.
3. To apply, hand the confirmed values to **Workflow B** (in-place write) — fetching and applying are two explicit steps, never one silent one.

### Workflow D — Library inspection (read-only `calibredb`)

Only `list`, `search`, `show_metadata`. Never a write.
```bash
calibredb list --library-path "<lib>" --fields title,authors,formats
calibredb search --library-path "<lib>" "author:Tolkien"
calibredb show_metadata --library-path "<lib>" <book_id>
```
Any request to `add`/`remove`/`set_metadata`/`add_format`/`remove_format`: stop and tell the user it's a mutating library operation outside this skill's scope; they can run it themselves.

---

## 4. Command Reference

The scoped surface. Full CLI: https://manual.calibre-ebook.com/generated/en/cli-index.html · local inventory: `calibre_cli_reference.md`.

| Tool | Use | Class |
|---|---|---|
| `ebook-convert IN OUT [opts]` | Convert formats; build from a file/recipe | Read-only (writes a new file) |
| `ebook-meta FILE` | Read metadata | Read-only |
| `ebook-meta FILE --field …` | Write metadata in place | **Mutating (in-place)** |
| `fetch-ebook-metadata …` | Online metadata/cover lookup | Read-only (network) |
| `calibredb list/search/show_metadata` | Inspect a library | Read-only |
| `calibredb add/remove/set_metadata/…` | Modify a library | **Mutating — out of scope, gated** |
| `ebook-polish FILE` | Lossless fixes (fonts, punctuation, cover) | Mutating (in-place) — use only on request |

**Allowlisted (run without prompting):** `ebook-convert`, `ebook-meta`, `fetch-ebook-metadata`, `calibredb list`/`search`/`show_metadata`. Everything else prompts.

---

## 5. Decision Rules

| Situation | Action |
|---|---|
| User says "skip" a step | Respect it. |
| `ebook-convert --version` fails | Stop. Direct user to the PATH step in `calibre_cli_reference.md`; don't attempt bundle-path calls silently. |
| Output path already exists | Do not overwrite. Ask, or write to `<stem>.converted.<ext>` / `<stem>.new.<ext>` and report. |
| In-place metadata write (`ebook-meta --field`, `ebook-polish`) | Confirm first: name the file and the exact fields changing. For an irreplaceable/original file, offer to convert-to-copy or back up before writing. |
| Input and output format identical | Never write over the input; emit `<stem>.converted.<ext>`. |
| Batch > ~5 files, or writing into Dropbox tree | Issue Dropbox sync warning (CLAUDE.md rule 3) before starting. |
| One file in a batch fails | Log its stderr, continue; summarize failures at the end. |
| Any `calibredb` write requested | Out of scope — explain and hand back to the user. |
| DRM-locked input / DRM removal asked | Refuse the DRM step; explain the skill won't strip DRM. Convert only DRM-free files. |
| Empty/zero-byte output after convert | Treat as failure; surface stderr, keep the input intact. |
| GUI tool requested (`calibre`, `ebook-edit`, `ebook-viewer`) | Not headless-usable; tell the user to open Calibre directly. |

---

## 6. Harness Adaptations

**Required:**
- **Bash** — invoke the Calibre CLI, resolve paths, check exit codes.
- **Calibre CLI on PATH** — `ebook-convert`, `ebook-meta`, `fetch-ebook-metadata`, `calibredb` (per the PATH step in `calibre_cli_reference.md`).

**Optional (graceful degradation):**

| Capability | Used by | If missing |
|---|---|---|
| Read files | Confirming outputs, reading covers | Trust exit codes + `ebook-meta` re-read |
| Network | Workflow C (`fetch-ebook-metadata`) | Skip online lookup; use user-supplied metadata only |
| Permission allowlist | Prompt-free read-only + convert runs | Commands still run, just with a prompt each time |

**Path notes:** binaries live in `/Applications/calibre.app/Contents/MacOS/` and are symlinked into a PATH dir per machine. On a machine where they aren't linked, `ebook-convert --version` fails the pre-flight — fix PATH, don't fall back to hardcoded bundle paths in commands.

---

## 7. Eval Criteria

**Workflow correctness:**
- The right tool is chosen for the request (convert vs. metadata vs. fetch vs. library).
- Read-only vs. mutating is classified correctly; in-place writes are confirmed first.
- Conversions write a new file and never modify or overwrite the input.

**Safety:**
- No `calibredb` library writes performed autonomously.
- No GUI tool launched; no DRM stripped.
- Dropbox warning issued for bulk/heavy writes; output collisions never silently overwritten.

**Output quality:**
- Each run reports the concrete output path(s) and size, or a specific per-file failure reason.
- Metadata writes are verified by a re-read.
- Batch runs summarize successes and failures rather than aborting on the first error.

---

## 8. Version & Changelog

**v1.0.0 — 2026-07-15**
- **Initial release.** File-level Calibre CLI skill scoped to two primary flows: format conversion (`ebook-convert`) and metadata management (`ebook-meta` + `fetch-ebook-metadata`), plus read-only library inspection (`calibredb list`/`search`/`show_metadata`).
- **Non-destructive by contract:** conversions never touch the input; in-place metadata writes require explicit confirmation; output collisions never silently overwritten.
- **Hard scope boundary:** mutating `calibredb` subcommands, GUI tools, device/email, content server, and DRM removal are out of scope.
- **Allowlist-aligned** with the read-only vs. mutating split in `calibre_cli_reference.md` and the Claude/Codex permission setup from Session #30.
