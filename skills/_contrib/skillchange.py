#!/usr/bin/env python3
"""Gate, install and drift tooling for changes to MetaClaude-maintained skills.

Agents from other projects may change skills maintained in this repository,
but only through the protocol in ``skills/STANDARDS.md``. This tool is the
mechanical half of that protocol:

  status            show canonical/installed versions, drift and open changes
  gate              run the mechanical certification gate on a committed change
  register          record an installed copy that matches a known commit
  check-installed   report installed copies that drifted from their record
  lock / unlock     make installed copies read-only (or writable again)
  install           re-gate a certified commit, then install it and re-lock

A gate failure that the owner has accepted is recorded in the change folder's
GATE-EXCEPTIONS.json. It is accepted only when its check name, mode and exact
item list match the failure; any other failure still fails the gate.

Always run the main checkout's copy of this file. The repository is located
from the tool's own path, never from the current folder. Standard library only;
no network access; never writes tracked files of the main checkout.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

TOOL = Path(__file__).resolve()
JUNK_NAMES = {".DS_Store", "__pycache__"}
SESSION_SKILLS = ("newbeginning", "closingtime")
SHARED = "skills/_shared/"
PROTECTED = ("skills/_contrib", "skills/STANDARDS.md")
REGRESSION_CORPUS = "skills/_shared/recert_regressions.py"
TEST_PATH_RE = re.compile(r"(^|/)(evals|tests?)/|fixtures|recert_regressions|run_contract_tests|_test\.py$|(^|/)test_[^/]*\.py$")
EXCEPTIONS_NAME = "GATE-EXCEPTIONS.json"
# Only these checks can be owner-accepted. A change's own failing tests, privacy hits,
# protected-file edits, parity and version checks can never be waived.
ACCEPTABLE_CHECKS = ("regression_corpus_append_only", "base_tests_on_new_code:", "changes_inside_skills",
                     "only_declared_skills_touched", "no_binary_files")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FAILURE_LINE_RES = (
    re.compile(r"^\s*- (?P<item>[^\n]+?): [A-Za-z_][\w.]*(?:Error|Exception)\b"),  # contract suite: '  - case: AssertionError'
    re.compile(r"^(?P<item>[A-Za-z_][\w.]*(?:Error|Exception)\b[^\n]*)$"),          # final traceback line
    re.compile(r"^(?P<item>FAIL\s+\S+.*)$"),                                         # structural eval rows
)
CHANGE_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[A-Za-z0-9][A-Za-z0-9_.-]*$")
DOLLAR_DIGIT_RE = re.compile(r"\$\d")
PRIVACY_RES = {
    "absolute_user_path": re.compile(r"/Users/[A-Za-z]|/home/[a-z]|/Volumes/[A-Za-z]"),
    "email_address": re.compile(r"[\w.+-]+@(?!example\.(?:com|org|net)\b)(?!anthropic\.com\b)[\w-]+\.[A-Za-z][\w.]*"),
    "token_like": re.compile(r"sk-[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9-]{10,}"),
}
DEFAULT_TARGETS = {"claude": "~/.claude/skills", "codex": "~/.codex/skills"}
HEADING_VERSION_RES = (
    re.compile(r"^\s*\*\*v(\d+\.\d+\.\d+)\b"),
    re.compile(r"^\s*#{2,4}\s+v?(\d+\.\d+\.\d+)\b"),
    re.compile(r"^\s*\*\*Candidate\s+v?(\d+\.\d+\.\d+)\b"),
)


# --------------------------------------------------------------------------- basics

def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def run(cmd: list[str], cwd: Path, check: bool = True, timeout: int = 900,
        text: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=text, timeout=timeout, env=env)
    if check and proc.returncode != 0:
        err = proc.stderr if text else proc.stderr.decode(errors="replace")
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{err.strip()}")
    return proc


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], cwd, check=check).stdout.strip()


def git_ok(cwd: Path, *args: str) -> bool:
    return run(["git", *args], cwd, check=False).returncode == 0


def common_dir(path: Path) -> Path:
    return Path(git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()


MAIN = common_dir(TOOL.parent).parent          # main checkout, from the tool's own location
CHANGES = MAIN / "private-artifacts" / "skill-changes"
REGISTRY = CHANGES / "installed.json"


def cwd_repo() -> Path:
    """The worktree being gated; it must belong to the same repository as the tool."""
    here = Path.cwd()
    if not git_ok(here, "rev-parse", "--show-toplevel") or common_dir(here) != common_dir(MAIN):
        raise SystemExit(f"REFUSED: run this from a worktree of {MAIN}")
    return Path(git(here, "rev-parse", "--show-toplevel"))


def load_registry() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {"schema_version": "1.0", "entries": {}}


def save_registry(data: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(REGISTRY)


def tree_hash(path: Path) -> str | None:
    """SHA-256 over relative paths and bytes, ignoring caches and Finder files."""
    if not path.is_dir() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path)
        if any(part in JUNK_NAMES for part in rel.parts) or item.suffix == ".pyc":
            continue
        if item.is_symlink():
            digest.update(f"L {rel.as_posix()} {os.readlink(item)}\n".encode())
        elif item.is_file():
            digest.update(f"F {rel.as_posix()}\n".encode())
            digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def copy_ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in JUNK_NAMES or n.endswith(".pyc")}


def set_writable(path: Path, writable: bool) -> None:
    if not path.exists() or path.is_symlink():
        return
    for item in [path, *path.rglob("*")]:
        if item.is_symlink():
            continue
        mode = item.stat().st_mode
        item.chmod(mode | stat.S_IWUSR if writable else mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def is_locked(path: Path) -> bool:
    if not path.exists() or path.is_symlink():
        return False
    return not any(os.access(p, os.W_OK) for p in [path, *path.rglob("*")] if not p.is_symlink())


def unsafe_target(path: Path) -> str | None:
    if path.is_symlink():
        return f"{path} is a symlink; installed copies must be real folders"
    if MAIN in path.resolve().parents or path.resolve() == MAIN:
        return f"{path} is inside the main checkout"
    return None


@contextmanager
def worktree_at(rev: str):
    """A fresh detached checkout of rev; always removed afterwards."""
    tmp = Path(tempfile.mkdtemp(prefix="skillgate-")).resolve()
    git(MAIN, "worktree", "add", "--detach", str(tmp / "wt"), rev)
    try:
        yield tmp / "wt"
    finally:
        run(["git", "worktree", "remove", "--force", str(tmp / "wt")], MAIN, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def extract(rev: str, skill: str) -> Path:
    """Unpack skills/<skill> at rev into a fresh temporary folder; caller removes it."""
    dest = Path(tempfile.mkdtemp(prefix="skilltree-")).resolve()
    archive = subprocess.run(["git", "archive", rev, f"skills/{skill}"], cwd=str(MAIN),
                             capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)
    return dest / "skills" / skill


def tree_hash_at(rev: str, skill: str) -> str | None:
    src = extract(rev, skill)
    try:
        return tree_hash(src)
    finally:
        shutil.rmtree(src.parent.parent, ignore_errors=True)


def blob(rev: str, path: str) -> bytes | None:
    proc = run(["git", "show", f"{rev}:{path}"], MAIN, check=False, text=False)
    return proc.stdout if proc.returncode == 0 else None


def object_id(rev: str, path: str) -> str | None:
    proc = run(["git", "rev-parse", "--verify", "--quiet", f"{rev}:{path}"], MAIN, check=False)
    return proc.stdout.strip() or None


# ------------------------------------------------------------------- versions

def _vt(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def skill_version(text: str) -> tuple[str | None, str]:
    """Frontmatter version, else the first changelog heading (the newest entry)."""
    fm = re.search(r'^\s*version:\s*"?(\d+\.\d+\.\d+)"?\s*$', frontmatter(text), re.M)
    if fm:
        return fm.group(1), "frontmatter"
    for line in text.splitlines():
        for rx in HEADING_VERSION_RES:
            m = rx.match(line)
            if m:
                return m.group(1), "changelog heading"
    return None, "none"


def changelog_heading_for(text: str, version: str) -> bool:
    exact = re.compile(rf"(?<![\d.]){re.escape(version)}(?![\d.])")
    for line in text.splitlines():
        for rx in HEADING_VERSION_RES:
            m = rx.match(line)
            if m and exact.fullmatch(m.group(1)):
                return True
    return False


# ----------------------------------------------------------------------- gate

def skill_scope(skill: str) -> list[str]:
    return [f"skills/{skill}/"] + ([SHARED] if skill in SESSION_SKILLS else [])


def touched_skills(paths: list[str]) -> set[str]:
    out = set()
    for p in paths:
        if p.startswith(SHARED):
            out.update(SESSION_SKILLS)
        m = re.match(r"skills/([^/_][^/]*)/", p)
        if m:
            out.add(m.group(1))
    return out


def name_status(base: str, head: str) -> list[tuple[str, str]]:
    raw = run(["git", "diff", "--name-status", "-z", "--no-renames", base, head], MAIN, text=False).stdout
    parts = [p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\0") if p]
    return list(zip(parts[0::2], parts[1::2]))


def base_sync_mapping(rev: str) -> dict:
    """File mapping from the base commit's sync script, evaluated in a subprocess."""
    src = blob(rev, "skills/_shared/sync_runtime_copies.py")
    if src is None:
        return {}
    with tempfile.TemporaryDirectory(prefix="skillsync-") as tmp:
        script = Path(tmp) / "sync_base.py"
        script.write_bytes(src)
        probe = (
            "import importlib.util,json,sys;"
            f"s=importlib.util.spec_from_file_location('m',{str(script)!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "out={k:{'runtime':list(m.RUNTIME_FILES),'refs':{n:m.reference_source(k,n,m.HERE).name for n in m.reference_files(k)}} for k in ('newbeginning','closingtime')};"
            "print(json.dumps(out))"
        )
        proc = run([sys.executable, "-I", "-c", probe], Path(tmp), check=False)
        return json.loads(proc.stdout) if proc.returncode == 0 else {}


