# local-whisper-transcription

> Run private, audit-ready transcription of interviews, calls, and meetings entirely on your own machine, powered by whisper.cpp.

## Why this skill?

Sensitive recordings — client interviews, salary negotiations, medical calls — are exactly the ones you can't paste into a hosted transcription service. Running whisper.cpp locally solves the privacy half, but a model pointed at raw whisper.cpp tends to guess: it picks whichever model it finds, mixes a two-party stereo call down to mono and loses the cleaner channel, feeds a 90-minute file in as one span, and hands back a transcript with no way to tell which parts it was confident about.

**local-whisper-transcription** makes those judgment points explicit and testable. Readiness is diagnosed before anything runs; the model and the directories it may touch are fixed by a policy file *you* write; channel choice is decided by scored evidence rather than assumption; long recordings become physical chunks with hashes and global offsets; and assembly refuses to publish until every chunk is complete. Nothing is installed, downloaded, or uploaded without your explicit approval.

**Version:** 1.2.0

---

## Install

**Claude Code** — copy the skill folder into your skills directory:

```bash
# Personal (available in all projects)
cp -r skills/local-whisper-transcription ~/.claude/skills/local-whisper-transcription

# Project-scoped (available only in this project)
cp -r skills/local-whisper-transcription .claude/skills/local-whisper-transcription
```

**Cowork:** Import the `.skill` file from the [GitHub Releases](https://github.com/benjaminreal/MetaClaude/releases) page.

> If this is the first skill you install and `~/.claude/skills/` didn't exist before, restart Claude Code so it picks up the new directory.

---

## Requirements

- **whisper.cpp** — `whisper-cli` built and on your machine, plus at least one downloaded model.
- **ffmpeg / ffprobe** — for inspection, channel sampling, extraction, and chunking.
- **Python 3** and **Bash**.
- **A local policy file** — see [Setup](#setup) below. The skill will not run inference without one.
- **Apple Metal + Swift toolchain** *(optional)* — enables the accelerated route; the skill falls back to CPU automatically without it.
- **No network required.** Nothing leaves the machine.

---

## Setup

One-time, and deliberately yours to do rather than the agent's:

```bash
# 1. Check what's actually installed. Diagnoses only — never installs or downloads.
python3 skills/local-whisper-transcription/scripts/doctor.py --json

# 2. Write the policy with the executable, model, and roots you approve.
skills/local-whisper-transcription/scripts/configure_local_policy.sh \
  --whisper-cli /absolute/path/to/whisper-cli \
  --default-model /absolute/path/to/model.bin \
  --allow-root /absolute/path/to/project-root
```

The doctor's model suggestion is a *candidate*, not authorization — you review it, then put your choice into policy. The configurator canonicalizes every path, requires all targets to exist, writes mode `600`, and refuses to overwrite an existing policy. Details in [`references/local-policy.md`](references/local-policy.md).

---

## How to Use

Say what you want in plain language:

> `transcribe this interview` · `transcribe this call, it's a stereo recording` · `is my machine ready for local Whisper?` · `which channel is cleaner on this file?` · `re-do the section around 42 minutes, it's garbled`

The skill runs the doctor, inspects the source, and then walks the workflow — channel comparison for stereo, chunking for anything over ~10 minutes, inference, assembly — reporting the model and backend it actually used.

### What it does

1. **Diagnoses readiness** — reports `ready` or `setup_required` with the missing pieces, and stops rather than fixing them itself.
2. **Compares stereo channels** — samples several positions under identical inference settings, scores them, and asks you to review when the margin is too thin to call.
3. **Chunks long recordings** — physical 370-second mono windows with 20-second overlaps, hashes, and a global-offset manifest.
4. **Runs inference** — Metal-first through a hardened runner, with automatic CPU `-ng` fallback, producing TXT/SRT/JSON per chunk.
5. **Assembles the transcript** — global timestamps, high-confidence overlap duplicates removed, ambiguous ones flagged for review.
6. **Repairs difficult spans** — small physical windows over the parts that came out badly.

### What it won't do

- Install `ffmpeg`, build whisper.cpp, or download a model without your explicit approval
- Upload media anywhere, or substitute a cloud transcription service
- Run a model, or read/write a path, outside your policy
- Overwrite your source, follow symlinks, or overwrite existing output
- Publish a partial transcript when a chunk is missing or invalid
- Claim its speaker labels are verified, or that any transcript is certified verbatim

---

## How It Works (Under the Hood)

A 7-section skill:

| Section | What it covers |
|---|---|
| 1. Purpose and scope | Local-only, evidence-preserving, no certified quotation |
| 2. Preflight | Doctor status, policy, `ffprobe` inspection, script resolution |
| 3. Workflow | Video audio extraction, channel comparison, chunking, inference, assembly |
| 4. Harness adaptations | Per-capability behavior and graceful degradation |
| 5. Decision rules | Missing model, thin margins, policy violations, overlap ambiguity |
| 6. Evaluation criteria | What makes a run trustworthy enough to publish |
| 7. Version and transfer status | Transfer scope + release history |

### Safety model

The design assumption is that the agent should be able to use local hardware acceleration **without** being handed general access to the machine.

- **One narrow door.** Only `run_whisper_metal_default.sh` is meant to hold persistent unsandboxed approval — never a shell, package manager, policy configurator, or the low-level runner (`run_whisper_chunk.sh`, whose `--force` and passthrough surface is intentionally ineligible).
- **Policy is owner-written.** The runner validates executable, model, input/output roots, overwrite state, and atomic publication against a file the agent cannot create for you.
- **Metal is an optimization, not a dependency.** CPU fallback is automatic, and the backend actually used is always disclosed.
- **Evidence is retained.** Chunk hashes, boundaries, offsets, channel-selection samples, and raw per-chunk output all survive the run.

---

## Evals

```bash
# Structural — 25 checks, no whisper.cpp required
python3 skills/local-whisper-transcription/evals/structural_eval.py

# Runtime — 15 checks against fixtures
python3 skills/local-whisper-transcription/evals/runtime_eval.py
```

Structural covers section structure, the Metal-optional guarantee, script executability, install/download prohibitions, policy enforcement (unsafe options rejected, out-of-policy output rejected), and the absence of owner or project paths. Runtime covers channel prepare/score/extract, chunk manifests and hashes, overlap assembly, and doctor behavior with and without policy.

---

_Part of [MetaClaude](https://github.com/benjaminreal/MetaClaude) — a personal skills workspace._
