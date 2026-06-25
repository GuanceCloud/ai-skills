#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <commit-message> [--no-push]" >&2
  exit 1
fi

commit_message="$1"
push_enabled=1

if [[ "${2:-}" == "--no-push" ]]; then
  push_enabled=0
fi

branch_name="$(git branch --show-current)"
if [[ -z "$branch_name" ]]; then
  echo "Cannot determine current branch; stopped." >&2
  exit 1
fi

git add -A

if git diff --cached --quiet; then
  echo "No changes to commit." >&2
  exit 1
fi

commit_file="$(mktemp)"
trap 'rm -f "$commit_file"' EXIT

printf '%s\n\nGenerated-by: OpenAI Codex\n' "$commit_message" > "$commit_file"
git commit -F "$commit_file"

if [[ "$push_enabled" -eq 0 ]]; then
  echo "Commit completed; push skipped."
  exit 0
fi

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "$branch_name"
fi
