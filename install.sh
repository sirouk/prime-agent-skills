#!/usr/bin/env bash
# Installer for the deep-solve skill and /deep-solve prompt template (prime-agent).
#
#   curl -fsSL https://raw.githubusercontent.com/sirouk/prime-agent-deep-solve/main/install.sh | bash
#
# Change the GitHub owner/repo in ONE place: DEEP_SOLVE_DEFAULT_REPO below
# (or set DEEP_SOLVE_REPO in the environment).
set -euo pipefail

DEEP_SOLVE_DEFAULT_REPO="sirouk/prime-agent-deep-solve"

REPO="${DEEP_SOLVE_REPO:-$DEEP_SOLVE_DEFAULT_REPO}"
REF="${DEEP_SOLVE_REF:-main}"
SOURCE_DIR="${DEEP_SOLVE_SOURCE_DIR:-}"
AGENT_DIR="${PRIME_AGENT_DIR:-$HOME/.prime/agent}"

MODE="install"
SCOPE="user"

usage() {
  cat <<EOF
Install the deep-solve skill and /deep-solve prompt template for prime-agent.

Usage: install.sh [--project] [--uninstall] [-h|--help]

Options:
  --project     Install into ./.prime/agent/ (current directory) instead of the user dir.
  --uninstall   Remove skills/deep-solve and prompts/deep-solve.md from the target dir.
  -h, --help    Show this help.

Environment:
  PRIME_AGENT_DIR         Target agent dir (default: \$HOME/.prime/agent).
  DEEP_SOLVE_REPO         GitHub owner/repo (default: $DEEP_SOLVE_DEFAULT_REPO).
  DEEP_SOLVE_REF          Branch, tag, or commit to download (default: main).
  DEEP_SOLVE_SOURCE_DIR   Install from this local checkout instead of downloading.

Alternative: prime-agent package install https://github.com/$REPO
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) MODE="uninstall" ;;
    --project) SCOPE="project" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ "$SCOPE" = "project" ]; then
  AGENT_DIR="$PWD/.prime/agent"
fi

SKILL_DEST="$AGENT_DIR/skills/deep-solve"
PROMPT_DEST="$AGENT_DIR/prompts/deep-solve.md"

if [ "$MODE" = "uninstall" ]; then
  rm -rf "$SKILL_DEST" "$PROMPT_DEST"
  echo "Removed:"
  echo "  $SKILL_DEST"
  echo "  $PROMPT_DEST"
  echo "Run /reload in open prime-agent sessions."
  exit 0
fi

TMP_DIR=""
STAGE_PATHS=""
cleanup() {
  if [ -n "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
  if [ -n "$STAGE_PATHS" ]; then
    # STAGE_PATHS holds newline-separated paths; none contain newlines.
    old_ifs="$IFS"
    IFS='
'
    for p in $STAGE_PATHS; do
      rm -rf "$p"
    done
    IFS="$old_ifs"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/deep-solve-install.XXXXXX")"

download() {
  # download <url> <output file>
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    die "need curl or wget to download the package"
  fi
}

command -v tar >/dev/null 2>&1 || [ -n "$SOURCE_DIR" ] || die "tar is required"

if [ -n "$SOURCE_DIR" ]; then
  [ -d "$SOURCE_DIR" ] || die "DEEP_SOLVE_SOURCE_DIR is not a directory: $SOURCE_DIR"
  SRC_ROOT="$(cd "$SOURCE_DIR" && pwd)"
  ORIGIN="local checkout $SRC_ROOT"
else
  URL="https://github.com/$REPO/archive/$REF.tar.gz"
  echo "Downloading $URL"
  download "$URL" "$TMP_DIR/pkg.tar.gz" || die "download failed: $URL"
  mkdir -p "$TMP_DIR/extract"
  tar -xzf "$TMP_DIR/pkg.tar.gz" -C "$TMP_DIR/extract" || die "could not extract the archive"
  SRC_ROOT=""
  for d in "$TMP_DIR"/extract/*/; do
    if [ -d "$d" ]; then
      SRC_ROOT="${d%/}"
      break
    fi
  done
  [ -n "$SRC_ROOT" ] || die "archive is empty: $URL"
  ORIGIN="$URL"
fi

[ -d "$SRC_ROOT/skills/deep-solve" ] || die "missing skills/deep-solve in $ORIGIN"
[ -f "$SRC_ROOT/prompts/deep-solve.md" ] || die "missing prompts/deep-solve.md in $ORIGIN"

# skill_name <SKILL.md>: print the frontmatter `name:` value.
skill_name() {
  awk '
    NR == 1 { if ($0 ~ /^---[ \t\r]*$/) { infm = 1; next } else { exit } }
    infm && /^---[ \t\r]*$/ { exit }
    infm && /^name:/ {
      v = $0
      sub(/^name:[ \t]*/, "", v)
      sub(/[ \t\r]+$/, "", v)
      gsub(/^["\047]|["\047]$/, "", v)
      print v
      exit
    }
  ' "$1"
}

validate_skill_dir() {
  [ -f "$1/SKILL.md" ] || die "SKILL.md not found in $1"
  found="$(skill_name "$1/SKILL.md")"
  [ "$found" = "deep-solve" ] || die "SKILL.md frontmatter name is '$found', expected 'deep-solve'"
}

# replace_path <staged> <dest>: swap a staged copy into place.
replace_path() {
  staged="$1"
  dest="$2"
  backup="$dest.old.$$"
  STAGE_PATHS="$STAGE_PATHS
$backup"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    mv "$dest" "$backup"
  fi
  if ! mv "$staged" "$dest"; then
    if [ -e "$backup" ]; then
      mv "$backup" "$dest"
    fi
    die "could not install $dest"
  fi
  rm -rf "$backup"
}

mkdir -p "$AGENT_DIR/skills" "$AGENT_DIR/prompts"

SKILL_STAGE="$SKILL_DEST.new.$$"
PROMPT_STAGE="$PROMPT_DEST.new.$$"
STAGE_PATHS="$SKILL_STAGE
$PROMPT_STAGE"

rm -rf "$SKILL_STAGE" "$PROMPT_STAGE"
cp -R "$SRC_ROOT/skills/deep-solve" "$SKILL_STAGE"
cp "$SRC_ROOT/prompts/deep-solve.md" "$PROMPT_STAGE"

validate_skill_dir "$SKILL_STAGE"

replace_path "$SKILL_STAGE" "$SKILL_DEST"
replace_path "$PROMPT_STAGE" "$PROMPT_DEST"

validate_skill_dir "$SKILL_DEST"
[ -f "$PROMPT_DEST" ] || die "prompt template missing after install: $PROMPT_DEST"

echo "Installed ($SCOPE scope) from $ORIGIN:"
echo "  skill:  $SKILL_DEST"
(cd "$SKILL_DEST" && find . -type f | sort | sed 's|^\./|          |')
echo "  prompt: $PROMPT_DEST"
echo
echo "Next steps:"
echo "  - Run /reload in open prime-agent sessions."
echo "  - Use \`/deep-solve <problem>\` or just describe a hard problem."
echo "  - Alternative: prime-agent package install https://github.com/$REPO"
