"""Recertification regression corpus: reviewer, adversarial and userlab reproductions.

Binding spec: private-artifacts/evals/vnext/phase4_5_r3/REPAIR-DECISIONS-R4.md,
section "Tests first (T)" and decisions P1-P8 (two documentation reproductions
belong to P9/P10 and are grouped separately). Freeze rule
(phase4_tools/README.md): a case changes only with a cited owner or spec
decision, recorded next to the case.

Source IDs in case titles:
  R1, R2, R3   independent reviewer reproductions of rounds 1, 2 and 3
  ADV2, ADV3   UNSAFE adversarial cases (phase4_5_r2|r3/adversarial/EDGE-CASES.md)
  UL2, UL3     external-user blockers (phase4_5_r2|r3/userlab/REPORT.md)
  AUD3         round-3 claim-audit items the round-3 decision cites
  R3.2         real-log compatibility forms that must keep passing

Every case builds throwaway packages from this directory's runtime files (the
code under test; the synced package copies are never executed) and a fresh
project under a realpath-resolved temporary directory. Nothing is read from
private-artifacts/ or the current directory at run time. Crash cases inject a
fault from this file into a subprocess, as the reviewer drivers did; the
package files are never modified.

Reproductions already held by an existing fixture with the same assertion are
not duplicated; OVERLAPS names the fixture that holds each one.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import helpers as H
import schemas as S
from repair_fixtures import refuses

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
RUNTIME = ("helpers.py", "schemas.py", "runtime_cli.py", "workflow.py")
POLICY = "private-artifacts/session-journal/_policy.json"
OWNER = "Approve the displayed synthetic scope."
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
INDEX = ("# Synthetic Project\n\nUpdated: 2026-10-28\n\n## Summary\nOriginal summary.\n\n"
         "## Active TODOs\nFrozen mirror.\n\n## Key Decisions\nKeep source evidence.\n")
PENDING = ("## Candidate 1\n**Type:** observation\n**Insight:** Verify saved bytes before reporting success.\n"
           "**Connection:** synthetic\n**Status:** pending\n")


def entry(number="[N]", date="2026-10-28"):
    return (f"### Session #{number} | {date} | Code (Synthetic)\n\n**Focus:** Review synthetic state.\n"
            "**Done:** Checked synthetic evidence.\n**Next:** Inspect the next fixture.\n**Blockers:** None.\n")


SEED = "# Session Log\n\n" + entry(1, "2026-10-21") + "\n---\n\n" + entry(2, "2026-10-22")

# Keys of a draft receipt frozen by 3.2.2 (helpers.freeze_draft at that version).
RECEIPT_322_KEYS = {
    "schema_version", "kind", "recovery_version", "invocation_id", "skill", "workspace_root", "workspace_id",
    "continue_parent", "snapshot_sha256", "snapshot_observed_at", "snapshot_captured_at", "invocation_started_at",
    "observed_tail_sha256", "entry_sha256", "entry_words", "index_draft_sha256", "index_draft", "m2_preimages",
    "scope_operations", "local_payload_hashes", "scope_lines", "scope_sha256", "drafted_at", "approved_at",
    "scope_string", "owner_reply", "receipt_sha256",
}

OVERLAPS = {
    "R1 normal-controls, R2 r1-unborn, R3 r1-unborn": "round3_fixtures 'Round-1 reasons' (unborn close journals once)",
    "R1 dropbox-conflict, R2 r1-dropbox-*, R3 r1-conflict-*": "round3_fixtures 'Round-1 reasons' (conflicted copy: SYNC_CONFLICT, EINVALIDENVELOPE)",
    "R1 unborn-git": "round3_fixtures 'Round-1 reasons'; repair_fixtures 'D7-D9 skew ... first unborn close'",
    "R1 second-header, R2 r1-entry-history, R3 r1-entry-refusals": "round3_fixtures 'Round-1 reasons' (EENTRYFORMAT); repair_fixtures 'D9 rendered entry refusals'",
    "R1 other-workspace, R2 r1-foreign, R3 r1-foreign-root": "round3_fixtures 'Round-1 reasons' (WORKSPACE_MISMATCH, EWORKSPACEMISMATCH)",
    "R1 post-append-interruption, R1 fresh-reclose-duplicate": "round3_fixtures 'R1 D5c foreign index'; repair_fixtures 'D4 crash states, fresh close'",
    "R1 journal-failure, R2 r1-journal-obstruction, R3 r1-journal-obstructed": "round3_fixtures 'Round-1 reasons' (EJOURNAL, log absent)",
    "R1 edited-entry/changed-tail, R2 r1-edited-entry/r1-changed-tail": "round3_fixtures 'Round-1 reasons' (EDRAFTMISMATCH, ESTALE)",
    "R1 receipt-validation, R2/R3 r1-receipts-*": "round3_fixtures 'Round-1 reasons'; repair_fixtures 'D6-D8 identity, capability and parsed clock matrix'",
    "R2 r1-approval-exclusion, R3 r1-scope-foreign": "round3_fixtures 'Round-1 reasons' (SCOPE_UNAPPROVED)",
    "R2 E2b-learning-noop, ADV2 E2b, R3 r2-learning-unused": "round3_fixtures 'S1 ... S2 E2b'; round3_1_fixtures 'F1 skipped/zero learning'",
    "R2 D5c-foreign-index, ADV2 D5c, R3 r2-foreign-index, R3 r2-abandon-child": "round3_fixtures 'R1 D5c foreign index'",
    "ADV2 D4 (abandon of appended intent, no words)": "round3_fixtures 'R1 D5c foreign index'; repair_fixtures 'D4 crash states'",
    "R2 D5c-relocated, R2 relocated-complete, R3 r2-moved-*, R3 r2-nb-moved-index, UL3 13": "round3_fixtures 'R1 relocated-complete and unfinished remount'",
    "R2 D1-crash-lock, UL2 blocker 1, R3 r2-crashed-lock": "round3_fixtures 'R3 D1-crash-lock immediate recovery'",
    "R2 D1b-temp-lock, ADV2 D1b, R3 r2-lock-domain": "round3_fixtures 'R3 ... D1b TMPDIR'",
    "R2 C3b-superseded, R3 r2-superseded": "round3_fixtures 'R5 ... C3b invocation reuse'",
    "R2 A1-index-alias, ADV2 A1, R3 r2-index-alias(-late)": "round3_fixtures 'R2 A1 all-target preflight'",
    "R2 B7b-stale-*, ADV2 B7b, R2 E6-old-approval-first-use, R3 r2-stale-*": "round3_fixtures 'R5 B7b/E6 wall-clock evidence'",
    "R2 E6-clock-reuse, ADV2 E6, R3 two-day-pending-approval": "round3_fixtures 'R5 ... old pending approval and owner words'",
    "R3 r2-delay-*": "round3_1_fixtures 'F5 constructor timestamps, 15-minute boundary'",
    "R2 gap2-audit-first-entry, UL2 gap 2, R3 r2-first-under-title": "round3_fixtures 'R4 gap2 direct title entry'",
    "ADV2 A7c": "round3_fixtures 'R4 ... unicode digits'",
    "R2 C10b-snapshot-target, ADV2 C10b": "round3_fixtures 'R4 ... C10b'",
    "R2 nb-bootstrap, R3 nb-bootstrap, R3 nb-reconstruct": "repair_fixtures 'D5 opening index, preimage existence'",
    "R3 r31-stage-once": "round3_1_fixtures 'F1 verified append ...' and 'F1 ESTAGE ...'",
}
NOT_TESTED = {
    "R2 A8-index-case, ADV2 A8": "case-sensitive twin files: out of scope in REPAIR-DECISIONS-R4; volume is case-insensitive",
    "R3 r2-superseded-first": "superseded draft approved first: out of scope (conversation duty)",
    "R3 lineage-parser": "compares two parser versions; its four inputs are the A8g/h/i/j cases below",
}

CHECKS = []  # (group, label, fn)


def case(group, label):
    def register(fn):
        CHECKS.append((group, label, fn))
        return fn
    return register


def sha_bytes(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes()) if path.exists() else "absent"


def tree(root):
    """Every path below root, with file hashes: detects created dirs, locks and records."""
    return {p.relative_to(root).as_posix(): ("dir" if p.is_dir() else sha_bytes(p.read_bytes()))
            for p in sorted(root.rglob("*"))}


def tree_diff(before, after):
    return {"added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after)),
            "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k])}


def codes(verdict):
    return {f["code"] for f in verdict.get("failures", [])}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


class Lab:
    """One temporary base: packages built from this directory, projects and scratch inputs."""

    def __init__(self, base):
        self.base = base
        self.seq = 0
        self.packages = {}
        (base / "scratch").mkdir()

    def scripts(self, skill):
        if skill not in self.packages:
            package = self.base / "packages" / skill
            (package / "scripts").mkdir(parents=True)
            shutil.copy2(SKILLS / skill / "SKILL.md", package / "SKILL.md")
            for name in RUNTIME:
                shutil.copy2(HERE / name, package / "scripts" / name)
            self.packages[skill] = package / "scripts"
        return self.packages[skill]

    def save(self, name, value):
        self.seq += 1
        path = self.base / "scratch" / f"{self.seq:03d}-{name}"
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def run(self, skill, *args, script=None):
        target = script or self.scripts(skill) / "runtime_cli.py"
        command = [sys.executable, "-B", str(target), *map(str, args)]
        proc = subprocess.run(command, cwd=self.base, capture_output=True, text=True, env=ENV)
        try:
            out = json.loads(proc.stdout)
        except ValueError:
            out = {"stdout": proc.stdout[-300:], "stderr": proc.stderr[-300:]}
        return proc.returncode, out

    def ok(self, skill, *args):
        rc, out = self.run(skill, *args)
        assert rc == 0, (args[0], rc, out)
        return out

    def refused(self, skill, *args, code=None):
        """A helper refusal: exit 2 with the CLI's JSON error object (not an argparse error)."""
        rc, out = self.run(skill, *args)
        assert rc == 2 and out.get("ok") is False, ("expected refusal", args[0], rc, out)
        if code:
            assert out["error"]["code"] == code, ("expected " + code, args[0], out["error"])
        return out

    def inject(self, skill, body, *args):
        script = self.save("inject.py", "import json, os, pathlib, sys\nsys.dont_write_bytecode = True\n"
                                        "sys.path.insert(0, sys.argv[1])\nimport helpers\n" + body)
        return self.run(skill, self.scripts(skill), *args, script=script)

    def project(self, name="project", session=None, index=INDEX):
        root = self.base / name
        root.mkdir(parents=True)
        if index is not None:
            (root / "project_index.md").write_text(index, encoding="utf-8")
        if session is not None:
            (root / "project_session.md").write_text(session, encoding="utf-8")
        return root

    def envelope(self, root, skill="closingtime", scope=None, hashes=None):
        e = self.ok(skill, "new-envelope", root)
        e["project"] = "Synthetic"
        e["capability_profile"]["external"] = {"tasks_mcp": "absent", "open_brain": "absent"}
        e["mcp_receipts"] = [{"schema_version": "1.0", "capability": "tasks_mcp", "identity": {"project": "Synthetic"},
                              "observed_at": e["invocation_started_at"],
                              "operation_fingerprint": sha_bytes(b"synthetic unavailable task read"),
                              "row_fingerprint": None, "row_count": 0, "status": "unavailable", "capability_state": "absent"}]
        e["mutation_scope"]["M2"] = list(scope or [])
        if hashes:
            e["local_payload_hashes"] = dict(hashes)
        return e

    def freeze_args(self, e, text=None, index=None, cont=None):
        args = ["freeze-draft", self.save("envelope.json", e)]
        if text is not None:
            args.append(self.save("entry.md", text))
        if index is not None:
            args += ["--index-draft", self.save("index-draft.md", index)]
        if cont:
            args += ["--continue", cont]
        return args

    def freeze(self, e, text=None, index=None, cont=None):
        return self.ok(e["skill"], *self.freeze_args(e, text, index, cont))

    def approve(self, e, draft, words=OWNER):
        a = self.ok(e["skill"], "approve-draft", self.save("draft.json", draft), draft["scope_lines"], "--owner-reply", words)
        e["approval"] = {"granted": True, "scope_string": a["scope_string"]}
        return a

    def append_args(self, e, a, text=None):
        return ["append", self.save("approved-envelope.json", e), self.save("entry.md", text or entry()), self.save("approved.json", a)]

    def append(self, e, a, text=None):
        return self.ok("closingtime", *self.append_args(e, a, text))

    def write_args(self, e, a, target, payload, operation="replace", expect=None, words=OWNER, rows=None):
        args = ["write-approved", self.save("write-envelope.json", e), self.save("approved.json", a), target]
        if payload is not None:
            args.append(self.save("payload.md", payload))
        args += ["--operation", operation, "--expect", expect]
        if words is not None:
            args += ["--owner-reply", words]
        if rows is not None:
            args += ["--mirror-rows", self.save("rows.json", rows)]
        return args

    def write(self, e, a, target, payload, **kw):
        return self.ok(e["skill"], *self.write_args(e, a, target, payload, **kw))

    def close(self, root, index=True, stage=False, index_text=INDEX):
        scope = ["project_session.md"] + (["project_index.md"] if index else []) + (["pending_learnings.md"] if stage else [])
        e = self.envelope(root, scope=scope)
        a = self.approve(e, self.freeze(e, entry(), index_text if index else None))
        out = self.append(e, a)
        if index:
            self.write(e, a, "project_index.md", index_text, expect=a["m2_preimages"]["project_index.md"])
        return e, a, out

    def audit(self, root):
        return self.ok("closingtime", "audit", root)


