#!/bin/sh
set -eu

MODE=
OUTPUT=
OSSUTIL_VERSION=2.3.0
OSSUTIL_LINUX_AMD64_SHA256=3ae4d9fc85a7a6e9f5654d1599766f1a3a42a3692870887b5ae9338d582ef65a
OSSUTIL_LINUX_ARM64_SHA256=f6c95ba0c2d2ef30290af686ce4d706c701f4734ce8090bee4288a77e3f1d764
OSSUTIL_MAC_AMD64_SHA256=8437fdd3ef1a3eb12310f61fcf1c00a5bff5cdab47b4fea815527472e7cf896c
OSSUTIL_MAC_ARM64_SHA256=058fd048f321f8c80def8b748030531646eefe3a82837bf16b581ba7d9c84ac7

usage() {
  cat <<'EOF'
Usage: release.sh (--dry-run | --publish) [--output DIR]

--dry-run builds and validates all release artifacts without OSS credentials.
--publish requires a clean Git worktree and these environment variables:
  OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_REGION, OSS_ENDPOINT,
  OSS_BUCKET, OSS_PREFIX, OSS_PUBLIC_BASE_URL
EOF
}
die() { printf 'release.sh: %s\n' "$*" >&2; exit 1; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run|--publish) [ -z "$MODE" ] || die "choose exactly one mode"; MODE=$1; shift ;;
    --output) [ "$#" -ge 2 ] || die "--output requires a value"; OUTPUT=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -n "$MODE" ] || die "choose --dry-run or --publish"

REPO=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v git >/dev/null 2>&1 || die "git is required"
VERSION=$(git -C "$REPO" rev-parse HEAD)
if [ -z "$OUTPUT" ]; then OUTPUT=$(mktemp -d "${TMPDIR:-/tmp}/ai-skills-release.XXXXXX")
else mkdir -p "$OUTPUT"; OUTPUT=$(CDPATH= cd -- "$OUTPUT" && pwd); fi

if [ "$MODE" = --publish ] && [ -n "$(git -C "$REPO" status --porcelain)" ]; then
  die "--publish requires a clean Git worktree"
fi

python3 "$REPO/scripts/build_skill_release.py" --repo "$REPO" --output "$OUTPUT" --version "$VERSION"
printf 'Built release %s at %s\n' "$VERSION" "$OUTPUT"
[ "$MODE" = --publish ] || exit 0

for name in OSS_ACCESS_KEY_ID OSS_ACCESS_KEY_SECRET OSS_REGION OSS_ENDPOINT OSS_BUCKET OSS_PREFIX OSS_PUBLIC_BASE_URL; do
  eval "value=\${$name-}"
  [ -n "$value" ] || die "$name is required for --publish"
  case "$value" in '<fill-manually>') die "$name still contains its placeholder" ;; esac
done

OSS_PREFIX=$(printf '%s' "$OSS_PREFIX" | sed 's#^/*##; s#/*$##')
OSS_PUBLIC_BASE_URL=$(printf '%s' "$OSS_PUBLIC_BASE_URL" | sed 's#/*$##')
PUBLIC_ROOT=$OSS_PUBLIC_BASE_URL
[ -z "$OSS_PREFIX" ] || PUBLIC_ROOT=$PUBLIC_ROOT/$OSS_PREFIX

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}

install_ossutil() {
  os=$(uname -s); arch=$(uname -m)
  case "$os/$arch" in
    Linux/x86_64|Linux/amd64) package=linux-amd64; expected=$OSSUTIL_LINUX_AMD64_SHA256 ;;
    Linux/aarch64|Linux/arm64) package=linux-arm64; expected=$OSSUTIL_LINUX_ARM64_SHA256 ;;
    Darwin/x86_64) package=mac-amd64; expected=$OSSUTIL_MAC_AMD64_SHA256 ;;
    Darwin/arm64) package=mac-arm64; expected=$OSSUTIL_MAC_ARM64_SHA256 ;;
    *) die "unsupported publish platform: $os/$arch" ;;
  esac
  tool_root=$(mktemp -d "${TMPDIR:-/tmp}/ossutil.XXXXXX")
  archive=$tool_root/ossutil.zip
  url=https://gosspublic.alicdn.com/ossutil/v2/$OSSUTIL_VERSION/ossutil-$OSSUTIL_VERSION-$package.zip
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 3 "$url" -o "$archive"
  else die "curl is required to download ossutil"; fi
  [ "$(hash_file "$archive")" = "$expected" ] || die "ossutil SHA-256 verification failed"
  python3 - "$archive" "$tool_root" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    archive.extractall(sys.argv[2])
PY
  OSSUTIL=$(find "$tool_root" -type f -name ossutil | head -n 1)
  [ -n "$OSSUTIL" ] || die "ossutil binary not found in official archive"
  chmod 755 "$OSSUTIL"
  export OSSUTIL
}

install_ossutil

object_url() {
  relative=$1
  if [ -n "$OSS_PREFIX" ]; then printf 'oss://%s/%s/%s\n' "$OSS_BUCKET" "$OSS_PREFIX" "$relative"
  else printf 'oss://%s/%s\n' "$OSS_BUCKET" "$relative"; fi
}

upload_file() {
  file=$1 relative=$2 cache=$3
  "$OSSUTIL" cp "$file" "$(object_url "$relative")" --force --cache-control "$cache"
}

remote_version_sums=$OUTPUT/remote-version-SHA256SUMS
version_exists=0
if curl -fsSL --retry 2 "$PUBLIC_ROOT/versions/$VERSION/SHA256SUMS" -o "$remote_version_sums" 2>/dev/null; then
  cmp -s "$OUTPUT/versions/$VERSION/SHA256SUMS" "$remote_version_sums" || die "immutable version $VERSION already exists with different checksums"
  version_exists=1
  printf 'Immutable version %s already exists and matches; skipping version uploads.\n' "$VERSION"
fi

if [ "$version_exists" -eq 0 ]; then
  find "$OUTPUT/versions/$VERSION" -type f | LC_ALL=C sort | while IFS= read -r file; do
    relative=${file#"$OUTPUT/"}
    upload_file "$file" "$relative" 'public,max-age=31536000,immutable'
  done
fi

# Mutable entrypoints are published last. The two indexes are the latest pointer.
for relative in install.sh install.ps1 SHA256SUMS skills-index.json skills-index.tsv; do
  upload_file "$OUTPUT/$relative" "$relative" 'no-cache'
done

verify_dir=$(mktemp -d "${TMPDIR:-/tmp}/ai-skills-verify.XXXXXX")
attempt=1
while [ "$attempt" -le 6 ]; do
  failed=0
  while IFS= read -r line; do
    expected=${line%%  *}; relative=${line#*  }
    target=$verify_dir/$(printf '%s' "$relative" | tr '/' '_')
    if ! curl -fsSL --retry 2 "$PUBLIC_ROOT/$relative" -o "$target" || [ "$(hash_file "$target")" != "$expected" ]; then failed=1; break; fi
  done < "$OUTPUT/SHA256SUMS"
  [ "$failed" -eq 0 ] && break
  attempt=$((attempt + 1)); sleep 5
done
[ "$failed" -eq 0 ] || die "public read-back verification failed after retries"
printf 'Published and verified: %s\n' "$PUBLIC_ROOT"
