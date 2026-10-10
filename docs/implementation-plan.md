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
| F4 | The raw line has **9 fields**, not 8: `ts,Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp,Pres,Name`. | Raw files | Documentation and parsers need to agree. |
| F5 | `Elapsed_ms` is a signed 32-bit counter and **wraps every ~24.8 days**. It went negative on 2026-10-10 (`-2147288954`). | Raw file 2026-10-10 | Any live-time or dead-time maths must "unwrap" it. |
| F6 | Dead time is logged but never used. | Processors | Rates are not dead-time corrected. |
| F7 | `GetDataRawACM0.py` opens the output file once per line and never closes it, and has no reconnect handling. | Collector | Risk of file-handle leaks or lost data if USB drops. Relies on systemd restart. |
| F8 | Hard-coded `/home/pi`, `su pi`, `/dev/ttyACM0`, and `ACM0` in every path and file name. | All scripts, service, cron | Blocks items 5, 6, and 7. |
| F9 | `install.sh` appends to root's crontab on every run, and `update.sh` runs `crontab -r` (wipes **all** root cron jobs). | `install/`, `update/` | Duplicate or lost cron entries. |
| F10 | `log-error.txt` is filled with gnuplot `No entry for terminal type "unknown"` noise. | `logfiles/log-error.txt` | Real errors get lost (item 12). |
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
│   ├── picomuon.cron           # installed to /etc/cron.d/picomuon (CRON_TZ=UTC)
│   ├── USB.ini.example
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
│   ├── ComputeCoefficients.py  # β (pressure), α (temperature)
│   ├── ApplyCorrections.py     # P and P+T corrected series
│   ├── EvaluateAlerts.py       # high/low rate, no-data, heartbeat email
│   ├── uploadRemote.py         # FTP/FTPS
│   ├── publishWeb.sh           # copy to /var/www/html + plot-options.json
│   ├── processData.sh  processRollingData.sh  reprocessData.sh  manageLogfiles.sh
│   ├── updatePicoMuon.py       # GitHub release updater (item 8)
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
| L0 raw | `data/raw/YYYY/YYYY-MM/YYYY-MM-DD.txt` | Unchanged line format (back-compatible) | `GetDataRaw.py` |
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

---

## 3. Phased implementation (maps to your 12 items)

### Phase 0 – Foundations (items 1, 2, 5, 12)
1. **Versioning:** `VERSION` (CalVer `YYYY.MM.patch`, already `2026.10.0`) is
   read by `picomuon_common.get_version()`. It is shown in logs, the web page
   footer, and the email footer. Releases get a git tag `v2026.11.0`.
2. **Changelog:** maintain `CHANGELOG.md` (already present) with an
   `[Unreleased]` section. The release notes are copied from it.
3. **No `pi` user:** `install.sh` uses `${SUDO_USER}`. It templates
   `@PICOMUON_USER@` and `@PICOMUON_BASE_PATH@` into the service and cron
   files. Scripts find their base path from their own location
   (`picomuon-env.sh` / `get_base_path()`), as in the Magnetometer suite.
4. **UTC everywhere:** `CRON_TZ=UTC` and a single `utc_yesterday()` helper. The
   daily job starts at about 00:10 UTC (fixes F3).
5. **Logging:** Python `logging` writes to two handlers. `logfiles/picomuon.log`
   gets INFO and above (the "good" log), and `logfiles/picomuon-error.log` gets
   WARNING and above. Both use the existing `timestamp : source : message`
   format. Shell scripts use `logging.sh`. Add `TERM=dumb` and `set term
   pngcairo` before any output in `.gp` files to remove the gnuplot noise
   (F10). Rotation is done with `manageLogfiles.sh` (keep N weeks) or
   `logrotate`.
6. **Locking:** `runCronJob.sh` wraps each job in `flock` so runs never
   overlap.

*Done when:* a fresh install works under any user name, `grep -r /home/pi`
finds nothing, and the error log is empty on a healthy day.

### Phase 1 – Collector and serial identity (items 6, 7)
1. Rename `GetDataRawACM0.py` to `GetDataRaw.py` and `PicoMuonACM0.service` to
   `PicoMuon.service`. Remove the `ACM0` suffix from **all** script, plot, and
   data folder names (item 7).
2. `ConfigureUSB.py` (ported from the Magnetometer suite) scans
   `/dev/serial/by-id/*`, reads a few lines from each port, and recognises a
   PicoMuon by the line format. It records `serial_port` (stable by-id path),
   `id_serial`, and **`detector_name`** (for example `V53/D/09/034`) in
   `config/USB.ini`. Optional: install a udev rule that creates
   `/dev/picomuon`.
