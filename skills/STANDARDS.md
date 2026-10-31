# Skill change standards

The single entry point for any agent, in any project or harness, that needs to
change a skill maintained in this repository. Read it completely before you
edit anything. If a rule here conflicts with what your own project needs, stop
and ask the owner; do not work around it.

Skills maintained here: `newbeginning`, `closingtime` (the session skills,
which share `skills/_shared/`), `boss-hunt-research`, `calibre`,
`local-whisper-transcription`, `nate-update`, `research-triangulation`,
`sync-jobs`.

`<MetaClaude>` below means the root of the main checkout of this repository.
Your global instructions give its local path.

## 1. Rules that always apply

1. **Never edit an installed copy.** Folders under `~/.claude/skills`,
   `~/.codex/skills`, `~/.agents/skills` and `~/.config/opencode/skills` are
   deployment targets. They are read-only on purpose. Do not `chmod` them.
2. **Never work in the main checkout.** It may hold another session's
   uncommitted candidate. Work in your own git worktree on a `contrib/` branch.
3. **You execute; you do not certify yourself.** You make the change, run the
   gate and write the evidence. A different agent session reviews it. The owner
   approves installation.
4. **Tests come before the repair.** Any behaviour change needs a test that
   fails on the base commit and passes on yours.
5. **This repository is public.** Never commit private data: personal,
   financial, health, legal, job-search or client material, credentials, or
   absolute personal paths. Change records stay in `private-artifacts/`, which
   git never sees.
6. **Do not change the rules or the tooling to make your change pass.** A change
   to this file or to `skills/_contrib/` fails the gate. Propose it to the
   owner instead.

## 2. Protocol

Always run the tool from the main checkout's copy:
`python3 <MetaClaude>/skills/_contrib/skillchange.py <command>`.

| Step | What you do | Output |
|---|---|---|
| 0. Status | Run `status`. If your skill shows uncommitted files ("open candidate"), stop and ask the owner which commit to build on. | Base commit |
| 1. Request | Create `<MetaClaude>/private-artifacts/skill-changes/<change-id>/REQUEST.md` from `skills/_contrib/REQUEST_TEMPLATE.md`. Use `<change-id>` = `YYYY-MM-DD_<your-project>_<skill>_<slug>`. | Request record |
| 2. Claim | Check that no other open request in `status` covers the same skill. If one does, coordinate through the owner. Set `**Status:** in-progress`. Record the request as a Tasks DB task in project `31_MetaClaude`, tagged `skill-change-request`, with the change-id in `refs`. Use your harness's approved task-write skill. | One active change per skill |
| 3. Worktree | `git -C <MetaClaude> worktree add -b contrib/<change-id> ~/worktrees/MetaClaude/<change-id> <base>`. Keep the worktree outside Dropbox. Never run git for this repository from two machines at once. | Isolated tree |
| 4. Test first | Add or extend the test that reproduces the needed behaviour (§4.C). Confirm it fails on the base commit. | Failing test |
| 5. Change | Implement under §4. Bump the version and add a changelog entry (§4.E). For the session skills, edit only `_shared` sources and run `python3 skills/_shared/sync_runtime_copies.py`. Commit. | Commit(s) |
| 6. Gate | In the worktree, run `gate --skill <skill> [--skill …] --level <1-3> --out <change folder>/GATE.json`. The gate measures your change from where your branch leaves the main line, so it includes every commit you made. It also runs the base commit's own tests against your code. Fix the change until it passes. Never weaken a test to make it pass. | `GATE.json` with PASS |
| 7. Packet | Write `PACKET.md` from `skills/_contrib/PACKET_TEMPLATE.md`. | Evidence packet |
| 8. Review | Start a different agent session as the reviewer. Prefer a different model family. It follows `REVIEW_TEMPLATE.md`, re-runs the gate itself and writes `REVIEW.md`. On FAIL, return to step 5. Each repair needs a fresh review of the new commit. | `REVIEW.md` with PASS |
| 9. Approval | Ask the owner to approve installation of the exact skills and commit. Record the reply word for word in `OWNER-APPROVAL.md` from `skills/_contrib/OWNER-APPROVAL_TEMPLATE.md`. | Approval record |
| 10. Install | Run `install <skill> [<skill> …] --commit <full sha> --change-id <change-id>`. The tool re-checks the three records, refuses if an installed copy drifted or your commit does not contain the installed commit, and re-runs the full gate. It then backs up every current copy, installs, verifies hashes and re-locks. If any copy fails, it rolls back all of them. Session skills sharing `_shared` changes install together. | `INSTALL.json`, locked copies |
| 11. Close | Set `**Status:** installed` in REQUEST.md and update the Tasks DB task. Leave the branch. A MetaClaude session merges it into the main line; `status` flags installed-but-unmerged commits. | Closed record |

