# Deterministic preprocessing

## Readiness and model recommendation

Run:

```bash
scripts/doctor.py --json
```

The doctor is read-only. It inventories local dependencies, validates the
policy, scans common local model caches, estimates whether installed models fit
conservatively within memory, and reports:

- `ready`: the policy default is authoritative and executable;
- `setup_required`: one or more local prerequisites are absent or invalid.

When no valid policy exists, the doctor may recommend an installed candidate
using `quality`, `balanced`, or `speed` preference. A candidate is not
authorized until the user configures it in the local policy. The doctor never
installs packages, downloads models, modifies policy, or invokes a cloud
service. Candidate ranking uses filename family, quantization marker, file
size, and a conservative memory estimate; it is not a measured accuracy
benchmark.

## Channel comparison

Prepare deterministic samples:

```bash
scripts/channel_compare.py prepare \
  --input <source> \
  --output-dir <comparison-dir>
```

For audio long enough to support it, the script samples 30 seconds centered at
15%, 50%, and 85% of the recording. It extracts every channel to mono PCM16
16 kHz WAV and records RMS, peak, active-frame ratio, clipping ratio, and a
bounded signal score in `channel_samples.json`.

Transcribe every sample with the same model, language, prompt, and backend.
Use each manifest entry's `transcript_prefix`; the scorer expects
`<transcript_prefix>.txt`.

Score:

```bash
scripts/channel_compare.py score \
  --manifest <comparison-dir>/channel_samples.json
```

The score weights transcript heuristics 80% and signal heuristics 20%.
Transcript heuristics cover usable text density, lexical diversity, repeated
trigrams, and common English/Spanish hallucination markers. Automatically
select only when the best channel leads by at least 7 points; otherwise require
manual review. Always spot-check names, amounts, decisions, and suspicious
background spans.

Extract the selected channel:

```bash
scripts/channel_compare.py extract \
  --input <source> \
  --channel <zero-based-channel> \
  --output <selected-mono.wav>
```

## Physical chunking

Create chunks only after selecting/extracting mono audio:

```bash
scripts/chunk_audio.py \
  --input <selected-mono.wav> \
  --output-dir <chunks-dir>
```

Defaults are 370-second chunks with 20-second overlaps. The script refuses
implicit stereo mixdown, stages all chunks, emits mono PCM16 16 kHz WAV, hashes
the source and chunks, and writes `chunks.json` with global millisecond
offsets. Use `--allow-mixdown` only after explicitly deciding that channel
selection is unnecessary.

Transcribe each manifest entry's `audio_file` to its `transcript_prefix`.

## Assembly

Assemble after every chunk has a non-empty SRT:

```bash
scripts/assemble_transcript.py \
  --manifest <chunks-dir>/chunks.json \
  --output-prefix <assembled-prefix>
```

The assembler parses SRT blocks structurally, adds each chunk's global offset,
and compares only segments inside physical overlap regions. It removes exact
or high-similarity duplicates conservatively at a default similarity threshold
of `0.88`. It publishes TXT, global-time SRT, audit JSON, and readable
timestamped Markdown together.

Exit code `4` means assembly succeeded but ambiguous overlap items require
audio review. The JSON names every removed duplicate and every review item.
Speaker turns and uncertified wording remain human-review boundaries.
