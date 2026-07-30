#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_whisper_metal_default.sh \
    --input FILE \
    --output PREFIX \
    [--model FILE] \
    [--language LANG] \
    [--prompt TEXT] \
    [--threads N] \
    [--cpu] \
    [--dry-run]

Metal is the default after a real-device preflight. Any preflight or inference
failure falls back to CPU. Outputs are staged and published only when TXT, SRT,
and JSON are all present and non-empty.

Machine-specific paths come from:
  <home>/.config/local-whisper-transcription/policy.conf

The runner accepts only fixed options, never overwrites outputs, and permits
only paths and models allowlisted by that local policy.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 2
}

canonical_existing_file() {
  local path="$1"
  [[ -f "$path" ]] || die "file not found: $path"
  realpath "$path"
}

canonical_existing_dir() {
  local path="$1"
  [[ -d "$path" ]] || die "directory not found: $path"
  (cd "$path" && pwd -P)
}

resolve_user_home() {
  local resolved_home=""
  if [[ "$(uname -s)" == "Darwin" && -x /usr/bin/dscl ]]; then
    resolved_home="$(/usr/bin/dscl . -read "/Users/$(id -un)" NFSHomeDirectory 2>/dev/null |
      /usr/bin/sed -n 's/^NFSHomeDirectory: //p')"
  fi
  if [[ -z "$resolved_home" ]]; then
    resolved_home="${HOME:-}"
  fi
  [[ -n "$resolved_home" ]] || die "could not resolve the current user's home directory"
  canonical_existing_dir "$resolved_home"
}

is_under_root() {
  local path="$1"
  local root="$2"
  [[ "$path" == "$root" || "$path" == "$root/"* ]]
}

is_allowed_data_path() {
  local path="$1"
  local root
  for root in "${allowed_roots[@]}"; do
    if is_under_root "$path" "$root"; then
      return 0
    fi
  done
  return 1
}

is_allowed_model() {
  local path="$1"
  local candidate
  for candidate in "${allowed_models[@]}"; do
    if [[ "$path" == "$candidate" ]]; then
      return 0
    fi
  done
  return 1
}

print_command() {
  printf 'command:'
  printf ' %q' "$@"
  printf '\n'
}

input=""
output=""
model=""
language="auto"
prompt=""
threads="4"
force_cpu="false"
dry_run="false"
policy_override=""

while (($#)); do
  case "$1" in
    --input)
      (($# >= 2)) || die "--input requires a value"
      input="$2"
      shift 2
      ;;
    --output)
      (($# >= 2)) || die "--output requires a value"
      output="$2"
      shift 2
      ;;
    --model)
      (($# >= 2)) || die "--model requires a value"
      model="$2"
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
    --cpu)
      force_cpu="true"
      shift
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    --test-policy)
      (($# >= 2)) || die "--test-policy requires a value"
      policy_override="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown or unsafe option: $1"
      ;;
  esac
done

[[ -z "$policy_override" || "$dry_run" == "true" ]] ||
  die "--test-policy is restricted to --dry-run validation"

user_home="$(resolve_user_home)"
policy_file="$user_home/.config/local-whisper-transcription/policy.conf"
if [[ -n "$policy_override" ]]; then
  policy_file="$policy_override"
fi
policy_file="$(canonical_existing_file "$policy_file")"

policy_version=""
whisper_cli=""
default_model=""
allowed_roots=()
allowed_models=()

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  [[ "$line" == *"="* && -n "$value" ]] || die "invalid local policy line"
  case "$key" in
    version)
      [[ -z "$policy_version" ]] || die "duplicate policy key: version"
      policy_version="$value"
      ;;
    whisper_cli)
      [[ -z "$whisper_cli" ]] || die "duplicate policy key: whisper_cli"
      whisper_cli="$value"
      ;;
    default_model)
      [[ -z "$default_model" ]] || die "duplicate policy key: default_model"
      default_model="$value"
      ;;
    allowed_root)
      allowed_roots+=("$value")
      ;;
    allowed_model)
      allowed_models+=("$value")
      ;;
    *)
      die "unknown local policy key: $key"
      ;;
  esac
done <"$policy_file"