3. Collector hardening:
   - keep one file handle open and roll it over at UTC midnight
   - `flush()` each line
   - catch `SerialException` and reconnect with back-off
   - validate the field count
   - write malformed lines to `data/raw/rejected/` instead of dropping them
     silently
   - warn if `DetectorName` doesn't match `USB.ini`
4. Write `data/status/current.json` (last event time, rate, temperature,
   pressure) for the web page and alerts.

### Phase 2 – Fast processing (item 3)
1. `ProcessDaily.py`: one pass over L0 produces the L1 minute file, ADC
   histogram, and L2 hourly file, and merges NMDB data by timestamp. It
   handles the `Elapsed_ms` wrap (F5) and computes **live time** per minute
   from `Elapsed_ms` and `Dead_ms` differences. Rates are reported as
   counts per live-second (F6).
2. `ProcessPeriod.py` builds week, month, 3-month, **6-month, and year**
   products from L2. A completeness rule (as in the Magnetometer suite's
   `period_min_valid_days_percent`) prevents misleading plots.
3. `reprocessData.sh --from YYYY-MM-DD --to YYYY-MM-DD [--dry-run]`
   back-fills L1/L2 for your 1.5 years of history. Expect minutes, not weeks.
4. The cron schedule collapses to one `processData.sh` at about 00:10 UTC that
   runs fetch NMDB → daily → period → coefficients → plots → publish → upload.

*Done when:* the full daily chain finishes in under 2 minutes on a Pi4, and
the outputs match the legacy outputs for a sample day. A pytest test compares
them.

### Phase 3 – Rolling 24-hour plot (item 4)
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
`config/remote-upload.ini`, which uses the same keys as the Magnetometer suite
plus `protocol = ftp|ftps`. Implement it in Python `ftplib` (`FTP_TLS` for
FTPS) with timeout, passive mode, mkdir -p, and retry. Uploads go to
`<dir>/yesterday`, `<dir>/rolling`, and `<dir>/status`. The ini file is
`chmod 600`. `testRemoteUpload.sh` provides a one-off test.

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
`scripts/updatePicoMuon.py` (run with `sudo`):
1. Query `https://api.github.com/repos/UKradioastro/UKRAA_PicoMuon/releases/latest`.
   Compare its `tag_name` with `VERSION` and exit if already up to date.
   Support `--check`, `--version vX`, and `--rollback`.
2. Download the release tarball to a temporary directory. Verify the SHA-256
   checksum if a checksum asset is published.
3. Back up `scripts/ install/ WWW/ VERSION` to `backup/<old-version>/`.
   **Never touch** `config/ data/ plots/ logfiles/`.
4. Copy the new files, run `MergeConfig.py` and any migrations, re-template the
   service and cron files, `systemctl daemon-reload` and restart the service,
   and run `runPostUpdateChecks.sh`. Restore the backup if any step fails.
5. `MigrateLegacyInstall.py` runs once and handles the old setup. It moves
   `data/raw/ACM0/*` to `data/raw/` (and the same for the processed and plots
   folders). It removes old `ACM0` cron lines **only** (no more
   `crontab -r`), disables `PicoMuonACM0.service`, enables `PicoMuon.service`,
   and reprocesses history.
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

**Suggested order:** 0 → 1 → 2 (biggest win) → 3 → 4 → 7 (so users can get
later phases by updating) → 5 → 6 → 8.

---

## 4. Other improvement suggestions
- Use `/etc/cron.d/picomuon` instead of editing root's crontab, and run jobs as
  the install user, not root.
- Remove MariaDB/PHP from the installer (F12). Apache (or lighttpd/nginx)
  serving static files is enough.
- Add a `data/status/health.json` marker and a dashboard one-liner
  (`checkDailyPublishHealth.sh` and `showDashboardSummary.sh` from the
  Magnetometer suite).
- Sanitise `DetectorName` (`V53/D/09/034` → `V53-D-09-034`) for file names and
  show it on every plot. This allows a future multi-detector Pi
  (`data/raw/<detector>/…`).
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

## 6. Decisions for you
1. Keep `data/raw` file format unchanged (recommended) or add a header/ISO `Z` timestamps?
2. Single detector per Pi (`data/raw/…`) or per-detector folders (`data/raw/<detector>/…`) from day one?
3. Updater in Python (`updatePicoMuon.py`, as requested) only, or also a thin `updatePicoMuon.sh` wrapper for consistency with the Magnetometer suite?
4. FTP only, or also FTPS/SFTP (recommended for passwords over the internet)?
5. Source for upper-air temperature (Open-Meteo recommended – free, no key).
