#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
INDEX_DIR="$REPO_ROOT/ros2_parser/index"
REMOTE="${1:-origin}"

if [ ! -f "$INDEX_DIR/distros.json" ]; then
  echo "Error: No index found at $INDEX_DIR" >&2
  exit 1
fi

WORK_DIR=$(mktemp -d)
trap 'cd "$REPO_ROOT" && git worktree remove --force "$WORK_DIR" 2>/dev/null; rm -rf "$WORK_DIR"' EXIT

if git ls-remote --heads "$REMOTE" gh-pages | grep -q gh-pages; then
  git fetch "$REMOTE" gh-pages
  git worktree add "$WORK_DIR" "$REMOTE/gh-pages"
  cd "$WORK_DIR"
  git checkout -B gh-pages "$REMOTE/gh-pages"
else
  git worktree add --detach "$WORK_DIR"
  cd "$WORK_DIR"
  git checkout --orphan gh-pages
  git rm -rf . 2>/dev/null || true
fi

rm -rf index/
mkdir -p index/
cp -r "$INDEX_DIR"/* index/
touch .nojekyll

git add -A
if git diff --cached --quiet; then
  echo "No changes to deploy."
else
  DISTROS=$(python3 -c "import json; print(', '.join(json.load(open('index/distros.json'))))")
  git commit -m "Update index: $DISTROS ($(date -u +%Y-%m-%d))"
  git push "$REMOTE" gh-pages
  echo "Deployed to gh-pages."
fi
