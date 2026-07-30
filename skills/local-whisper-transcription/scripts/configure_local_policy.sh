#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  configure_local_policy.sh \
    --whisper-cli FILE \
    --default-model FILE \
    --allow-root DIR [--allow-root DIR ...] \
    [--allow-model FILE ...] \
    [--dry-run]

Creates:
  <home>/.config/local-whisper-transcription/policy.conf

The file is owner-only and is never overwritten. Move an existing policy aside
before intentionally replacing it.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 2
}

canonical_file() {
  [[ -f "$1" ]] || die "file not found: $1"
  realpath "$1"
}

canonical_dir() {
  [[ -d "$1" ]] || die "directory not found: $1"
  (cd "$1" && pwd -P)
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
  canonical_dir "$resolved_home"
}

whisper_cli=""
default_model=""
allowed_roots=()
allowed_models=()
dry_run="false"

while (($#)); do
  case "$1" in
    --whisper-cli)
      (($# >= 2)) || die "--whisper-cli requires a value"
      whisper_cli="$2"
      shift 2
      ;;
    --default-model)
      (($# >= 2)) || die "--default-model requires a value"
      default_model="$2"
      shift 2
      ;;
    --allow-root)
      (($# >= 2)) || die "--allow-root requires a value"
      allowed_roots+=("$2")
      shift 2
      ;;
    --allow-model)
      (($# >= 2)) || die "--allow-model requires a value"
      allowed_models+=("$2")
      shift 2
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ -n "$whisper_cli" ]] || die "--whisper-cli is required"
[[ -n "$default_model" ]] || die "--default-model is required"
((${#allowed_roots[@]} > 0)) || die "at least one --allow-root is required"

whisper_cli="$(canonical_file "$whisper_cli")"
[[ -x "$whisper_cli" ]] || die "whisper-cli is not executable: $whisper_cli"
default_model="$(canonical_file "$default_model")"
if ((${#allowed_models[@]} == 0)); then
  allowed_models=("$default_model")
fi

for index in "${!allowed_roots[@]}"; do
  allowed_roots[$index]="$(canonical_dir "${allowed_roots[$index]}")"
done
for index in "${!allowed_models[@]}"; do
  allowed_models[$index]="$(canonical_file "${allowed_models[$index]}")"
done

model_allowed="false"
for candidate in "${allowed_models[@]}"; do
  if [[ "$candidate" == "$default_model" ]]; then
    model_allowed="true"
  fi
done
[[ "$model_allowed" == "true" ]] || die "default model must also be allowlisted"

render_policy() {
  printf 'version=1\n'
  printf 'whisper_cli=%s\n' "$whisper_cli"
  printf 'default_model=%s\n' "$default_model"
  local value
  for value in "${allowed_roots[@]}"; do
    printf 'allowed_root=%s\n' "$value"
  done
  for value in "${allowed_models[@]}"; do
    printf 'allowed_model=%s\n' "$value"
  done
}

if [[ "$dry_run" == "true" ]]; then
  render_policy
  exit 0
fi

user_home="$(resolve_user_home)"
policy_dir="$user_home/.config/local-whisper-transcription"
policy_file="$policy_dir/policy.conf"
[[ ! -e "$policy_file" && ! -L "$policy_file" ]] ||
  die "policy already exists; move it aside before replacing: $policy_file"

umask 077
mkdir -p "$policy_dir"
temp_policy="$(mktemp "$policy_dir/.policy.XXXXXX")"
cleanup() {
  rm -f "$temp_policy"
}
trap cleanup EXIT INT TERM
render_policy >"$temp_policy"
chmod 600 "$temp_policy"
mv "$temp_policy" "$policy_file"
trap - EXIT INT TERM
printf 'created: %s\n' "$policy_file"