@contextlib.contextmanager
def lab():
    with tempfile.TemporaryDirectory(prefix="recert-") as raw:
        yield Lab(Path(os.path.realpath(raw)))


def numbers(items):
    return [x["session_number"] for x in items]


def history_refused(L, root, warning):
    """Malformed history: both validators flag EHISTORY; freeze refuses; no byte changes."""
    before = tree(root)
    e = L.envelope(root, scope=["project_session.md"])
    assert warning in e["local_snapshot"]["parse_warnings"], e["local_snapshot"]["parse_warnings"]
    for skill in ("newbeginning", "closingtime"):
        check = e if skill == "closingtime" else L.envelope(root, skill)
        rc, verdict = L.run(skill, "validate", L.save("validate.json", check))
        assert rc == 1 and "EHISTORY" in codes(verdict), (skill, verdict)
    L.refused("closingtime", *L.freeze_args(e, entry()), code="EHISTORY")
    assert tree(root) == before, tree_diff(before, tree(root))


def adopt(L, root):
    """adopt-history proposal: (output, exact policy text, its SHA-256, scope line)."""
    out = L.ok("closingtime", "adopt-history", root)
    texts = list(strings(out))
    policies = []
    for text in texts:
        try:
            value = json.loads(text)
        except ValueError:
            continue
        if isinstance(value, dict) and "historical_entries" in value:
            policies.append(text)
    assert len(policies) == 1, ("one exact policy text expected", out)
    digest = sha_bytes(policies[0].encode("utf-8"))
    assert digest in texts or digest[len("sha256:"):] in texts, ("policy SHA-256 missing", digest, out)
    lines = {line for text in texts for line in text.splitlines()
             if line.startswith("M2 replace " + POLICY + " (adopt ")}
    assert len(lines) == 1, ("one adopt scope line expected", out)
    return out, policies[0], digest, lines.pop()


