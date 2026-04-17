#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "用法: $0 <commit-message> [--no-push]" >&2
  exit 1
fi

commit_message="$1"
push_enabled=1

if [[ "${2:-}" == "--no-push" ]]; then
  push_enabled=0
fi

branch_name="$(git branch --show-current)"
if [[ -z "$branch_name" ]]; then
  echo "无法识别当前分支，已停止。" >&2
  exit 1
fi

git add -A

if git diff --cached --quiet; then
  echo "没有可提交的改动。" >&2
  exit 1
fi

commit_file="$(mktemp)"
trap 'rm -f "$commit_file"' EXIT

printf '%s\n\nGenerated-by: OpenAI Codex\n' "$commit_message" > "$commit_file"
git commit -F "$commit_file"

if [[ "$push_enabled" -eq 0 ]]; then
  echo "已完成 commit，未执行 push。"
  exit 0
fi

if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "$branch_name"
fi