[[ "$policy_version" == "1" ]] || die "unsupported or missing local policy version"
[[ -n "$whisper_cli" ]] || die "local policy is missing whisper_cli"
[[ -n "$default_model" ]] || die "local policy is missing default_model"
((${#allowed_roots[@]} > 0)) || die "local policy has no allowed_root entries"
((${#allowed_models[@]} > 0)) || die "local policy has no allowed_model entries"

whisper_cli="$(canonical_existing_file "$whisper_cli")"
[[ -x "$whisper_cli" ]] || die "configured whisper_cli is not executable: $whisper_cli"
default_model="$(canonical_existing_file "$default_model")"

for index in "${!allowed_roots[@]}"; do
  allowed_roots[$index]="$(canonical_existing_dir "${allowed_roots[$index]}")"
done
for index in "${!allowed_models[@]}"; do
  allowed_models[$index]="$(canonical_existing_file "${allowed_models[$index]}")"
done
is_allowed_model "$default_model" || die "default_model is not included in allowed_model"

[[ -n "$input" ]] || die "--input is required"
[[ -n "$output" ]] || die "--output is required"
[[ "$threads" =~ ^[1-9][0-9]*$ ]] || die "--threads must be a positive integer"
((threads <= 32)) || die "--threads must be 32 or fewer"
[[ "$language" == "auto" || "$language" =~ ^[A-Za-z][A-Za-z0-9_-]{0,15}$ ]] ||
  die "--language contains unsupported characters"

input="$(canonical_existing_file "$input")"
if [[ -z "$model" ]]; then
  model="$default_model"
fi
model="$(canonical_existing_file "$model")"
is_allowed_data_path "$input" || die "input is outside the local policy roots: $input"
is_allowed_model "$model" || die "model is not allowlisted by local policy: $model"

case "${input##*.}" in
  wav|WAV|mp3|MP3|flac|FLAC|ogg|OGG) ;;
  *) die "input must be WAV, MP3, FLAC, or OGG after local preparation" ;;
esac

output_dir="$(canonical_existing_dir "$(dirname "$output")")"
output_base="$(basename "$output")"
[[ -n "$output_base" && "$output_base" != "." && "$output_base" != ".." ]] ||
  die "invalid output prefix"
output="$output_dir/$output_base"
is_allowed_data_path "$output" || die "output is outside the local policy roots: $output"

for suffix in txt srt json; do
  candidate="${output}.${suffix}"
  [[ ! -e "$candidate" && ! -L "$candidate" ]] ||
    die "output exists or is a symlink: $candidate"
  [[ "$candidate" != "$input" ]] || die "output would overwrite the input: $candidate"
done

base_cmd=(
  "$whisper_cli"
  "-t" "$threads"
  "-m" "$model"
  "-f" "$input"
  "-l" "$language"
)
if [[ -n "$prompt" ]]; then
  base_cmd+=("--prompt" "$prompt")
fi
base_cmd+=("-otxt" "-osrt" "-oj")

if [[ "$dry_run" == "true" ]]; then
  printf 'policy: Metal-first with automatic CPU fallback\n'
  print_command "${base_cmd[@]}" "-of" "$output"
  print_command "${base_cmd[@]}" "-ng" "-of" "$output"
  exit 0
fi

stage_dir="$(mktemp -d "$output_dir/.whisper-stage.XXXXXX")"
stage_prefix="$stage_dir/result"

cleanup_stage() {
  local suffix
  for suffix in txt srt json; do
    rm -f "$stage_prefix.$suffix"
  done
  rmdir "$stage_dir" 2>/dev/null || true
}
trap cleanup_stage EXIT INT TERM

run_and_validate() {
  local backend="$1"
  shift
  local status=0
  printf 'backend attempt: %s\n' "$backend" >&2
  set +e
  "$@" "-of" "$stage_prefix"
  status=$?
  set -e
  if ((status != 0)); then
    printf 'backend failed: %s (exit %d)\n' "$backend" "$status" >&2
    return "$status"
  fi
  local suffix
  for suffix in txt srt json; do
    if [[ ! -s "$stage_prefix.$suffix" ]]; then
      printf 'backend failed: %s did not produce non-empty %s\n' "$backend" "$suffix" >&2
      return 1
    fi
  done
}

metal_available="false"
if [[ "$force_cpu" != "true" ]]; then
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  preflight_source="$script_dir/metal_preflight.swift"
  preflight_cache="$user_home/.cache/local-whisper-transcription"
  preflight_binary="$preflight_cache/metal-preflight"
  module_cache="$preflight_cache/swift-modules"
  mkdir -p "$module_cache"
  chmod 700 "$preflight_cache" "$module_cache"
  if [[ ! -x /usr/bin/xcrun ]]; then
    printf 'Metal toolchain unavailable; using CPU fallback\n' >&2
  elif [[ ! -x "$preflight_binary" || "$preflight_source" -nt "$preflight_binary" ]]; then
    if CLANG_MODULE_CACHE_PATH="$module_cache" SWIFT_MODULE_CACHE_PATH="$module_cache" \
      /usr/bin/xcrun swiftc "$preflight_source" -o "$preflight_binary"; then
      chmod 700 "$preflight_binary"
    else
      printf 'Metal preflight compilation failed; using CPU fallback\n' >&2
    fi
  fi
  if [[ -x "$preflight_binary" ]]; then
    if metal_device="$("$preflight_binary" 2>&1)"; then
      metal_available="true"
      printf 'Metal preflight: %s\n' "$metal_device" >&2
    else
      printf 'Metal preflight failed: %s; using CPU fallback\n' "$metal_device" >&2
    fi
  fi
fi

used_backend=""
if [[ "$metal_available" == "true" ]]; then
  if run_and_validate "Metal" "${base_cmd[@]}"; then
    used_backend="Metal"
  else
    for suffix in txt srt json; do
      rm -f "$stage_prefix.$suffix"
    done
    printf 'retrying with CPU fallback\n' >&2
  fi
fi

if [[ -z "$used_backend" ]]; then
  run_and_validate "CPU (-ng)" "${base_cmd[@]}" "-ng" ||
    die "CPU fallback failed; no output was published"
  used_backend="CPU (-ng)"
fi

for suffix in txt srt json; do
  mv "$stage_prefix.$suffix" "${output}.${suffix}"
done
rmdir "$stage_dir"
trap - EXIT INT TERM

printf 'backend used: %s\n' "$used_backend" >&2
printf 'published: %s.txt %s.srt %s.json\n' "$output" "$output" "$output" >&2