def write_policy(L, root, policy, digest, expect):
    e = L.envelope(root, scope=[{"path": POLICY, "operation": "replace"}], hashes={POLICY: digest})
    draft = L.freeze(e)
    assert "M2 replace " + POLICY in draft["scope_lines"], draft["scope_lines"]
    a = L.approve(e, draft, "Adopt the listed historical entries.")
    out = L.write(e, a, POLICY, policy, expect=expect)
    assert (root / POLICY).read_text(encoding="utf-8") == policy
    return out


def assert_clean(audit, historical):
    assert not audit["unjournaled"] and not audit["orphan_records"] and not audit["errors"], audit
    assert numbers(audit.get("historical", [])) == historical, audit.get("historical")


# --------------------------------------------------------------------------
# P1 legacy heading grammar
# --------------------------------------------------------------------------

@case("P1 legacy heading grammar", "R3 A8j; ADV3 A8j '## Session 2026-10-22 ...' is text and the next close is #3, not #2027 (P1.1)")
def dated_heading_close():
    with lab() as L:
        root = L.project(session=SEED + "\n---\n\n## Session 2026-10-22 planning notes\n\nNext: Legacy action.\n")
        e = L.envelope(root, scope=["project_session.md"])
        snap = e["local_snapshot"]
        assert snap["session"]["latest_session_number"] == 2, snap["session"]
        assert not set(snap["parse_warnings"]) & S.HISTORY_ERRORS, snap["parse_warnings"]
        out = L.append(e, L.approve(e, L.freeze(e, entry())))
        assert out["session_number"] == 3, out
        text = (root / "project_session.md").read_text()
        assert "### Session #3 |" in text and "#2027" not in text
        audit = L.audit(root)
        assert audit["entries"] == 3 and audit["journaled"] == 1 and not audit["errors"], audit


@case("P1 legacy heading grammar", "R3 A8j; ADV3 A8j dated, slash, compact, dotted, Spanish and five-digit tokens: no number, no entry boundary (P1.1)")
def dated_tokens():
    for heading in ("## Session 2026-10-22 planning notes", "## Session 2026/10/22", "## Session 20261022",
                    "### Session 2026-10-22 review", "#### Session 2026.10.22", "## Sesión 2026-10-22 notas",
                    "## Session 12345 — five digits"):
        assert S.legacy_session_number(heading) is None, (heading, S.legacy_session_number(heading))
        text = SEED + "\n" + heading + "\nNext: legacy prose.\n"
        entries, warnings = S.parse_history(text)
        assert numbers(entries) == [1, 2], heading
        assert heading in entries[-1]["chunk"], (heading, "became an entry boundary")
        assert not set(warnings) & S.HISTORY_ERRORS, (heading, warnings)
        assert H._last_session_entries(text)[1] == 2, (heading, H._last_session_entries(text)[1])
    assert S.legacy_session_number("## Session 5 — Old") == 5  # a real v1 heading keeps its number


@case("P1 legacy heading grammar", "R3 A8g; ADV3 A8g impossible legacy range '2026-13-45–16' refuses EHISTORY, no bytes change (P1.2)")
def impossible_range():
    with lab() as L:
        root = L.project(session=SEED + "\n---\n\n### Session #3 | 2026-13-45–16 | Code (Synthetic)\n\nNext: Legacy action.\n")
        history_refused(L, root, "session_date_impossible")
    for dates, impossible in (("2026-10-05–03", True), ("2026-10-30–11-31", True), ("2026-02-28–30", True),
                              ("2026-10-02–03", False), ("2026-10-30–11-02", False)):
        text = SEED + f"\n---\n\n### Session #3 | {dates} | Code (Synthetic)\nLegacy multi-day entry.\n"
        warnings = S.parse_history(text)[1]
        assert ("session_date_impossible" in warnings) == impossible, (dates, warnings)


