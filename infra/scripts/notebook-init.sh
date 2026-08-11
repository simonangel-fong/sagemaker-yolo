#!/bin/bash
# Clone the project repo into a JupyterLab space on app start.
# Runs on EVERY app start

set -eux

# github repo rule
REPO_URL="${repo_url}"
# clone dir
REPO_DIR="/home/sagemaker-user/$(basename "$REPO_URL" .git)"

if [ -d "$REPO_DIR/.git" ]; then
    echo "repo already present at $REPO_DIR, skipping clone"
else
    git clone "$REPO_URL" "$REPO_DIR"
    echo "cloned $REPO_URL -> $REPO_DIR"
fi
