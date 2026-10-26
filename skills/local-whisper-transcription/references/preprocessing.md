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

The channel helpers inspect and process the first audio stream in their input.
For a source with multiple audio streams, extract each selected stream to its
own single-stream file first. Keep verified speaker tracks separate, record
their source-stream identities, and use separate output directories for each
track. Multiple streams alone do not establish separate speakers.

### Speech coverage and phase cancellation

Review whether channels are alternative captures of the same conversation or
contain distinct speech, including speakers isolated to different channels in
a single stereo stream. A high channel score does not prove speech coverage.
Select one channel only after verifying that all needed speech is retained;
otherwise extract and process the required channels separately within the
approved inference scope.

Before a stereo mixdown, compare `0.5*c0+0.5*c1` with `0.5*c0-0.5*c1`
using `pan` and `volumedetect` on the same speech-bearing spans with equal
gains. A much quieter sum is evidence of possible cancellation. This check
does not establish speaker identity or prove that a single channel is complete.
Even largely inverted channels can each contain unique speech. If coverage is
uncertain, retain both channels and process them separately. A whole-recording
average can hide cancellation in shorter spans; inspect relevant spans too.

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
trigrams, and common English/Spanish hallucination markers. Select one
alternative capture only after verifying speech coverage and when the best
channel leads by at least 7 points; otherwise require manual review. Retain
distinct speech in separate channel workflows regardless of the margin. Always
spot-check names, amounts, decisions, and suspicious background spans.

Extract the selected channel:

```bash
scripts/channel_compare.py extract \
  --input <source> \
  --channel <zero-based-channel> \
  --output <selected-mono.wav>
```

### Source-relative timestamps

Before extraction, record the original file and stream/channel identities,
container and stream start times, time bases, and the extraction command in a
sidecar record. Choose and record a common source time origin. Verify which
source instant corresponds to time zero after extraction and mono conversion;
do not assume that stream-copy always resets timestamps or that a WAV retains
the original offset.

Treat this sidecar as sensitive recording data. Keep it in owner-approved
private local storage within the permitted data roots, with access restricted
to the owner. Exclude it from version control, skill packages, PR attachments,
and other shared artifacts. Do not copy credentials into recorded commands.
For explicitly approved sharing, create a separate sanitized copy: remove
personal filenames, absolute paths, participant/project identifiers, and
sensitive command arguments; use neutral track IDs where provenance is needed.
Review that copy before sharing and retain the original privately.

For an uncut extraction with unchanged playback timing, retain the verified
constant mapping `source_relative_ms = track_local_ms + offset_ms`. For
example, content starting at 00:02 in the source and at 00:00 in the mono WAV
has `offset_ms = 2000`: a track-local cue at 00:00.250 belongs at source time
00:02.250. Check the mapping near both ends. Cuts, gaps, or timing changes need
an explicit mapping rather than an assumed constant offset.

The chunker records offsets from its input audio's zero; the assembler adds
those chunk offsets only. Neither automatically restores the original stream
offset. Preserve raw manifests and assembled artifacts. When source-relative
delivery is required, write separate derived outputs, apply the verified
mapping exactly once to cue starts and ends, and record the mapping and source
artifacts used. If the mapping is unresolved, label timestamps as track-local
and disclose the alignment gap rather than presenting them as source-relative.

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
