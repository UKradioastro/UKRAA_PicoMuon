# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses calendar versioning in the format `YYYY.MM.patch`.

## [Unreleased]

### Added
- `scripts/AddRawHeaders.py`: preview and safely add column headers to historic and current raw event files while collectors are stopped, with byte-exact backups and atomic per-file replacement.
- Phase 2 high-speed processing engine replacing the 9+ hour multi-pass bubble-sort:
  - `scripts/ProcessDaily.py`: Single-pass streaming daily parser that simultaneously computes 1,440-minute CPM, 288 5-minute Day records merged with NMDB neutron flux, 1,024-bin ADC energy spectra, 24 hourly L2 summaries with missing-event tracking, and daily quality metrics written to `data/daily/summary.csv`.
  - `scripts/ProcessPeriod.py`: Fast multi-day period aggregator producing week (7 days, 10-min bins, 1,008 rows), month (31 days, 1-hour bins, 744 rows), and 3-month (90 days, 1-day bins, 90 rows) derived products directly from 5-minute daily data in seconds instead of reading raw files. Enforces 90% completeness rule.
  - `scripts/reprocessData.sh`: Command-line tool supporting `--from`, `--to`, `--dry-run`, and optional `--plot` for safe, reproducible historical back-fills.
  - Automated test suite in `tests/test_phase2.py` verifying full parser output parity and period aggregations against actual hardware datasets.
- Phase 1 collector modernization and stable USB serial configuration:
  - Aligned columnar logging standard (`YYYY-MM-DD HH:MM:SS UTC : %-26s : message`) via `scripts/logging.sh` and `scripts/picomuon_common.py` (`log_message`, `log_error`, uncaught exception hook).
  - Hardened continuous serial collector `scripts/GetDataRaw.py` with rollover at UTC midnight, line-buffering and immediate flushing, backoff reconnect loop on `SerialException`, 8/9-field payload validation, malformed row archiving under `data/raw/rejected/`, and atomic status monitoring output to `data/status/current.json`.
  - Interactive USB configuration utility `scripts/ConfigureUSB.py` with automatic `/dev/serial/by-id/` discovery, detector probing, and label sanitization.
  - Template configuration utility `scripts/MergeConfig.py` and template `install/USB.ini.example`.
  - Service unit `install/PicoMuon.service` replacing legacy `PicoMuonACM0.service`.
- Phase 0 runtime foundations: validated version/date helpers, owner-aware service and installer setup, managed cron scheduling, and separate timestamped error logging.
- Dynamic installation-root lookup for the legacy processing and plot scripts.

### Changed
- Raw collectors write one column-header line to new or empty event files; current and legacy raw readers support both headered and headerless files without changing event counts or column order.
- Correct daily web publishing to copy generated PNGs from `temp/`, not stale assets in `WWW/temp/`. Log source, destination and file count, fail explicitly when no PNGs exist, and capture pipeline/publishing command errors in `log-error.txt`. Published images have web-readable permissions.
- `scripts/ProcessDaily.py` and `scripts/ProcessPeriod.py` support `--date` as an alias for `--target-date`.
- `scripts/picomuon_common.py` resolves neutron files from both `data/neutrons/` and `data/NMDB/neutrons/`.
- `scripts/processData.sh` and `scripts/reprocessData.sh` avoid unnecessary `su` invocations when executed by the file owner, eliminating interactive password prompts.
- `scripts/processData.sh` verifies web directory write permissions before publishing plot assets, avoiding permission errors when invoked manually as a non-root user.
- Gnuplot scripts (`PlotDataDayACM0.gp`, `PlotDataWeekACM0.gp`, `PlotDataMonthACM0.gp`) guard against missing neutron stats, avoiding undefined variable runtime errors when neutron flux data is unavailable.
- `scripts/ProcessDaily.py` missing-event counter bounds event jumps to avoid spurious large counters during reboot or multi-detector switching.
- `install/install.sh` automatically migrates from `PicoMuonACM0.service` to `PicoMuon.service`, initializes `config/USB.ini`, and creates status and rejected data directories.
- Logging output from `processData.sh`, `runCronJob.sh`, and `GetDataNeutron.py` aligned to the columnar format.
- Remove legacy `processCPM.sh`, `processADC.sh`, and `processData.sh` cron entries when installing the managed schedule, avoiding duplicate processing.
- Corrected systemd path quoting and validate the rendered collector unit before installation.
- Daily processing now runs as a single locked pipeline at 01:15 local time; until Phase 2 replaces the legacy processing implementation, runtimes can remain long.
- Updated the installation instructions for non-`pi` users.