If the tool refuses, read its reason and fix the cause. Do not bypass it with
manual copies. Stop after two failed attempts at the same refusal and report to
the owner.

## 3. Risk levels

Choose the lowest level that honestly fits, and state it in the packet. The
reviewer may raise it.

| Level | Change | Extra requirements |
|---|---|---|
| 1 | Wording or documentation with no behavioural effect: README, HANDOFF, clarifying prose | Gate plus independent review |
| 2 | Behaviour change in one skill: workflow steps, triggers, rules, scripts | Level 1, plus a test added first that fails on base, plus the skill's structural evaluation |
| 3 | Session-skill shared runtime or contracts (`skills/_shared`, schemas, receipts, file formats, approval or mutation rules), or any change to an approval, privacy or destructive-action boundary in any skill | Level 2, plus the full contract suite, plus no lost regression case. The reviewer must reproduce at least one failure path independently. |

Certification here allows installation. For the session skills, it does not
replace the program's transferability recertification (Phase 4.5) or promotion
(Phase 5). Those remain decisions for a MetaClaude session.

## 4. Standards checklist

These rules exist already. This section collects them; it does not invent any.

### A. Authoring
- Session-skill `SKILL.md` keeps sections 1–7, from Purpose & Scope to Version
  & Changelog.
- Session-skill size limits:
  - The SKILL.md body must not grow: newbeginning ≤ 15,154 bytes, closingtime
    ≤ 21,210 bytes, both ≤ 500 lines.
  - Output caps stay: brief ≤ 250 words, session entry ≤ 300 words, index
    narrative ≤ 400 words.
- Frontmatter has `name`, a description with a `MUST trigger on:` list, and a
  version.
  - The session skills' 21 trigger phrases and 5 negatives are frozen.
- Progressive disclosure:
  - Put rationale, schemas, SQL, examples, state tables and error catalogues in
    `references/` or code, not in SKILL.md prose.
  - Prefer code over prose for deterministic work.
- Placeholders: never write a dollar sign followed by a digit anywhere in a
  skill body or reference, prose included. Use `<angle>` placeholders.
- Cross-skill references use named anchors (for example
  `OBSERVATION_GATE`), never step numbers.
- Instruction resolution has three cases: project root, ancestor, absent.
  Never assume a root `CLAUDE.md`.
- Harness adaptations describe capabilities, not products. No model-name branch
  may change evidence, approval or mutation rules.
- Language:
  - Skill files are in English.
  - Replies follow the user's language.
  - Learning candidates follow `skills/_shared/candidate_quality_contract.md`.
- Portability:
  - Tests and evaluations assert by pattern, never by private literal.
  - Fixtures use synthetic IDs and synthetic profiles.
- `project_index.md`, `project_session.md` and `pending_learnings.md` stay
  byte-format compatible with v1 readers.
- Changelogs record shipped work, not plans.
- Machine-wide constraints belong in global instructions, not in a skill.

### B. Shared runtime (session skills)
- The editable sources are:
  - `skills/_shared/` (`helpers.py`, `schemas.py`, `runtime_cli.py`,
    `workflow.py` and the reference `.md` files)
  - each package's SKILL.md, README.md and HANDOFF.md
  - `evals/structural_eval.py`
- The copies under `skills/<skill>/scripts|references` are regenerated by
  `sync_runtime_copies.py`. Never hand-edit them; the gate checks they are
  identical.