def shared_parity(tree: Path, mapping: dict) -> list[str]:
    if not mapping:
        return ["could not read the base commit's sync mapping"]
    shared = tree / "skills" / "_shared"
    problems = []
    for skill, spec in mapping.items():
        pkg = tree / "skills" / skill
        pairs = [(shared / n, pkg / "scripts" / n) for n in spec["runtime"]]
        pairs += [(shared / src, pkg / "references" / n) for n, src in spec["refs"].items()]
        for src, dst in pairs:
            if not src.exists() or not dst.exists() or src.read_bytes() != dst.read_bytes():
                problems.append(f"{dst.relative_to(tree)} differs from {src.relative_to(tree)}")
    return problems


def test_commands(tree: Path, skills: list[str]) -> list[str]:
    cmds = []
    if any(s in SESSION_SKILLS for s in skills) and (tree / "skills/_shared/run_contract_tests.py").exists():
        cmds.append("skills/_shared/run_contract_tests.py")
    for s in skills:
        if (tree / "skills" / s / "evals" / "structural_eval.py").exists():
            cmds.append(f"skills/{s}/evals/structural_eval.py")
    return cmds


def gate(head: str, skills: list[str], level: int, mode: str,
         install_base: str | None = None, worktree: Path | None = None,
         exceptions: list[dict] | None = None) -> dict:
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str = "", items: list[str] | None = None) -> None:
        row = {"check": name, "result": "PASS" if ok else "FAIL", "detail": detail}
        if not ok:
            row["items"] = sorted(set(items if items is not None else [l.strip() for l in detail.splitlines() if l.strip()]))
        checks.append(row)

    head = git(MAIN, "rev-parse", head)
    main_head = git(MAIN, "rev-parse", "HEAD")
    if git_ok(MAIN, "merge-base", "--is-ancestor", head, main_head):
        if not install_base:
            raise SystemExit("REFUSED: this commit is already on the main line; nothing to gate")
        scope_base = install_base
    else:
        scope_base = git(MAIN, "merge-base", main_head, head)
    version_base = install_base or scope_base
    scope = sorted({p for s in skills for p in skill_scope(s)})

    if worktree is not None:
        dirty = git(worktree, "status", "--porcelain", "--untracked-files=all", "--", *scope)
        record("worktree_committed", not dirty, dirty[:400])
        record("worktree_head_is_gated_commit", git(worktree, "rev-parse", "HEAD") == head)
    if install_base:
        record("installed_commit_is_ancestor", git_ok(MAIN, "merge-base", "--is-ancestor", install_base, head),
               f"installed {install_base[:12]}")

    entries = name_status(scope_base, head)
    changed = [p for _, p in entries]
    record("has_changes", bool(changed), f"{len(changed)} files since {scope_base[:12]} (merge base with the main line)")
    for path in PROTECTED:
        same = object_id(head, path) == object_id(main_head, path)
        record(f"protected_unchanged:{path}", same,
               "" if same else "differs from the main line; changes to the rules or tool need a MetaClaude session, or rebase")
    outside = [p for p in changed if not p.startswith("skills/")]
    record("changes_inside_skills", not outside, ", ".join(outside[:20]), outside)
    undeclared = sorted(touched_skills(changed) - set(skills))
    record("only_declared_skills_touched", not undeclared, ", ".join(undeclared), undeclared)

    if REGRESSION_CORPUS in changed:
        diff = git(MAIN, "diff", "-U0", "--no-color", scope_base, head, "--", REGRESSION_CORPUS)
        removed_lines = [l[1:] for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
        removed = len(removed_lines)
        record("regression_corpus_append_only", removed == 0,
               f"{removed} removed lines; changing a reproduction needs a recorded owner decision", removed_lines)

    for skill in skills:
        rel = f"skills/{skill}/SKILL.md"
        new_raw, old_raw = blob(head, rel), blob(version_base, rel)
        if new_raw is None:
            record(f"{skill}:skill_md_present", False, f"{rel} missing at the commit")
            continue
        new_text = new_raw.decode(errors="replace")
        new_v, src = skill_version(new_text)
        old_v = skill_version(old_raw.decode(errors="replace"))[0] if old_raw else None
        record(f"{skill}:version_detectable", new_v is not None,
               f"{new_v} from {src}" if new_v else "add a frontmatter version or a **vX.Y.Z changelog heading")
        if new_v and old_v:
            record(f"{skill}:version_bumped", _vt(new_v) > _vt(old_v), f"{old_v} -> {new_v}")
        if new_v:
            record(f"{skill}:changelog_heading", changelog_heading_for(new_text, new_v),
                   f"SKILL.md needs a '**v{new_v} — date' or '### {new_v}' heading")

    dollar, privacy, binary = [], {k: [] for k in PRIVACY_RES}, []
    for status, path in entries:
        if status == "D" or not any(path.startswith(s) for s in scope):
            continue
        new = blob(head, path) or b""
        if b"\0" in new:
            binary.append(path)
            continue
        old_lines = set((blob(scope_base, path) or b"").decode(errors="replace").splitlines())
        for line in new.decode(errors="replace").splitlines():
            if line in old_lines:
                continue
            if path.endswith(".md") and DOLLAR_DIGIT_RE.search(line):
                dollar.append(f"{path}: {line.strip()[:80]}")
            for name, rx in PRIVACY_RES.items():
                if rx.search(line):
                    privacy[name].append(f"{path}: {line.strip()[:80]}")
    record("no_binary_files", not binary, ", ".join(binary[:10]) + (" (binary files need owner approval)" if binary else ""))
    record("no_dollar_digit_placeholders", not dollar, "; ".join(dollar[:5]))
    for name, hits in privacy.items():
        record(f"privacy:{name}", not hits, "; ".join(hits[:5]))

    if level >= 2:
        tests = [p for p in changed if any(p.startswith(s) for s in scope) and TEST_PATH_RE.search(p)]
        record("behavior_change_has_tests", bool(tests),
               ", ".join(tests[:10]) or "level 2-3 changes must add or extend a test before the repair")

    diff_check = run(["git", "diff", "--check", scope_base, head, "--", *scope], MAIN, check=False)
    record("git_diff_check", diff_check.returncode == 0, diff_check.stdout[:400])

    mapping = base_sync_mapping(version_base) if any(s in SESSION_SKILLS for s in skills) else {}
    with worktree_at(head) as tree:
        if mapping or any(s in SESSION_SKILLS for s in skills):
            problems = shared_parity(tree, mapping)
            record("shared_runtime_copies_identical", not problems,
                   "; ".join(problems[:6]) + ("  (run skills/_shared/sync_runtime_copies.py)" if problems else ""))
        for cmd in test_commands(tree, skills):
            proc = run([sys.executable, cmd], tree, check=False)
            tail = "\n".join(l for l in (proc.stdout + proc.stderr).strip().splitlines()[-8:] if l.strip())
            record(f"head_tests:{cmd}", proc.returncode == 0, tail, failure_items(proc.stdout + proc.stderr, tree))
    # The base commit's own tests must still pass against the new skill code, so a
    # change cannot pass by weakening or stubbing the tests it ships with.
    with worktree_at(head) as tree:
        overlaid = []
        for path in git(MAIN, "ls-tree", "-r", "--name-only", version_base, "--", *scope).splitlines():
            if TEST_PATH_RE.search(path):
                data = blob(version_base, path)
                if data is not None:
                    (tree / path).parent.mkdir(parents=True, exist_ok=True)
                    (tree / path).write_bytes(data)
                    overlaid.append(path)
        for cmd in test_commands(tree, skills):
            if cmd not in overlaid:
                continue
            proc = run([sys.executable, cmd], tree, check=False)
            tail = "\n".join(l for l in (proc.stdout + proc.stderr).strip().splitlines()[-8:] if l.strip())
            record(f"base_tests_on_new_code:{cmd}", proc.returncode == 0,
                   tail + ("\nAn intentional behaviour change that breaks an old test needs a recorded owner decision."
                           if proc.returncode else ""), failure_items(proc.stdout + proc.stderr, tree))

    accepted, unused = apply_exceptions(checks, exceptions or [], mode)
    failed = [c for c in checks if c["result"] == "FAIL"]
    return {
        "schema_version": "1.1",
        "tool_sha256": "sha256:" + hashlib.sha256(TOOL.read_bytes()).hexdigest(),
        "mode": mode, "level": level, "scope_base": scope_base, "version_base": version_base,
        "main_head": main_head, "head": head, "skills": skills,
        "skill_tree_sha256": {s: tree_hash_at(head, s) for s in skills},
        "ran_at": now(), "checks": checks,
        "verdict": "FAIL" if failed else "PASS", "failed": [c["check"] for c in failed],
        "accepted": accepted, "unused_exceptions": unused,
    }


def failure_items(output: str, tree: Path) -> list[str]:
    """Stable names of what failed in a test run: case names and exception lines, temp paths removed."""
    items = []
    for line in output.replace(str(tree), "<tree>").splitlines():
        for rx in FAILURE_LINE_RES:
            m = rx.match(line)
            if m:
                items.append(re.sub(r"/(?:private/)?(?:var|tmp)/\S+", "<tmp>", m.group("item").strip()))
                break
    return items or ["exit status nonzero, no failure lines recognised"]


def load_exceptions(path: Path | None) -> list[dict]:
    """Read GATE-EXCEPTIONS.json; refuse a malformed file instead of ignoring it."""
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"REFUSED: {path} is not valid JSON: {exc}")
    rows = data.get("exceptions") if isinstance(data, dict) else None
    if data.get("schema_version") != "1.0" or not isinstance(rows, list) or not rows:
        raise SystemExit(f"REFUSED: {path} needs schema_version 1.0 and a non-empty 'exceptions' list")
    for i, e in enumerate(rows):
        bad = []
        if not isinstance(e, dict):
            raise SystemExit(f"REFUSED: {path} exception {i} is not an object")
        if not isinstance(e.get("check"), str) or not any(
                e["check"] == a or (a.endswith(":") and e["check"].startswith(a)) for a in ACCEPTABLE_CHECKS):
            bad.append("check (only " + ", ".join(ACCEPTABLE_CHECKS) + " can be accepted)")
        if e.get("mode") not in ("contributor", "install"):
            bad.append("mode (contributor or install)")
        if not isinstance(e.get("items"), list) or not e["items"] or not all(isinstance(x, str) for x in e["items"]):
            bad.append("items (non-empty list of strings, copied from the gate output)")
        for key in ("decision", "owner_reply"):
            if not isinstance(e.get(key), str) or not e[key].strip('" '):
                bad.append(key)
        if not isinstance(e.get("date"), str) or not DATE_RE.match(e["date"]):
            bad.append("date (YYYY-MM-DD)")
        if bad:
            raise SystemExit(f"REFUSED: {path} exception {i} is missing or has invalid: {', '.join(bad)}")
    return rows


