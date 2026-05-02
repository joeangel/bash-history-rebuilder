# bash-history-rebuilder

This project rebuilds bash history from many fragmented backup files (for example, files like `.bashrc-2024-09-01T12:10:00+0800`).

Target environment: macOS with bash shell scripts.

## Setup

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pytest-cov
```

## Source Directory Origin (`~/bash_history/`)

In this project, `~/bash_history/` is the upstream source directory that stores periodic copies of `~/.bash_history`.

Recommended `.bashrc` history settings:

```bash
export HISTTIMEFORMAT='<%F %T %z> : '
export HISTSIZE=
export HISTFILESIZE=
export HISTCONTROL=ignoredups:ignorespace
shopt -s histappend
PROMPT_COMMAND="history -a"
```

Notes:
- `HISTTIMEFORMAT` adds a timestamp format that helps chronological recovery.
- `HISTCONTROL=ignoredups:ignorespace` avoids storing immediate duplicates and commands prefixed with a space.
- `histappend` and `history -a` reduce overwrite risk across multiple terminal sessions.

Current setup example:

1. `crontab` entry (runs at minute 10 every hour, absolute path required):
```cron
10 * * * * /Users/YOUR_USER_NAME/scripts/backup-bash-history.sh
```
2. Backup script copies `~/.bash_history` into timestamped fragments like:
```text
~/bash_history/.bashrc-2026-05-02T16:10:00+0800
```

Reference files in this repo:
- `examples/crontab.example`
- `examples/backup-bash-history.sh`

This rebuild project then syncs those fragments into `./bash_history/` and processes them.

If your source path is different, replace the `rsync` source path accordingly.

## Quick Start (recommended)

```bash
./run_rebuild.sh start
```

## Recommended Workflow

### First Run (initialize DB and first output)

1. Put source fragments into `bash_history/` (example):
```bash
rsync -av --ignore-existing ~/bash_history/ ./bash_history/
```
2. Run incremental rebuild (creates DB if not exists):
```bash
./run_rebuild.sh start
```
3. Validate and snapshot:
```bash
./run_rebuild.sh validate
./run_rebuild.sh snapshot first-run
```
4. Optional: sync snapshots to external backup location:
```bash
rsync -av ./snapshots/ ../rebuild_history-snapshots/
```
5. Optional: reclaim source space (DB/output kept):
```bash
./run_rebuild.sh cleanup-source
```

### Second Run and Later (incremental only)

1. Sync only new fragments:
```bash
rsync -av --ignore-existing ~/bash_history/ ./bash_history/
```
2. Continue rebuild without resetting DB:
```bash
./run_rebuild.sh start
```
3. Validate and snapshot:
```bash
./run_rebuild.sh validate
./run_rebuild.sh snapshot post-run
```
4. Optional: sync snapshots to external backup location:
```bash
rsync -av ./snapshots/ ../rebuild_history-snapshots/
```
5. Optional: clean source fragments:
```bash
./run_rebuild.sh cleanup-source
```

### When to use reset

Use `./run_rebuild.sh reset` only when you intentionally want a full rebuild from scratch and accept DB reset.

Useful commands:

```bash
./run_rebuild.sh status
./run_rebuild.sh stop
./run_rebuild.sh reset
./run_rebuild.sh cleanup-source
./run_rebuild.sh testcov
./run_rebuild.sh validate
./run_rebuild.sh snapshot post-run
./run_rebuild.sh log-new cleanup
cat logs/2026-05-02_full-rebuild.md
```

You can override defaults via environment variables (example):

```bash
TARGET_CPU=60 THROTTLE_MS=8 ./run_rebuild.sh start
```

Available environment variables for `run_rebuild.sh`:
- `INPUT_DIR` (default: `bash_history`)
- `GLOB_PATTERN` (default: `.bashrc-*`)
- `DB_PATH` (default: `output/rebuild_history.sqlite3`)
- `OUTPUT_FILE` (default: `output/bash_history_recovered`)
- `STATUS_FILE` (default: `output/rebuild_status.json`)
- `STOP_FLAG_FILE` (default: `output/STOP_REBUILD`)
- `BATCH_SIZE` (default: `5000`)
- `REPORT_EVERY` (default: `2`)
- `STATUS_EVERY` (default: `2`)
- `THROTTLE_MS` (default: `5`)
- `TARGET_CPU` (default: `65`)

## Direct Run (SQLite incremental mode)

```bash
python3 main.py \
  --input-dir bash_history \
  --glob '.bashrc-*' \
  --db-path output/rebuild_history.sqlite3 \
  --batch-size 5000 \
  --report-every 2 \
  --auto-throttle \
  --target-cpu 65 \
  --throttle-ms 5 \
  --stop-flag-file output/STOP_REBUILD \
  --status-file output/rebuild_status.json \
  --status-every 2 \
  --output output/bash_history_recovered
```

If you want to rebuild from scratch:

```bash
python3 main.py --reset-db
```

Important:
- `./run_rebuild.sh reset` clears and rebuilds the SQLite DB.
- `./run_rebuild.sh cleanup-source` deletes only files under `bash_history/` and keeps DB/output files.
- `./run_rebuild.sh snapshot <label>` creates a timestamped backup under `snapshots/`.

Force stop gracefully while it is running:

```bash
touch output/STOP_REBUILD
```

Then resume with the same command (it continues from `processed_files`).

## Verify

```bash
wc -l output/bash_history_recovered
head -n 10 output/bash_history_recovered
tail -n 10 output/bash_history_recovered
./run_rebuild.sh validate
cat logs/2026-05-02_full-rebuild.md
```

## Run Log

- Latest execution and verification summary is stored at `logs/2026-05-02_full-rebuild.md`.
- Log naming convention is documented in `logs/README.md`.
- You can create a new log template with `./run_rebuild.sh log-new <run-type>`.

## Notes

- Dedupe key is `(timestamp, command)` via SQLite `PRIMARY KEY`.
- Parser supports multi-line commands: from one `#timestamp` until the next `#timestamp`.
- Resume is supported by `processed_files` metadata (path + size + mtime).
- Supports graceful stop via `SIGINT`/`SIGTERM` or stop flag file.
- Progress includes CPU usage and adaptive throttle values.
- Writes JSON monitoring status to `output/rebuild_status.json`.
- Output format follows bash history conventions:
  - `#<unix_timestamp>`
  - `<command>`
