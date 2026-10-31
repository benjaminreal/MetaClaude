#!/usr/bin/env python3
"""Adversarial tests for skills/_contrib/skillchange.py.

Builds a scratch clone of this repository at a fixed base, installs into fake
target folders under a temporary directory, and never touches real installed
copies or the main checkout. Usage:

    python3 skills/_contrib/tests/adversarial_test.py [--keep]
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC_MAIN = Path(__file__).resolve().parents[3]
BASE_COMMIT = "e503814"
RESULTS: list[tuple[str, bool, str]] = []


def sh(cmd, cwd, check=True, env=None):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
             GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com", **(env or {}))
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=e)
    if check and p.returncode:
        raise RuntimeError(f"{cmd} failed: {p.stdout}\n{p.stderr}")
    return p


def expect(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      {detail[-600:]}"))


class Lab:
    def __init__(self, root: Path):
        self.root = root
        self.repo = root / "repo"
        sh(["git", "clone", "-q", "--no-hardlinks", str(SRC_MAIN), str(self.repo)], root)
        sh(["git", "checkout", "-q", "-b", "main-test", BASE_COMMIT], self.repo)
        for rel in ("skills/_contrib", "skills/STANDARDS.md"):
            src, dst = SRC_MAIN / rel, self.repo / rel
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            else:
                shutil.copy2(src, dst)
        sh(["git", "add", "skills/_contrib", "skills/STANDARDS.md"], self.repo)
        sh(["git", "commit", "-qm", "tooling"], self.repo)
        self.base = sh(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()
        self.tool = self.repo / "skills/_contrib/skillchange.py"
        self.changes = self.repo / "private-artifacts/skill-changes"
        self.n = 0

    def tool_run(self, *args, cwd=None):
        p = sh([sys.executable, str(self.tool), *args], cwd or self.repo, check=False)
        return p.returncode, p.stdout + p.stderr

    def worktree(self, base: str) -> Path:
        self.n += 1
        path = self.root / f"wt{self.n}"
        sh(["git", "worktree", "add", "-q", "-b", f"contrib/t{self.n}", str(path), base], self.repo)
        return path

    def commit(self, wt: Path, msg: str) -> str:
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-qm", msg], wt)
        return sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()

    def target(self, name: str, skill: str, rev: str) -> Path:
        tdir = self.root / name
        tdir.mkdir(exist_ok=True)
        archive = subprocess.run(["git", "archive", rev, f"skills/{skill}"], cwd=str(self.repo),
                                 capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(tdir), "--strip-components=1"], input=archive, check=True)
        return tdir

    def records(self, cid, sha, skills, level=1, decision="install", commit_field=None, reviewer="Reviewer B"):
        d = self.changes / cid
        d.mkdir(parents=True, exist_ok=True)
        c = commit_field or sha
        (d / "PACKET.md").write_text(f"**Implementer:** Implementer A\n**Commit:** {sha}\n**Level:** {level}\n")
        (d / "REVIEW.md").write_text(f"**Reviewer:** {reviewer}\n**Commit:** {c}\n**Verdict:** PASS\n")
        (d / "OWNER-APPROVAL.md").write_text(
            f"**Decision:** {decision}\n**Skills:** {', '.join(skills)}\n**Commit:** {sha}\n"
            f"**Owner reply:** \"yes, install it\"\n**Date:** 2026-10-31\n")
        return cid


def bump_calibre(wt: Path, version: str, extra: str = ""):
    p = wt / "skills/calibre/SKILL.md"
    t = p.read_text()
    import re
    t = re.sub(r"^version: .*$", f"version: {version}", t, count=1, flags=re.M)
    t += f"\n**v{version} — 2026-10-31**\n- Test change.{extra}\n"
    p.write_text(t)


def main() -> int:
    keep = "--keep" in sys.argv
    root = Path(tempfile.mkdtemp(prefix="skillchange-adv-")).resolve()
    try:
        lab = Lab(root)
        A = lab.target("targetA", "calibre", lab.base)
        B = lab.target("targetB", "calibre", lab.base)
        rc, out = lab.tool_run("register", "calibre", "--commit", lab.base, "--target", str(A), "--target", str(B))
        expect("register fake targets", rc == 0, out)
        lab.tool_run("lock", "calibre")

        # S1 happy path with an added file
        wt = lab.worktree(lab.base)
        bump_calibre(wt, "1.0.1")
        (wt / "skills/calibre/extra.md").write_text("Extra reference.\n")
        w1 = lab.commit(wt, "calibre 1.0.1")
        rc, out = lab.tool_run("gate", "--skill", "calibre", "--level", "1", cwd=wt)
        expect("S1 gate passes a clean level-1 change", rc == 0, out)
        cid = lab.records("2026-10-31_test_calibre_one", w1, ["calibre"])
        rc, out = lab.tool_run("install", "calibre", "--commit", w1, "--change-id", cid,
                               "--target", str(A), "--target", str(B))
        expect("S1 install succeeds", rc == 0, out)
        expect("S1 installed copy has extra.md and is locked",
               (A / "calibre/extra.md").exists() and not os.access(A / "calibre/SKILL.md", os.W_OK))

        # S2 a later change deletes the file: no stale files, no stray folders
        wt2 = lab.worktree(w1)
        (wt2 / "skills/calibre/extra.md").unlink()
        bump_calibre(wt2, "1.0.2")
        w2 = lab.commit(wt2, "calibre 1.0.2")
        cid2 = lab.records("2026-10-31_test_calibre_two", w2, ["calibre"])
        rc, out = lab.tool_run("install", "calibre", "--commit", w2, "--change-id", cid2,
                               "--target", str(A), "--target", str(B))
        expect("S2 install of a deletion succeeds", rc == 0, out)
        expect("S2 deleted file is gone and no stray skills/ folder appears",
               not (A / "calibre/extra.md").exists() and not (A / "skills").exists(), str(list(A.iterdir())))
        rc, out = lab.tool_run("check-installed")
        expect("S2 check-installed reports OK", rc == 0 and "DRIFT" not in out, out)

        # S3 planted intermediate commit touching protected and undeclared files
        wt3 = lab.worktree(w2)
        (wt3 / "skills/STANDARDS.md").write_text("weakened\n")
        (wt3 / "skills/sync-jobs/SKILL.md").write_text((wt3 / "skills/sync-jobs/SKILL.md").read_text() + "\nx\n")
        lab.commit(wt3, "planted")
        bump_calibre(wt3, "1.0.3")
        w3 = lab.commit(wt3, "calibre 1.0.3")
        rc, out = lab.tool_run("gate", "--skill", "calibre", "--level", "1", cwd=wt3)
        expect("S3 gate fails on planted protected/undeclared changes",
               rc == 1 and "protected_unchanged:skills/STANDARDS.md" in out and "only_declared_skills_touched" in out, out)
        cid3 = lab.records("2026-10-31_test_calibre_three", w3, ["calibre"])
        rc, out = lab.tool_run("install", "calibre", "--commit", w3, "--change-id", cid3, "--target", str(A))
        expect("S3 install refuses the planted change", rc == 1, out)

        # S4 quoted filename and binary file
        wt4 = lab.worktree(w2)
        bump_calibre(wt4, "1.0.3")
        (wt4 / "skills/calibre/notés.md").write_text("Contact bob@realmail.io at /Users/someone/x\n")
        (wt4 / "skills/calibre/blob.dat").write_bytes(b"abc\0def /Users/x\n")
        lab.commit(wt4, "quoted and binary")
        rc, out = lab.tool_run("gate", "--skill", "calibre", "--level", "1", cwd=wt4)
        expect("S4 gate catches quoted-name privacy and binary files",
               rc == 1 and "privacy:email_address" in out and "privacy:absolute_user_path" in out
               and "no_binary_files" in out, out)

        # S5 stubbed eval hiding a broken skill
        wt5 = lab.worktree(w2)
        bump_calibre(wt5, "1.0.3")
        p = wt5 / "skills/calibre/SKILL.md"
        p.write_text("\n".join(l for l in p.read_text().splitlines() if not l.startswith("description:")) + "\n")
        (wt5 / "skills/calibre/evals/structural_eval.py").write_text("import sys\nsys.exit(0)\n")
        lab.commit(wt5, "stub eval")
        rc, out = lab.tool_run("gate", "--skill", "calibre", "--level", "2", cwd=wt5)
        expect("S5 base tests catch a stubbed eval",
               rc == 1 and "base_tests_on_new_code:skills/calibre/evals/structural_eval.py" in out, out)

        # S6 approval records must be explicit
        wt6 = lab.worktree(w2)
        bump_calibre(wt6, "1.0.3")
        w6 = lab.commit(wt6, "calibre 1.0.3")
        cid6 = lab.records("2026-10-31_test_calibre_six", w6, ["calibre"], decision="do not install")
        rc, out = lab.tool_run("install", "calibre", "--commit", w6, "--change-id", cid6, "--target", str(A))
        expect("S6 'do not install' is refused", rc == 1 and "Decision" in out, out)
        lab.records(cid6, w6, ["calibre"], commit_field=w6[:7])
        rc, out = lab.tool_run("install", "calibre", "--commit", w6, "--change-id", cid6, "--target", str(A))
        expect("S6 short commit in review is refused", rc == 1 and "full commit" in out, out)
        lab.records(cid6, w6, ["calibre"], reviewer="Implementer A")
        rc, out = lab.tool_run("install", "calibre", "--commit", w6, "--change-id", cid6, "--target", str(A))
        expect("S6 self-review is refused", rc == 1 and "differ" in out, out)
        rc, out = lab.tool_run("install", "calibre", "--commit", w6, "--change-id", "../escape", "--target", str(A))
        expect("S6 path-like change id is refused", rc == 1 and "change id" in out, out)

        # S7 symlinked target
        S = root / "targetS"
        S.mkdir()
        (S / "calibre").symlink_to(A / "calibre")
        rc, out = lab.tool_run("register", "calibre", "--commit", w2, "--target", str(S))
        expect("S7 symlinked target is refused", rc == 1 and "symlink" in out, out)

        # S8 gate from an unrelated repository
        other = root / "other"
        other.mkdir()
        sh(["git", "init", "-q"], other)
        rc, out = lab.tool_run("gate", "--skill", "calibre", "--level", "1", cwd=other)
        expect("S8 gate refuses a foreign repository", rc != 0 and "REFUSED" in out, out)

        # S9 failure on the second target rolls everything back
        spec = importlib.util.spec_from_file_location("sc_lab", lab.tool)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        before = json.loads((lab.changes / "installed.json").read_text())
        real_copytree = mod.shutil.copytree

        def flaky(src, dst, *a, **k):
            if Path(dst).resolve() == (B / "calibre").resolve() and "skilltree-" in str(src):
                raise OSError("injected failure")
            return real_copytree(src, dst, *a, **k)

        mod.shutil.copytree = flaky
        cid9 = lab.records("2026-10-31_test_calibre_nine", w6, ["calibre"])
        cwd = os.getcwd()
        os.chdir(lab.repo)
        try:
            rc = mod.main(["install", "calibre", "--commit", w6, "--change-id", cid9,
                           "--target", str(A), "--target", str(B)])
        finally:
            os.chdir(cwd)
            mod.shutil.copytree = real_copytree
        after = json.loads((lab.changes / "installed.json").read_text())
        rc2, out2 = lab.tool_run("check-installed")
        expect("S9 partial failure rolls back both targets and leaves the registry unchanged",
               rc == 1 and before == after and rc2 == 0 and (lab.changes / cid9 / "INSTALL-FAILED.json").exists(), out2)

        # S10 session skills: unsynced shared edit fails; synced edit with both bumps passes
        wt10 = lab.worktree(lab.base)
        with open(wt10 / "skills/_shared/recovery.md", "a") as f:
            f.write("- Test line.\n")
        lab.commit(wt10, "unsynced")
        rc, out = lab.tool_run("gate", "--skill", "newbeginning", "--level", "1", cwd=wt10)
        expect("S10 unsynced shared edit fails parity and scope",
               rc == 1 and "shared_runtime_copies_identical" in out and "only_declared_skills_touched" in out, out)
        sh([sys.executable, "skills/_shared/sync_runtime_copies.py"], wt10)
        import re
        for skill in ("newbeginning", "closingtime"):
            p = wt10 / "skills" / skill / "SKILL.md"
            t = p.read_text()
            m = re.search(r'version: "(\d+)\.(\d+)\.(\d+)"', t)
            new = f"{m[1]}.{m[2]}.{int(m[3]) + 1}"
            t = t.replace(m[0], f'version: "{new}"', 1).replace(
                "## 7. Version & Changelog\n", f"## 7. Version & Changelog\n\n**v{new} — 2026-10-31 — candidate**\n\n- Test.\n", 1)
            p.write_text(t)
        lab.commit(wt10, "synced and bumped")
        rc, out = lab.tool_run("gate", "--skill", "newbeginning", "--skill", "closingtime", "--level", "1", cwd=wt10)
        expect("S10 synced session-skill change passes, including base tests", rc == 0, out)
    finally:
        if keep:
            print(f"kept {root}")
        else:
            for p in root.rglob("*"):
                try:
                    if not p.is_symlink():
                        p.chmod(p.stat().st_mode | 0o200)
                except OSError:
                    pass
            shutil.rmtree(root, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