def apply_exceptions(checks: list[dict], exceptions: list[dict], mode: str) -> tuple[list[str], list[int]]:
    """Mark a failure ACCEPTED only when an owner exception matches its check, mode and exact items."""
    used, accepted = set(), []
    for c in checks:
        if c["result"] != "FAIL":
            continue
        for i, e in enumerate(exceptions):
            if e["check"] == c["check"] and e["mode"] == mode and sorted(set(e["items"])) == c["items"]:
                c["result"], c["exception"] = "ACCEPTED", {"decision": e["decision"], "date": e["date"]}
                used.add(i)
                accepted.append(c["check"])
                break
    return accepted, [i for i in range(len(exceptions)) if i not in used]


def print_gate(result: dict) -> None:
    for c in result["checks"]:
        first = next((l for l in c["detail"].splitlines() if l.strip()), "")
        print(f"{c['result']:4}  {c['check']}" + (f"  — {first[:120]}" if first and c["result"] != "PASS" else ""))
        if c["result"] == "FAIL":
            print("      items: " + json.dumps(c.get("items", []), ensure_ascii=False)[:600])
        if c["result"] == "ACCEPTED":
            print(f"      owner exception {c['exception']['date']}: {c['exception']['decision'][:100]}")
    accepted = f"  ({len(result.get('accepted', []))} owner-accepted)" if result.get("accepted") else ""
    print(f"\nGATE {result['verdict']}{accepted}  head {result['head'][:12]}  scope base {result['scope_base'][:12]}")
    if result.get("unused_exceptions"):
        print(f"NOTE: exceptions {result['unused_exceptions']} matched no failure in {result['mode']} mode")


