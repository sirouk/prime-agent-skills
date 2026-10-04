#!/bin/sh
# Install or update prime-agent skills (and their /slash prompt templates).
#
#   curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-skills/main/install.sh | sh
#
# The shell entrypoint only resolves a frozen source snapshot (an exact commit).
# All copying, manifests, and uninstall logic lives in scripts/install.py from
# that same snapshot.
set -eu

# The GitHub owner/repo lives here, and only here (override with the env var).
SOURCE="${PRIME_AGENT_SKILLS_SOURCE:-https://github.com/sirouk/prime-agent-skills.git}"
REF="${PRIME_AGENT_SKILLS_REF:-main}"
COMMIT="${PRIME_AGENT_SKILLS_COMMIT:-}"
SOURCE_DIR="${PRIME_AGENT_SKILLS_SOURCE_DIR:-}"

usage() {
  cat <<'EOF'
Install prime-agent skills and prompt templates from sirouk/prime-agent-skills.

Usage: install.sh [--skills LIST] [--list] [--project] [--uninstall] [--force] [-h|--help]

Options:
  --skills LIST   Comma-separated skill slugs to act on (default: all).
  --list          Print the skills in the snapshot and exit.
  --project       Use ./.prime/agent/ in the current directory instead of the user dir.
  --uninstall     Remove installed skills and prompts that this installer manages.
  --force         Overwrite locally modified installed skills.
  -h, --help      Show this help.

Environment:
  PRIME_AGENT_DIR                Agent dir (default: $HOME/.prime/agent).
  PRIME_AGENT_SKILLS_SOURCE      Git URL of the source (default: https://github.com/sirouk/prime-agent-skills.git).
  PRIME_AGENT_SKILLS_REF         Branch, tag, or commit to install (default: main).
  PRIME_AGENT_SKILLS_COMMIT      Pin a full 40-hex commit (skips ref resolution).
  PRIME_AGENT_SKILLS_SOURCE_DIR  Install from this local checkout instead of downloading.
  PRIME_AGENT_SKILLS_DEST        Skills destination (default: $PRIME_AGENT_DIR/skills).
                                 Prompts then go to <DEST parent>/prompts.
  PRIME_AGENT_SKILLS_FORCE=1     Same as --force.

Needs python3. A remote install also needs curl and tar. No sudo.
Run /reload in open prime-agent sessions after installing.
EOF
}

for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
  esac
done

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_full_sha() {
  case "${1:-}" in
    *[!0-9a-fA-F]*|'') return 1 ;;
    *) [ "${#1}" -eq 40 ] ;;
  esac
}

normalize_sha() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

github_repo_from_source() {
  printf '%s' "$1" | sed -nE 's#^(https://github.com/|git@github.com:)([^/]+/[^/.]+)(\.git)?$#\2#p'
}

remote_commit() {
  source_url="$1"
  source_ref="$2"
  resolved=""

  if is_full_sha "$source_ref"; then
    normalize_sha "$source_ref"
    return 0
  fi

  if command -v git >/dev/null 2>&1; then
    resolved="$(GIT_TERMINAL_PROMPT=0 git ls-remote "$source_url" "$source_ref" 2>/dev/null | awk 'NR == 1 {print $1}')"
  fi
  if is_full_sha "$resolved"; then
    normalize_sha "$resolved"
    return 0
  fi

  repo="$(github_repo_from_source "$source_url")"
  if [ -n "$repo" ] && command -v curl >/dev/null 2>&1; then
    resolved="$(curl -fsSL "https://api.github.com/repos/$repo/commits/$source_ref" 2>/dev/null |
      sed -n 's/^[[:space:]]*"sha": "\([0-9a-fA-F][0-9a-fA-F]*\)",[[:space:]]*$/\1/p' |
      head -n 1)"
    if is_full_sha "$resolved"; then
      normalize_sha "$resolved"
      return 0
    fi
  fi

  return 1
}

SCRIPT_DIR=""
if [ -n "$SOURCE_DIR" ]; then
  SCRIPT_DIR="$(CDPATH='' cd -- "$SOURCE_DIR" 2>/dev/null && pwd || true)"
  [ -n "$SCRIPT_DIR" ] || die "PRIME_AGENT_SKILLS_SOURCE_DIR is not a directory: $SOURCE_DIR"
elif [ -n "${BASH_SOURCE:-}" ]; then
  SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$BASH_SOURCE")" 2>/dev/null && pwd || true)"
elif [ -f "$0" ]; then
  SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)"
fi

command -v python3 >/dev/null 2>&1 || die "python3 is required"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/scripts/install.py" ]; then
  if [ -z "$COMMIT" ] && [ -d "$SCRIPT_DIR/.git" ] && command -v git >/dev/null 2>&1; then
    COMMIT="$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || true)"
  fi
  if [ -z "$COMMIT" ]; then
    COMMIT="$(remote_commit "$SOURCE" "$REF" || true)"
  fi
  COMMIT="$(normalize_sha "$COMMIT")"
  is_full_sha "$COMMIT" || die "could not resolve a full source commit"

  SOURCE_DIRTY="${PRIME_AGENT_SKILLS_SOURCE_DIRTY:-}"
  if [ -z "$SOURCE_DIRTY" ]; then
    SOURCE_DIRTY="false"
    if [ -d "$SCRIPT_DIR/.git" ] && command -v git >/dev/null 2>&1 &&
       [ -n "$(git -C "$SCRIPT_DIR" status --porcelain 2>/dev/null || true)" ]; then
      SOURCE_DIRTY="true"
    fi
  fi

  exec python3 "$SCRIPT_DIR/scripts/install.py" \
    --source-root "$SCRIPT_DIR" \
    --source-url "$SOURCE" \
    --ref "$REF" \
    --commit "$COMMIT" \
    --source-dirty "$SOURCE_DIRTY" \
    "$@"
fi

command -v curl >/dev/null 2>&1 || die "curl is required for a remote install"
command -v tar >/dev/null 2>&1 || die "tar is required for a remote install"

if [ -z "$COMMIT" ]; then
  COMMIT="$(remote_commit "$SOURCE" "$REF" || true)"
fi
COMMIT="$(normalize_sha "$COMMIT")"
is_full_sha "$COMMIT" || die "could not resolve a full source commit for $SOURCE $REF"

REPO="$(github_repo_from_source "$SOURCE")"
[ -n "$REPO" ] || die "remote installation currently requires a GitHub source URL"

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/prime-agent-skills-install.XXXXXX")"
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$TEMP_ROOT/source"
curl -fsSL --retry 3 "https://github.com/$REPO/archive/$COMMIT.tar.gz" -o "$TEMP_ROOT/source.tar.gz"
tar -xzf "$TEMP_ROOT/source.tar.gz" -C "$TEMP_ROOT/source" --strip-components=1
[ -f "$TEMP_ROOT/source/scripts/install.py" ] || die "downloaded source snapshot is incomplete"

python3 "$TEMP_ROOT/source/scripts/install.py" \
  --source-root "$TEMP_ROOT/source" \
  --source-url "$SOURCE" \
  --ref "$REF" \
  --commit "$COMMIT" \
  --source-dirty false \
  "$@"
