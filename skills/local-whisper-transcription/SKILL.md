---
name: local-whisper-transcription
description: "Run private, audit-ready local transcription of interviews, calls, meetings, voice memos, video, or audio with whisper.cpp. Use for diagnosing local Whisper readiness, selecting a configured model, comparing stereo channels, creating physical overlapping chunks, running Metal-first or CPU inference, repairing difficult spans, and assembling global-time TXT/SRT/JSON/Markdown outputs. Never install, download, or upload without explicit user approval."
---

# Local Whisper Transcription

## 1. Purpose and scope

Keep recordings local, preserve source evidence, and produce reproducible raw
and readable transcripts. Support any configured project without embedding
owner paths. Treat machine output as semantic evidence, not certified
quotation.

Do not upload media, overwrite sources, claim automatic diarization is
human-verified, or publish partial inference output.

## 2. Preflight

1. Run `scripts/doctor.py --json`.
2. If status is `setup_required`, report the missing local dependencies and
   stop. Never install `ffmpeg`/`whisper.cpp`, download a model, or substitute a
   cloud service without explicit approval.
3. If an installed model is only a doctor recommendation, review it and create
   the owner-controlled local policy with
   `scripts/configure_local_policy.sh`. Read
   [references/local-policy.md](references/local-policy.md).
4. Inspect the source with `ffprobe`; verify the spoken language from audio.
5. Resolve every bundled script relative to this `SKILL.md`.

The inference runner uses the policy's exact `default_model`. An explicit
`--model` is accepted only when it is already listed as `allowed_model`.
Runtime inference never chooses or downloads a model implicitly.

## 3. Workflow

Read [references/preprocessing.md](references/preprocessing.md) before channel
comparison, chunking, or assembly.

1. For video, stream-copy the original audio with
   `ffmpeg -map 0:a:0 -c:a copy`. When fidelity matters, compare decoded-audio
   hashes between source and extraction.
2. For stereo/multichannel sources, use `scripts/channel_compare.py prepare`.
   Transcribe every deterministic sample under identical conditions, then use
   `score`. Accept automatic selection only above its margin; otherwise review
   samples manually. Use `extract` to create the selected full mono WAV.
3. For recordings longer than about ten minutes, use
   `scripts/chunk_audio.py`. Its defaults create physical 370-second mono WAV
   windows with 20-second overlaps and a global-offset manifest.
4. Run `scripts/run_whisper_metal_default.sh` once per manifest chunk. Execute
   that exact script outside a managed sandbox when Metal is desired. Request
   persistent approval only for the hardened inference runner, never for a
   shell, package manager, policy configurator, preprocessing script, or
   low-level runner.
5. Use `scripts/assemble_transcript.py` after every chunk has TXT/SRT/JSON.
   Review any overlap item it flags; repair difficult spans with small physical
   windows.
6. Retain raw chunks and assemble a readable transcript with uncertainty and
   editorial speaker-label disclosure.

```bash
scripts/run_whisper_metal_default.sh \
  --input <absolute-chunk.wav> \
  --output <absolute-transcript-prefix> \
  --language <language> \
  --prompt "<confirmed names and domain terms>"
```

The runner preflights Metal, stages TXT/SRT/JSON, and retries automatically on
CPU `-ng`. Use `scripts/run_whisper_chunk.sh` only for sandbox-only CPU work or
specialized options; its `--force` and passthrough surface is intentionally
ineligible for persistent unsandboxed approval.

## 4. Harness adaptations

| Capability | Behavior when present | Graceful degradation |
|---|---|---|
| Local `ffmpeg` and `ffprobe` | Inspect, sample, extract, and chunk media | Stop with doctor actions |
| Local `whisper-cli` and model | Run private inference | Stop; request approval before setup |
| Valid local policy | Enforce executable, model, and data roots | Stop; never widen implicitly |
| Unsandboxed process approval | Use Metal through the hardened runner | Use CPU fallback |
| Apple Metal and Swift toolchain | Preflight and accelerate inference | Use CPU `-ng` |
| Stereo source | Compare deterministic channel samples | Use the available mono stream |
| Complete chunk SRT set | Assemble global timestamps and overlaps | Publish nothing until complete |

