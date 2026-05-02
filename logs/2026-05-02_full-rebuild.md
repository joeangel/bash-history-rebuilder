Rebuild Run Log
Date: 2026-05-02
Project: /Users/apple/git/python/rebuild_history

Summary
- Full rebuild completed successfully with SQLite incremental pipeline.
- Status: completed
- Input files processed: 2824 / 2824
- Total input bytes: 3,755,476,183 (~3.5GB)
- Raw parsed entries: 88,654,781
- New dedup entries: 46,557
- Output entries: 46,557
- Elapsed time: 470.57 seconds (~7m 51s)
- Average throughput: 7.6109 MB/s

Outputs
- output/bash_history_recovered
  - Size: 1.9MB
  - Line count: 93,549
- output/rebuild_history.sqlite3
  - Size: 4.8MB
- output/rebuild_status.json
  - Final state: completed

Verification Notes
- Head/tail inspection is readable and ordered.
- First lines include:
  - #123
  - (empty command line)
  - #1698998245
  - ls
- Last lines include:
  - #1776241841
  - rm client7-joe.ovpn
  - #1776241842
  - ll
  - #1777514370
  - whois [REDACTED_TARGET]
- There is at least one empty-command record (e.g., timestamp #123). This is preserved from source data by current parser policy.

Current AGENTS.md Progress Alignment
- Completed:
  - Root cause analysis
  - Recovery script (SQLite incremental)
  - Observability (progress/ETA/CPU/status JSON)
  - Operability (graceful stop/resume + runner script)
  - Test coverage workflow
- Remaining TODO:
  - Cleanup: purge 2800+ redundant fragment files after verification

Test/Coverage Snapshot
- Command: ./run_rebuild.sh testcov
- Result: 9 passed
- Coverage:
  - src/history_rebuilder.py: 89%
  - Total: 89%

Cleanup Preconditions (not executed yet)
1. Keep:
   - output/bash_history_recovered
   - output/rebuild_history.sqlite3
2. Target for deletion (if approved):
   - bash_history/ (~3.5GB)
