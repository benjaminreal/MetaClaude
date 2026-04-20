#!/usr/bin/env bash
# Release a skill: build .skill bundle, tag, and publish to GitHub Releases.
#
# Usage:  ./scripts/release.sh <skill-name> <version>
# Example: ./scripts/release.sh research-triangulation 1.3.2
#
# Run from the repo root. Requires: git, gh (authenticated), python3, zip.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <skill-name> <version>"
  echo "Example: $0 research-triangulation 1.3.2"
  exit 1
fi

SKILL="$1"
VERSION="$2"
TAG="${SKILL}-v${VERSION}"
BUNDLE="${SKILL}_v${VERSION}.skill"
SKILL_DIR="skills/${SKILL}"

# --- Validation ---

if [[ ! -d "${SKILL_DIR}" ]]; then
  echo "Error: ${SKILL_DIR}/ not found. Run this script from the repo root." >&2
  exit 1
fi

if [[ ! -f "${SKILL_DIR}/SKILL.md" ]]; then
  echo "Error: ${SKILL_DIR}/SKILL.md not found." >&2
  exit 1
fi

# Changelog entry must exist for this version.
if ! grep -qE "^### ${VERSION}([^0-9]|$)" "${SKILL_DIR}/SKILL.md"; then
  echo "Error: No changelog entry '### ${VERSION}' found in ${SKILL_DIR}/SKILL.md" >&2
  exit 1
fi

# Working tree must be clean.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: Working tree is not clean. Commit or stash changes first." >&2
  git status --short >&2
  exit 1
fi

# Tag must not already exist locally.
if git rev-parse "${TAG}" >/dev/null 2>&1; then
  echo "Error: Tag ${TAG} already exists locally." >&2
  exit 1
fi

# Structural eval (if the skill has one).
if [[ -f "${SKILL_DIR}/evals/structural_eval.py" ]]; then
  echo "→ Running structural eval..."
  python3 "${SKILL_DIR}/evals/structural_eval.py"
fi

# --- Build the bundle ---

TMPDIR=$(mktemp -d)
trap "rm -rf ${TMPDIR}" EXIT

echo "→ Building ${BUNDLE}..."
(cd skills && zip -rq "${TMPDIR}/${BUNDLE}" "${SKILL}/" -x "*.DS_Store")
echo "  Bundle: $(du -h "${TMPDIR}/${BUNDLE}" | cut -f1)  ${TMPDIR}/${BUNDLE}"

# --- Extract release notes ---

NOTES_FILE="${TMPDIR}/release_notes.md"
awk -v v="${VERSION}" '
  $0 ~ "^### " v "([^0-9]|$)" { found=1; next }
  found && /^### / { exit }
  found { print }
' "${SKILL_DIR}/SKILL.md" > "${NOTES_FILE}"

# Strip leading/trailing blank lines.
awk 'NF {found=1} found' "${NOTES_FILE}" | awk '{lines[NR]=$0} END {for (i=1;i<=NR;i++) if (lines[i] != "" || printed) {print lines[i]; printed=1}}' > "${NOTES_FILE}.tmp"
mv "${NOTES_FILE}.tmp" "${NOTES_FILE}"

echo "--- Release notes preview ---"
cat "${NOTES_FILE}"
echo "-----------------------------"

# --- Confirm and ship ---

read -r -p "Proceed with tag + push + release? [y/N] " CONFIRM
if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

git tag "${TAG}"
git push origin "${TAG}"

gh release create "${TAG}" \
  --title "${SKILL} v${VERSION}" \
  --notes-file "${NOTES_FILE}" \
  "${TMPDIR}/${BUNDLE}"

echo "✓ Released: $(gh release view "${TAG}" --json url --jq .url)"
