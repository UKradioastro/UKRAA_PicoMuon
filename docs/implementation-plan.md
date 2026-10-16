# UKRAA PicoMuon – Implementation Plan (v2026.11 onwards)

This plan modernises the PicoMuon suite using the structure and patterns that
already work in `UKRAA_PicoMagnetometer` (config `.ini` files, base-path
discovery, USB identity, updater, FTP upload, alerts, tests). It is based on a
review of the code running on the RPi (`examples/UKRAA_PicoMuon`).

---

## 1. What the review found

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| F1 | **The processing time comes from the algorithm, not the Pi.** Every time bin re-opens the raw file and `strptime`s every line. CPM = 1,440 full passes, Day = 288 passes, Week/Month/90-day do the same over merged files. | `ProcessDataCpmACM0.py`, `ProcessDataDayACM0.py`, `ProcessData90DaysACM0.py` | CPM takes about 20 minutes on the Pi (log 00:30→00:49). Cron jobs are spread from 00:30 to 09:30 to avoid overlap. |
| F2 | A single pass over the same day (21,177 events) takes **0.05 s** on a desktop PC, so it should take about 1 s on a Pi4. | Benchmark on `2026-10-09.txt` | About 1,000× faster. No pandas needed for the daily step. |
| F3 | **UTC/local-time mismatch.** Raw files are split on the UTC date, but cron runs on local time. At 00:30 BST it is 23:30 UTC, so "yesterday's" file is still being written. | `GetDataRawACM0.py` uses `timezone.utc`, and the processors use `now()` | Up to 1 hour of data per day may be missing from processed output during British Summer Time. |
| F4 | The raw line has **9 fields**, not 8: `RPiTimestamp,Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName` (confirmed). | Raw files | Documentation and parsers need to agree. |
| F5 | `Elapsed_ms` is a signed 32-bit counter and **wraps every ~24.8 days**. It went negative on 2026-10-10 (`-2147288954`). | Raw file 2026-10-10 | Any elapsed-time maths must "unwrap" it. See section 2a. |
| F6 | Dead time is logged but not used. Measured over 127 days, it is **0.125–0.148 % of live time** (about 5.5 ms per event). | Raw files | Negligible, as you thought. See section 2a. |
| F7 | `GetDataRawACM0.py` opens the output file once per line and never closes it, and has no reconnect handling. | Collector | Risk of file-handle leaks or lost data if USB drops. Relies on systemd restart. |
| F8 | Hard-coded `/home/pi`, `su pi`, `/dev/ttyACM0`, and `ACM0` in every path and file name. | All scripts, service, cron | Blocks items 5, 6, and 7. |
| F9 | `install.sh` appends to root's crontab on every run, and `update.sh` runs `crontab -r` (wipes **all** root cron jobs). | `install/`, `update/` | Duplicate or lost cron entries. |
| F10 | `log-error.txt` is filled with gnuplot `No entry for terminal type "unknown"` noise. This comes from the crontab running `su pi -c "gnuplot …"` directly. The Magnetometer suite does not get this noise: its cron runs `runCronJob.sh` → `processData.sh`, and the shell script does the `su "$FILE_OWNER"`. | `logfiles/log-error.txt`, Magnetometer `runCronJob.sh` | Real errors get lost (item 12). Fix: adopt the Magnetometer pattern. |
| F11 | The pressure coefficient is already fitted in gnuplot (`fit … via a0`, no intercept). It is about **−0.188 %/hPa**, which is physically sensible. It is fitted on *daily* values. | `PlotData90DaysPcoeffACM0.gp`, `data/environment/coefficient/*.txt` | Good starting point. Hourly fitting gives far more leverage. |
| F12 | Installer installs MariaDB/PHP that the static page does not use. | `install.sh` | Unnecessary attack surface and SD-card wear. |

---

## 2. Target layout (mirrors PicoMagnetometer)

