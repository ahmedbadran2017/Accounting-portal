#!/usr/bin/env bash
# Build the SPA, commit the refreshed bundle, and push.
# Run from the repo root: ./deploy.sh "optional commit message"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/frontend"

echo "▸ Building SPA…"
[ -d node_modules ] || npm install
npm run build

cd "$ROOT"
MSG="${1:-build: refresh SPA bundle}"

if git diff --quiet && git diff --cached --quiet; then
  echo "▸ Nothing changed — bundle already current."
  exit 0
fi

echo "▸ Committing…"
git add -A
git commit -m "$MSG"

if git remote get-url origin >/dev/null 2>&1; then
  echo "▸ Pushing…"
  git push
  echo "✓ Pushed. Now on the server: bench get-app / migrate (see DEPLOY.md)."
else
  echo "✓ Committed locally. Add a remote and push:"
  echo "    git remote add origin git@github.com:ahmedbadran2017/accounting_portal.git"
  echo "    git push -u origin main"
fi