# ---------------------------------------------------------------- commands

def cmd_gate(args) -> int:
    tree = cwd_repo()
    exceptions = load_exceptions(Path(args.exceptions) if args.exceptions else None)
    result = gate(args.head if args.head != "HEAD" else git(tree, "rev-parse", "HEAD"),
                  args.skill, args.level, "contributor", worktree=tree, exceptions=exceptions)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print_gate(result)
    return 0 if result["verdict"] == "PASS" else 1


def target_dir(name: str, skill: str) -> Path:
    return Path(os.path.expanduser(DEFAULT_TARGETS.get(name, name))) / skill


def cmd_register(args) -> int:
    if bool(args.commit) == bool(args.snapshot):
        print("REFUSED: pass exactly one of --commit <sha> or --snapshot \"<reason>\"")
        return 1
    sha = git(MAIN, "rev-parse", args.commit) if args.commit else None
    reg = load_registry()
    expected = tree_hash_at(sha, args.skill) if sha else None
    for name in args.target:
        tdir = target_dir(name, args.skill)
        problem = unsafe_target(tdir)
        if problem:
            print(f"REFUSED {args.skill}@{name}: {problem}")
            return 1
        actual = tree_hash(tdir)
        if actual is None:
            print(f"REFUSED {args.skill}@{name}: {tdir} is not an installed folder")
            return 1
        if sha and actual != expected:
            print(f"REFUSED {args.skill}@{name}: installed tree {actual} != commit tree {expected}")
            return 1
        reg["entries"][f"{args.skill}@{name}"] = {
            "skill": args.skill, "target": name, "path": str(tdir), "commit": sha,
            "snapshot_reason": args.snapshot, "tree_sha256": actual,
            "version": skill_version((tdir / "SKILL.md").read_text())[0],
            "change_id": args.change_id, "recorded_at": now(),
        }
        print(f"registered {args.skill}@{name} " + (f"@ {sha[:12]}" if sha else "as snapshot (install refused)"))
    save_registry(reg)
    return 0