- newbeginning receives the read-only `task_operations_newbeginning.md`. The
  opening skill's task access stays read-only.
- Standard library only.
- The two skills version independently, but a change to the shared surface
  releases both.

### C. Testing
- Local gate (the tool runs these):
  - `python3 skills/_shared/run_contract_tests.py` for the session skills
  - `python3 skills/<skill>/evals/structural_eval.py` where it exists
  - `git diff --check`
- `skills/_shared/recert_regressions.py` is a permanent regression corpus.
  - Add cases only.
  - Changing or removing a reproduction needs a recorded owner decision cited
    beside the test.
  - Every reproduced reviewer finding gets a regression case.
- Mutants remove exactly one thing and must fail with their declared code.
- Retired checks leave both numerator and denominator.
- Failure-path tests use temporary, isolated copies with no live continuity
  files and no live Tasks data.
- Temporary paths must resolve symlinks.
- Historical transcripts find failure modes. Proving a fix needs fresh
  controlled runs.

### D. Review and certification
- The implementer cannot certify their own change.
- Any repair invalidates earlier evidence for the affected files. Re-gate and
  re-review the new commit.
- Structural validation is not behavioural or transferability certification.
  Say which one you ran.
- A session-skill candidate is frozen only after it passes every earlier round's
  reproductions.

### E. Versions and changelog
- Version bumps:
  - patch for content fixes
  - minor for methodology or behaviour changes
  - major only for incompatible file-format or contract changes
- The gate requires a version higher than the base version and a changelog
  line naming it.
  - Where the skill has a frontmatter version, update it there.
  - Session-skill changelog heading: `**vX.Y.Z — YYYY-MM-DD — candidate**`.
- Commit messages: `type(scope): summary (version)`, for example
  `fix(closingtime): exclusion reply is not approval (3.1.1)`.
- Tags and GitHub releases are made by a MetaClaude session, not by
  contributors.

### F. Installation
- Only `skillchange.py install` installs, after steps 6–9.
- One change per install. The tool keeps the previous copy in the change
  folder's `previous/` directory.
- Parity is checked on disk by hash, never from the skill list a model sees.
- Harness overlays (OpenCode's added `references/opencode_connections.md`) are
  not handled by the tool. OpenCode copies are updated only by a MetaClaude
  session.

### G. Approvals and safety
- Before any external model run, follow the global "Agents and external models"
  rules. Metered calls outside the logged allowance need approval.
- Installation, merging, pushing and history rewriting are separate approvals.
  A Tasks DB task never authorizes any of them.
- Never push branches or open pull requests for contributor changes unless the
  owner asks. Pushing publishes to a public repository.

## 5. Not yet rules

Do not treat these as rules, and do not invent answers. If your change depends
on one, ask the owner.
- Proposed:
  - Evaluation runs never install into `~/.claude` or `~/.codex`.
  - Validator results are reported with their mode.
- Undecided:
  - A single version location and changelog format for every skill.
  - When the "candidate" label is dropped.
  - Structural limits for skills other than the session skills.

## 6. Tool reference

| Command | Purpose |
|---|---|
| `status` | Canonical versions, open candidates, installed copies (drift, lock, merge) and open requests |
| `gate --skill S --level L [--out F]` | Mechanical gate on committed work, run from your worktree |
| `check-installed` | Exit 1 if any registered installed copy drifted or is missing |
| `install S… --commit C --change-id ID` | Verified install of a certified commit |
| `register`, `lock`, `unlock` | Owner/MetaClaude maintenance only |

The gate checks:
- the work is committed
- only declared skills and `skills/` paths changed since the branch left the
  main line
- the rules and the tool are identical to the main line
- the regression corpus is append-only
- the version is bumped, with a changelog heading
- no binary files, no dollar-digit placeholders, and no personal paths,
  emails or tokens in new lines
- level 2–3 changes include tests
- `git diff --check` passes
- the shared runtime copies are identical (using the base commit's mapping)
- the new tests pass, and the base commit's tests also pass against the new
  code

The tool's own adversarial tests are in `skills/_contrib/tests/`.

It cannot judge whether the change is right. That is the reviewer's job.
