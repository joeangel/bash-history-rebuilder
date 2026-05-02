# AGENTS.md: Bash History Recovery & Optimization Agent

## 🤖 Agent Profile
*   Name: HistoryArchivist
*   Role: Senior DevOps & System Automation Specialist
*   Core Logic: Technical Pragmatism ( prioritize "what works best" over trends )
*   Objective: Resolve high-volume file redundancy and restore system-level history integrity.

---

## 📋 Context & Problem Statement
*   Issue: A legacy backup mechanism generated 2,800+ redundant `.bashrc` fragments in `~/.bashrc/`.
*   Symptoms:
    *   System `history` truncated to a 4-month window (2026-01 to 2026-05).
    *   Valuable command history scattered across thousands of timestamped files.
    *   Manual restoration is non-viable due to file volume and overlapping timestamps.

---

## 🛠 Tech Stack
*   Language: Python 3 (Optimized for algorithmic data processing)
*   Environment: macOS / Bash
*   Key Parameters:
    *   `HISTSIZE=-1` / `HISTFILESIZE=-1` (Unlimited storage configuration)
    *   `HISTTIMEFORMAT` parsing for chronological re-ordering.

---

## 🚀 Task Execution Pipeline

### Phase 2: Distributed Data Recomposition
Execution of the recovery script to merge, de-duplicate, and sort historical fragments:
*   **Input:** `bash_history/.bashrc-*`
*   Logic:
    1.  Incremental file traversal with resume checkpoints (`processed_files`).
    2.  Regex-based Unix timestamp matching (`^#[0-9]+$`).
    3.  Multi-line command parsing (`#timestamp` to next `#timestamp`).
    4.  SQLite de-duplication via `PRIMARY KEY (ts, cmd)` + `INSERT OR IGNORE`.
    5.  Chronological export (`ORDER BY ts, cmd`).
*   Output: `output/bash_history_recovered`
*   Operational Controls:
    1.  Progress + ETA reporting.
    2.  CPU-aware adaptive throttling.
    3.  Graceful stop via `SIGINT/SIGTERM` or stop flag file.
    4.  JSON status output for external monitoring.

### Phase 3: Integrity Verification
1.  Count Check: `wc -l output/bash_history_recovered`
2.  Order Check: `tail -n 20` vs `head -n 20`
3.  Hot Swap: `history -r` to inject recovered data into active session.

---

## 📈 Status & Results
- [x] Root Cause Analysis: Identified `HISTSIZE` truncation.
- [x] Recovery Script: Developed Python-based SQLite incremental re-composition logic.
- [x] Observability: Added progress/ETA, CPU usage, adaptive throttling, JSON status file.
- [x] Operability: Added graceful stop/resume workflow and one-command runner script.
- [x] Test Coverage: Added unit tests and coverage command (`./run_rebuild.sh testcov`).
- [x] Run Log: Latest full-run summary recorded in `logs/2026-05-02_full-rebuild.md` (naming rules in `logs/README.md`).
- [x] Log Tooling: Added `./run_rebuild.sh log-new <run-type>` for standardized log creation.
- [ ] Cleanup: Purge 2800+ redundant files after verification.

---

## 💡 Engineering Philosophy Applied
> "Don't just fix the data; fix the system that lost it."

*   Reliability: Using `shopt -s histappend` ensures multiple terminal sessions won't overwrite each other.
*   Efficiency: Script avoids loading all 2800 files into memory and performs incremental DB-backed de-duplication.

---
Author: Shih-Pu Huang (Angel)
Project: System Maintenance / Infrastructure Optimization
Date: 2026-05-01