def installed_report() -> list[dict]:
    rows = []
    for key, e in sorted(load_registry()["entries"].items()):
        path = Path(e["path"])
        actual = tree_hash(path)
        rows.append({
            "entry": key, "version": e.get("version"), "commit": (e["commit"] or "snapshot")[:12],
            "state": "MISSING" if actual is None else ("OK" if actual == e["tree_sha256"] else "DRIFT"),
            "locked": is_locked(path),
            "merged": not e["commit"] or any(git_ok(MAIN, "merge-base", "--is-ancestor", e["commit"], ref)
                                             for ref in ("HEAD", "refs/heads/main", "refs/remotes/origin/main")),
        })
    return rows


def print_installed(rows: list[dict], indent: str = "") -> None:
    for r in rows:
        merge = "" if r["merged"] else "  <- installed but not merged into the main line"
        print(f"{indent}{r['state']:7} {'locked' if r['locked'] else 'WRITABLE':8} {r['entry']:32} "
              f"{r['version']} @ {r['commit']}{merge}")
    if not rows:
        print(f"{indent}none registered")


def cmd_check_installed(_args) -> int:
    rows = installed_report()
    print_installed(rows)
    return 1 if any(r["state"] != "OK" for r in rows) else 0


def cmd_lock(args, writable: bool) -> int:
    for key, e in load_registry()["entries"].items():
        if e["skill"] in args.skill:
            path = Path(e["path"])
            if unsafe_target(path):
                print(f"skipped {key}: {unsafe_target(path)}")
                continue
            set_writable(path, writable)
            print(f"{'unlocked' if writable else 'locked'} {key}")
    return 0


