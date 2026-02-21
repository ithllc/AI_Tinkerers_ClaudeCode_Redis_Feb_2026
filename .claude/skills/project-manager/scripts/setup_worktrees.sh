#!/bin/bash
# setup_worktrees.sh - Initialize git worktrees for parallel workers
#
# Usage: ./setup_worktrees.sh [num_workers] [base_path]
#
# This script creates isolated git worktrees for parallel Claude Code workers.
# Each worktree is a separate working directory with its own HEAD.

set -e

NUM_WORKERS=${1:-3}
BASE_PATH=${2:-"../worktrees"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(git -C "$SKILL_DIR" rev-parse --show-toplevel)"

# Resolve base path relative to skill directory
if [[ "$BASE_PATH" != /* ]]; then
    BASE_PATH="$SKILL_DIR/$BASE_PATH"
fi
BASE_PATH="$(cd "$(dirname "$BASE_PATH")" 2>/dev/null && pwd)/$(basename "$BASE_PATH")"

echo "============================================"
echo "Project Manager Worktree Setup"
echo "============================================"
echo "Repository: $REPO_ROOT"
echo "Worktrees:  $BASE_PATH"
echo "Workers:    $NUM_WORKERS"
echo ""

# Create base directory
mkdir -p "$BASE_PATH"

# Check for existing worktrees
echo "Checking existing worktrees..."
EXISTING=$(git -C "$REPO_ROOT" worktree list --porcelain | grep "^worktree" | wc -l)
echo "Found $EXISTING existing worktrees"
echo ""

# Create worktrees
for i in $(seq 1 $NUM_WORKERS); do
    WORKTREE_PATH="$BASE_PATH/worktree-$i"
    BRANCH_NAME="worker-$i-base"

    if [ -d "$WORKTREE_PATH" ]; then
        echo "✓ Worktree $i already exists: $WORKTREE_PATH"

        # Verify it's a valid worktree
        if git -C "$WORKTREE_PATH" rev-parse --git-dir > /dev/null 2>&1; then
            echo "  Valid git worktree"
        else
            echo "  ⚠ Invalid worktree, recreating..."
            rm -rf "$WORKTREE_PATH"
            git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" HEAD
        fi
    else
        echo "Creating worktree $i: $WORKTREE_PATH"

        # Check if branch already exists
        if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
            echo "  Branch $BRANCH_NAME exists, using it"
            git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
        else
            echo "  Creating new branch $BRANCH_NAME"
            git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" HEAD
        fi

        echo "  ✓ Created"
    fi
done

echo ""
echo "============================================"
echo "Worktree Summary"
echo "============================================"
git -C "$REPO_ROOT" worktree list

echo ""
echo "Setup complete!"
echo ""
echo "Usage tips:"
echo "  - Each worker operates in its own worktree"
echo "  - Workers create feature branches from the base branch"
echo "  - Completed work is merged back to main"
echo "  - To remove a worktree: git worktree remove <path>"
echo "  - To prune stale worktrees: git worktree prune"
