#!/bin/bash

# Script to set up a test scenario for the internships bot
# Resets the repo to an older state and saves current listings as previous_data.json
# Usage: ./setup_test_update.sh [number_of_commits_back]
#   e.g. ./setup_test_update.sh 3     # Go back 3 commits
#        ./setup_test_update.sh       # Default: go back 2 commits

# Configuration
REPO_DIR="Summer2026-Internships"
LISTINGS_PATH=".github/scripts/listings.json"
COMMITS_BACK=${1:-2}  # Use first argument if provided, otherwise default to 2

# Validate COMMITS_BACK is a positive number
if ! [[ "$COMMITS_BACK" =~ ^[0-9]+$ ]] || [ "$COMMITS_BACK" -lt 1 ]; then
    echo "Error: COMMITS_BACK must be a positive number"
    exit 1
fi

# Save current directory
ORIGINAL_DIR=$(pwd)

# Ensure we're in the correct directory
cd "$(dirname "$0")" || exit 1

# Save current HEAD for restoration later if needed
echo "Saving current HEAD reference..."
cd "$REPO_DIR" || exit 1
CURRENT_HEAD=$(git rev-parse HEAD)
echo "$CURRENT_HEAD" > ../current_head.txt

# Reset to older commit
echo "Resetting repository to $COMMITS_BACK commits back..."
git reset --hard "HEAD~$COMMITS_BACK"

# Copy the older version of listings to previous_data.json
echo "Copying older listings file to previous_data.json..."
cp "$LISTINGS_PATH" "../previous_data.json"

echo "Test scenario set up complete!"
echo "Previous HEAD was: $CURRENT_HEAD"
echo "Current HEAD is:  $(git rev-parse HEAD)"
echo ""
echo "To restore the repository to its original state:"
echo "  cd $REPO_DIR && git reset --hard \$(cat ../current_head.txt)"
echo ""
echo "The bot should now detect updates when it pulls from origin."

# Return to original directory
cd "$ORIGINAL_DIR" || exit 1