#!/bin/sh
set -eu

PROGRAM=${0##*/}
BASE_URL=
SKILLS=
INSTALL_ALL=0
AGENT=
SCOPE=user
PROJECT_DIR=
VERSION=latest
UPGRADE=0
FORCE=0
RUN_SETUP=0
ASSUME_YES=0
CUSTOM_DEST=

usage() {
  cat <<'EOF'
Usage: install.sh --base-url URL [--skill NAME | --all] [options]

Required:
  --base-url URL       Complete release root, including the OSS prefix.

Selection:
  --skill NAME         Install one skill; may be repeated.
  --all                Install every published skill.
  --agent NAME         codex|claude|opencode|pi|gemini|copilot|cursor|amp|agents
  --scope SCOPE        user (default) or project
  --dest DIR           Override the agent destination root.
  --project-dir DIR    Override project root for project scope.
  --version SHA        Install an immutable commit version (default: latest).

Safety:
  --upgrade            Update an installed skill when a newer version exists.
  --force              Replace an existing managed skill, even at the same version.
  --run-setup          Run setup declared by the release manifest.
  --yes                Skip write/setup confirmation prompts.
  --help               Show this help.
EOF
}

die() { printf '%s: %s\n' "$PROGRAM" "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url) [ "$#" -ge 2 ] || die "--base-url requires a value"; BASE_URL=$2; shift 2 ;;
    --skill) [ "$#" -ge 2 ] || die "--skill requires a value"; SKILLS="${SKILLS}${SKILLS:+ }$2"; shift 2 ;;
    --all) INSTALL_ALL=1; shift ;;
    --agent) [ "$#" -ge 2 ] || die "--agent requires a value"; AGENT=$2; shift 2 ;;
    --scope) [ "$#" -ge 2 ] || die "--scope requires a value"; SCOPE=$2; shift 2 ;;
    --dest) [ "$#" -ge 2 ] || die "--dest requires a value"; CUSTOM_DEST=$2; shift 2 ;;
    --project-dir) [ "$#" -ge 2 ] || die "--project-dir requires a value"; PROJECT_DIR=$2; shift 2 ;;
    --version) [ "$#" -ge 2 ] || die "--version requires a value"; VERSION=$2; shift 2 ;;
    --upgrade) UPGRADE=1; shift ;;
    --force) FORCE=1; shift ;;
    --run-setup) RUN_SETUP=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ -n "$BASE_URL" ] || die "--base-url is required"
BASE_URL=${BASE_URL%/}
case "$BASE_URL" in http://*|https://*) ;; *) die "--base-url must start with http:// or https://" ;; esac
[ "$SCOPE" = user ] || [ "$SCOPE" = project ] || die "--scope must be user or project"
[ "$INSTALL_ALL" -eq 0 ] || [ -z "$SKILLS" ] || die "--all cannot be combined with --skill"
if [ "$VERSION" != latest ]; then
  case "$VERSION" in *[!0-9a-fA-F]*|'') die "--version must be a commit SHA" ;; esac
  [ "${#VERSION}" -eq 40 ] || die "--version must be a full 40-character commit SHA"
fi

TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai-skills-install.XXXXXX")
COMMITTED=0
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT HUP INT TERM

download() {
  url=$1 output=$2
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 3 "$url" -o "$output"
  elif command -v wget >/dev/null 2>&1; then wget -q --tries=3 -O "$output" "$url"
  else die "curl or wget is required"; fi
}

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 "$1" | awk '{print $NF}'
  else die "a SHA-256 tool (sha256sum, shasum, or openssl) is required"; fi
}

INDEX_PATH=skills-index.tsv
[ "$VERSION" = latest ] || INDEX_PATH="versions/$VERSION/skills-index.tsv"
INDEX_FILE=$TMP_ROOT/index.tsv
download "$BASE_URL/$INDEX_PATH" "$INDEX_FILE"

available_skills() { awk -F '\t' '!/^#/ && NF >= 6 {print $1}' "$INDEX_FILE"; }

choose_from_menu() {
  label=$1; shift
  [ -r /dev/tty ] || die "$label is required in non-interactive mode"
  printf '%s\n' "$label:" >/dev/tty
  index=1
  for value in "$@"; do printf '  %s) %s\n' "$index" "$value" >/dev/tty; index=$((index + 1)); done
  printf '> ' >/dev/tty
  read -r choice </dev/tty
  index=1
  for value in "$@"; do [ "$choice" = "$index" ] && { printf '%s\n' "$value"; return; }; index=$((index + 1)); done
  die "invalid selection"
}

if [ "$INSTALL_ALL" -eq 1 ]; then
  SKILLS=$(available_skills | tr '\n' ' ')
elif [ -z "$SKILLS" ]; then
  set -- $(available_skills)
  SKILLS=$(choose_from_menu "Select a skill" "$@")
fi

if [ -z "$CUSTOM_DEST" ] && [ -z "$AGENT" ]; then
  AGENT=$(choose_from_menu "Select an agent" codex claude opencode pi gemini copilot cursor amp agents)