@case("P1 legacy heading grammar", "R3 A8h; ADV3 A8h impossible level-2 date '2026-99-99' refuses EHISTORY, no bytes change (P1.2)")
def impossible_level2():
    with lab() as L:
        root = L.project(session=SEED + "\n---\n\n## Session #3 | 2026-99-99 | Code (Synthetic)\n\nNext: Legacy action.\n")
        history_refused(L, root, "session_date_impossible")
    for heading, impossible in (("## Session 3 — 2026-02-30 retro", True), ("#### Session #2A | 2026-13-01 | Code", True),
                                ("## Session 3 — 2026-02-28 retro", False)):
        warnings = S.parse_history(SEED + "\n" + heading + "\nb\n")[1]
        assert ("session_date_impossible" in warnings) == impossible, (heading, warnings)


@case("P1 legacy heading grammar", "R3 A8i; ADV3 A8i '## Session 2' beside strict #2 warns legacy_duplicate_number, does not block, allocates #3 (P1.3)")
def legacy_duplicate():
    assert "legacy_duplicate_number" not in S.HISTORY_ERRORS
    with lab() as L:
        root = L.project(session=SEED + "\n---\n\n## Session 2 — Duplicate legacy number\n\nNext: Legacy action.\n")
        e = L.envelope(root, scope=["project_session.md"])
        warnings = e["local_snapshot"]["parse_warnings"]
        assert "legacy_duplicate_number" in warnings and not set(warnings) & S.HISTORY_ERRORS, warnings
        assert L.ok("newbeginning", "validate", L.save("nb.json", L.envelope(root, "newbeginning")))["valid"]
        out = L.append(e, L.approve(e, L.freeze(e, entry())))
        assert out["session_number"] == 3, out
        assert not L.audit(root)["errors"]
        v1 = L.project("v1", session="# Log\n\n## Session 5 — First\nb\n\n## Session 5 — Repeated\nc\n")
        snap = L.ok("closingtime", "snapshot", v1)
        assert "legacy_duplicate_number" in snap["parse_warnings"] and snap["session"]["latest_session_number"] == 5, snap["parse_warnings"]
        supplement = L.project("supplement", session="# Log\n\n" + entry(12, "2026-10-01") + "\n### Session #12A | 2026-10-02 | Code\nb\n")
        assert "legacy_duplicate_number" not in L.ok("closingtime", "snapshot", supplement)["parse_warnings"]


@case("P1 legacy heading grammar", "R3.2 real-log forms: title suffix, subheading, supplement, v1/Spanish v1, multi-day range and plain legacy duplicate stay non-blocking (P1.3)")
def real_log_forms():
    log = ("# Session Log — Synthetic Project\n\n## Session 4 — Kickoff\nNext: a.\n\n## Session 5 — Planning\nNext: b.\n\n"
           "## Session 5 — Planning, continued\nNext: c.\n\n## Sesión 6 · 3 de mayo\nNext: d.\n\n---\n\n" + entry(7, "2026-10-01")
           + "\n## Session Context\nInternal subheading.\n\n### Session #7A | 2026-10-02 | Code\nSupplement.\n\n"
           "### Session #8 | 2026-10-02–03 | Code\nMulti-day legacy entry.\n\n---\n\n" + entry(9, "2026-10-04"))
    with lab() as L:
        root = L.project(session=log)
        e = L.envelope(root, scope=["project_session.md"])
        snap = e["local_snapshot"]
        assert not set(snap["parse_warnings"]) & S.HISTORY_ERRORS, snap["parse_warnings"]
        assert snap["session"]["latest_session_number"] == 9, snap["session"]
        out = L.append(e, L.approve(e, L.freeze(e, entry())))
        assert out["session_number"] == 10, out
        assert (root / "project_session.md").read_text().startswith(log)
        assert not L.audit(root)["errors"]
        assert "legacy_duplicate_number" in snap["parse_warnings"], snap["parse_warnings"]


@case("P1 legacy heading grammar", "R3 A8j; ADV3 A8j fix: append scope shows '(Session #3)' before approval; a 3.2.2-shaped receipt still approves (P1.4)")
def scope_number():
    with lab() as L:
        root = L.project(session=SEED)
        e = L.envelope(root, scope=["project_session.md", "project_index.md"])
        draft = L.freeze(e, entry(), INDEX)
        old = {k: copy.deepcopy(v) for k, v in draft.items() if k in RECEIPT_322_KEYS}
        old["scope_operations"] = [{k: op[k] for k in ("class", "operation", "path") if k in op} for op in draft["scope_operations"]]
        old["scope_lines"] = re.sub(r" \(Session #[0-9]+\)", "", draft["scope_lines"])
        old["scope_sha256"] = H._sha256_text(old["scope_lines"])
        old["receipt_sha256"] = H._receipt_digest(old)
        a = L.approve(e, old)
        out = L.append(e, a)
        assert out["session_number"] == 3 and out["readback_ok"], out
        L.write(e, a, "project_index.md", INDEX, expect=a["m2_preimages"]["project_index.md"])
        assert L.audit(root)["journaled"] == 1
    with lab() as L:
        root = L.project(session=SEED)
        draft = L.freeze(L.envelope(root, scope=["project_session.md"]), entry())
        assert "M2 append project_session.md (Session #3) (+ journal receipt" in draft["scope_lines"], draft["scope_lines"]


# --------------------------------------------------------------------------
# P2 legacy projection
# --------------------------------------------------------------------------

@case("P2 legacy projection", "R3 N17; AUD3 N17 pure English/Spanish v1 log projects both headings and their Next: lines (P2)")
def legacy_projection():
    log = ("# Session Log: Synthetic\n\n## Session 1 — Legacy\nNext: Preserve this handoff.\n\n"
           "## Sesión 2 — Legacy\nNext: Preserve second handoff.\n")
    with lab() as L:
        root = L.project(session=log)
        e = L.envelope(root, "newbeginning")
        assert L.ok("newbeginning", "validate", L.save("env.json", e))["valid"]
        snap = e["local_snapshot"]
        assert snap["session"]["latest_session_number"] == 2
        tail = snap["projection"]["session"]["tail"]
        assert tail.startswith("## Session 1 — Legacy") and tail.rstrip().endswith("Preserve second handoff."), repr(tail)
        assert "Next: Preserve this handoff." in tail and "Next: Preserve second handoff." in tail


