# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses calendar versioning in the format `YYYY.MM.patch`.

## [Unreleased]

### Fixed
- Open the existing Unit_1 cron-wrapper lock read-only for Linux exclusive flock, avoiding unnecessary write permission while preserving the lock inode, contents and busy-lock protection.
- Pin Unit_1 configuration permissions to the reviewed production backup (`USB.ini` 0644, `legacy.ini` 0664) during readiness, publication and recovery, rather than rejecting the existing legacy configuration's group-write permission.
- Accept fuser's resolved serial-device label as well as the requested by-id alias during Unit_1 ownership checks, while rejecting diagnostics, unknown labels and invalid PID output.
- All plot families show actual generation timestamps in UTC; day/week/month muon-flux axes use the configured observatory location instead of a hard-coded station. Missing minute/five-minute observations now remain `nan` through plotting and period aggregation, while observed zero counts are retained. Frequency histograms exclude missing minutes; entirely unobserved days render explicit empty plots. Existing products require reprocessing, not just replotting.
- Pass configured detector labels to the installer's service preflight so explicitly authorised named installations can proceed. Regression tests execute the actual installer preflight without package, file or live-service changes.

### Added
- Fixed Unit_1 attended collection-trial runner with check-only default, pinned staging/preflight verification, device-owner and collection-advancement checks, explicit trial/recovery gating, a narrowly scoped daily-processing hold, config-only deployment and journaled return to single-mode. No boot enablement, archive merging or processing-script deployment. Disposable-host fault tests do not substitute for pending native Pi readiness and execution approval.
- Separate fixed-batch `AdoptUnit1Archive.py`: read-only manifest generation by default; explicit exact-manifest-hash approval and backup/restore/stopped-writer confirmations for Linux-only copy adoption or guarded quarantine rollback. Pins October 10-20 Unit_1 candidates and the reviewed October 13 exception, stages before no-clobber promotion, journals/resumes partial runs and preserves sources and pre-existing no-ops. Live Linux durability/locking and production adoption acceptance remain pending.
- Read-only `PreviewArchiveMigration.py` for the explicit confirmed production-to-Unit_1 mapping: full completed-file validation, timestamp ordering/overlap checks, proposed destinations and conflicts, separate rejected diagnostics, source hashes and provisional active UTC-day files. No apply mode or archive/configuration/service changes.
- Full-installer mock rehearsal covering opt-in activation/reversal, rendered services, managed-cron preservation/idempotency, staged web files, raw-file preservation and failure propagation without changing host services, packages, cron or web files.
- Opt-in named service installation: `install/install.sh --activate-services` validates named configuration and transitions collector units without overlapping old and new instances. Ordinary installation refuses named-mode activation; switching back from active/enabled named collectors also requires the flag. Historical archive adoption and live RPi acceptance remain pending.
- Phase 2a named plot/web pilot: all six plot families use isolated named inputs, latest images and archives. `ProcessDetectors.py` processes selected/all configured units independently, downloads shared site inputs once, and publishes date-labelled per-unit pages and status snapshots locally or to an explicit web root without replacing the legacy site. Per-unit pipeline locks, stale-output checks, image/status validation and separate log rotation accompany rendering/publication regressions. Live RPi acceptance and historical adoption remain deferred.
- Phase 2a explicit offline processing pilot: `--detector LABEL` on daily, period and historical reprocessing; isolated named products/summaries/temporary files and processing locks; detector-specific historical settings; selected-archive dry runs and three-detector isolation tests.
- Readable NMDB attribution, station and request comments plus a CSV column header in new neutron downloads; readers retain headerless-file compatibility.
- Optional `AddRawHeaders.py --remove-metadata` preview/apply cleanup of obsolete raw JSON comments, preserving event bytes and byte-exact backups while collectors are stopped.
- Optional Open-Meteo hourly modelled 2 m outdoor temperature overlays on all three CPM plots, using the existing observatory coordinates and an opt-in `[weather]` section in `config/user.ini`, UTC daily downloads and historical-forecast retrieval for older dates. Weather/source attribution is retained in data, images and the web page; day/week/month images also carry a short NMDB/Oulu credit alongside the existing full web acknowledgements.
- Phase 2a collection-pilot foundation (not yet a production multi-detector pipeline):
  - Validated `[detectors]` mappings with case-preserving labels, mandatory stable by-id paths and per-unit USB identity, duplicate device/alias checks, and atomic `ConfigureUSB.py --register` updates.
  - Explicit `GetDataRaw.py --detector LABEL`, isolated raw/rejected/status output and labelled logs, plus a `PicoMuon@.service` template with separate log paths (installed but enabled only by explicit opt-in).
  - Independent `[legacy:LABEL]` fallback settings with no shared-default inheritance; stable labels are retained in raw paths.
  - Concurrent simulated collector tests, independent reconnect/UTC rollover, identity mismatch and processing safety checks; POSIX pseudo-terminal exclusive-access test for the RPi.