def open_changes() -> list[str]:
    rows = []
    for req in sorted(CHANGES.glob("*/REQUEST.md")):
        state = field(req.read_text(), "Status") or "unknown"
        if not state.lower().startswith(("done", "installed", "withdrawn", "rejected")):
            skills = field(req.read_text(), "Skill(s)") or "?"
            rows.append(f"{req.parent.name}: {state}  (skills: {skills})")
    return rows


def cmd_status(_args) -> int:
    print(f"main checkout: {MAIN}\nbranch: {git(MAIN, 'rev-parse', '--abbrev-ref', 'HEAD')}  "
          f"head: {git(MAIN, 'rev-parse', 'HEAD')}\n")
    print(f"{'skill':30} {'HEAD':10} {'working':10} uncommitted in main checkout")
    for skill_dir in sorted((MAIN / "skills").iterdir()):
        if skill_dir.name.startswith("_") or not (skill_dir / "SKILL.md").exists():
            continue
        name = skill_dir.name
        head_raw = blob("HEAD", f"skills/{name}/SKILL.md")
        head_v = skill_version(head_raw.decode(errors="replace"))[0] if head_raw else "untracked"
        work_v = skill_version((skill_dir / "SKILL.md").read_text())[0]
        dirty = [l for l in git(MAIN, "status", "--porcelain", "--", *skill_scope(name)).splitlines() if l.strip()]
        flag = f"{len(dirty)} files  <- open candidate: ask the owner which commit to build on" if dirty else "-"
        print(f"{name:30} {str(head_v):10} {str(work_v):10} {flag}")
    print("\ninstalled copies:")
    print_installed(installed_report(), "  ")
    print("\nopen change requests:")
    for row in open_changes() or ["none"]:
        print(f"  {row}")
    return 0


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def field(text: str, name: str) -> str | None:
    m = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.+?)\s*$", text, re.M | re.I)
    return m.group(1).strip() if m else None