```text
UKRAA_PicoMuon/
├── VERSION                     # 2026.11.0  (CalVer YYYY.MM.patch – already started)
├── CHANGELOG.md                # Keep a Changelog format (already started)
├── README.md  LICENSE
├── install/
│   ├── install.sh              # user-agnostic, idempotent, templated
│   ├── PicoMuon.service        # @PICOMUON_USER@ / @PICOMUON_BASE_PATH@
│   ├── crontabPicoMuon.cron    # templated; replaces only the PicoMuon block
│   ├── USB.ini.example         # serial port; [detectors] for multi-detector mode
│   ├── station.ini.example     # site name, latitude, longitude, altitude
│   ├── plot.ini.example
│   ├── nmdb.ini.example
│   ├── coefficients.ini.example
│   ├── alerts.ini.example
│   └── remote-upload.ini.example
├── scripts/
│   ├── picomuon_common.py      # base path, config, UTC dates, logging, raw parser
│   ├── picomuon-env.sh  logging.sh  runCronJob.sh (flock + TERM=dumb)
│   ├── GetDataRaw.py           # collector (service)
│   ├── ConfigureUSB.py         # pick detector by /dev/serial/by-id + detector name
│   ├── MergeConfig.py          # add new ini keys on update, never overwrite user values
│   ├── ProcessDaily.py         # ONE pass: raw → minute/5-min/hour/ADC products
│   ├── ProcessRolling.py       # last 24 h, every 5 minutes
│   ├── ProcessPeriod.py        # week / month / 3month / 6month / year from hourly files
│   ├── GetDataNMDB.py  nest.py # station(s) from nmdb.ini
│   ├── GetDataUpperAir.py      # Open-Meteo pressure-level temperatures → T_eff
│   ├── ComputeCoefficients.py  # β (pressure), α (temperature)
│   ├── ApplyCorrections.py     # P and P+T corrected series
│   ├── EvaluateAlerts.py       # high/low rate, no-data, heartbeat email
│   ├── uploadRemote.sh         # plain FTP (Python ftplib inside, as in the Magnetometer suite)
│   ├── publishWeb.sh           # copy to /var/www/html + plot-options.json
│   ├── processData.sh  processRollingData.sh  reprocessData.sh  manageLogfiles.sh
│   ├── updatePicoMuon.sh       # GitHub release updater (item 8)
│   ├── MigrateLegacyInstall.py # /home/pi + ACM0 → new layout
│   └── Plot*.gp                # gnuplot kept; paths passed in with -e
├── analysis/                   # optional science tools (section 5)
│   ├── Harmonics.py  Forbush.py  SolarCycle.py
├── WWW/index.html              # reads status/plot-options.json to show/hide panels
├── tests/                      # pytest using real sample days
└── docs/
# created at install time, git-ignored:
config/  data/  plots/  logfiles/  temp/
```

### Data levels (the core of item 3)

| Level | Path | Content | Written by |
|-------|------|---------|------------|
| L0 raw | `data/raw/YYYY/YYYY-MM/YYYY-MM-DD.txt` | 9-field event rows preceded by a single column-header line (decision 1) | `GetDataRaw.py` |
| L1 minute | `data/minute/YYYY/…/YYYY-MM-DD.csv` | `utc,T,B,C,live_s,temp,pres,adc_mean` | `ProcessDaily.py` |
| L1 ADC | `data/adc/…` | ADC histogram for the day | `ProcessDaily.py` |
| L2 hour | `data/hour/…` | Hourly counts, P, T, NMDB, **P- and PT-corrected** % deviation | `ProcessDaily.py` + `ApplyCorrections.py` |
| Period | `data/period/<week|month|3month|6month|year>/…` | Built by concatenating L2 files (≤ 8,760 rows/year) | `ProcessPeriod.py` |

The raw file is read **once per day**. Everything longer than a day is built
from small hourly files, so a 1-year plot takes seconds, not hours.

**Library choice:** use pure Python (or NumPy) for the daily pass, since it has
no dependencies and is already fast. Use pandas and NumPy (installed with `apt`
as `python3-pandas`/`python3-numpy`, because Bookworm blocks system `pip`) for
period, coefficient, and FFT work. gnuplot stays as the plotting engine. Python
only writes the CSV files that gnuplot plots.

### 2a. Using `EventCount`, `Elapsed_ms` and `Dead_ms` (F5, F6)

**Unwrapping `Elapsed_ms` (F5).** The Pico keeps milliseconds since power-on in
a 32-bit counter. It is printed as a *signed* number, so after 2³¹ ms
(24.86 days) it jumps from +2147483647 to −2147483648. The values can't be
used directly, but the **difference between consecutive events** always can:

```python
delta = (elapsed - prev_elapsed) % 2**32      # handles the wrap automatically
```

The `% 2**32` absorbs the wrap, so it needs no special case. On 2026-10-09
(which contains a wrap) this gives 86,397 s for the day, as expected. Two
situations must be detected rather than unwrapped:

| Situation | How to recognise it | Action |
|---|---|---|
| Detector reboot or power cut | `EventCount` goes *down* (resets), or `delta` > 1 hour | Start a new "run segment". Don't compute a delta across it. |
| Lost lines (USB/serial drop) | `EventCount` jumps by more than 1 | Record `missing_events = jump − 1` in the minute file (QC). |

