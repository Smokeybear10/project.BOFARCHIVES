#!/usr/bin/env bash
# Bootstrap the private research data folder.
#
# Clones (or updates) Smokeybear10/801-DATA.FORTIFY into ~/Github/DATA/FORTIFY
# and symlinks it as ./Data so the pipeline can read raw xlsx files.
#
# The data repo is private. This script never commits or pushes anything.
# Idempotent: run as many times as you want.
#
# Requires: gh CLI authenticated to a GitHub account with read access to the
# private data repo. Run `gh auth login` first if you haven't.

set -e

DATA_REPO="Smokeybear10/801-DATA.FORTIFY"
LOCAL_CLONE="${HOME}/Github/DATA/FORTIFY"
SYMLINK="$(cd "$(dirname "$0")" && pwd)/Data"

# 1. gh must be authenticated
if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI not installed. Install from https://cli.github.com" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh CLI not authenticated. Run: gh auth login" >&2
  exit 1
fi

# 2. Clone or update the private data repo
mkdir -p "$(dirname "$LOCAL_CLONE")"
if [ -d "$LOCAL_CLONE/.git" ]; then
  echo "→ updating existing clone at $LOCAL_CLONE"
  git -C "$LOCAL_CLONE" pull --ff-only
else
  echo "→ cloning $DATA_REPO into $LOCAL_CLONE"
  gh repo clone "$DATA_REPO" "$LOCAL_CLONE"
fi

# 3. Symlink ./Data → local clone
if [ -L "$SYMLINK" ]; then
  CURRENT=$(readlink "$SYMLINK")
  if [ "$CURRENT" = "$LOCAL_CLONE" ]; then
    echo "→ symlink already correct: Data → $LOCAL_CLONE"
  else
    echo "→ repointing symlink: Data → $LOCAL_CLONE (was $CURRENT)"
    rm "$SYMLINK"
    ln -s "$LOCAL_CLONE" "$SYMLINK"
  fi
elif [ -e "$SYMLINK" ]; then
  echo "ERROR: $SYMLINK exists and is not a symlink. Move it aside first." >&2
  exit 1
else
  echo "→ creating symlink: Data → $LOCAL_CLONE"
  ln -s "$LOCAL_CLONE" "$SYMLINK"
fi

# 4. Sanity check
echo ""
echo "→ verifying contents reachable via Data/"
ls "$SYMLINK/Subjects Considered Data Visualization Assignment/" >/dev/null 2>&1 \
  && echo "  ✓ Subjects Considered Data Visualization Assignment/" \
  || { echo "  ✗ Subjects folder missing — clone may be incomplete" >&2; exit 1; }
ls "$SYMLINK/Defense Budget Visualization Assignment/" >/dev/null 2>&1 \
  && echo "  ✓ Defense Budget Visualization Assignment/" \
  || { echo "  ✗ Defense Budget folder missing" >&2; exit 1; }
ls "$SYMLINK/Appropriations/Completed Spreadsheets/" >/dev/null 2>&1 \
  && echo "  ✓ Appropriations/Completed Spreadsheets/" \
  || { echo "  ✗ Appropriations folder missing" >&2; exit 1; }

echo ""
echo "Done. Data is ready. Run the pipelines next:"
echo "  python run_bof_analysis.py  &&  python run_budget_analysis.py"
echo "  python run_combined_analysis.py  &&  python run_master_ledger.py"