def check_records(change: Path, sha: str, skills: list[str]) -> tuple[list[str], int]:
    problems = []
    review, packet, approval = (read(change / n) for n in ("REVIEW.md", "PACKET.md", "OWNER-APPROVAL.md"))
    if (field(review, "Verdict") or "").upper() != "PASS":
        problems.append("REVIEW.md: '**Verdict:** PASS' missing")
    for name, text in (("REVIEW.md", review), ("PACKET.md", packet), ("OWNER-APPROVAL.md", approval)):
        if field(text, "Commit") != sha:
            problems.append(f"{name}: '**Commit:**' must be the full commit {sha}")
    implementer, reviewer = field(packet, "Implementer"), field(review, "Reviewer")
    if not implementer or not reviewer or implementer.lower() == reviewer.lower():
        problems.append("PACKET.md Implementer and REVIEW.md Reviewer must both be present and differ")
    level_raw = field(packet, "Level") or ""
    level = int(level_raw[0]) if level_raw[:1] in ("1", "2", "3") else 0
    if not level:
        problems.append("PACKET.md: '**Level:**' must be 1, 2 or 3")
    if (field(approval, "Decision") or "").lower() != "install":
        problems.append("OWNER-APPROVAL.md: '**Decision:** install' missing")
    approved = {s.strip() for s in (field(approval, "Skills") or "").split(",") if s.strip()}
    if approved != set(skills):
        problems.append(f"OWNER-APPROVAL.md: '**Skills:**' must list exactly {', '.join(sorted(skills))}")
    if not (field(approval, "Owner reply") or "").strip('" '):
        problems.append("OWNER-APPROVAL.md: '**Owner reply:**' must quote the owner")
    return problems, level


def restore(dst: Path, backup: Path) -> None:
    if dst.exists():
        set_writable(dst, True)
        shutil.rmtree(dst)
    shutil.copytree(backup, dst, symlinks=True)
    set_writable(dst, False)


