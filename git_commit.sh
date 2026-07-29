#!/bin/bash

echo ""
echo "=================================="
echo " Stock Momentum Agent Git Commit"
echo "=================================="

# Ensure we're in a git repository
git rev-parse --is-inside-work-tree >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Not inside a Git repository."
    exit 1
fi

# Show status
echo ""
echo "Current Git status:"
git status

echo ""
read -p "Commit message: " MESSAGE

if [ -z "$MESSAGE" ]; then
    echo "Commit cancelled."
    exit 1
fi

echo ""
echo "Adding files..."

git add .

echo ""
echo "Committing..."

git commit -m "$MESSAGE"

echo ""
echo "Pushing..."

git push

echo ""
echo "Done."