fi

if [ "$SCOPE" = project ]; then
  if [ -z "$PROJECT_DIR" ]; then
    PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  fi
  PROJECT_DIR=$(cd "$PROJECT_DIR" && pwd)
fi

destination_root() {
  [ -n "$CUSTOM_DEST" ] && { printf '%s\n' "$CUSTOM_DEST"; return; }
  if [ "$SCOPE" = user ]; then
    case "$AGENT" in
      codex) printf '%s/.codex/skills\n' "$HOME" ;;
      claude) printf '%s/.claude/skills\n' "$HOME" ;;
      opencode) printf '%s/.config/opencode/skills\n' "$HOME" ;;
      pi) printf '%s/.pi/agent/skills\n' "$HOME" ;;
      gemini) printf '%s/.gemini/skills\n' "$HOME" ;;
      copilot) printf '%s/.copilot/skills\n' "$HOME" ;;
      cursor) printf '%s/.cursor/skills\n' "$HOME" ;;
      amp) printf '%s/.config/agents/skills\n' "$HOME" ;;
      agents) printf '%s/.agents/skills\n' "$HOME" ;;
      *) die "unsupported agent: $AGENT" ;;
    esac
  else
    case "$AGENT" in
      codex|agents|amp) printf '%s/.agents/skills\n' "$PROJECT_DIR" ;;
      claude) printf '%s/.claude/skills\n' "$PROJECT_DIR" ;;
      opencode) printf '%s/.opencode/skills\n' "$PROJECT_DIR" ;;
      pi) printf '%s/.pi/skills\n' "$PROJECT_DIR" ;;
      gemini) printf '%s/.gemini/skills\n' "$PROJECT_DIR" ;;
      copilot) printf '%s/.github/skills\n' "$PROJECT_DIR" ;;
      cursor) printf '%s/.cursor/skills\n' "$PROJECT_DIR" ;;
      *) die "unsupported agent: $AGENT" ;;
    esac
  fi
}

DEST_ROOT=$(destination_root)
mkdir -p "$DEST_ROOT"
DEST_ROOT=$(cd "$DEST_ROOT" && pwd)

entry_for() { awk -F '\t' -v wanted="$1" '!/^#/ && $1 == wanted {print; found=1; exit} END {if (!found) exit 1}' "$INDEX_FILE"; }

is_modified() {
  installed=$1
  [ -f "$installed/.skill-files.sha256" ] && [ -f "$installed/.skill-files.list" ] || return 0
  while IFS= read -r line; do
    expected=${line%%  *}; relative=${line#*  }
    [ -f "$installed/$relative" ] || return 0
    [ "$(hash_file "$installed/$relative")" = "$expected" ] || return 0
  done < "$installed/.skill-files.sha256"
  (cd "$installed" && find . -type f ! -name .skill-install.json ! -name .skill-files.sha256 ! -name .skill-files.list ! -name .skill-setup.tsv | sed 's#^./##' | LC_ALL=C sort) > "$TMP_ROOT/current-files"
  cmp -s "$installed/.skill-files.list" "$TMP_ROOT/current-files" || return 0
  return 1
}

SELECTED=$TMP_ROOT/selected
: > "$SELECTED"
for skill in $SKILLS; do
  case "$skill" in *[!A-Za-z0-9_-]*|'') die "invalid skill name: $skill" ;; esac
  line=$(entry_for "$skill") || die "skill is not published: $skill"
  printf '%s\n' "$line" >> "$SELECTED"
done

PENDING=$TMP_ROOT/pending
: > "$PENDING"
PENDING_SKILLS=
tab=$(printf '\t')
while IFS="$tab" read -r skill version tar_path tar_hash zip_path zip_hash; do
  [ "$VERSION" = latest ] || [ "$version" = "$VERSION" ] || die "release index version does not match --version"
  installed=$DEST_ROOT/$skill
  if [ -d "$installed" ]; then
    installed_version=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$installed/.skill-install.json" 2>/dev/null | head -n 1 || true)
    if [ "$FORCE" -ne 1 ] && [ "$installed_version" = "$version" ]; then
      printf 'Already up to date: %s@%s\n' "$skill" "$version"
      continue
    fi
  elif [ "$UPGRADE" -eq 1 ]; then
    die "$skill is not installed; omit --upgrade for the initial installation"
  fi
  printf '%s\n' "$skill${tab}$version${tab}$tar_path${tab}$tar_hash${tab}$zip_path${tab}$zip_hash" >> "$PENDING"
  PENDING_SKILLS="${PENDING_SKILLS}${PENDING_SKILLS:+ }$skill"
done < "$SELECTED"

[ -s "$PENDING" ] || { printf 'All selected skills are already up to date.\n'; exit 0; }