def cmd_install(args) -> int:
    if not CHANGE_ID_RE.match(args.change_id) or "/" in args.change_id or ".." in args.change_id:
        print("REFUSED: change id must look like YYYY-MM-DD_<project>_<skill>_<slug>")
        return 1
    sha = git(MAIN, "rev-parse", "--verify", f"{args.commit}^{{commit}}")
    change = CHANGES / args.change_id
    problems, level = check_records(change, sha, args.skill)
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems))
        return 1

    exceptions = load_exceptions(change / EXCEPTIONS_NAME)
    reg = load_registry()
    plan = []
    for skill in args.skill:
        for target in args.target:
            entry = reg["entries"].get(f"{skill}@{target}")
            if not entry:
                print(f"REFUSED: {skill}@{target} is not registered")
                return 1
            if not entry.get("commit"):
                print(f"REFUSED: {skill}@{target} is a snapshot entry ({entry.get('snapshot_reason')}); "
                      "the tool cannot rebuild that copy from a commit, so a MetaClaude session installs it")
                return 1
            dst = Path(entry["path"])
            problem = unsafe_target(dst)
            if problem:
                print(f"REFUSED: {skill}@{target}: {problem}")
                return 1
            if tree_hash(dst) != entry["tree_sha256"]:
                print(f"REFUSED: {skill}@{target} drifted from its record; resolve the drift first")
                return 1
            if not git_ok(MAIN, "merge-base", "--is-ancestor", entry["commit"], sha):
                print(f"REFUSED: installed commit {entry['commit'][:12]} ({skill}@{target}) is not an ancestor of "
                      f"{sha[:12]}; rebase onto it so installed work is not dropped")
                return 1
            plan.append((skill, target, entry, dst))
    for base in {e["commit"] for _, _, e, _ in plan}:
        if any(p.startswith(SHARED) for p in git(MAIN, "diff", "--name-only", base, sha).splitlines()) \
                and not set(SESSION_SKILLS) <= set(args.skill):
            print("REFUSED: skills/_shared changed; install newbeginning and closingtime together")
            return 1
        result = gate(sha, args.skill, level, "install", install_base=base, exceptions=exceptions)
        (change / f"INSTALL-GATE-{base[:8]}.json").write_text(json.dumps(result, indent=2) + "\n")
        if result["verdict"] != "PASS":
            print_gate(result)
            print(f"REFUSED: re-gate from installed commit {base[:12]} failed")
            return 1

    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    backups = []
    for i, (skill, target, entry, dst) in enumerate(plan):
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", target).strip("_") or "target"
        backup = change / "previous" / stamp / f"{i:02d}_{safe}" / skill
        if backup.exists() or change.resolve() not in backup.resolve().parents:
            print(f"REFUSED: unsafe backup path {backup}")
            return 1
        backup.parent.mkdir(parents=True)
        shutil.copytree(dst, backup, symlinks=True, ignore=copy_ignore)
        if tree_hash(backup) != tree_hash(dst):
            print(f"REFUSED: backup of {skill}@{target} does not match the installed copy; nothing changed")
            return 1
        backups.append(backup)

    sources = {skill: extract(sha, skill) for skill in args.skill}
    done = []
    try:
        for (skill, target, entry, dst), backup in zip(plan, backups):
            done.append((dst, backup))
            set_writable(dst, True)
            shutil.rmtree(dst)
            shutil.copytree(sources[skill], dst, symlinks=True, ignore=copy_ignore)
            if tree_hash(dst) != tree_hash(sources[skill]):
                raise RuntimeError(f"post-copy hash mismatch for {skill}@{target}")
            set_writable(dst, False)
    except Exception as exc:
        for dst, backup in reversed(done):
            restore(dst, backup)
        (change / "INSTALL-FAILED.json").write_text(json.dumps(
            {"commit": sha, "error": str(exc), "rolled_back": [str(d) for d, _ in done], "at": now()}, indent=2) + "\n")
        print(f"FAILED: {exc}; all {len(done)} replaced copies restored; registry unchanged")
        return 1
    finally:
        for src in sources.values():
            shutil.rmtree(src.parent.parent, ignore_errors=True)

    log = {"commit": sha, "change_id": args.change_id, "level": level, "at": now(), "installed": []}
    for skill, target, entry, dst in plan:
        version = skill_version((dst / "SKILL.md").read_text())[0]
        entry.update({"commit": sha, "version": version, "tree_sha256": tree_hash(dst),
                      "change_id": args.change_id, "recorded_at": now()})
        log["installed"].append({"skill": skill, "target": target, "version": version, "path": str(dst)})
        print(f"installed {skill}@{target} = {version} @ {sha[:12]} (locked)")
    save_registry(reg)
    (change / "INSTALL.json").write_text(json.dumps(log, indent=2) + "\n")
    if not git_ok(MAIN, "merge-base", "--is-ancestor", sha, "HEAD"):
        print("NOTE: not yet on the main line; a MetaClaude session must merge contrib branch for this commit.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    g = sub.add_parser("gate", help="run from your contrib worktree")
    g.add_argument("--head", default="HEAD")
    g.add_argument("--skill", action="append", required=True)
    g.add_argument("--level", type=int, choices=(1, 2, 3), required=True)
    g.add_argument("--out", help="write the JSON result here (the change folder's GATE.json)")
    g.add_argument("--exceptions", help=f"owner-accepted failures (the change folder's {EXCEPTIONS_NAME})")
    r = sub.add_parser("register")
    r.add_argument("skill")
    r.add_argument("--commit", help="commit whose skill tree the installed copy matches exactly")
    r.add_argument("--snapshot", help="reason the copy cannot match a commit (lean or harness-specific build)")
    r.add_argument("--target", action="append", required=True, help="claude, codex or a skills directory")
    r.add_argument("--change-id", default="baseline")
    sub.add_parser("check-installed")
    for name in ("lock", "unlock"):
        sub.add_parser(name).add_argument("skill", nargs="+")
    i = sub.add_parser("install")
    i.add_argument("skill", nargs="+")
    i.add_argument("--commit", required=True)
    i.add_argument("--change-id", required=True)
    i.add_argument("--target", action="append", default=None)
    args = p.parse_args(argv)
    if args.cmd == "install" and not args.target:
        args.target = list(DEFAULT_TARGETS)
    return {
        "status": cmd_status, "gate": cmd_gate, "register": cmd_register,
        "check-installed": cmd_check_installed, "lock": lambda a: cmd_lock(a, False),
        "unlock": lambda a: cmd_lock(a, True), "install": cmd_install,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
