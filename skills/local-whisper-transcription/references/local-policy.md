# Local policy

Keep machine-specific paths outside the portable skill. The hardened Metal
runner reads one owner-controlled file:

`<home>/.config/local-whisper-transcription/policy.conf`

Create it once with `scripts/configure_local_policy.sh`. Supply:

- `auto` for the newest installed stable whisper.cpp 1.9.5 or higher, or an
  explicit local `whisper-cli` executable pin;
- the default local model;
- every project or temporary root where input and output are permitted;
- any additional models that may be selected.

Before configuration, run `scripts/doctor.py --json`. Treat its model result as
an installed candidate, not authorization. Review the candidate and then put
the chosen executable, default model, roots, and optional models into policy.
The doctor never installs or downloads anything.

The configurator validates the selected CLI's `--version`, preserves `auto`
without resolving it to a versioned path, canonicalizes explicit paths, requires all targets to exist,
includes the default model in the model allowlist, writes mode `600`, and
refuses to overwrite an existing policy.

Example:

```bash
scripts/configure_local_policy.sh \
  --whisper-cli auto \
  --default-model <absolute-model> \
  --allow-root <absolute-project-root> \
  --allow-root <absolute-temporary-root>
```

Policy format:

```text
version=1
whisper_cli=auto
default_model=<absolute-model>
allowed_root=<absolute-root>
allowed_model=<absolute-model>
```

Repeat `allowed_root` and `allowed_model` as needed. Unknown keys, missing
values, nonexistent targets, or a default model absent from the allowlist stop
execution.

`auto` checks all PATH entries, plus the standard Homebrew `opt` and `Cellar`
locations on Apple Silicon, Intel macOS, and Linuxbrew. It deduplicates resolved
executables, probes `--version`, and selects the highest numeric stable release
at least 1.9.5. It does not search the network or install software. For a custom
build, add its directory to PATH or configure its absolute executable path.

To migrate an existing versioned Cellar pin, back up the policy and change only
`whisper_cli` to `auto`, with owner authorization. Keep model and root entries
unchanged and rerun the doctor. Explicit pins are never bypassed automatically;
a missing, old, prerelease, or unverified pinned CLI requires setup.