@case("P2 legacy projection", "R3 N17 mixed logs: nearest legacy headings and supplements fill the count; enough strict entries project as 3.2.2 (P2)")
def mixed_projection():
    one = "# Log\n\n## Session 1 — Kickoff\nNext: first.\n\n---\n\n" + entry(2, "2026-10-02")
    tail, latest = H._last_session_entries(one)
    assert latest == 2 and tail.startswith("## Session 1 — Kickoff"), repr(tail[:40])
    supplement = ("# Log\n\n## Session 1 — Kickoff\nNext: a.\n\n### Session #1A | 2026-10-01 | Code\nNext: b.\n\n---\n\n"
                  + entry(2, "2026-10-02"))
    assert H._last_session_entries(supplement, 2)[0].startswith("### Session #1A"), H._last_session_entries(supplement, 2)[0][:40]
    assert H._last_session_entries(supplement, 3)[0].startswith("## Session 1 — Kickoff")
    full = "# Log\n\n## Session 0 — Old\nb\n\n---\n\n" + entry(1) + "\n---\n\n" + entry(2)
    assert H._last_session_entries(full)[0] == full[full.index("### Session #1"):].strip()


# --------------------------------------------------------------------------
# P3 foreign snapshot
# --------------------------------------------------------------------------

@case("P3 foreign snapshot", "R3 C4d; ADV3 C4d workspace A's identity-bearing snapshot in an envelope for B is invalid in both skills (P3)")
def foreign_snapshot():
    with lab() as L:
        a = L.project("A")
        L.close(a, index=False)
        foreign = L.ok("closingtime", "snapshot", a)
        assert foreign["workspace_id"]
        b = L.project("B")
        before = tree(b)
        for skill in ("newbeginning", "closingtime"):
            e = L.envelope(b, skill)
            e["local_snapshot"] = foreign
            rc, verdict = L.run(skill, "validate", L.save("foreign.json", e))
            assert rc == 1 and S.WORKSPACE_MISMATCH in codes(verdict), (skill, verdict)
            e["mutation_scope"]["M2"] = ["project_index.md"]
            L.refused(skill, *L.freeze_args(e, None, INDEX), code="EWORKSPACEMISMATCH")
        assert L.ok("newbeginning", "validate", L.save("own.json", L.envelope(a, "newbeginning")))["valid"]
        assert tree(b) == before, tree_diff(before, tree(b))


# --------------------------------------------------------------------------
# P4 pending replacement bound to content
# --------------------------------------------------------------------------

@case("P4 pending binding", "R3 C13; ADV3 C13 pending replace or delete without a local_payload_hashes binding refuses EDRAFTMISMATCH at freeze (P4.1)")
def pending_unbound():
    with lab() as L:
        root = L.project()
        (root / "pending_learnings.md").write_text(PENDING)
        before = tree(root)
        for scope in (["pending_learnings.md"], [{"path": "pending_learnings.md", "operation": "replace"}],
                      [{"path": "pending_learnings.md", "operation": "delete"}]):
            L.refused("closingtime", *L.freeze_args(L.envelope(root, scope=scope)), code="EDRAFTMISMATCH")
        assert tree(root) == before, tree_diff(before, tree(root))


@case("P4 pending binding", "R3 C13; ADV3 C13; R2 E6-old-pending-revision one approval writes only the bound payload, once (P4.2, P4.3)")
def pending_bound():
    with lab() as L:
        root = L.project()
        target = root / "pending_learnings.md"
        e = L.envelope(root, scope=["pending_learnings.md"], hashes={"pending_learnings.md": sha_bytes(PENDING.encode())})
        a = L.approve(e, L.freeze(e))
        for other in ("anything at all\n", "## Candidate 9\nArbitrary second replacement.\n"):
            L.refused("closingtime", *L.write_args(e, a, "pending_learnings.md", other, expect="absent"), code="EDRAFTMISMATCH")
            assert not target.exists()
        out = L.write(e, a, "pending_learnings.md", PENDING, expect="absent")
        for payload in (PENDING, "anything at all\n"):
            L.refused("closingtime", *L.write_args(e, a, "pending_learnings.md", payload, expect=out["readback_sha256"],
                                                   words="A later revision."), code="EDRAFTMISMATCH")
        assert target.read_text() == PENDING
        delete = L.envelope(root, scope=[{"path": "pending_learnings.md", "operation": "delete"}], hashes={"pending_learnings.md": "absent"})
        d = L.approve(delete, L.freeze(delete))
        L.write(delete, d, "pending_learnings.md", None, operation="delete", expect=sha(target))
        assert not target.exists()
        L.refused("closingtime", *L.write_args(delete, d, "pending_learnings.md", None, operation="delete", expect="absent"),
                  code="EDRAFTMISMATCH")


# --------------------------------------------------------------------------
# P5 approval words
# --------------------------------------------------------------------------

@case("P5 approval words", "R3 C10; ADV3 C10 approve-draft with empty or blank owner words refuses SCOPE_UNAPPROVED and consumes nothing (P5)")
def empty_owner():
    with lab() as L:
        root = L.project()
        e = L.envelope(root, scope=["project_session.md", "pending_learnings.md"])
        draft = L.freeze(e, entry())
        before = tree(root)
        path = L.save("draft.json", draft)
        L.refused("closingtime", "approve-draft", path, draft["scope_lines"], code="SCOPE_UNAPPROVED")
        L.refused("closingtime", "approve-draft", path, draft["scope_lines"], "--owner-reply", " \t\n", code="SCOPE_UNAPPROVED")
        assert tree(root) == before, tree_diff(before, tree(root))
        words = "Approve the close and the optional staging."
        a = L.approve(e, draft, words)
        L.append(e, a)
        out = L.write(e, a, "pending_learnings.md", PENDING, operation="stage", expect="absent", words=None)
        assert json.loads(Path(out["journal_record_path"]).read_text())["owner_reply"] == words


# --------------------------------------------------------------------------
# P6 task-mirror fields
# --------------------------------------------------------------------------

