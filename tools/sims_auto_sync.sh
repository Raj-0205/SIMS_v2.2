#!/usr/bin/env bash

set -u

REPO="/home/raj_28_arp/SIMS_v2.2"
DEBOUNCE_SECONDS=5

cd "$REPO" || {
    echo "ERROR: Cannot enter repository: $REPO"
    exit 1
}

echo "=========================================="
echo " SIMS v2.2 GitHub Auto-Sync"
echo "=========================================="
echo "Repository: $REPO"
echo "Watching for file changes..."
echo "Press Ctrl+C to stop."
echo

sync_repo() {
    echo
    echo "[AUTO-SYNC] Change detected."
    echo "[AUTO-SYNC] Waiting ${DEBOUNCE_SECONDS}s for additional changes..."
    sleep "$DEBOUNCE_SECONDS"

    # Make sure there is actually something Git needs to commit.
    if [[ -z "$(git status --porcelain)" ]]; then
        echo "[AUTO-SYNC] No Git changes to commit."
        return
    fi

    echo "[AUTO-SYNC] Staging changes..."
    git add .

    if ! git diff --cached --quiet; then
        CHANGED_FILES=$(git diff --cached --name-only | wc -l)

        echo "[AUTO-SYNC] Committing ${CHANGED_FILES} changed file(s)..."

        git commit -m "Auto-sync: ${CHANGED_FILES} file(s) updated"

        if [[ $? -ne 0 ]]; then
            echo "[AUTO-SYNC] ERROR: Commit failed."
            return
        fi

        echo "[AUTO-SYNC] Pushing to GitHub..."
        git push

        if [[ $? -eq 0 ]]; then
            echo "[AUTO-SYNC] SUCCESS: GitHub updated."
        else
            echo "[AUTO-SYNC] ERROR: Push failed."
        fi
    else
        echo "[AUTO-SYNC] Nothing staged."
    fi
}

inotifywait \
    -m \
    -r \
    -e close_write,create,delete,move \
    --exclude '(^|/)(\.git|\.venv|venv|\.ruff_cache|__pycache__)(/|$)' \
    "$REPO" |
while read -r DIRECTORY EVENT FILE; do

    # Ignore the auto-sync script itself.
    if [[ "$DIRECTORY$FILE" == "$REPO/tools/sims_auto_sync.sh" ]]; then
        continue
    fi

    sync_repo

done
