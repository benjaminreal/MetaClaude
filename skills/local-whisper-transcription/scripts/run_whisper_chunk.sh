#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_whisper_chunk.sh \
    --input FILE \
    --model FILE \
    --output PREFIX \
    [--language LANG] \
    [--prompt TEXT] \
    [--threads N] \
    [--gpu] \
    [--force] \
    [--dry-run] \
    [-- WHISPER_OPTIONS...]

CPU is the default and is enforced with whisper-cli -ng.
GPU/Metal is experimental and requires the explicit --gpu flag.
Outputs are PREFIX.txt, PREFIX.srt, and PREFIX.json.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 2
}

input=""
model=""
output=""
language="auto"
prompt=""
threads="4"
use_gpu="false"
force="false"
dry_run="false"
extra_args=()

while (($#)); do
  case "$1" in
    --input)
      (($# >= 2)) || die "--input requires a value"
      input="$2"
      shift 2
      ;;
    --model)
      (($# >= 2)) || die "--model requires a value"
      model="$2"
      shift 2
      ;;
    --output)
      (($# >= 2)) || die "--output requires a value"
      output="$2"
      shift 2
      ;;
    --language)
      (($# >= 2)) || die "--language requires a value"
      language="$2"
      shift 2
      ;;
    --prompt)
      (($# >= 2)) || die "--prompt requires a value"
      prompt="$2"
      shift 2
      ;;
    --threads)
      (($# >= 2)) || die "--threads requires a value"
      threads="$2"
      shift 2
      ;;
    --gpu)
      use_gpu="true"
      shift
      ;;
    --force)
      force="true"
      shift
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      extra_args=("$@")
      break
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ -n "$input" ]] || die "--input is required"
[[ -n "$model" ]] || die "--model is required"
[[ -n "$output" ]] || die "--output is required"
[[ "$threads" =~ ^[1-9][0-9]*$ ]] || die "--threads must be a positive integer"
[[ -f "$input" ]] || die "input file not found: $input"
[[ -f "$model" ]] || die "model file not found: $model"

whisper_cli="${WHISPER_CLI:-whisper-cli}"
command -v "$whisper_cli" >/dev/null 2>&1 || die "whisper-cli not found: $whisper_cli"

if [[ "$force" != "true" ]]; then
  for suffix in txt srt json; do
    [[ ! -e "${output}.${suffix}" ]] || die "output exists: ${output}.${suffix}; use --force only after verifying the prefix"
  done
fi

output_dir="$(dirname "$output")"
if [[ "$dry_run" != "true" ]]; then
  mkdir -p "$output_dir"
fi

cmd=("$whisper_cli")
if [[ "$use_gpu" == "true" ]]; then
  printf 'backend: GPU/Metal (explicit experimental opt-in)\n' >&2
else
  cmd+=("-ng")
  printf 'backend: CPU (-ng)\n' >&2
fi

cmd+=(
  "-t" "$threads"
  "-m" "$model"
  "-f" "$input"
  "-l" "$language"
)

if [[ -n "$prompt" ]]; then
  cmd+=("--prompt" "$prompt")
fi

cmd+=(
  "-otxt"
  "-osrt"
  "-oj"
  "-of" "$output"
)

if ((${#extra_args[@]})); then
  cmd+=("${extra_args[@]}")
fi

if [[ "$dry_run" == "true" ]]; then
  printf 'command:'
  printf ' %q' "${cmd[@]}"
  printf '\n'
  exit 0
fi

"${cmd[@]}"