@case("P6 mirror fields", "R3 C12; ADV3 C12 newline-bearing Tasks id/due refuse EBADROWS at the mirror write; index bytes unchanged (P6)")
def mirror_injection():
    with lab() as L:
        root = L.project()
        e = L.envelope(root, scope=["project_session.md", "project_index.md"])
        rows = [{"id": "task-1\n## Key Decisions\nInjected outside mirror", "title": "Synthetic row", "project": "Synthetic",
                 "priority": 1, "due": "2026-11-01\n## Summary\nInjected summary"}]
        fp = L.ok("closingtime", "fingerprint-rows", L.save("rows.json", rows))
        receipt = {"schema_version": "1.0", "capability": "tasks_mcp", "identity": {"project": "Synthetic"},
                   "observed_at": fp["fingerprinted_at"], "operation_fingerprint": sha_bytes(b"synthetic query"),
                   "row_fingerprint": fp["row_fingerprint"], "row_count": 1, "status": "current"}
        e["capability_profile"]["external"]["tasks_mcp"] = "working"
        e["mcp_receipts"] = [receipt]
        e["returned_rows_by_capability"] = {"tasks_mcp": rows}
        draft_index = INDEX.replace("Original summary.", "Reviewed summary.")
        a = L.approve(e, L.freeze(e, entry(), draft_index))
        L.append(e, a)
        e["mirror_receipt"] = receipt
        before = (root / "project_index.md").read_bytes()
        L.refused("closingtime", *L.write_args(e, a, "project_index.md", draft_index,
                                               expect=a["m2_preimages"]["project_index.md"], rows=rows), code="EBADROWS")
        assert (root / "project_index.md").read_bytes() == before
        L.refused("closingtime", "render-mirror", L.save("rows.json", rows), "2026-10-28", code="EBADROWS")


@case("P6 mirror fields", "R3 C12; ADV3 C12 control characters in id, due, review_on or title refuse EBADROWS; title whitespace still normalised (P6)")
def mirror_fields():
    good = {"id": "7b0e8c6a-2b55-4c1b-9d3e-1f2a3b4c5d6e", "title": "Synthetic task", "priority": 1,
            "due": "2026-11-01", "review_on": "2026-11-02"}
    for field, value in (("id", "task-1\n## Key Decisions"), ("id", "task\x00"), ("due", "2026-11-01\r\n## Summary"),
                         ("due", "2026-11-01\x7f"), ("review_on", "2026-11-02\x1b[2J"), ("title", "Synthetic\x07 task"),
                         ("title", "Synthetic\x00task")):
        refuses("EBADROWS", lambda: H.render_task_mirror([dict(good, **{field: value})], "2026-10-28"))
    text = H.render_task_mirror([dict(good, title="Synthetic\n\t task")], "2026-10-28")
    assert "- [P1] Synthetic task (" in text and text.count("\n") == 2, text


# --------------------------------------------------------------------------
# P7 read-only opening recovery
# --------------------------------------------------------------------------

CRASH_STAGE = """
real = helpers.os.replace
def crash(source, destination):
    if pathlib.Path(destination).name == 'pending_learnings.md':
        os._exit(87)
    return real(source, destination)
helpers.os.replace = crash
envelope, receipt = (json.loads(pathlib.Path(p).read_text()) for p in sys.argv[2:4])
helpers.write_approved_file(envelope, receipt, 'pending_learnings.md', pathlib.Path(sys.argv[4]).read_text(),
                            operation='stage', expect='absent')
"""
CRASH_APPEND = """
real = helpers._move_record
def crash(path, suffix):
    if suffix == '.done' and json.loads(path.read_text()).get('kind') == 'append_intent':
        os._exit(86)
    return real(path, suffix)
helpers._move_record = crash
helpers.append_session_entry(json.loads(pathlib.Path(sys.argv[2]).read_text()), pathlib.Path(sys.argv[3]).read_text(),
                             json.loads(pathlib.Path(sys.argv[4]).read_text()))
"""
CRASH_WRITE_DONE = """
real = helpers._move_record
def crash(path, suffix):
    if suffix == '.done' and json.loads(path.read_text()).get('kind') == 'write_intent':
        os._exit(88)
    return real(path, suffix)
helpers._move_record = crash
envelope, receipt = (json.loads(pathlib.Path(p).read_text()) for p in sys.argv[2:4])
helpers.write_approved_file(envelope, receipt, 'project_index.md', pathlib.Path(sys.argv[4]).read_text(), expect='absent')
"""


@case("P7 read-only opening recovery", "R3 D11; ADV3 D11 resume on a project without a journal creates nothing in either package (P7.2)")
def resume_clean():
    with lab() as L:
        for skill in ("newbeginning", "closingtime"):
            root = L.project("project-" + skill, session=SEED)
            before = tree(root)
            out = L.ok(skill, "resume", root)
            assert not out.get("operations") and not out.get("unfinished_operations"), (skill, out)
            assert tree(root) == before, (skill, tree_diff(before, tree(root)))


@case("P7 read-only opening recovery", "R3 N8 opening resume after a crashed closing stage writes nothing; closingtime resume finishes it (P7.1)")
def opening_resume_stage():
    with lab() as L:
        root = L.project()
        e, a, _ = L.close(root, index=False, stage=True)
        rc, out = L.inject("closingtime", CRASH_STAGE, L.save("e.json", e), L.save("a.json", a), L.save("stage.md", PENDING))
        assert rc == 87, (rc, out)
        assert L.ok("newbeginning", "snapshot", root)["unfinished_operations"]
        before = tree(root)
        inspection = L.ok("newbeginning", "resume", root)
        assert tree(root) == before, tree_diff(before, tree(root))
        assert not (root / "pending_learnings.md").exists()
        assert "closingtime" in json.dumps(inspection), inspection
        L.ok("closingtime", "resume", root)
        assert (root / "pending_learnings.md").read_text() == PENDING
        assert not L.ok("closingtime", "snapshot", root)["unfinished_operations"]


@case("P7 read-only opening recovery", "R3 N8; R2 D1-crash-lock opening resume after a crashed append keeps lock, intent and log; closingtime recovers once (P7.1)")
def opening_resume_append():
    with lab() as L:
        root = L.project()
        e = L.envelope(root, scope=["project_session.md", "project_index.md"])
        a = L.approve(e, L.freeze(e, entry(), INDEX))
        rc, out = L.inject("closingtime", CRASH_APPEND, *L.append_args(e, a)[1:])
        assert rc == 86, (rc, out)
        before = tree(root)
        assert "private-artifacts/session-journal/.lock" in before
        L.ok("newbeginning", "resume", root)
        assert tree(root) == before, tree_diff(before, tree(root))
        resumed = L.ok("closingtime", "resume", root)
        assert "ELOCK_STALE_RECOVERED" in resumed["warnings"], resumed
        inputs = next(op["recovery_inputs"] for op in resumed["operations"] if "recovery_inputs" in op)
        L.write(inputs["envelope"], inputs["approved_draft"], "project_index.md", INDEX, expect=a["m2_preimages"]["project_index.md"])
        assert L.audit(root)["journaled"] == 1 and not L.ok("closingtime", "snapshot", root)["unfinished_operations"]


