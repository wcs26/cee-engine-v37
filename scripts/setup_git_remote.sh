#!/usr/bin/env bash
# V37.1.1 — Configure le remote git + push initial.
# Tu dois avoir un compte GitHub et soit gh CLI loggué, soit une URL ssh existante.
set -u
REPO_NAME="cee-engine-v37"

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  echo "✓ gh CLI loggué — création du repo + push autonome"
  gh repo create "$REPO_NAME" --private --source=. --push --description "CEE Engine V37.1.1 — audit CEE prédictif + tunnel commercial"
else
  echo "⚠ gh CLI absent ou non loggué."
  echo "  Option A : brew install gh && gh auth login && ./scripts/setup_git_remote.sh"
  echo "  Option B : crée le repo manuellement sur https://github.com/new puis :"
  echo "    git remote add origin git@github.com:<TOI>/$REPO_NAME.git"
  echo "    git branch -M main"
  echo "    git push -u origin main"
fi
