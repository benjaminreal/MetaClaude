# Optional English Phonon-2 workflow

## Supported scope and limits

This adapter supports the Fermion **0.2.4** producer signature for **English**
Phonon-2 inference on Apple silicon through **MLX**. Whisper remains the default
for Spanish, mixed-language, multilingual, and translation work. Do not infer
Phonon language support from the Parakeet teacher used during training.

The CLI identifies successful raw inference when it exits with status zero and
returns complete, structurally valid JSON with `truncated: false`. That means
the producer completed; it does not prove recognition accuracy, word alignment,
or superiority to Whisper. Decoding windows can span multiple words and must not
be described as word timing. A difference between Phonon and Whisper is model
disagreement, not evidence that either result is correct.

The published [model card](https://huggingface.co/FermionResearch/Phonon-2)
and [CLI reference](https://github.com/fermionresearch/phonon/blob/main/docs/cli.md)
describe the model and command. Producer metadata, conversion and assembly
checks below establish format compatibility only. Speed, recognition quality,
memory use, and offline behavior require separate local measurement.

## Separate preflight and authorization

1. Inspect the platform, installed package metadata, executable path, configured
   model profile, and installation receipt without importing or invoking a
   model. The Whisper doctor and model allowlist do not establish Phonon
   readiness. Missing or inconsistent prerequisites mean `setup_required`.
2. Read the installed Fermion CLI help for the installed executable. The
   read-only model inventory may identify candidates, but it is not an
   integrity check.
3. Validate the selected producer context. A local model directory must be an
   unpacked Phonon-2 directory with regular `config.json`,
   `packed_manifest.json`, and `model.fermion` files. Their byte lengths and
   SHA-256 digests must match the installation receipt. Reject symlink
   traversal, escaping receipt entries, profile/receipt disagreement,
   and unsupported packed format/container. This verifies local recorded
   integrity, not publisher authenticity or a particular inference run.
4. If setup is needed, first present a concrete proposal for an isolated
   environment, pinned package version, acquisition source/revision, cache
   destination, and expected disk use. Obtain separate approval before package
   installation or weight acquisition. Recheck upstream instructions then;
   never execute an unversioned install recipe from this reference.
5. Before each inference run, obtain approval naming **FermionResearch/Phonon-2**,
   provider **Fermion Research (local weights; no hosted provider)**, the exact
   local Fermion executable/version with MLX, purpose, exact recording/windows,
   output paths, and maximum expected monetary cost. Local inference is expected
   to incur $0 provider charges, excluding hardware/electricity. Ask again if
   the model, harness, inputs, outputs, or cost changes. Setup approval does
   not authorize inference.

The supported package version is exactly `0.2.4`; do not guess, default, or
silently accept another version. The optional local model profile has this
shape (other installed fields may remain):

```json
{
  "version": 1,
  "model_id": "FermionResearch/Phonon-2",
  "model_directory": "/absolute/path/to/unpacked-model",
  "engine": "mlx",
  "installation_receipt": "/absolute/path/to/installation-receipt.json"
}
```

The receipt identifies `model`, `model_directory`, `revision`, `cli_version`,
and `files`, whose entries are `{ "path", "bytes", "sha256" }`. Required model
files are `config.json`, `packed_manifest.json`, and `model.fermion`; receipt
member paths must be exactly those basenames. The receipt location and model
directory must be absolute paths. Do not
modify the profile, receipt, or model while preparing or converting a run.
The packed manifest must identify `format: "fermion-five-value-parakeet-v1"`
and `container: "model.fermion"`; when it includes container byte length or
SHA-256, those values must agree with the receipt.

## Run approved inference

Use a fresh private staging directory, pass the verified local model directory
rather than an alias, capture exit status and stderr, and set offline mode as
defense in depth. Offline mode is not proof of zero network activity. This is a
proposed command shape, not authorization:

```bash
HF_HUB_OFFLINE=1 /absolute/venv/bin/fermion transcribe \
  /absolute/verified-phonon-2-model /absolute/chunk.wav --json \
  > /absolute/fresh-private-stage/raw.json \
  2> /absolute/fresh-private-stage/inference.log
```

Stop if inference requests network access, model resolution, another download,
or a new backend. Do not start a server or microphone, invoke a punctuation
model, automatically switch to Whisper/CPU, or treat setup approval as run
approval. Repairing a failed window requires a separately approved run.

## Producer JSON and adapter contract

The adapter accepts only a Fermion `0.2.4` producer result with these required
fields:

```json
{
  "model": "FermionResearch/Phonon-2",
  "profile": "five-value",
  "backend": "phonon2-five-value",
  "engine": "mlx",
  "text": "Synthetic example.",
  "duration_seconds": 2.0,
  "segment_count": 1,
  "truncated": false,
  "segments": [{"start": 0.0, "end": 2.0, "text": "Synthetic example."}]
}
```

The model may instead be the exact verified local model directory when a valid
profile is supplied. `duration_seconds` must be positive and finite; segment
count must equal the number of windows, including empty-text windows. Every
window needs numeric finite times, a positive span, ordered non-overlapping
bounds inside the producer duration, and endpoints representable to SRT
milliseconds. The normalized top-level text must equal the ordered join of
nonempty segment text. An empty `segments` list is valid only with count zero,
empty top-level text, and `truncated: false`. These states mean completed with
no text; they are not a verified no-speech finding. Empty windows remain in raw
JSON but do not produce TXT text or SRT cues. Optional timing fields and segment
IDs are preserved; the adapter does not invent them. Already-converted JSON is
rejected.

Use the standard-library converter. The frozen Python API is:

```python
load_producer_contract(*, model_profile=None, fermion_version=None) -> dict
convert(raw: bytes, *, producer_contract: dict) -> dict[str, str]
```

The CLI flags are `--input`, `--output-prefix`, optional `--model-profile`,
and optional `--fermion-version`. A local model-path payload requires
`--model-profile`. A repository-ID payload requires a profile or explicit
`--fermion-version 0.2.4`. If both profile and
version are passed, they must match. There is no default version or version
guessing. Example with a local model profile:

```bash
python3 scripts/convert_phonon_json.py \
  --input /absolute/fresh-private-stage/raw.json \
  --output-prefix /absolute/manifest-transcript-prefix \
  --model-profile /absolute/local-model-profile.json \
  --fermion-version 0.2.4
```

The converter performs no model/package import, inference, subprocess call, or
network request. It preserves producer fields and adds `_local_transcription`:

- `adapter_version: 2`, `source_json_sha256`,
  `timing_precision: "decoding_window"`, and
  `speaker_labels: "not_provided"`;
- `producer_contract`, containing `fermion_version`, `model_id`,
  `model_directory` (null if none), `revision` (null if unavailable), and
  `evidence` with the source for each identity field;
- `producer: {model, profile, backend, engine}` copied from the raw producer;
- `completion_state: "completed"` or `"completed_no_text"`,
  `cue_count`, and `empty_segment_count`.

Version evidence is marked `caller_declared` or `installation_receipt`;
receipt-derived revision and hashes are marked `installation_receipt`. These
describe the recorded context, not verified execution. A repository-ID-only
context does not invent a local path, revision, installed state, or run
attestation. The raw JSON hash is a record of input bytes; assembly cannot
recreate those original bytes from reserialized JSON or prove producer
execution from the hash field.

Canonical TXT joins nonempty segment text using normalized single spaces and
ends with one newline. Canonical SRT contains exactly those segments, uses
rounded-millisecond local times and contiguous one-based cue numbers, with a
stable newline format. A completed no-text chunk has a newline-only TXT, an
empty SRT, and preserves its empty/zero-window state in JSON. The converter
refuses existing destinations, symlink paths, invalid producer data, and
partial publication.

## Assemble and audit

Use the existing `scripts/assemble_transcript.py` with the chunk manifest after
each chunk has converted. It requires readable TXT/SRT/JSON files and validates
Phonon version-2 metadata, recorded producer context, producer/segment
semantics, and canonical TXT/SRT against JSON before assembly. Missing or
malformed metadata on recognizable Phonon/Fermion output is rejected. Legacy
Whisper chunks retain schema version 1; a manifest mixing engines is rejected
before publication.

For each Phonon chunk, manifest `end_ms` must exceed `start_ms`, producer
duration must match the manifest span within 1 ms, and `duration_ms` (when
present) must equal `end_ms - start_ms`. Out-of-range cues fail instead of
being dropped or clamped. At the one-millisecond rounding boundary only, a cue
endpoint may be normalized to the manifest boundary and the adjustment is
recorded. Other global times equal the chunk offset plus local cue time. The
existing overlap heuristic is unchanged: high-confidence duplicates may be
removed, ambiguous spans remain flagged for review, and exit code 4 means
review is needed.

Phonon assembly audit JSON uses `schema_version: 2`,
`transcription_engine: "phonon"`, `completion_state`, and a per-chunk
`producers` list with producer identity/context/evidence, adapter metadata,
counts, manifest offsets/duration, and any rounding adjustment. The Markdown
heading identifies Phonon-2 and discloses decoding-window timing and
machine-generated text. If every chunk completed with no text, assembly still
publishes the zero-cue TXT/SRT plus explicit no-text completion in Markdown and
audit JSON. A mix of no-text and spoken chunks is complete chunk coverage.
Assembly validates the recorded context structurally; it does not reload model
weights or verify current installation files.

## Synthetic evaluation and acceptance

Run the model-free adapter regression eval:

```bash
python3 skills/local-whisper-transcription/evals/phonon_adapter_eval.py
```

It creates disposable synthetic identity files under a temporary directory;
it does not read or modify an installed profile, receipt, or model. Passing it
validates format, context, publication, and assembly behavior only. Do not call
that a model-quality evaluation.

For each real approved run, retain the exact approval scope, raw JSON, stderr,
input hash, manifest, output hashes, and conversion metadata. Review overlap
windows against audio, including automatically removed matches. Spot-check
names, numbers, decisions, and disputed spans; label speaker names as editorial
unless independently verified. Model-only comparisons report agreement and
disagreement; they cannot establish accuracy. No reference transcript is needed
for conversion and assembly validation. Use a separately
approved Whisper run if precise subtitle alignment or a disputed span needs
comparison.