@case("P7 read-only opening recovery", "R3 N8 exception; R3 nb-bootstrap newbeginning may finish its own interrupted approved index write (P7.1)")
def opening_own_index():
    with lab() as L:
        root = L.project(index=None)
        e = L.envelope(root, "newbeginning", scope=["project_index.md"])
        a = L.approve(e, L.freeze(e, None, INDEX))
        rc, out = L.inject("newbeginning", CRASH_WRITE_DONE, L.save("e.json", e), L.save("a.json", a), L.save("index.md", INDEX))
        assert rc == 88, (rc, out)
        assert L.ok("newbeginning", "snapshot", root)["unfinished_operations"]
        L.ok("newbeginning", "resume", root)
        assert (root / "project_index.md").read_text() == INDEX
        assert not L.ok("newbeginning", "snapshot", root)["unfinished_operations"]


# --------------------------------------------------------------------------
# P8 adopting history and reconciling edits
# --------------------------------------------------------------------------

@case("P8 adopt history", "R3 A11; ADV3 A11 pre-journal #1-#2: read-only adopt-history, approved policy write, clean audit, re-edit detected (P8.1-P8.3)")
def adopt_history():
    with lab() as L:
        root = L.project(session=SEED)
        L.close(root)
        audit = L.audit(root)
        assert numbers(audit["unjournaled"]) == [1, 2], audit
        before = tree(root)
        _, policy, digest, line = adopt(L, root)
        assert tree(root) == before, tree_diff(before, tree(root))
        assert re.fullmatch(r"M2 replace private-artifacts/session-journal/_policy\.json \(adopt 2 historical entries\)", line), line
        proposed = json.loads(policy)
        assert {(x["session_number"], x["entry_sha256"]) for x in proposed["historical_entries"]} == \
            {(x["session_number"], x["entry_sha256"]) for x in audit["unjournaled"]}, proposed
        write_policy(L, root, policy, digest, "absent")
        assert_clean(L.audit(root), [1, 2])
        L.close(root)
        clean = L.audit(root)
        assert_clean(clean, [1, 2])
        assert clean["journaled"] == 2, clean
        log = root / "project_session.md"
        log.write_text(log.read_text().replace("Checked synthetic evidence.", "Corrected synthetic evidence.", 1))
        assert numbers(L.audit(root)["unjournaled"]) == [1]
    with lab() as L:  # an existing version-1 policy keeps its ceiling
        root = L.project(session=SEED)
        old = json.dumps({"schema_version": "1.0", "grandfather_session_ceiling": 1, "recorded_at": "2026-08-04T00:00:00Z"}, indent=2) + "\n"
        (root / "private-artifacts/session-journal").mkdir(parents=True)
        (root / POLICY).write_text(old)
        L.close(root)
        assert numbers(L.audit(root)["unjournaled"]) == [2]
        _, policy, digest, line = adopt(L, root)
        assert line.endswith("(adopt 1 historical entries)") or line.endswith("(adopt 1 historical entry)"), line
        assert json.loads(policy)["grandfather_session_ceiling"] == 1
        write_policy(L, root, policy, digest, sha(root / POLICY))
        audit = L.audit(root)
        assert_clean(audit, [2])
        assert numbers(audit["grandfathered"]) == [1], audit


@case("P8 adopt history", "UL3 11 legacy log (title suffix, subheading, #2A supplement): next #3, no duplicate warning, adoption completes the gate (P8, P1.3)")
def userlab_legacy():
    log = ("# Session Log — Project\n\n" + entry(1) + "\n## Session Context\nAn internal entry subheading.\n\n---\n\n"
           + entry(2) + "\n---\n\n### Session #2A | 2026-10-28 | Code (Codex)\n**Focus:** Supplement.\n**Next:** Review.\n")
    with lab() as L:
        root = L.project(session=log)
        e, _, out = L.close(root)
        assert out["session_number"] == 3, out
        assert "legacy_duplicate_number" not in e["local_snapshot"]["parse_warnings"], e["local_snapshot"]["parse_warnings"]
        assert numbers(L.audit(root)["unjournaled"]) == [1, 2]
        _, policy, digest, line = adopt(L, root)
        assert line.endswith("(adopt 2 historical entries)"), line
        write_policy(L, root, policy, digest, "absent")
        assert_clean(L.audit(root), [1, 2])


@case("P8 adopt history", "R3 R5; AUD3 R5 hand-edited finished entry: resume reports edited_after_close and continues; adoption supersedes the orphan (P8.4, P8.1, P8.3)")
def edited_entry():
    second = INDEX.replace("Original summary.", "Second summary.")
    with lab() as L:
        root = L.project()
        L.close(root)
        e = L.envelope(root, scope=["project_session.md", "project_index.md"])
        a = L.approve(e, L.freeze(e, entry(), second))
        L.append(e, a)  # session #2 verified, its index child remains
        log = root / "project_session.md"
        log.write_text(log.read_text().replace("Checked synthetic evidence.", "Corrected synthetic evidence.", 1))
        resumed = L.ok("closingtime", "resume", root)
        assert "edited_after_close" in [op["state"] for op in resumed["operations"]], resumed["operations"]
        inputs = next(op["recovery_inputs"] for op in resumed["operations"] if "recovery_inputs" in op)
        L.write(inputs["envelope"], inputs["approved_draft"], "project_index.md", second, expect=a["m2_preimages"]["project_index.md"])
        assert not L.ok("closingtime", "snapshot", root)["unfinished_operations"]
        L.close(root, index_text=second)
        audit = L.audit(root)
        assert numbers(audit["unjournaled"]) == [1] and len(audit["orphan_records"]) == 1, audit
        orphan = audit["orphan_records"][0]
        relative = Path(orphan["path"]).relative_to(root).as_posix()
        _, policy, digest, line = adopt(L, root)
        proposed = json.loads(policy)
        assert [(x["session_number"], x["entry_sha256"]) for x in proposed["historical_entries"]] == \
            [(1, audit["unjournaled"][0]["entry_sha256"])], proposed
        assert proposed["superseded_records"] == [{"path": relative, "session_number": 1, "entry_sha256": orphan["entry_sha256"]}], proposed
        write_policy(L, root, policy, digest, "absent")
        clean = L.audit(root)
        assert_clean(clean, [1])
        superseded = [v for k, v in clean.items() if "superseded" in k]
        assert superseded and relative.rsplit("/", 1)[-1] in json.dumps(superseded), clean
        L.ok("closingtime", "resume", root)