printf 'Install destination: %s\n' "$DEST_ROOT"
printf 'Skills: %s\n' "$PENDING_SKILLS"
AUTO_APPROVED=0
if [ "$INSTALL_ALL" -eq 0 ] && { [ "$UPGRADE" -eq 1 ] || [ "$FORCE" -eq 1 ]; }; then AUTO_APPROVED=1; fi
if [ "$ASSUME_YES" -ne 1 ] && [ "$AUTO_APPROVED" -ne 1 ]; then
  [ -r /dev/tty ] || die "confirmation requires a terminal; pass --yes for non-interactive use"
  printf 'Continue? [y/N] ' >/dev/tty; read -r answer </dev/tty
  case "$answer" in y|Y|yes|YES) ;; *) die "cancelled" ;; esac
fi

TXN=$DEST_ROOT/.ai-skills-txn.$$
mkdir "$TXN"
PREPARED=$TMP_ROOT/prepared
mkdir "$PREPARED"
while IFS="$tab" read -r skill version tar_path tar_hash zip_path zip_hash; do
  case "$tar_path" in /*|*../*|../*|*'/..') die "unsafe archive path in release index: $tar_path" ;; esac
  case "$tar_hash" in *[!0-9a-f]*|'') die "invalid archive hash for $skill" ;; esac
  [ "${#tar_hash}" -eq 64 ] || die "invalid archive hash for $skill"
  archive=$TMP_ROOT/$skill.tar.gz
  download "$BASE_URL/$tar_path" "$archive"
  [ "$(hash_file "$archive")" = "$tar_hash" ] || die "SHA-256 mismatch for $skill"
  listing=$TMP_ROOT/$skill.listing
  tar -tzf "$archive" > "$listing"
  awk -v root="$skill/" 'index($0, root) != 1 || $0 ~ /(^|\/)\.\.($|\/)/ || $0 ~ /^\// {bad=1} END {exit bad}' "$listing" || die "unsafe archive paths for $skill"
  tar -xzf "$archive" -C "$PREPARED"
  [ -f "$PREPARED/$skill/SKILL.md" ] || die "archive for $skill has no SKILL.md"
  installed=$DEST_ROOT/$skill
  if [ -d "$installed" ]; then
    installed_version=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$installed/.skill-install.json" 2>/dev/null | head -n 1 || true)
    [ "$UPGRADE" -eq 1 ] || [ "$FORCE" -eq 1 ] || die "$skill is already installed; pass --upgrade or --force"
    if is_modified "$installed"; then
      [ "$FORCE" -eq 1 ] || die "$skill has local modifications; pass --force to replace it"
    fi
  fi
  cat > "$PREPARED/$skill/.skill-install.json" <<EOF
{"schema_version":1,"name":"$skill","version":"$version","archive_sha256":"$tar_hash","source":"$BASE_URL/$tar_path","installed_at":"$(date -u '+%Y-%m-%dT%H:%M:%SZ')"}
EOF
done < "$PENDING"

rollback() {
  [ -f "$TMP_ROOT/applied" ] || return
  while IFS= read -r skill; do
    [ -d "$DEST_ROOT/$skill" ] && rm -rf "$DEST_ROOT/$skill"
    [ -d "$TXN/old-$skill" ] && mv "$TXN/old-$skill" "$DEST_ROOT/$skill"
  done < "$TMP_ROOT/applied"
}
trap 'if [ "$COMMITTED" -ne 1 ]; then rollback; fi; cleanup' EXIT HUP INT TERM

: > "$TMP_ROOT/applied"
for skill in $PENDING_SKILLS; do
  [ -d "$PREPARED/$skill" ] || continue
  [ -d "$DEST_ROOT/$skill" ] && mv "$DEST_ROOT/$skill" "$TXN/old-$skill"
  printf '%s\n' "$skill" >> "$TMP_ROOT/applied"
  mv "$PREPARED/$skill" "$DEST_ROOT/$skill"
done

COMMITTED=1
rm -rf "$TXN"

if [ "$RUN_SETUP" -eq 1 ]; then
  for skill in $PENDING_SKILLS; do
    setup_file=$DEST_ROOT/$skill/.skill-setup.tsv
    [ -s "$setup_file" ] || { printf 'No setup declared for %s\n' "$skill"; continue; }
    executable=$(awk -F '\t' '$1 == "unix-executable" {print $2; exit}' "$setup_file")
    [ -n "$executable" ] || { printf 'No Unix setup declared for %s\n' "$skill"; continue; }
    set -- "$executable"
    while IFS="$tab" read -r kind value; do [ "$kind" = unix-arg ] && set -- "$@" "$value"; done < "$setup_file"
    printf 'Setup command for %s:' "$skill"; printf ' %s' "$@"; printf '\n'
    if [ "$ASSUME_YES" -ne 1 ]; then printf 'Run setup? [y/N] ' >/dev/tty; read -r answer </dev/tty; case "$answer" in y|Y|yes|YES) ;; *) continue ;; esac; fi
    (cd "$DEST_ROOT/$skill" && "$@")
  done
fi

printf 'Installed successfully into %s\n' "$DEST_ROOT"