Metal acceleration is optional and must not become a correctness dependency.
Model recommendations are advisory until policy makes them authoritative.

## 5. Decision rules

| Situation | Action |
|---|---|
| Whisper or model absent | Diagnose and stop; do not auto-install/download |
| Several installed models, no policy | Rank locally installed candidates; ask the user to authorize configuration |
| Explicit model outside policy | Stop; do not bypass model allowlisting |
| Channel score margin below 7 | Require sample review; do not auto-select |
| Input remains multichannel before chunking | Select a channel or explicitly approve mixdown |
| Recording exceeds about ten minutes | Create physical chunks and retain the manifest |
| Metal unavailable or crashes | Retry on CPU using private staging |
| Chunk SRT missing/invalid | Stop assembly without publishing |
| High-confidence overlap duplicate | Remove and record the decision |
| Ambiguous overlap or speaker boundary | Keep/flag it and review against audio |
| Existing output or symlink | Stop and choose a new path |

## 6. Evaluation criteria

A run succeeds only when:

- the source remains unchanged;
- doctor status was `ready` before inference;
- the actual model/backend and any model override are disclosed;
- channel samples used identical inference conditions and the selection
  evidence is retained;
- chunk hashes, boundaries, overlap, and global offsets are retained;
- every chunk produced non-empty TXT/SRT/JSON together;
- assembly parsed SRT structurally and disclosed removed/ambiguous overlaps;
- names, amounts, decisions, speaker changes, and flagged spans were
  spot-checked;
- no package installation, model download, cloud upload, overwrite, path
  widening, or arbitrary unsandboxed command occurred implicitly.

Restart after a boundary violation or partial-output defect. Patch readable
transcript wording only as disclosed editorial cleanup.

## 7. Version and transfer status

A competent external user can diagnose an unprepared machine, understand what
requires approval, configure an installed model, select or review a channel,
create reproducible chunks, run inference, and evaluate overlap assembly using
only this skill. The skill still cannot authorize package/model acquisition,
certify verbatim accuracy, or infer reliable speaker identities.

### Changelog

**v1.2.0 — 2026-07-28**
- **Initial release.** Private, audit-ready local transcription on whisper.cpp,
  built and hardened in one pass; earlier version numbers were internal
  iterations and were never published.
- **Readiness diagnosis** — `scripts/doctor.py --json` reports `ready` or
  `setup_required` and ranks installed models as candidates only. It never
  installs, downloads, or authorizes anything.
- **Owner-controlled policy** — the hardened Metal runner reads exactly one
  file (`~/.config/local-whisper-transcription/policy.conf`, mode `600`,
  written by `scripts/configure_local_policy.sh`). It pins the executable,
  the default model, the model allowlist, and every permitted data root.
  Arbitrary commands, unapproved models, paths outside the roots, overwrites,
  symlinks, and partial output publication are all rejected.
- **Metal-first with automatic CPU fallback** — `run_whisper_metal_default.sh`
  preflights Metal, stages TXT/SRT/JSON, and retries on CPU `-ng` on failure.
  Acceleration is an optimization, never a correctness dependency; the actual
  backend is always disclosed.
- **Evidence-based channel selection** — `channel_compare.py` samples multiple
  deterministic positions under identical inference conditions and scores them;
  selection below the margin requires manual review rather than auto-selecting.
- **Physical overlapping chunks** — `chunk_audio.py` writes 370-second mono
  windows with 20-second overlaps, hashes, and a global-offset manifest;
  implicit stereo mixdown is refused.
- **Structural assembly** — `assemble_transcript.py` parses chunk SRT
  structurally, removes only high-confidence overlap duplicates, flags
  ambiguous ones for review, and publishes nothing until every chunk is complete.
- **Portable** — no owner or project paths in the skill; machine specifics live
  only in local policy. Evals: 25 structural + 15 runtime checks.