- Backward-compatible 8/12-field detector capture: append legacy settings from `config/legacy.ini` only when absent, preserve detector-reported settings, and reject malformed suffixes.
- Installer provisioning/merging of legacy and observation configuration templates.
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
- Correct daily missing-event QC to compare independent T/B/C counters within each run segment; retain genuine large positive gaps. Sum the shared elapsed clock once across mixed event types, clear all baselines at reset/name/gap boundaries, and split exposure across UTC hours without changing event counts or CSV schemas. Regenerate derived daily files to correct older QC values; raw data and collectors are unchanged.
- Group temporary CPM/ADC/frequency plots in `temp/yesterday/` and day/week/month plots in `temp/periods/`. Plotting creates the folders automatically; publishing uses both groups while preserving existing flat web image URLs and ignoring obsolete flat temporary PNGs.
- Raw collectors no longer emit JSON metadata comments or embed observation details. ADC/CPM/day/hour/all period products now include detector name and four settings as CSV columns; day/period and hourly products include `neutrons,station`, retaining hourly pressure.
- Per-bin differing metadata fields are `mixed`, without splitting or changing counts. At the user's explicit request, missing historical settings are filled from current legacy configuration with an assumption logged. Recorded settings take precedence.
- Daily summaries no longer write JSON comments; legacy processing entry points use the shared writers. Day/week/month plots select the neutron column for either historical or new layouts.
- USB identity failures now prevent opening the serial port, including in single-detector mode; collectors and detector probing use exclusive serial access.
- Installer and legacy processors continue to refuse named multi-detector mode. Modern daily/period processors and reprocessing require explicit detector selection; `processData.sh` and `plots.sh` now dispatch named configurations to the opt-in pipeline. Named reprocessing supports `--plot` without publication; insufficient period history removes stale named target-date products. Day/week/month charts explicitly label unavailable neutron data or absent muon events rather than displaying fallback means.
- Standardise runtime logs as UTC timestamp, aligned process name and message. Shared command logging formats external diagnostics without double-prefixing existing entries, preserves exit codes and prefixes multiline Python messages and tracebacks.
- Daily processing, reprocessing and standalone plotting share gnuplot logging and input checks. Missing period products are skipped, real plot failures count towards the final failure status, and plots use the requested UTC target date.
- Raw collectors write one column-header line to new or empty event files; current and legacy raw readers support both headered and headerless files without changing event counts or column order.
- Correct daily web publishing to copy generated PNGs from `temp/`, not stale assets in `WWW/temp/`. Log source, destination and file count, fail explicitly when no PNGs exist, and capture pipeline/publishing command errors in `log-error.txt`. Published images have web-readable permissions.
- `scripts/ProcessDaily.py` and `scripts/ProcessPeriod.py` support `--date` as an alias for `--target-date`.
- `scripts/picomuon_common.py` resolves neutron files from both `data/neutrons/` and `data/NMDB/neutrons/`.
- `scripts/processData.sh` and `scripts/reprocessData.sh` avoid unnecessary `su` invocations when executed by the file owner, eliminating interactive password prompts.
- `scripts/processData.sh` verifies web directory write permissions before publishing plot assets, avoiding permission errors when invoked manually as a non-root user.
- Gnuplot scripts (`PlotDataDayACM0.gp`, `PlotDataWeekACM0.gp`, `PlotDataMonthACM0.gp`) guard against missing neutron stats, avoiding undefined variable runtime errors when neutron flux data is unavailable.
- Superseded: the initial `scripts/ProcessDaily.py` missing-event jump cap masked a shared-counter assumption; the corrected per-type/segment accounting above replaces that cap.
- `install/install.sh` automatically migrates from `PicoMuonACM0.service` to `PicoMuon.service`, initializes `config/USB.ini`, and creates status and rejected data directories.
- Logging output from `processData.sh`, `runCronJob.sh`, and `GetDataNeutron.py` aligned to the columnar format.
- Remove legacy `processCPM.sh`, `processADC.sh`, and `processData.sh` cron entries when installing the managed schedule, avoiding duplicate processing.
- Corrected systemd path quoting and validate the rendered collector unit before installation.
- Daily processing now runs as a single locked pipeline at 01:15 local time; until Phase 2 replaces the legacy processing implementation, runtimes can remain long.
- Updated the installation instructions for non-`pi` users.
