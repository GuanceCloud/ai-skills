#!/bin/sh
set -eu

PROGRAM=${0##*/}
SKILLS=
UNINSTALL_ALL=0
AGENT=
SCOPE=user
PROJECT_DIR=
FORCE=0
ASSUME_YES=0
CUSTOM_DEST=

usage() {
  cat <<'EOF'
Usage: uninstall.sh [--skill NAME | --all] [options]

Selection:
  --skill NAME         Uninstall one managed skill; may be repeated.
  --all                Uninstall every managed skill in the destination.
  --agent NAME         codex|claude|opencode|pi|gemini|copilot|cursor|amp|agents
  --scope SCOPE        user (default) or project
  --dest DIR           Override the agent destination root.
  --project-dir DIR    Override project root for project scope.

Safety:
  --force              Back up and remove locally modified managed skills.
  --yes                Skip the removal confirmation.
  --help               Show this help.
EOF
}

die() { printf '%s: %s\n' "$PROGRAM" "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skill) [ "$#" -ge 2 ] || die "--skill requires a value"; SKILLS="${SKILLS}${SKILLS:+ }$2"; shift 2 ;;
    --all) UNINSTALL_ALL=1; shift ;;
    --agent) [ "$#" -ge 2 ] || die "--agent requires a value"; AGENT=$2; shift 2 ;;
    --scope) [ "$#" -ge 2 ] || die "--scope requires a value"; SCOPE=$2; shift 2 ;;
    --dest) [ "$#" -ge 2 ] || die "--dest requires a value"; CUSTOM_DEST=$2; shift 2 ;;
    --project-dir) [ "$#" -ge 2 ] || die "--project-dir requires a value"; PROJECT_DIR=$2; shift 2 ;;
    --force) FORCE=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[ "$SCOPE" = user ] || [ "$SCOPE" = project ] || die "--scope must be user or project"
[ "$UNINSTALL_ALL" -eq 0 ] || [ -z "$SKILLS" ] || die "--all cannot be combined with --skill"

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

if [ -z "$CUSTOM_DEST" ] && [ -z "$AGENT" ]; then
  AGENT=$(choose_from_menu "Select an agent" codex claude opencode pi gemini copilot cursor amp agents)
fi

if [ "$SCOPE" = project ]; then
  if [ -z "$PROJECT_DIR" ]; then PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd); fi
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
[ -d "$DEST_ROOT" ] || die "skill destination does not exist: $DEST_ROOT"
DEST_ROOT=$(cd "$DEST_ROOT" && pwd)

managed_skills() {
  for marker in "$DEST_ROOT"/*/.skill-install.json; do
    [ -f "$marker" ] || continue
    basename "$(dirname "$marker")"
  done | LC_ALL=C sort
}

if [ "$UNINSTALL_ALL" -eq 1 ]; then
  SKILLS=$(managed_skills | tr '\n' ' ')
elif [ -z "$SKILLS" ]; then
  set -- $(managed_skills)
  [ "$#" -gt 0 ] || die "no managed skills found in $DEST_ROOT"
  SKILLS=$(choose_from_menu "Select a skill to uninstall" "$@")
fi
[ -n "$SKILLS" ] || die "no managed skills found in $DEST_ROOT"

TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/ai-skills-uninstall.XXXXXX")
COMMITTED=0
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT HUP INT TERM

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 "$1" | awk '{print $NF}'
  else die "a SHA-256 tool (sha256sum, shasum, or openssl) is required"; fi
}

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

MODIFIED=$TMP_ROOT/modified
: > "$MODIFIED"
for skill in $SKILLS; do
  case "$skill" in *[!A-Za-z0-9_-]*|'') die "invalid skill name: $skill" ;; esac
  installed=$DEST_ROOT/$skill
  [ -d "$installed" ] || die "skill is not installed: $skill"
  [ ! -L "$installed" ] || die "refusing to remove a symbolic-link skill directory: $installed"
  [ -f "$installed/.skill-install.json" ] || die "refusing to remove unmanaged directory: $installed"
  if is_modified "$installed"; then
    [ "$FORCE" -eq 1 ] || die "$skill has local modifications; pass --force to back it up and uninstall it"
    printf '%s\n' "$skill" >> "$MODIFIED"
  fi
done

printf 'Uninstall destination: %s\n' "$DEST_ROOT"
printf 'Skills: %s\n' "$SKILLS"
if [ "$ASSUME_YES" -ne 1 ]; then
  [ -r /dev/tty ] || die "confirmation requires a terminal; pass --yes for non-interactive use"
  printf 'Remove these managed skills? [y/N] ' >/dev/tty; read -r answer </dev/tty
  case "$answer" in y|Y|yes|YES) ;; *) die "cancelled" ;; esac
fi

TXN=$DEST_ROOT/.ai-skills-uninstall-txn.$$
mkdir "$TXN"
MOVED=$TMP_ROOT/moved
: > "$MOVED"
rollback() {
  [ -f "$MOVED" ] || return
  while IFS= read -r skill; do [ -d "$TXN/$skill" ] && mv "$TXN/$skill" "$DEST_ROOT/$skill"; done < "$MOVED"
}
trap 'if [ "$COMMITTED" -ne 1 ]; then rollback; fi; cleanup' EXIT HUP INT TERM

for skill in $SKILLS; do
  mv "$DEST_ROOT/$skill" "$TXN/$skill"
  printf '%s\n' "$skill" >> "$MOVED"
done

BACKUP_ROOT=
if [ -s "$MODIFIED" ]; then
  stamp=$(date -u '+%Y%m%dT%H%M%SZ')-$$
  if [ "$SCOPE" = project ]; then BACKUP_ROOT=$PROJECT_DIR/.ai-skills/backups/$stamp
  else BACKUP_ROOT=${XDG_DATA_HOME:-$HOME/.local/share}/ai-skills/backups/$stamp; fi
  mkdir -p "$BACKUP_ROOT"
  while IFS= read -r skill; do cp -R "$TXN/$skill" "$BACKUP_ROOT/$skill"; done < "$MODIFIED"
fi

COMMITTED=1
rm -rf "$TXN"
printf 'Uninstalled successfully: %s\n' "$SKILLS"
if [ -n "$BACKUP_ROOT" ]; then printf 'Modified skills were backed up to: %s\n' "$BACKUP_ROOT"
else printf 'No backup was created for unmodified skills.\n'; fi
