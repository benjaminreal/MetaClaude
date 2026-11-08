#!/usr/bin/env python3
"""Build the tools index: TOOLS.md (public) and a local companion (private).

Usage:
  python3 tools/build_tools_index.py            # write both files
  python3 tools/build_tools_index.py --check    # exit 1 if TOOLS.md is out of date

TOOLS.md is built only from this repository, so it is the same on every machine
and safe to publish. Descriptions are written in CATALOG below; versions are read
from each skill's SKILL.md. The build fails if a skill folder has no catalog
entry, or an entry has no folder, so a new skill cannot be left out silently.

The local companion, private-artifacts/TOOLS_LOCAL.md, adds what is installed on
this machine: skill versions in each harness folder and the MCP server names in
each harness configuration, plus private notes from
private-artifacts/tools_index_local_notes.json. It reads server names and types
only, never URLs, headers, environment values or keys. private-artifacts/ is
excluded from git, so nothing private lives in this script.

Standard library only. No network access.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PUBLIC_OUT = REPO / "TOOLS.md"
LOCAL_OUT = REPO / "private-artifacts" / "TOOLS_LOCAL.md"
HOME = Path.home()

# Text that must never appear in the public file.
PUBLIC_FORBIDDEN = [
    (re.compile(r"/Users/|/Volumes/|/private/|/home/"), "absolute personal path"),
    (re.compile(r"\.supabase\.co"), "service hostname"),
    (re.compile(r"\b\d{2}_[A-Za-z]"), "private sibling-project folder name"),
]

# --------------------------------------------------------------------- catalog
# Hand-written: what each item is for and how it works. Keep it public-safe:
# no absolute paths, service references or private project names here. Put
# those in private-artifacts/tools_index_local_notes.json instead.

SKILLS = {
    "newbeginning": {
        "group": "Sessions",
        "what": "Opens a work session with a short brief: where the project stands, last session's next step, top tasks.",
        "how": [
            "Reads `project_index.md` and the last two entries of `project_session.md`, plus the project's top tasks from the Tasks database.",
            "Returns at most 250 words and one question (pick up, discuss a task, or focus elsewhere), then stops.",
            "Read-only. The one exception is rebuilding a missing index, and only after approval.",
            "Snapshots, hashes, task receipts and the word count run through `scripts/runtime_cli.py`, so the brief cites checked evidence.",
        ],
        "use": "`/newbeginning`, or \"where did we leave off\"",
    },
    "closingtime": {
        "group": "Sessions",
        "what": "Closes a work session: logs it, updates the project index and tasks, and stages learnings.",
        "how": [
            "Builds evidence from local files and the Tasks database, then drafts the session entry, index update, task changes and learning candidates together.",
            "Asks for one approval of the exact changes, writes them, and reads every one back before it reports.",
            "Shares its runtime with newbeginning. Both are built from `skills/_shared/` with `sync_runtime_copies.py`.",
        ],
        "use": "`/closingtime`, or \"wrap up\"",
    },
    "evidence-research": {
        "group": "Research",
        "what": "Bounded desk research for a decision, with checked sources and visible limits.",
        "how": [
            "Reuses prior work first, then picks the smallest method that can answer the question.",
            "Checks decisive claims against their sources and keeps unknowns visible instead of smoothing them over.",
            "Stops at the stated bounds and says what it did not check.",
            "Hands multi-platform consolidation to research-triangulation and hiring-contact dossiers to boss-hunt-research.",
        ],
        "use": "\"research X for this decision\", \"verify this claim\"",
    },
    "research-triangulation": {
        "group": "Research",
        "what": "Runs one research question on several AI deep-research tools and merges the reports.",
        "how": [
            "Writes a prompt for each platform (Claude, Perplexity, Gemini, ChatGPT, Grok and others).",
            "Scores each report against a rubric.",
            "Consolidates the reports by where they agree and disagree, so you know which findings are well supported.",
        ],
        "use": "\"triangulate this across platforms\", \"consolidate these reports\"",
    },
    "boss-hunt-research": {
        "group": "Career",
        "what": "Read-only research into the people behind a specific job or company: hiring manager, recruiter, sponsor and warm connectors.",
        "how": [
            "Each candidate route carries its evidence and a check that the information is still current.",
            "Never drafts or sends outreach.",
            "Includes a consistency validator and a privacy gate that runs before anything is published.",
        ],
        "use": "\"who is the hiring manager for this job\"",
    },
    "sync-jobs": {
        "group": "Career",
        "what": "Captures job postings you pick and syncs them into a local Excel tracker and archive.",
        "how": [
            "Accepts LinkedIn, employer, ATS and Indeed postings, or postings from an unfamiliar job board.",
            "Validates each posting before it is synced.",
            "Optional triage scores postings against a candidate profile you choose. Real profiles stay local; the package ships only a synthetic example.",
        ],
        "use": "a posting URL, or \"sync my saved jobs\"",
    },
    "local-whisper-transcription": {
        "group": "Media",
        "what": "Private transcription on your own machine with whisper.cpp, plus an optional English route through Phonon-2/MLX.",
        "how": [
            "Checks that the machine is ready before anything runs. A policy file you write fixes the model and the folders it may touch.",
            "Picks the audio channel by scored evidence, splits long audio into overlapping chunks, repairs difficult spans, and assembles TXT, SRT, JSON and Markdown with global timestamps.",
            "Never installs, downloads or uploads anything without approval.",
        ],
        "use": "\"transcribe this recording\"",
    },
    "calibre": {
        "group": "Media",
        "what": "Converts ebooks between formats and reads or fixes their metadata with Calibre's command-line tools.",
        "how": [
            "Keeps read-only commands separate from commands that change files.",
            "Never overwrites the input file and never touches a managed Calibre library.",
            "`scripts/calibre-machine-setup.sh` prepares a machine for it. Run that script in your own terminal, not from an agent session.",
        ],
        "use": "\"convert this to epub\", \"fix this book's metadata\"",
    },
    "nate-update": {
        "group": "Knowledge",
        "what": "Brings the Nate B. Jones archive up to date and ingests it into Open Brain.",
        "how": [
            "A seven-stage pipeline: find new Substack posts, then download articles, transcripts and prompt kits through browser automation.",
            "Ingests the new material into Open Brain.",
            "Keeps a state file, so an interrupted run resumes where it stopped.",
            "Claude Code only.",
        ],
        "use": "`/nate-update`",
    },
}

REPO_TOOLS = [
    {
        "name": "skillchange.py",
        "path": "skills/_contrib/skillchange.py",
        "what": "Gate, installs and drift checks for every change to a skill in this repo.",
        "how": "Commands: `status` shows source and installed versions; `gate` runs the certification checks; `install` re-gates a certified commit, backs up the installed copy and installs into the Claude Code and Codex skill folders; `check-installed` reports drift; `lock`/`unlock` make the installed copies read-only or writable. Follow `skills/STANDARDS.md` when you use it.",
    },
    {
        "name": "Session-skill runtime",
        "path": "skills/_shared/",
        "what": "The single source for the code and references that newbeginning and closingtime share.",
        "how": "`runtime_cli.py` handles snapshots, receipts, approvals and checked writes. Edit only here, then run `sync_runtime_copies.py` to copy the files into both skills. Contract tests: `run_contract_tests.py`, `run_helper_tests.py`.",
    },
    {
        "name": "Skill evals",
        "path": "skills/<skill>/evals/",
        "what": "Structural regression checks for each skill: file shape, metadata, references.",
        "how": "Run `python3 skills/<skill>/evals/structural_eval.py`. Some skills also have behavioural fixtures or runtime evals in the same folder.",
    },
    {
        "name": "books-api",
        "path": "tools/books-api/",
        "what": "Read-only lookup of public book metadata from Open Library and Google Books, as an MCP server or from the command line.",
        "how": "`books_status`, `books_search` (ISBN, or title and author, up to 10 results) and `books_get_record`. Sends one request per call, caches responses for 24 hours and never merges records from different providers. The source exists only on branch `chore/books-api-source` until that branch is merged. Details: `tools/books-api/README.md`.",
    },
    {
        "name": "openrouter_spend.py",
        "path": "tools/openrouter_spend.py",
        "what": "Checks today's OpenRouter spend against the agent allowance, and logs each agent run.",
        "how": "Run with no arguments for the spend check. Exit 0 means allowance is left, 3 means it is used up, 2 means something failed. `--record ...` appends one run to the local run log. Never prints a key.",
    },
    {
        "name": "release.sh",
        "path": "scripts/release.sh",
        "what": "Publishes one skill as a release.",
        "how": "`./scripts/release.sh <skill> <version>` builds a `.skill` bundle, tags `<skill>-v<version>` and publishes a GitHub release. This is outward-facing, so it needs the owner's go-ahead.",
    },
    {
        "name": "calibre-machine-setup.sh",
        "path": "scripts/calibre-machine-setup.sh",
        "what": "Prepares a machine for the calibre skill.",
        "how": "Links Calibre's command-line tools onto PATH, adds a read-only permission allowlist and installs the skill. It is safe to run again. Run it in your own terminal, not from an agent session, because it changes permissions.",
    },
    {
        "name": "skill-doc-generator (patched)",
        "path": "tooling/skill-doc-generator-patched/",
        "what": "Generates and validates README files from SKILL.md files.",
        "how": "A fork of the stock skill-doc-generator with four bug fixes. Usage is in its `PATCH_NOTES.md`.",
    },
    {
        "name": "Tasks dashboard",
        "path": "tasks-dashboard/",
        "what": "A read-only web view of the Tasks database. Its first question is what is slipping.",
        "how": "A Next.js app that reads through a read-only gateway. Task changes still go through skills. Not yet tracked in git. Details: `tasks-dashboard/README.md`.",
    },
    {
        "name": "build_tools_index.py",
        "path": "tools/build_tools_index.py",
        "what": "Builds this index.",
        "how": "Run `python3 tools/build_tools_index.py` to rewrite this file and its local companion. `--check` exits 1 when this file is out of date. Descriptions live in the script's catalog; versions come from the skill files.",
    },
]

MCP_SERVERS = [
    {
        "name": "tasks_mcp",
        "aliases": ["tasks_mcp", "tasks-mcp"],
        "what": "Gateway to the Tasks database, limited to tasks. It is the single source of truth for cross-project to-dos.",
        "tools": "`urgency` (ranked open tasks for one project, or the whole portfolio), `list_tasks`, `get_task`, `create_task`, `update_task`",
        "how": "Read freely. Every write needs owner approval of the exact change and goes through the task-db or closingtime skill. Deletes, schema changes and view changes never go through agents.",
        "source": "Separate private project",
    },
    {
        "name": "open-brain",
        "aliases": ["open-brain", "open_brain"],
        "what": "Personal knowledge store: captured thoughts and learnings, plus the Nate B. Jones archive.",
        "tools": "`search_thoughts`, `list_thoughts`, `capture_thought`, `thought_stats`, `search_nate_content`, `nate_content_stats`",
        "how": "Search compares meaning, not just keywords. Captures happen during a session or at closingtime, and only after approval.",
        "source": "Separate private project",
    },
    {
        "name": "kb-search",
        "aliases": ["kb-search"],
        "what": "Search over a reviewed personal reading knowledge base: notes on books, articles, talks and podcasts, plus their full sources.",
        "tools": "`search`, `get_note`, `get_passage`",
        "how": "Runs locally only while a session needs it. Meaning search embeds the question with a local model; when that model is not running, search falls back to keywords and says so.",
        "source": "Separate private project",
    },
    {
        "name": "books-api",
        "aliases": ["books-api", "books_api"],
        "what": "Public book metadata. See books-api under Repository tools.",
        "tools": "`books_status`, `books_search`, `books_get_record`",
        "how": "Read-only, and runs locally over stdio.",
        "source": "This repo: `tools/books-api/`",
    },
]

HARNESSES = [
    ("Claude Code", "~/.claude/skills", "Installed by `skillchange.py install`, locked, drift-checked."),
    ("Codex", "~/.codex/skills", "Installed by `skillchange.py install`, locked, drift-checked."),
    ("OpenCode", "~/.config/opencode/skills", "Copied by hand, with no drift check. OpenCode also loads `~/.claude/skills`; nate-update is hidden there by a permission rule."),
    ("Gemini", "~/.gemini/config/skills", "Copied by hand, with no drift check. Holds only some of the skills."),
    ("claude.ai", "uploaded zip", "Uploaded by hand. It can lag behind the installed version."),
]

# Private, machine-specific notes live outside git; see load_local_notes().
LOCAL_NOTES_FILE = REPO / "private-artifacts" / "tools_index_local_notes.json"

SKILL_FOLDERS = {
    "claude": HOME / ".claude/skills",
    "codex": HOME / ".codex/skills",
    "opencode": HOME / ".config/opencode/skills",
    "gemini": HOME / ".gemini/config/skills",
    "agents": HOME / ".agents/skills",
}

# ------------------------------------------------------------------- helpers


def load_skillchange():
    spec = importlib.util.spec_from_file_location("skillchange", REPO / "skills/_contrib/skillchange.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_local_notes() -> dict:
    """Private notes for the local companion. Missing or unreadable means none."""
    try:
        return json.loads(LOCAL_NOTES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def version_of(skill_md: Path, sc) -> str:
    if not skill_md.is_file():
        return "—"
    version, _ = sc.skill_version(skill_md.read_text(encoding="utf-8"))
    return version or "unversioned"


def repo_skills() -> list[str]:
    return sorted(p.parent.name for p in (REPO / "skills").glob("*/SKILL.md"))


def check_catalog(found: list[str]) -> list[str]:
    errors = [f"skill folder `skills/{s}/` has no catalog entry" for s in found if s not in SKILLS]
    errors += [f"catalog entry `{s}` has no `skills/{s}/SKILL.md`" for s in SKILLS if s not in found]
    for t in REPO_TOOLS:
        p = t["path"]
        if "<" not in p and not (REPO / p).exists():
            errors.append(f"repository tool path `{p}` does not exist")
    return errors


def mcp_names() -> dict[str, dict[str, str]]:
    """Server name -> type, per harness. Reads names and types only."""
    out: dict[str, dict[str, str]] = {}
    try:
        d = json.loads((HOME / ".claude.json").read_text())
        out["Claude Code"] = {n: c.get("type", "stdio") for n, c in (d.get("mcpServers") or {}).items()}
    except (OSError, ValueError):
        out["Claude Code"] = {"(config unreadable)": ""}
    try:
        d = tomllib.loads((HOME / ".codex/config.toml").read_text())
        out["Codex"] = {n: ("http" if "url" in c else "stdio") for n, c in (d.get("mcp_servers") or {}).items()}
    except (OSError, ValueError):
        out["Codex"] = {"(config unreadable)": ""}
    try:
        text = (HOME / ".config/opencode/opencode.jsonc").read_text()
        text = re.sub(r"(?m)^\s*//.*$", "", text)
        d = json.loads(text)
        out["OpenCode"] = {n: c.get("type", "") for n, c in (d.get("mcp") or {}).items()}
    except (OSError, ValueError):
        out["OpenCode"] = {"(config unreadable)": ""}
    return out


# ----------------------------------------------------------------- rendering


def render_public(sc) -> str:
    found = repo_skills()
    L = [
        "# Tools index",
        "",
        "Every skill, tool and MCP server used with this repository: what each one is for and how it works.",
        "",
        "_Generated by `python3 tools/build_tools_index.py` from the skill files and the catalog in that script. "
        "Do not edit by hand. Versions are the source versions in this checkout; installed versions per harness are in "
        "the local companion file `private-artifacts/TOOLS_LOCAL.md`, which is not published._",
        "",
        "## Skills",
        "",
        "Each skill is a folder under `skills/` with a `SKILL.md` (when it triggers, and the instructions) and a `README.md`.",
        "",
        "| Skill | Area | Version | What it does | How to call it |",
        "|---|---|---|---|---|",
    ]
    for s in found:
        e = SKILLS[s]
        v = version_of(REPO / "skills" / s / "SKILL.md", sc)
        L.append(f"| [`{s}`](skills/{s}/) | {e['group']} | {v} | {e['what']} | {e['use']} |")
    L += ["", "### How each skill works", ""]
    for s in found:
        e = SKILLS[s]
        L.append(f"**[`{s}`](skills/{s}/README.md)**")
        L += [f"- {h}" for h in e["how"]]
        L.append("")
    L += [
        "Changes to any of these skills follow [`skills/STANDARDS.md`](skills/STANDARDS.md): a request record, the agent's own git worktree, tests written first, the gate, an independent review, owner approval, then `skillchange.py install`.",
        "",
        "## Repository tools",
        "",
        "| Tool | Where | What it does | How it works |",
        "|---|---|---|---|",
    ]
    for t in REPO_TOOLS:
        L.append(f"| {t['name']} | `{t['path']}` | {t['what']} | {t['how']} |")
    L += [
        "",
        "## MCP servers",
        "",
        "MCP (Model Context Protocol) servers give an agent extra tools. These are the servers the skills rely on.",
        "",
        "| Server | What it is | Tools | How it works | Source |",
        "|---|---|---|---|---|",
    ]
    for m in MCP_SERVERS:
        L.append(f"| `{m['name']}` | {m['what']} | {m['tools']} | {m['how']} | {m['source']} |")
    L += [
        "",
        "## Harnesses",
        "",
        "A harness is the agent app that runs a model and loads these skills and servers.",
        "",
        "| Harness | Skill folder | How skills get there |",
        "|---|---|---|",
    ]
    for name, folder, how in HARNESSES:
        L.append(f"| {name} | `{folder}` | {how} |")
    L.append("")
    return "\n".join(L)


def render_local(sc) -> str:
    found = repo_skills()
    folders = {k: v for k, v in SKILL_FOLDERS.items() if v.is_dir()}
    L = [
        "# Tools index: local companion",
        "",
        "_Private and machine-specific. Generated by `tools/build_tools_index.py`; do not edit by hand. "
        "The public part is `TOOLS.md`._",
        "",
        "## Skill versions: source and installed copies",
        "",
        "`—` means the skill is not installed in that folder. claude.ai and claude-science copies are not read here.",
        "",
        "| Skill | Source (this checkout) | " + " | ".join(f"`{p}`".replace(str(HOME), "~") for p in folders.values()) + " |",
        "|---|---|" + "---|" * len(folders),
    ]
    for s in found:
        src = version_of(REPO / "skills" / s / "SKILL.md", sc)
        cells = [version_of(p / s / "SKILL.md", sc) for p in folders.values()]
        L.append(f"| `{s}` | {src} | " + " | ".join(cells) + " |")
    L += [
        "",
        "Run `python3 skills/_contrib/skillchange.py status` for drift and lock state of the Claude Code and Codex copies.",
        "",
        "## MCP servers configured per harness",
        "",
        "Names and transport types only, read from each harness's configuration file. "
        "Servers added at launch (for example by a starter script) do not appear.",
        "",
    ]
    servers = mcp_names()
    for harness, names in servers.items():
        listed = ", ".join(f"`{n}` ({t})" if t else f"`{n}`" for n, t in sorted(names.items())) or "none"
        L.append(f"- **{harness}:** {listed}")
    notes = load_local_notes()
    L += ["", "## Where the external servers live", ""]
    for m in MCP_SERVERS:
        note = notes.get("servers", {}).get(m["name"])
        if note:
            L.append(f"- **`{m['name']}`:** {note}")
    L += [
        "",
        "## Configuration files (names only; never print their values)",
        "",
    ]
    L += [f"- {line}" for line in notes.get("config_files", [])] or ["- (no local notes file)"]
    L.append("")
    return "\n".join(L)


def configured_service_refs() -> set[str]:
    """First hostname label of each remote MCP server in the Claude Code config (for example a project ref)."""
    from urllib.parse import urlparse

    refs = set()
    try:
        d = json.loads((HOME / ".claude.json").read_text())
    except (OSError, ValueError):
        return refs
    for c in (d.get("mcpServers") or {}).values():
        host = urlparse(c.get("url") or "").hostname or ""
        label = host.split(".")[0]
        if len(label) >= 12:
            refs.add(label)
    return refs


def public_violations(text: str, extra_forbidden: set[str] | None = None) -> list[str]:
    """Labels and line numbers of private text. Never echoes the matched text."""
    hits = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for rx, label in PUBLIC_FORBIDDEN:
            if rx.search(line):
                hits.append(f"line {i}: {label}")
        for ref in extra_forbidden or ():
            if ref in line:
                hits.append(f"line {i}: configured service reference")
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if TOOLS.md is out of date; write nothing")
    args = ap.parse_args(argv)

    errors = check_catalog(repo_skills())
    if errors:
        print("catalog out of step with the repository:", *errors, sep="\n  ", file=sys.stderr)
        return 2
    sc = load_skillchange()
    public = render_public(sc)
    bad = public_violations(public, configured_service_refs())
    if bad:
        print("refusing: TOOLS.md would contain private text:", *bad, sep="\n  ", file=sys.stderr)
        return 2

    if args.check:
        current = PUBLIC_OUT.read_text(encoding="utf-8") if PUBLIC_OUT.exists() else ""
        if current != public:
            print("TOOLS.md is out of date; run python3 tools/build_tools_index.py", file=sys.stderr)
            return 1
        print("TOOLS.md is up to date")
        return 0

    PUBLIC_OUT.write_text(public, encoding="utf-8")
    print(f"wrote {PUBLIC_OUT.relative_to(REPO)}")
    if LOCAL_OUT.parent.is_dir():
        LOCAL_OUT.write_text(render_local(sc), encoding="utf-8")
        print(f"wrote {LOCAL_OUT.relative_to(REPO)}")
    else:
        print("skipped local companion: private-artifacts/ not present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
