---
name: local-whisper-transcription
description: "Run private, audit-ready local transcription of interviews, calls, meetings, voice memos, video, or audio with whisper.cpp or optional English Phonon-2/MLX. Use for diagnosing local Whisper readiness, selecting a configured model, comparing stereo channels, creating physical overlapping chunks, running Metal-first or CPU inference, repairing difficult spans, and assembling global-time TXT/SRT/JSON/Markdown outputs. Never install, download, or upload without explicit user approval."
---

# Local Whisper Transcription

## 1. Purpose and scope

Keep recordings local, preserve source evidence, and produce reproducible raw
and readable transcripts. Support any configured project without embedding
owner paths. Treat machine output as semantic evidence, not certified
quotation.

Do not upload media, overwrite sources, claim automatic diarization is
human-verified, or publish partial inference output.

## Engine selection and approval

Whisper remains the default for multilingual, Spanish, mixed-language, and
translation work. For English recordings, the supported optional local route is
Fermion 0.2.4 with Phonon-2 on Apple silicon through MLX; read
[references/phonon-2.md](references/phonon-2.md). Do not infer multilingual
capability from its Parakeet teacher or silently change the default.

Before any model run, obtain explicit approval for the exact model, provider,
harness, purpose, input recordings/windows, and maximum expected cost. Skill
editing, setup approval, and an existing installation do not authorize inference.
Keep package installation and model acquisition separately approved. This applies
to local Whisper and Phonon alike; offline processing still invokes a model.

The doctor, model allowlist, Metal preflight, and inference runners below are
**Whisper-only**. Their status or policy does not authorize or validate Phonon.
Use the Phonon reference's separate preflight and output conversion workflow.
Never silently switch engines, change defaults, or start a microphone/server.
The Phonon converter and assembler validate data shape and artifact consistency;
they do not run a model or establish transcription quality.

## 2. Preflight

1. Run `scripts/doctor.py --json` before each job. With `whisper_cli=auto`
   in local policy, it checks every `whisper-cli` on PATH and standard Homebrew
   installations, verifies each CLI's `--version`, and selects the newest
   installed stable whisper.cpp **1.9.5 or higher**. Compare versions numerically;
   never rely on a previous session's version or a hardcoded Cellar path.
   Older, prerelease, failed, or unknown versions cannot establish readiness.
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

Use `whisper_cli=auto` to follow installed upgrades. An explicit executable
path remains an owner-selected pin and must also pass the 1.9.5 minimum; do not
silently bypass a pin. Both runners repeat the version check before inference
and disclose the selected executable and version. The CPU runner defaults to
automatic discovery; `WHISPER_CLI` is its explicit pin. Version discovery only
runs `--version`; it never loads a model, downloads, or upgrades software.

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

For English Phonon-2 jobs, follow the separate profile, version, inference
approval, conversion, and assembly procedure in
[references/phonon-2.md](references/phonon-2.md). Do not pass Whisper-only
language, prompt, backend, or policy options to Fermion.

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
| No verified stable whisper.cpp at least 1.9.5 | Stop before inference; report candidates and request approval only if installation/upgrade is needed |
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

A Whisper run succeeds only when (Phonon has additional checks in its reference):

- the source remains unchanged;
- doctor status was `ready` before inference;
- the selected executable and verified whisper.cpp version were recorded;
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

For Phonon, a zero exit status with `truncated: false` and structurally valid
producer JSON establishes successful raw inference completion. It does not
establish recognition accuracy, word alignment, or that Phonon is better than
Whisper. The synthetic adapter eval checks conversion and assembly behavior;
model-only comparisons can report agreement and disagreement, not accuracy.
No reference transcript is required to validate this integration.

## 7. Version and transfer status

Version 1.4.0 adds the versioned Fermion 0.2.4 / English Phonon-2 conversion and
assembly contract. It preserves producer metadata, checks the configured local
model receipt when supplied, and supports completed no-text windows. It does
not run inference or claim model quality. Whisper remains the default.

Version 1.3.1 adds installed-runtime discovery and a whisper.cpp 1.9.5 minimum
shared by the doctor, configurator, and both runners. Automatic policy follows
newer installed stable releases; explicit pins remain enforced. The earlier
Phonon draft remained unmerged; version 1.4.0 is its first integrated release.

A competent external user can diagnose an unprepared machine, understand what
requires approval, configure an installed model, select or review a channel,
create reproducible chunks, run inference, and evaluate overlap assembly using
only this skill. The skill still cannot authorize package/model acquisition,
certify verbatim accuracy, or infer reliable speaker identities.

### Changelog

**v1.4.0 — 2026-10-26**
- Supports only the documented Fermion 0.2.4 producer signature for English
  Phonon-2 on MLX, while retaining Whisper as the default.
- Adds profile/receipt identity validation, canonical TXT/SRT conversion,
  explicit completed-no-text metadata, and schema-version-2 Phonon assembly.
- Adds synthetic adapter/assembly regression coverage; no model is run by the
  eval and no quality claim follows from format validation.

**v1.3.1**
- Added installed-runtime discovery and the shared whisper.cpp 1.9.5 minimum;
  automatic selection follows newer stable installed versions while explicit
  executable pins remain enforced.

**v1.2.0 — 2026-07-28**
- Initial release of private, audit-ready local transcription on whisper.cpp.
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
  only in local policy. Structural, runtime, version-selection, and Phonon
  adapter evals use synthetic fixtures and do not perform model inference.
