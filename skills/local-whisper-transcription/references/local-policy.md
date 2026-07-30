# Local policy

Keep machine-specific paths outside the portable skill. The hardened Metal
runner reads one owner-controlled file:

`<home>/.config/local-whisper-transcription/policy.conf`

Create it once with `scripts/configure_local_policy.sh`. Supply:

- the local `whisper-cli` executable;
- the default local model;
- every project or temporary root where input and output are permitted;
- any additional models that may be selected.

Before configuration, run `scripts/doctor.py --json`. Treat its model result as
an installed candidate, not authorization. Review the candidate and then put
the chosen executable, default model, roots, and optional models into policy.
The doctor never installs or downloads anything.

The configurator canonicalizes every path, requires all targets to exist,
includes the default model in the model allowlist, writes mode `600`, and
refuses to overwrite an existing policy.

Example:

```bash
scripts/configure_local_policy.sh \
  --whisper-cli <absolute-whisper-cli> \
  --default-model <absolute-model> \
  --allow-root <absolute-project-root> \
  --allow-root <absolute-temporary-root>
```

Policy format:

```text
version=1
whisper_cli=<absolute-whisper-cli>
default_model=<absolute-model>
allowed_root=<absolute-root>
allowed_model=<absolute-model>
```

Repeat `allowed_root` and `allowed_model` as needed. Unknown keys, missing
values, nonexistent targets, or a default model absent from the allowlist stop
execution.
