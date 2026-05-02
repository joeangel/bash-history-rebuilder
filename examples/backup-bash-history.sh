#!/usr/bin/env bash
set -euo pipefail

# Example script for macOS (bash) environment.
# Adjust USER_HOME to your actual home path, e.g. /Users/alice
USER_HOME="/Users/YOUR_USER_NAME"

TARGET_FILE_PATH="$USER_HOME/.bash_history"
BACKUP_DIR="$USER_HOME/bash_history"
LOG_SUCCESS_PATH="$USER_HOME/logs/backup-bash-history.log"
LOG_FAILURE_PATH="$USER_HOME/logs/backup-bash-history-error.log"

mkdir -p "$BACKUP_DIR" "$(dirname "$LOG_SUCCESS_PATH")"

NOW="$(date +%FT%T%z)"
BACKUP_FILE_PATH="$BACKUP_DIR/.bashrc-$NOW"

if cp "$TARGET_FILE_PATH" "$BACKUP_FILE_PATH" >>"$LOG_SUCCESS_PATH" 2>>"$LOG_FAILURE_PATH"; then
  echo "$(date +%FT%T%z) success copied: $BACKUP_FILE_PATH" >>"$LOG_SUCCESS_PATH"
else
  echo "$(date +%FT%T%z) error occurs during copy" >>"$LOG_FAILURE_PATH"
  exit 1
fi