@case("P8 adopt history", "R3 A11 adopt-history refuses while an operation is unfinished and writes nothing (P8.1)")
def adopt_refuses_unfinished():
    with lab() as L:
        root = L.project(session=SEED)
        e = L.envelope(root, scope=["project_session.md", "project_index.md"])
        L.append(e, L.approve(e, L.freeze(e, entry(), INDEX)))
        before = tree(root)
        L.refused("closingtime", "adopt-history", root)
        assert tree(root) == before, tree_diff(before, tree(root))


@case("P8 adopt history", "R3 A11 policy writer: newbeginning ESKILL; closingtime needs the hash binding and writes only the bound bytes (P8.5)")
def policy_boundary():
    policy = json.dumps({"schema_version": "2.0", "grandfather_session_ceiling": 0, "historical_entries": []}, indent=2) + "\n"
    digest = sha_bytes(policy.encode())
    with lab() as L:
        root = L.project(session=SEED)
        scope = [{"path": POLICY, "operation": "replace"}]
        L.refused("newbeginning", *L.freeze_args(L.envelope(root, "newbeginning", scope=scope, hashes={POLICY: digest})), code="ESKILL")
        L.refused("closingtime", *L.freeze_args(L.envelope(root, scope=scope)))
        e = L.envelope(root, scope=scope, hashes={POLICY: digest})
        a = L.approve(e, L.freeze(e))
        L.refused("closingtime", *L.write_args(e, a, POLICY, policy.replace('"historical_entries": []', '"historical_entries": [{"session_number": 1, "entry_sha256": "sha256:' + "0" * 64 + '"}]'), expect="absent"))
        assert not (root / POLICY).exists()
        L.write(e, a, POLICY, policy, expect="absent")
        assert (root / POLICY).read_text() == policy


# --------------------------------------------------------------------------
# P9/P10 documentation reproductions (outside P1-P8)
# --------------------------------------------------------------------------

@case("P9-P10 documentation (outside P1-P8)", "R3 C6; UL3 gap 2 closingtime SKILL names 'runtime_cli.py skip-plan', which emits the acknowledgement (P10)")
def skip_entrypoint():
    text = (SKILLS / "closingtime" / "SKILL.md").read_text(encoding="utf-8")
    with lab() as L:
        out = L.ok("closingtime", "skip-plan", "learning")
    assert "Learning extraction intentionally skipped" in json.dumps(out), out
    assert "Run `scripts/workflow.py` for each skip acknowledgement" not in text
    assert "runtime_cli.py skip-plan" in text


@case("P9-P10 documentation (outside P1-P8)", "R3 C23; AUD3 C23 task UPDATE templates compare observed updated_at and return it; the project query selects updated_at (P9)")
def update_templates():
    text = (HERE / "task_operations.md").read_text(encoding="utf-8")
    query = re.search(r"select (.+?)\nfrom task_urgency", text, re.S)
    updates = [" ".join(u.split()) for u in re.findall(r"update tasks .+?;", text, re.S)]
    assert len(updates) == 4, updates
    assert query and "updated_at" in query.group(1), query and query.group(1)
    for update in updates:
        assert "where id = '<task-uuid>' and updated_at = '<observed-updated_at>'" in update, update
        assert update.endswith("returning id, status, priority, flagged, updated_at;"), update


# --------------------------------------------------------------------------
# Guards: reproductions that are safe today and not held by another fixture
# --------------------------------------------------------------------------

@case("guards (already safe)", "R1 recognized-conflict a sync-conflict copy appearing after approval refuses append; log unchanged")
def late_conflict():
    with lab() as L:
        root = L.project(session=SEED)
        e = L.envelope(root, scope=["project_session.md"])
        a = L.approve(e, L.freeze(e, entry()))
        (root / "project_session.sync-conflict-late.md").write_text("synthetic conflicting device")
        before = (root / "project_session.md").read_bytes()
        L.refused("closingtime", *L.append_args(e, a), code="SYNC_CONFLICT")
        assert (root / "project_session.md").read_bytes() == before


@case("guards (already safe)", "ADV2 D4 a second abandon of the same child refuses ERECOVERY; the verified append stays journaled")
def second_abandon():
    with lab() as L:
        root = L.project()
        e = L.envelope(root, scope=["project_session.md", "project_index.md"])
        L.append(e, L.approve(e, L.freeze(e, entry(), INDEX)))
        child = next(op["intent"] for op in L.ok("closingtime", "resume", root)["operations"] if op.get("path") == "project_index.md")
        relative = Path(child).relative_to(root).as_posix()
        L.ok("closingtime", "resume", root, "--abandon", relative, "--owner-reply", "Abandon only the index child.")
        before = tree(root)
        L.refused("closingtime", "resume", root, "--abandon", relative, "--owner-reply", "Abandon it again.", code="ERECOVERY")
        assert tree(root) == before, tree_diff(before, tree(root))
        assert L.audit(root)["journaled"] == 1


# --------------------------------------------------------------------------

def results():
    rows = []
    for group, label, fn in CHECKS:
        try:
            fn()
            rows.append((group, label, None))
        except Exception as exc:  # noqa: BLE001 - every failure is reported, none is fatal
            rows.append((group, label, f"{type(exc).__name__}: {str(exc)[:400]}"))
    return rows


def run_groups():
    """[(group, total, [failure strings])] in declaration order."""
    groups = {}
    for group, label, problem in results():
        entry_ = groups.setdefault(group, [0, []])
        entry_[0] += 1
        if problem:
            entry_[1].append(f"{label}: {problem}")
    return [(group, total, bad) for group, (total, bad) in groups.items()]


def run():
    return [problem for _, _, bad in run_groups() for problem in bad]


if __name__ == "__main__":
    rows = results()
    for group, label, problem in rows:
        print(f"[{'FAIL' if problem else 'PASS'}] {group} | {label}")
        if problem:
            print("       " + problem.replace("\n", " ")[:300])
    print(f"\n{sum(p is None for _, _, p in rows)} passed, {sum(p is not None for _, _, p in rows)} failed, {len(rows)} cases")
    sys.exit(1 if any(p for _, _, p in rows) else 0)