**Is dead time significant (F6)?** No, you are right. The measured dead
fraction is 0.13 % and it varies by only about ±0.01 % from day to day. A
constant 0.13 % scales every count equally, so it doesn't change any %
deviation plot. A ±0.01 % wobble is far below the Poisson noise (about 3.4 %
per hour, 0.7 % per day, and still 0.05 % for a year's diurnal analysis).
**Decision: no dead-time correction.** `Dead_ms` is still summed per day into
the QC file, because a sudden rise would show a noisy or faulty detector.

**Why use `Elapsed_ms` at all?** It shows exactly how much of each minute or
hour the detector was really counting. If the collector restarts or USB drops
for 3 minutes, that hour currently shows as a 5 % dip, which looks like a
Forbush decrease. With exposure known, the hour is either normalised
(counts ÷ exposure) or flagged incomplete and left out of fits and alerts.
That is the main benefit, rather than dead-time correction.

### 2b. Multi-detector layout (decision 2 – target for Phase 2a)

**Current implementation:** `ConfigureUSB.py` updates one `[usb]` selection
in `config/USB.ini`; running it twice replaces that selection, rather than
registering two detectors. A non-empty `label` directs the collector to
`data/raw/<label>/...`, but does not create a second collector. Existing raw
files are left where they are. The multi-detector behaviour below is a target,
not an available feature yet.

**Default (almost all users): one detector.** Use the same paths as the
PicoMagnetometer suite, with no detector level:
`data/raw/2026/2026-10/2026-10-09.txt`, `plots/day/…`, and so on.

**Optional multi-detector mode (Phase 2a).** It will be enabled by listing more than one
detector in `config/USB.ini`:

```ini
[detectors]
# label (your choice, max 16 chars, file-safe) = stable serial port. Only needed for 2+ detectors.
V56-123-456 = /dev/serial/by-id/usb-Raspberry_Pi_Pico_E6614103E7xxxxxx-if00
roof-east   = /dev/serial/by-id/usb-Raspberry_Pi_Pico_E6614864D3yyyyyy-if00
```

In this mode every data, plot, and log path gets a `<detector>` level, for
example `data/raw/V56-123-456/2026/…`. One templated systemd unit
(`PicoMuon@.service`) runs one collector per detector, and the processing
scripts loop over the configured labels.

**What `<detector>` should be.** It should be a **label the RPi owner chooses
once in `USB.ini`**, bound to the stable `/dev/serial/by-id` path. It must be
file-safe (`[A-Za-z0-9_-]`, maximum 16 characters). `ConfigureUSB.py` proposes
a default from the `DetectorName` it reads at setup time, with `/` replaced
by `-` (for example `V56-123-456`). After that, the label never changes
automatically. Reasons:
- **Not `ACM0`/`ACM1`:** Linux hands these out in plug-in order, so they can
  swap after a reboot and mix up two detectors' data. That is the problem
  behind items 6 and 7.
- **Not the live `DetectorName`:** users can rename their detector (up to 16
  characters, for example `orange`) by uploading an `.ini` file to it, and the
  new name takes effect after a reset. If the folder followed the name, a
  rename would split one detector's history across two folders, possibly in
  the middle of a day.
- **The by-id path** (from the Pico's USB serial number) identifies the
  physical unit. It only changes if the Pico board is replaced. Then the user
  edits one line in `USB.ini` (or re-runs `ConfigureUSB.py`) and keeps the
  same label, so the history continues.

**Handling a detector rename (or reset) mid-day.** `DetectorName` is treated
as **metadata, never as a key**:
- The collector keeps writing to the same daily file, because the file is
  chosen by port and label, not by name. It logs one info line, `detector
  name changed: 'V56-123-456' → 'orange'`, rather than warning on every line.
- The reset that applies the new name is handled by the section 2a logic. The
  `EventCount` drop starts a new run segment, and the missing seconds are
  recorded as reduced exposure for that minute or hour, so no fake dip
  appears.
- The parser takes the name as "everything after the 8th comma". A name
  containing a comma therefore can't break the field count.
- The daily summary records every name seen that day, and plots show the
  **current** name in the title. Anyone looking back can see when the rename
  happened.
- Cable-swap check: if a port suddenly reports a name that belongs to a
  *different* configured detector, that is a likely cable swap, so it is
  logged as an error.

**Migration:** single-detector users go from `data/raw/ACM0/…` to `data/raw/…`.
Your multi-detector Pis go from `data/raw/ACMn/…` to `data/raw/<label>/…`.
The migration script proposes each label from the most recent `DetectorName`
in that folder and asks you to confirm.

### 2c. Upper-air temperature from Open-Meteo (decision 5)

Checked on 2026-10-10:
- **Recent days:** the Open-Meteo forecast API returns hourly
  `temperature_<level>hPa` (1000 → 30 hPa) and `geopotential_height_<level>hPa`
  for the UK. `past_days=2` gives yesterday's values.
- **Back-filling history:** the Historical Forecast API
  (`historical-forecast-api.open-meteo.com`) covers about 2022 onwards. That
  covers all your existing data. A 2021 request came back empty.
- **Before 2022:** ERA5 pressure levels (Copernicus CDS, free account) would be
  needed. This isn't required now.
- **No API key** is needed. Data is licensed CC-BY 4.0, so the plots will be
  credited "Weather data by Open-Meteo.com".

`GetDataUpperAir.py` runs daily. It reads `latitude`/`longitude` from
`config/station.ini`, saves `data/upperair/YYYY/YYYY-MM/YYYY-MM-DD.csv`, and
computes `T_eff` per hour (see section 5.2).

---

## 3. Phased implementation (maps to your 12 items)

### Phase 0 – Foundations (items 1, 2, 5, 12)
1. **Versioning:** `VERSION` (CalVer `YYYY.MM.patch`, already `2026.10.0`) is
   read by `picomuon_common.get_version()`. It is shown in logs, the web page
   footer, and will be used for the email footer when Phase 6 adds email
   alerts. Releases get a git tag `v2026.11.0`.
2. **Changelog:** maintain `CHANGELOG.md` (already present) with an
   `[Unreleased]` section. The release notes are copied from it.
3. **No `pi` user:** `install/install.sh` uses `${SUDO_USER}`. It templates
   `@PICOMUON_USER@`, `@PICOMUON_GROUP@` and `@PICOMUON_BASE_PATH@` into the
   service and cron files. Scripts find their base path from their own location
   (`picomuon-env.sh` / `get_base_path()`), as in the Magnetometer suite.
4. **UTC everywhere (F3):** all "which day?" decisions are made in code by one
   `utc_yesterday()` helper, never by the cron schedule. Debian's cron (used
   by Raspberry Pi OS) does not support `CRON_TZ`. So the daily job runs at
   **01:15 local time** for UK installations, which is after 00:00 UTC in both
   GMT and BST. Installations in other time zones must schedule after
   00:00 UTC in their local time; the helper still selects the UTC date.
5. **Cron and `su` pattern (F10), copied from the Magnetometer suite:**
   - The crontab only calls
     `runCronJob.sh /bin/bash <base>/scripts/processData.sh`. There is no
     `su pi -c "gnuplot …"` in the crontab.
   - `processData.sh` sources `picomuon-env.sh` to get `BASE_PATH` and
     `FILE_OWNER`, then runs each step with
     `su "$FILE_OWNER" -c "…"`. The `if … then … else … FAILED` checks write
     a one-line failure to the error log.
   - `runCronJob.sh` timestamps any stderr into `log-error.txt` and returns
     the exit code; the service writes stdout/stderr to the corresponding
     good/error log files.
   - As a safety net, also `export TERM=dumb` in `picomuon-env.sh`, and put
     `set terminal pngcairo` first in every `.gp` file.
   - The installer replaces only the `# UKRAA PicoMuon` block in root's
     crontab. It never appends duplicates or runs `crontab -r` (F9).
6. **Logging (item 12):** two files, using the Magnetometer suite's format
   (`timestamp : source : message`, via `logging.sh` and the Python
   equivalent in `picomuon_common.py`).
   - `log-PicoMuon.txt` is the "good" log: Started/Completed lines and
     summaries, for example "2026-10-09: 21,177 C events, 1,440/1,440
     minutes, 0 missing events".
   - `log-error.txt` gets only real problems: FAILED, tracebacks, missing NMDB
     data, serial reconnects, and rejected lines.
   - `manageLogfiles.sh` rotates both weekly and keeps N weeks (set in an ini
     file).
7. **Locking:** `runCronJob.sh` wraps each job in `flock` so runs never
   overlap (for example, a long reprocess and the 5-minute rolling job).

*Done when:* a fresh install works under any user name, no runtime code assumes
the `pi` account or its home directory, and the error log is empty on a healthy
day.

### Phase 1 – Collector and serial identity (items 6, 7)
1. Rename `GetDataRawACM0.py` to `GetDataRaw.py` and `PicoMuonACM0.service` to
   `PicoMuon.service`. Remove the `ACM0` suffix from **all** script, plot, and
   data folder names (item 7).
2. `ConfigureUSB.py` (ported from the Magnetometer suite) scans
   `/dev/serial/by-id/*`, reads a few lines from each port, and recognises a
   PicoMuon by the line format. It records `serial_port` (stable by-id path),
   `id_serial`, and a proposed **`label`** (from the current `DetectorName`,
   editable) in `config/USB.ini`. Optional: install a udev rule that creates
   `/dev/picomuon`.
3. Collector hardening:
   - keep one file handle open and roll it over at UTC midnight
   - `flush()` each line
   - catch `SerialException` and reconnect with back-off
   - validate the field count
   - write malformed lines to `data/raw/rejected/` instead of dropping them
     silently
   - log `DetectorName` changes once (info), and log an error if the name
     belongs to another configured detector (cable swap, section 2b)
4. Write `data/status/current.json` (last event time, rate, temperature,
   pressure) for the web page and alerts.

### Phase 2 – Fast processing (item 3)
1. `ProcessDaily.py`: one pass over L0 produces the L1 minute file, ADC
   histogram, and L2 hourly file, and merges NMDB data by timestamp. It uses
   `EventCount` and `Elapsed_ms` deltas (section 2a) to get exposure per
   minute and the missing-event count. It does **not** apply a dead-time
   correction (F6).
2. `ProcessPeriod.py` builds week, month, 3-month, **6-month, and year**
   products from L2. A completeness rule (as in the Magnetometer suite's
   `period_min_valid_days_percent`) prevents misleading plots.
3. `reprocessData.sh --from YYYY-MM-DD --to YYYY-MM-DD [--dry-run]`
   back-fills L1/L2 for your 1.5 years of history. It can also be run after a
   later software or correction-coefficient update to rebuild derived products
   from the unchanged raw files. Reprocessing is repeatable: it replaces only
   the selected date range's generated products, never the raw input. Expect
   minutes, not weeks.
4. The cron schedule collapses to one `processData.sh` at 01:15 local time.
   It runs: fetch NMDB and upper-air data → daily → period → coefficients →
   plots → publish → FTP upload.

*Done when:* the full daily chain finishes in under 2 minutes on a Pi4, and
the outputs match the legacy outputs for a sample day. A pytest test compares
them.

### Phase 2a – Concurrent multi-detector support (before Phase 3)

Phases 0-2 have implementation entries in the changelog; Phase 3 was the next
planned feature. Insert this phase first: two physical detectors have now been
recognised together on a powered USB hub, but simultaneous collection and
processing are not yet wired end to end. The hub resolved USB enumeration;
software configuration alone could not resolve that hardware issue.

1. Extend `ConfigureUSB.py` and `USB.ini` to register and edit multiple
   detectors without replacing previously configured units. Use the
   `[detectors]` label-to-by-id mapping in section 2b, with per-detector USB
   identity checks. Validate labels and reject duplicate physical devices,
   including aliases resolving to the same device. Preserve existing `[usb]`
   single-detector configurations and paths.
2. Add `PicoMuon@.service`, with one collector instance per configured label.
   Each instance selects exactly one detector and verifies its USB identity
   before reading; an identity mismatch must not permit collection from the
   wrong unit. Configure independent reconnect handling so unplugging one
   detector does not interrupt the other. Installer/service transitions must
   prevent the old single collector and a new instance reading the same port.
3. Isolate all detector-specific outputs: raw and rejected rows, status,
   logs, daily summaries, processed data, plots, temporary files and published
   web assets. Raw files use `data/raw/unit_1/YYYY/YYYY-MM/YYYY-MM-DD.txt`
   and `data/raw/unit_2/YYYY/YYYY-MM/YYYY-MM-DD.txt`, for example. No shared
   status file, summary or generated filename may overwrite another unit's
   output. Keep the default single-detector layout unchanged.
4. Make daily, period and historical reprocessing operate on explicitly
   selected detectors, with scheduled processing covering all configured
   units. Scope locks appropriately and keep counts, exposure and summaries
   separate. In multi-detector mode, do not silently fall back to another
   detector's or an unlabelled raw file when input is missing.
5. Provide separate web views/status for each detector. Establish the same
   detector selection and output-path contract for Phase 3 rolling plots and
   later publishing, alerts and science products; do not combine detector
   counts implicitly.
6. Provide a dry-run, explicit historical-data mapping when adopting labels.
   Preserve original raw files, verify any copies and stop on conflicting
   destination contents, following the Phase 7 migration safeguards. A
   configuration change alone must never move or relabel historical data.
   Handle a label change partway through a UTC day explicitly so subsequent
   processing does not silently omit the earlier part of that day.
7. Document setup, safe service transitions, historical-data handling and
   powered-hub troubleshooting. Test two simulated serial streams, USB
   reconnects and swapped ACM numbers, identity mismatches, duplicate
   configurations, UTC rollover, output isolation, missing input and
   single-detector compatibility.

*Done when:* `unit_1` and `unit_2` record concurrently to distinct raw files
using stable by-id identities; disconnecting either leaves the other recording;
daily/period processing and web output remain separate; historical raw files
remain intact; and the existing single-detector tests still pass. Confirm the
two-detector collection and reconnect behaviour on the RPi before Phase 3.

### Phase 3 – Rolling 24-hour plot (item 4)
- Depends on Phase 2a: run independently for each configured detector, using
  its own raw input, rolling CSV, plot, status and published web location.
  Retain the paths below for the default single-detector installation.
- Cron runs every 5 minutes: `processRollingData.sh` → `ProcessRolling.py`.
  It reads only the tail of today's and yesterday's raw files (about 2 MB,
  under 1 s), writes `data/rolling/last24h.csv`, and runs `PlotRolling.gp`.
  The page auto-refreshes.
- Panels: coincidence counts per 5 minutes (with ±1σ Poisson band), T/B singles
  (if present), pressure and temperature, and the latest NMDB value when
  available.

### Phase 4 – Configurable plots and NMDB (item 9)
`config/plot.ini`:
```ini
[plots]
plot_cpm = true
plot_freq = true
plot_adc = true
plot_day = true
plot_rolling = true
plot_week = true
plot_month = true
plot_3month = true
plot_6month = false
plot_year = false
plot_pressure_coefficient = true
plot_corrected = true          # P / P+T corrected overlays
plot_harmonics = false         # section 5
period_min_valid_days_percent = 90
```
`config/nmdb.ini`:
```ini
[nmdb]
enabled = true
stations = OULU            # e.g. KIEL2, JUNG, NEWK, SOPO – comma separated
table = revori
refetch_days = 3           # re-download recent days as NMDB revises data
```
`MergeConfig.py` adds new keys on update without touching user values.
`publishWeb.sh` writes `plot-options.json` so `index.html` only shows enabled
panels.

### Phase 5 – FTP publishing (item 10)
**Plain FTP only for now (decision 4).** Copy the Magnetometer suite's
`uploadRemote.sh` and `config/remote-upload.ini` (same keys: `enabled`,
`site`, `user`, `password`, `port`, `directory`, `timeout_seconds`, `passive`,
`create_dirs`). It uses Python's built-in `ftplib`, so there's nothing extra
to install, and it gives mkdir -p, retry, and a log line per file.
- Uploads go to `<dir>/yesterday` after the daily run, `<dir>/rolling` every
  5 minutes (optional), and `<dir>/status/plot-options.json`.
- `remote-upload.ini` is `chmod 600` and owned by the install user.
- `testRemoteUpload.sh` provides a one-off connection and upload test.
- Plain FTP sends the password unencrypted, so the README should recommend a
  **separate FTP account limited to the upload folder** rather than the main
  hosting login.

**What adding encryption later would involve (not in this release):**

| Option | How it works | Code needed | Host requirement |
|---|---|---|---|
| **FTPS** (FTP over TLS) | Same FTP protocol and port 21, with the login and data encrypted | About 5 lines: `ftplib.FTP_TLS` + `prot_p()`, selected by `protocol = ftps` in the ini. Same library, so nothing to install. | The host must enable "explicit FTP over TLS". Many hosts already do, sometimes without saying so. It's worth a one-off test. |
| **SFTP** (file transfer over SSH) | A different protocol on port 22, usually with an SSH key instead of a password | A different code path: the system `sftp`/`scp` command with a key, or the `paramiko` package. Key setup goes in the README. | The host must give SSH/SFTP access, which is often on higher-tier plans only. |

The ini file gets a `protocol = ftp` key now, so FTPS can be added later
without changing users' config files.

### Phase 6 – Email alerts (item 11)
`config/alerts.ini` contains `[alerts] [smtp] [email] [heartbeat]`, as in the
Magnetometer suite.
- **High-rate alert:** baseline λ is the rolling 24-hour median, P- and
  T-corrected. Alert when the Poisson tail probability `P(k ≥ observed | λ)` is
  below `1e-6` on 1-minute **and** 10-second windows. Use hysteresis and a
  cooldown (for example 1 email per 6 h).
- **Low-rate (possible Forbush decrease) alert:** hourly corrected deviation
  below `−k·σ` for at least 6 h, with a cross-check against NMDB.
- **Health alerts:** no data for N minutes (USB or detector failure), disk
  above 90 %, or temperature out of range.
- **Daily heartbeat email** (optional) with yesterday's summary and plot.
- **Expectation:** a small 2-paddle detector rarely sees an extensive air
  shower as a "high count". Most spikes will be electrical noise, which is why
  the ADC values and the 10-second burst test help. Real excess events of
  interest are Ground Level Enhancements, which will also appear in NMDB.

### Phase 7 – Updater and migration (item 8)
`scripts/updatePicoMuon.sh` (decision 3; run with `sudo`), modelled on the
Magnetometer suite's `updateMagnetometer.sh`. It copies itself to a temporary
directory before running, so it can safely replace its own file during the
update.
1. Query `https://api.github.com/repos/UKradioastro/UKRAA_PicoMuon/releases/latest`
   with `curl`. Compare its `tag_name` with `VERSION` and exit if already up to
   date. Support `--check`, `--version vX`, and `--rollback`.
2. Download the release tarball to a temporary directory. Verify the SHA-256
   checksum if a checksum asset is published.
3. Back up `scripts/ install/ WWW/ VERSION` to `backup/<old-version>/`.
   **Never overwrite or delete** `config/ data/ plots/ logfiles/` as part of
   installing release files. Historical raw data is preserved as the source
   of truth; generated products can be rebuilt with `reprocessData.sh`.
4. Copy the new files, run `MergeConfig.py` and any migrations, re-template the
   service and cron files, `systemctl daemon-reload` and restart the service,
   and run `runPostUpdateChecks.sh`. Restore the backup if any step fails.
5. `MigrateLegacyInstall.py` runs once and handles the old setup. Migration
   must be non-destructive and restart-safe:
   - offer a `--dry-run` preview and record the source/destination mapping;
   - copy, do not move, `data/raw/ACM0/*` to `data/raw/` (or to
     `data/raw/<label>/` in multi-detector mode); preserve the original files
     until the user has verified the new installation;
   - verify copied files (at minimum, relative paths, sizes, and counts; use
     SHA-256 checks where practical) before switching configured paths;
   - retain a migration manifest and never overwrite a destination file with
     different contents; stop with a clear error if a conflict is found;
   - migrate generated data and plots only if safe; otherwise regenerate them
     from the preserved raw data using `reprocessData.sh`;
   - remove the old PicoMuon cron lines **only** (no more `crontab -r`),
     disable `PicoMuonACM0.service`, enable `PicoMuon.service`, and reprocess
     history only after the raw-data copy has passed verification.

   The original legacy tree is not automatically deleted. Cleanup is a
   separate, user-approved step after checking the new files and plots.
6. `docs/RELEASING.md` gives the release steps: bump `VERSION`, move
   `[Unreleased]` in `CHANGELOG.md`, tag, and publish a GitHub release.

### Phase 8 – Science features (section 5)
### Phase 9 – Tests and docs
pytest covering:
- raw parsing (including malformed lines and the 32-bit wrap)
- daily binning against legacy output
- config merge
- USB detection (mocked)
- updater dry-run
- coefficient fit on synthetic data with a known β

Update the README with the same section layout as the PicoMagnetometer README.

**Suggested order:** 0 → 1 → 2 (biggest win) → 2a (multi-detector support) →
3 → 4 → 7 (so users can get
later phases by updating) → 5 → 6 → 8.

---

## 4. Other improvement suggestions
- Run cron jobs through `runCronJob.sh` and switch to the install user inside
  the scripts (Phase 0, item 5), rather than calling `su pi -c` in the crontab.
- Remove MariaDB/PHP from the installer (F12). Apache (or lighttpd/nginx)
  serving static files is enough.
- Add a `data/status/health.json` marker and a dashboard one-liner
  (`checkDailyPublishHealth.sh` and `showDashboardSummary.sh` from the
  Magnetometer suite).
- Show the detector label and `DetectorName` on every plot (section 2b).
- Timing: enable `chrony`. For network studies between several UKRAA
  detectors, a GPS PPS gives microsecond timestamps. That would allow true
  **coincidence of air showers between sites**, which is much more meaningful
  than a single-detector "high count".
- Acknowledge NMDB in plots and README (required by NMDB data policy).
- Store fitted coefficients with their provenance (window, n, R², σ) rather
  than one number per file.

---

## 5. Science plan

### 5.1 Pressure coefficient β
Model: `ln(N/N₀) = β·(P − P₀)`, so the corrected count is
`N_P = N·exp(−β(P − P₀))`.
- **Data:** hourly L2 counts and mean pressure. Weight each point by its
  Poisson error (σ = 1/√N).
- **Remove primary cosmic-ray variation first:** divide by the
  pressure-corrected NMDB station rate (scaled), or detrend with a 27-day
  running mean. Without this step, Forbush decreases and solar modulation bias
  β.
- **Fit:** weighted least squares with an intercept (the current gnuplot fit
  forces it through zero). Exclude flagged Forbush or GLE days.
- **Windows:** a rolling 90-day estimate gives monitoring. A **frozen**
  coefficient in `config/coefficients.ini` is used for correction, so
  reprocessed history doesn't change daily. The plot shows the β history so
  you can decide when to update the frozen value.
- **Expectation:** your −0.188 %/hPa is in the normal surface-muon range
  (about −0.12 to −0.20 %/hPa). With about 880 counts/hour, 90 days of hourly
  data gives σ(β) well below 0.01 %/hPa.

### 5.2 Temperature coefficient(s)
There are **two different temperature effects**, and they must be kept apart:
1. **Atmospheric temperature effect.** Muons are produced at around 100–200 hPa
   altitude, so their count depends on the *upper-air* temperature, not the
   room temperature. Get daily or hourly temperatures on pressure levels for
   your location (for example the free Open-Meteo historical/forecast API,
   which has levels 1000–30 hPa, or ERA5). Compute an **effective temperature**
   `T_eff` (a weighted average over levels; a mass-weighted average is a good
   start). Fit `ln(N_P/N₀) = α_T·(T_eff − T_eff₀)`. Typical α_T is about
   −0.1 to −0.2 %/K for surface muons, mostly a seasonal effect. It needs at
   least 6–12 months of data. Fit P and T **together** (multiple regression)
   once a year of data exists, because both vary seasonally and are
   correlated.
2. **Instrument temperature effect.** The Pico's sensor measures the detector
   box. The SiPM gain and threshold depend on it. Fit residuals against the
   detector temperature over short windows. **Caution:** indoor temperature
   has a daily cycle, so this correction can create or remove a fake daily
   variation. Check it with the ADC spectrum (gain drift shifts the ADC peak),
   and prefer stabilising the detector temperature.

Correction chain (in `ApplyCorrections.py`):
`N_PT = N · exp(−β·ΔP) · exp(−α_T·ΔT_eff) [· exp(−α_det·ΔT_det)]`.
It is applied to the L2 hourly files, so all week-to-year plots get raw,
P-corrected, and PT-corrected curves next to NMDB.

### 5.3 Daily (solar) variation – FFT / harmonic analysis
- Use **PT-corrected hourly** data, detrended by a 24-hour running mean (or the
  NMDB ratio).
- The data has gaps, so use **harmonic fitting** (24 h and 12 h sine/cosine
  least squares) or **Lomb–Scargle** rather than a plain FFT. Also produce a
  *superposed-day* plot (average count against local solar time with error
  bars).
- **Sensitivity:** the amplitude error is about √(2/N_total). At about 21,000
  events per day:

  | Duration | σ (amplitude) |
  |---|---|
  | 1 month | ≈ 0.18 % |
  | 1 year | ≈ 0.05 % |

  The expected solar diurnal anisotropy for surface muons is about 0.1–0.2 %,
  so **1 year of data gives a real (~3σ) detection**. A month does not.
- **Systematic checks:** compare the solar (24 h) result with the sidereal
  (23.934 h) and **anti-sidereal (24.066 h)** periods. The anti-sidereal period
  should show nothing, so any signal there measures seasonal artefacts. Also
  check that the phase doesn't follow the room-temperature cycle.
- Look for the 27-day solar-rotation recurrence with Lomb–Scargle on daily data.

### 5.4 Solar cycle and Forbush decreases
- **Forbush decreases (good prospects):** large events give about 1–5 % drops in
  surface muons (5–20 % in neutron monitors). Daily noise is about 0.7 %, so
  big events are visible on 6–24 hour averages. Implementation:
  - flag a drop of at least k·σ relative to a 27-day baseline
  - cross-check against simultaneous NMDB drops
  - mark candidate times from NASA DONKI ICME/CME and Kp/Dst (reuse the
    Magnetometer suite's `space_weather.py` and period overlay plan)
  - **superposed-epoch analysis** over many events
  - the muon/neutron drop ratio gives a rough measure of the rigidity spectrum
- **11-year cycle (long-term, harder):** surface muon modulation over a cycle is
  a few percent at most, compared with about 15–25 % for high-latitude neutron
  monitors. Detector drift (SiPM ageing, threshold, temperature) is the real
  limit. Planned approach:
  - monthly or 27-day means of the PT-corrected rate
  - monthly SILSO sunspot number (`https://www.sidc.be/SILSO/INFO/snmtotcsv.php`)
  - the NMDB monthly rate
  - **lagged cross-correlation** (cosmic rays lag sunspots by months)
  - track the **muon/NM ratio** to separate detector drift from real
    modulation

  Cycle 25 peaked around 2024–25, so cosmic-ray intensity should *rise* over
  2026–2030. With stable detectors this could show after about 3–5 years,
  sooner if several UKRAA detectors are combined.

---

## 6. Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Raw file format | **Revised 2026-10-16:** keep the 9 event fields unchanged and add one column-header line to RPi raw files. New files get the header automatically; migrate historic and current files with `AddRawHeaders.py` while collectors are stopped. Readers accept both formats. |
| 2 | Folder layout | **Single detector:** `data/raw/YYYY/…` (as in the Magnetometer suite). **Optional multi-detector:** `data/raw/<label>/YYYY/…`, where the label is set once in `USB.ini` and bound to the by-id port. It is never taken from the live `DetectorName`, which users can rename (section 2b). |
| 3 | Updater | **`updatePicoMuon.sh`**, as in the Magnetometer suite. |
| 4 | Remote upload | **Plain FTP.** A `protocol` key is reserved so FTPS can be added later (section 3, Phase 5). |
| 5 | Upper-air temperature | **Open-Meteo:** the forecast API for daily updates and the historical-forecast API for back-fill from 2022 onwards (section 2c). |
| – | Dead time (F6) | Not corrected (0.13 % fraction, about ±0.01 % variation). Logged for QC only. |
