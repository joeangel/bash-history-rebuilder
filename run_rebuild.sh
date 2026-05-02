#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT_DIR="${INPUT_DIR:-bash_history}"
GLOB_PATTERN="${GLOB_PATTERN:-.bashrc-*}"
DB_PATH="${DB_PATH:-output/rebuild_history.sqlite3}"
OUTPUT_FILE="${OUTPUT_FILE:-output/bash_history_recovered}"
STATUS_FILE="${STATUS_FILE:-output/rebuild_status.json}"
STOP_FLAG_FILE="${STOP_FLAG_FILE:-output/STOP_REBUILD}"

BATCH_SIZE="${BATCH_SIZE:-5000}"
REPORT_EVERY="${REPORT_EVERY:-2}"
STATUS_EVERY="${STATUS_EVERY:-2}"
THROTTLE_MS="${THROTTLE_MS:-5}"
TARGET_CPU="${TARGET_CPU:-65}"

usage() {
  cat <<'EOF'
Usage:
  ./run_rebuild.sh start   # start or resume rebuild
  ./run_rebuild.sh reset   # rebuild from scratch
  ./run_rebuild.sh stop    # graceful stop via stop flag
  ./run_rebuild.sh status  # print current JSON status
  ./run_rebuild.sh testcov # run unit tests with coverage report
  ./run_rebuild.sh validate # validate source/db/output consistency
  ./run_rebuild.sh log-new <run-type> # create logs/YYYY-MM-DD_<run-type>.md
EOF
}

run_rebuild() {
  local reset_flag="${1:-}"
  python3 main.py \
    --input-dir "$INPUT_DIR" \
    --glob "$GLOB_PATTERN" \
    --db-path "$DB_PATH" \
    --output "$OUTPUT_FILE" \
    --batch-size "$BATCH_SIZE" \
    --report-every "$REPORT_EVERY" \
    --status-file "$STATUS_FILE" \
    --status-every "$STATUS_EVERY" \
    --auto-throttle \
    --target-cpu "$TARGET_CPU" \
    --throttle-ms "$THROTTLE_MS" \
    --stop-flag-file "$STOP_FLAG_FILE" \
    $reset_flag
}

cmd="${1:-start}"
case "$cmd" in
  start)
    rm -f "$STOP_FLAG_FILE"
    run_rebuild
    ;;
  reset)
    rm -f "$STOP_FLAG_FILE"
    run_rebuild --reset-db
    ;;
  stop)
    mkdir -p "$(dirname "$STOP_FLAG_FILE")"
    touch "$STOP_FLAG_FILE"
    echo "Stop requested: $STOP_FLAG_FILE"
    ;;
  status)
    if [[ -f "$STATUS_FILE" ]]; then
      cat "$STATUS_FILE"
    else
      echo "Status file not found: $STATUS_FILE"
      exit 1
    fi
    ;;
  testcov)
    python3 -m pytest --cov=src --cov-report=term-missing -q
    ;;
  validate)
    python3 -m src.validate_rebuild \
      --input-dir "$INPUT_DIR" \
      --glob "$GLOB_PATTERN" \
      --db-path "$DB_PATH" \
      --output "$OUTPUT_FILE"
    ;;
  log-new)
    run_type="${2:-}"
    if [[ -z "$run_type" ]]; then
      echo "Missing <run-type>. Example: ./run_rebuild.sh log-new full-rebuild"
      exit 1
    fi
    python3 -m src.log_utils "$run_type"
    ;;
  *)
    usage
    exit 1
    ;;
esac
