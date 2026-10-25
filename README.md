<div align=center>
<img src="images/UKRAA_Logo_Black.svg" width=**400** height=**400**/>
</div>


# Python code for the UKRAA PicoMuon
[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](/LICENSE)
[![Python 3](https://img.shields.io/badge/Python-3-blue.svg?logo=python)](https://www.python.org/)
[![Bash](https://img.shields.io/badge/Shell-Bash-4EAA25.svg?logo=gnubash)](https://www.gnu.org/software/bash/)
[![gnuplot](https://img.shields.io/badge/Plots-gnuplot-4F4F4F.svg)](https://www.gnuplot.info/)
[![Raspberry Pi 4/5](https://img.shields.io/badge/Raspberry%20Pi-4%2F5-A22846.svg?logo=raspberrypi)](https://www.raspberrypi.com/)
[![PicoMuon data](https://img.shields.io/badge/PicoMuon-Muon%20detector%20data-0078D4.svg)](https://github.com/UKradioastro/UKRAA_PicoMuon)


Set of Python, gnuplot and Bash scripts to run on a Raspberry Pi 4/5 to record, process and present data from the UKRAA PicoMuon detector.

This software was written to suit a specific set-up, feel free to use as you see fit.


Instructions for setting up a Raspberry Pi4/5 are included in the **docs** folder

---

&nbsp;
<!-- =============================================================================== -->
## Contents

- [Temporary plots](#temporary-plots)
- [Can I update to the latest version?](#can-i-update-to-latest-version)
- [Where is my detector?](#where-is-my-detector)
- [Getting the software onto your RPi](#getting-the-software-onto-your-rpi)
- [Using the code](#using-the-code)
- [Installing the software onto your RPi](#installing-the-software-onto-your-rpi)
- [What does the code do?](#what-does-the-code-do)
  - [Observation and legacy detector configuration](#observation-and-legacy-detector-configuration)
  - [Phase 2a development: named-detector collection and processing pilot](#phase-2a-development-named-detector-collection-and-processing-pilot)
    - [Explicit offline processing in the pilot](#explicit-offline-processing-in-the-pilot)
    - [Named daily plots and web pilot](#named-daily-plots-and-web-pilot)
  - [Raw event columns](#raw-event-columns)
  - [Metadata in processed and shared data](#metadata-in-processed-and-shared-data)
  - [Neutron file attribution and headers](#neutron-file-attribution-and-headers)
  - [Upgrading existing data files](#upgrading-existing-data-files)
  - [Adding headers to historic and current raw files](#adding-headers-to-historic-and-current-raw-files)
  - [Outdoor temperature on CPM plots](#outdoor-temperature-on-cpm-plots)
  - [Log format](#log-format)
- [Check GetDataRaw.py is running](#check-getdatarawpy-is-running)
- [Updating your software](#updating-your-software)
- [License](#license)
- [Contact us](#contact-us)

&nbsp;

---

&nbsp;
<!-- =============================================================================== -->
### Temporary plots

Latest plot copies are grouped below `temp/`:

```text
temp/
  yesterday/   # CPM, ADC and frequency plots (T, B and C)
  periods/     # day, week and month plots
```

Plotting entry points create these directories automatically as the project
owner, including on existing installations. Dated archives under `plots/`
are unchanged. Daily publishing reads both groups and keeps the existing flat
web image URLs, so no web-page update is required.

For a manual upgrade, copy all six `scripts/PlotData*ACM0.gp` files together
with `scripts/logging.sh` and `scripts/processData.sh`. The next plotting run
populates the new directories; no reinstall or collector restart is needed.
Old PNGs directly under `temp/` are no longer updated or published. After
checking the new plots, those obsolete flat copies can be removed manually.
Historical reprocessing with `--plot` also refreshes these latest-copy folders
for its requested date, as before.

---

&nbsp;
<!-- =============================================================================== --> 
### Can I update to latest version?

See [Updating your software](#updating-your-software) for instructions.

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
### Where is my detector?

Plug your detector into any of the RPi USB ports - I normally use the blue ports (USB3).

1. Open a terminal window and type the following command and press enter
```
ls /dev/tty*
```

![img_48](images/RPi_imager_48.PNG)

&nbsp;

2. You are looking for **/dev/ttyACM0** - this is on the right hand side of the screen shot above.

&nbsp;

3. This is the USB address for your attached detector - if you have more than one detector attached you may see **/dev/ttyACM1** etc.

&nbsp;

4. If you do not see **/dev/ttyACM0**, then unplug and plug the detector back in and try again.

&nbsp;

5. As long as you see **/dev/ttyACM0** then you do not have to make any changes to the python scripts, because they are looking for **ACM0**.

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
## Getting the software onto your RPi

1. Log into your Raspberry Pi4/5 using VNC.

&nbsp;

2. Open a terminal window, type the following command and press enter
```
git clone https://github.com/UKradioastro/UKRAA_PicoMuon
```

![img_01](images/RPi_imager_01.PNG)

This downloads the code into a `UKRAA_PicoMuon` directory under the current user's home directory.

---

&nbsp;
<!-- =============================================================================== --> 
## Using the code

The raw data collector resolves serial settings from `config/USB.ini`, with support for stable `/dev/serial/by-id/` device paths configured via `python3 scripts/ConfigureUSB.py` (defaulting gracefully to `/dev/ttyACM0`). The installer uses the account that invoked `sudo`, so the software does not require a user named `pi`. Python and gnuplot scripts resolve paths from the installation directory.

**GetDataRaw.py** is run as the systemd service `PicoMuon.service`. Daily processing and plotting are run by a managed root crontab entry, with jobs executed as the installing user.

---

&nbsp;
<!-- =============================================================================== --> 
## Installing the software onto your RPi


1. Open a terminal window and type the following command and press enter
```
cd ~/UKRAA_PicoMuon
```

![img_02](images/RPi_imager_02.PNG)

This takes you to the root of your cloned repository.


2. Type the following command and press enter
```
sudo bash install/install.sh
```

![img_04](images/RPi_imager_04.PNG)

The installer installs the required packages, configures the collector service for your account, and replaces only the PicoMuon block in root's crontab. Daily processing starts at 01:15 local time.

---

&nbsp;
<!-- =============================================================================== --> 
## What does the code do?

The code receives the event data from the UKRAA PicoMuon detector via serial over the supplied USB cable and stores the event data to the raw data folder:

The raw data will be processed overnight, via CRON, to get counts per minute, the frequency of the counts per minute and the frequency of the adc values for your previous day's data.

Processed products are stored directly under `data/` in their own folders (for example, `data/cpm/`, `data/day/`, and `data/adc/`); they are no longer nested under `data/processed/`. Raw and processed detector files have ordinary CSV column headers, with detector/settings values on each data row. New output does not contain `# picomuon_metadata:` JSON comments.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Observation and legacy detector configuration

The installer creates `config/legacy.ini` and `config/user.ini` from the templates in `install/`, without overwriting existing values. For a manual upgrade, copy `install/legacy.ini.example` and `install/user.ini.example` to those configuration paths if they do not already exist. Stop collection before upgrading, configure the files, then restart the service.

**Check all four values in `config/legacy.ini` against your detector's actual settings before collecting data.** The example values are not a calibration or an automatic measurement. The collector accepts either:

```text
Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName
Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName,threshold_top,reset_top,threshold_bottom,reset_bottom
```

When the detector provides all four settings, those values take precedence. When it omits all four, the collector reads them from `[legacy]` in `config/legacy.ini`. Values must be non-negative integers in the firmware's native units; no unverified upper limit or threshold/reset relationship is imposed. Partial or invalid setting suffixes are rejected, not silently replaced. A missing or invalid legacy configuration stops collection with a logged error when an old-format event needs it. New-format detectors do not require this file.

Use CSV quoting if a detector name contains commas, particularly a numeric suffix. A limited compatibility path accepts historic unquoted names such as `MyDetector,Unit1`, but an unquoted numeric suffix is ambiguous with partial settings and is rejected. Stored names are CSV-escaped.

Keep observation details in `config/user.ini` for future sharing/upload features:

- Station identifier, name, location, decimal-degree latitude/longitude (north/east positive), coordinate datum, and altitude in metres with its height reference.
- Observer name and optional public identifier (for example ORCID).
- Detector model, firmware version, settings units, calibration reference/date, orientation, scintillator dimensions, detector separation, shielding, and installation notes.

Blank values mean unspecified, not zero. Latitude and longitude must be finite numbers within their geographic ranges; altitude must be finite. `observatory_tz` describes the site timezone (for example `Europe/London`); recorded timestamps remain UTC. Observation details, observer contact information and calibration descriptions are **not copied into new detector data files**. No uploading is implemented.

The collector records the detector name and four settings on every raw event. Legacy settings are reread whenever an event needs them, so edits apply to subsequent events without a restart. Existing recorded settings are never overwritten during processing. At the user's explicit request, processing historical rows without settings now uses current `config/legacy.ini` values and logs an `ASSUMPTION` message; this is not proof of historical configuration. Missing/invalid required legacy settings cause an explicit failure rather than invented defaults.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Phase 2a development: named-detector collection and processing pilot

**Named-detector service activation is an explicit migration; historical archive
adoption and live RPi acceptance remain pending.** Explicitly selected
daily/period processing, reprocessing, isolated plotting, static web publication
and scheduled daily orchestration are implemented. The default installer refuses
to activate a named configuration. After checking every detector mapping,
identity and required `[legacy:LABEL]` settings, explicitly run:

```bash
sudo bash install/install.sh --activate-services
```

The installer stops and disables all old systemd-managed single/named collectors
before starting the configured mode. Stop any manually launched collectors
before using the flag as well. Without the flag, a named configuration or an
active/enabled named service being switched back to single-detector mode is
refused before package or configuration changes. This does not move or relabel
historical raw data, resolve same-day label changes, or prove the physical
detector assignments; verify those separately before a production cutover. See the
[implementation status and deferred work](docs/implementation-plan.md#phase-2a--concurrent-multi-detector-support-before-phase-3).
Legacy processors still refuse implicit named selection. Modern processing/plot
entry points dispatch to the named pipeline when `[detectors]` is configured.

#### Read-only production archive migration preview

Run [PreviewArchiveMigration.py](scripts/PreviewArchiveMigration.py) before
planning any historical adoption:

```bash
python3 -B scripts/PreviewArchiveMigration.py \
    --source-base "$HOME/UKRAA_PicoMuon" \
    --destination-base "$HOME/UKRAA_PicoMuon-pilot.arQgce"
```

Replace the destination with the intended installation root. Omit
`--destination-base` to preview adoption into the source installation's named
layout. The source defaults to `PICOMUON_BASE_PATH` (or the script's installation
root). JSON is printed to stdout; redirect it to a report **outside the archive**
if desired. Exit status is 0 for a conflict-free preview, 1 for reported
conflicts or a source/read failure, and 2 for invalid command-line arguments.

The mapping is deliberately specific: the user-confirmed production detector
`56/148/627`, USB serial `E660D4A0A7598522`, from **2026-10-10 onwards**, maps to
`Unit_1`. Both `data/raw/ACM0/YYYY/YYYY-MM/YYYY-MM-DD.txt` and
`data/raw/YYYY/YYYY-MM/YYYY-MM-DD.txt` are inspected. This is not a generic
name-based mapping tool and does not infer physical identity from event rows or
change USB configuration. Other named archives (including Unit_2/Unit_3 pilot
data) are not sources.

Every discovered completed-day event file is read in full: CSV shape, numeric
fields, finite temperature/pressure, recorded settings when present, expected
name, UTC date, path layout and strictly increasing timestamps are checked.
Signed timer wraps and event-counter resets are not treated as timestamp
ordering failures. Invalid rows stay in their original source and are reported
by reason/count with up to 20 line-numbered samples per file; nothing is silently
discarded or repaired. Legacy settings are not filled from current configuration.
Reports include byte-snapshot SHA-256 hashes, event totals and timestamp bounds.

Same-day source segments are ordered by their actual timestamp bounds, not by
directory name. Disjoint validated segments propose chronological concatenation;
any intersecting range (including a shared endpoint or duplicate copy) blocks
adoption. The October 13 split must pass these checks, not just an endpoint
inspection. Destinations under `data/raw/Unit_1/` are reported without being
created. Existing different destinations, blocked parent paths, symbolic links
and files changing during inspection are conflicts. A single byte-identical
destination is an `already_present` no-op; no implicit merge or overwrite is
proposed.

Today's **UTC** production file is always **provisional**, even if currently
well-formed; future-dated files are provisional and flagged as conflicts.
Neither is eligible for completed-day adoption. Rejected files are listed in
`rejected_diagnostics`, never counted as events, with separate proposed
`Unit_1/rejected/legacy_ACM0/` and `Unit_1/rejected/current/` destinations retaining
their source-layout provenance.

**There is no apply mode.** The preview does not create, rename, move, rewrite,
deduplicate, merge, or delete archives, nor touch configuration, services, cron,
logs or locks. It cannot certify an active file as final or authorize cutover;
rerun against the complete production archive with collectors stopped before
any separately approved adoption.

#### Fixed-batch source-preserving adoption tool (not production acceptance)

[AdoptUnit1Archive.py](scripts/AdoptUnit1Archive.py) is a **separate tool**; the
preview above still has no apply mode. Its default operation only reads files
and prints a manifest for the reviewed **October 10-20, 2026** Unit_1 batch:

```bash
python3 -B scripts/AdoptUnit1Archive.py \
    --source-base "$HOME/UKRAA_PicoMuon" \
    --destination-base "$HOME/UKRAA_PicoMuon"
```

To save that manifest, redirect stdout to a new report outside both installation
trees; do not overwrite an existing approval file. Review its **actual paths**
and compute its SHA-256 with `sha256sum`. Paths are installation-specific:
a desktop manifest is not an approval to apply on the Pi.

The eleven candidate hashes are pinned to the reviewed rehearsal. October 13
alone permits timestamp ordering of the exact reviewed pair of sources,
retaining one identical header and every event-line byte/occurrence; the output
hash is pinned too. All other days are byte-exact copies, including October 17's
mixed-format file. Eight rejected diagnostic files stay separate. Sources
outside this fixed batch, active files and other detectors are not adopted.
A changed event source or an unexpected extra segment is a hard stop, not a
reason to edit the pinned hashes. Diagnostic bytes are bound by manifest approval.

**Do not apply until backup/restore verification, a reviewed manifest, stopped
writers and a separately approved execution window are established.** Service
activation, cron, USB configuration and web publication are not part of adoption.
Production Linux durability/locking acceptance remains required before live use.
In a separate Linux/RPi code/test copy, run
`python3 -B -m unittest discover -s tests -p test_archive_adoption.py -v`.
The suite uses synthetic temporary archives, never production services or data.
Its native locking/directory-flush test must run without skipping. Windows tests
substitute Linux-only hooks and cannot certify Linux ownership or crash durability.

For a separately approved operation, `--apply` requires all of:

- `--manifest PATH`: the exact reviewed JSON file.
- `--approve-manifest SHA256`: approval of those exact bytes, not just equivalent JSON.
- `--run-dir PATH`: a new/private run directory outside both installation trees,
  whose parent already exists on the destination filesystem.
- `--backup-verified`: operator confirmation that an independent backup **and**
  isolated restore have been verified.
- `--writers-stopped`: operator confirmation that relevant source/destination
  writers remain stopped throughout. These flags attest prerequisites; they
  do not automatically back up data, stop services or detect all writers.

Apply/rollback refuse non-Linux platforms. The Linux implementation uses a
private run lock, flushes staged files and directories, verifies the entire batch
before promotion and uses hard links for atomic **no-clobber** promotion. This
requires a filesystem supporting hard links and directory `fsync`; no copying
or rename fallback is used. Run as the account owning the sources and destination.
New candidate files use mode 0644; existing identical files keep their metadata.

Existing byte-identical destinations are verified no-ops. Any different file,
symbolic link, blocked parent, unapproved manifest, changed source or conflicting
run evidence stops the operation. Exit status is 0 for successful manifest/apply/
rollback, 1 for a reported failure and 2 for invalid command-line arguments.

The run directory holds the approved manifest, staged files and flushed journal.
**Retain it after success:** stages are hard-linked to newly promoted files and
provide identity evidence for recovery. Do not edit stage contents or recursively
clean up that directory as an operational step.

A failed/partial batch is not success. Keep the evidence. A normal resume uses
the same exact manifest, approval hash and run directory and repeats all source,
stage and destination checks. An interrupted partial stage/journal or changed
destination identity requires manual recovery; the tool does not silently repair it.
A crash after a successful link but before its journal completion is recoverable
from the flushed intent and the shared stage/destination inode.

`--rollback` requires the same approval and safety flags. It quarantines only
unchanged files provably created by that run, leaving originals, unrelated files
and pre-existing no-ops alone. Changed hashes/identities stop rollback. It does
not remove whole directories, revert configuration or reconcile newly collected
named data. Once a run has quarantined files, do not resume apply from that run.

The accounting qualifications remain: 2,943 confirmed skipped sequence numbers
are not reconstructed; missing raw settings remain missing; historical processing
assumptions stay explicit; detector elapsed span includes short capture gaps and
is neither calibrated nor dead-time corrected. Adoption is not proof of complete
acquisition or production service readiness.

#### Isolated native-Linux Unit_1 processing rehearsal

After archive acceptance, the optional
[`examples/RehearseUnit1Processing.py`](examples/RehearseUnit1Processing.py)
checks named daily/period processing and plotting on Linux without changing the
production installation or the existing pilot. Upload the current repository's
complete `scripts/` folder to `$HOME/unit1-processing-code/scripts/` and this
runner to `$HOME/RehearseUnit1Processing.py`. The runner pins every script hash
and the approved archive manifest; it refuses a partial or stale code copy.

Run as the normal installation owner, with Bash, `flock`, and gnuplot installed:

```bash
python3 -B "$HOME/RehearseUnit1Processing.py" \
    --source-base "$HOME/UKRAA_PicoMuon" \
    --code-dir "$HOME/unit1-processing-code" \
    --manifest "$HOME/unit1-adoption-manifest.RpgaZH.json"
```

It copies the approved 19 raw files into a new private home-directory scratch
installation, uses only the verified Unit_1 mapping and historical settings
assumption, then runs the named pipeline for October 10–20 with
`--skip-downloads`. Any stored neutron/weather inputs for those dates are copied
read-only. Plots and generated pages are written only below the scratch
installation's `WWW/`; no live publication, collector, service, cron or
production processing command is invoked. The report validates all daily
product row counts and CPM/hourly totals, expected weekly completeness, plot
images, source hashes and production raw-file hashes before/after.

Keep the printed rehearsal directory even on failure and review
`verification.json` and `rehearsal-logs/`. The script deliberately does not
delete failed evidence or alter/clean the production installation.
If processing completed but a later validation check failed, upload the corrected
runner and use `--validate-existing "$HOME/unit1-processing-rehearsal.ID"` with
the exact retained scratch path. This mode rechecks raw inputs, products, plots,
logs and source hashes without rerunning processing; it writes a separate
`validation-recheck.json` and preserves the original failure report.

#### Unit_1 production cutover read-only preflight

Before preparing a separate production collection cutover, use
[`scripts/CollectUnit1CutoverPreflight.sh`](scripts/CollectUnit1CutoverPreflight.sh)
as `pi` to collect a fresh, private evidence bundle:

```bash
bash "$HOME/CollectUnit1CutoverPreflight.sh"
```

Upload the script to `/home/pi/CollectUnit1CutoverPreflight.sh` first. The
repository enforces LF endings for shell scripts (`.gitattributes`), but a
Windows file-transfer client can convert them to CRLF. In WinSCP, set the
default transfer mode to **Binary** and check that the transfer dialog also
says Binary. Do not use Text or Automatic/text conversion for shell scripts.
If a Bash script reports `$'\r': command not found` or `set: pipefail`, it has
CRLF endings; normalize the uploaded copy before running it:

```bash
python3 -c 'from pathlib import Path; p=Path.home()/"CollectUnit1CutoverPreflight.sh"; b=p.read_bytes(); assert b"\0" not in b; b=b.replace(b"\r\n",b"\n"); assert b"\r" not in b; p.write_bytes(b)'
python3 -c 'from pathlib import Path; p=Path.home()/"CollectUnit1CutoverPreflight.sh"; b=p.read_bytes(); assert b"\r" not in b; print("LF-only script confirmed")'
bash "$HOME/CollectUnit1CutoverPreflight.sh"
```

The collector verifies the expected Unit_1 udev identity, captures current
service, process, cron, timer and active-file/status evidence, checks the
approved historical manifest against a fresh read-only rebuild, and creates a
private backup of current production config/code/install files and relevant
systemd unit/cron definitions. It does not stop services, edit production
files, install units, or change cron. The evidence contains private
configuration and system scheduling information; keep it private and review
all command statuses before using it to plan a cutover.

The installed `PicoMuon@.service` is a template: the preflight captures its
definition but records runtime properties as not applicable. Concrete services
such as `PicoMuon.service` and `PicoMuon@Unit_1.service` also have their runtime
properties captured. If an older helper stopped with a template-unit error,
retain that incomplete evidence folder, upload the corrected helper in Binary
mode, and rerun it; the new run creates a separate evidence folder.

This preflight does not authorize or perform a cutover. In particular, do not
run the full installer as a service-switch shortcut: it also changes packages,
configuration, root cron, Apache and website content. The named service must
reference the production path, not the existing pilot. A single collector must
own the Pico at any time; stop and verify the old collector before starting the
named one. Preserve the old and new current-day files separately and report any
capture gap. Production processing, publication, cron changes and reboot
acceptance require separate review and approval.

#### Unit_1 staging only (no production cutover)

After accepting the `unit1-cutover-preflight.YtqHwx` evidence and the
`unit1-processing-rehearsal.yo2to17p/validation-recheck.json` processing recheck,
upload [`scripts/StageUnit1Cutover.py`](scripts/StageUnit1Cutover.py) in Binary
mode to `/home/pi/StageUnit1Cutover.py`. Run as `pi`, without sudo:

```bash
python3 -B "$HOME/StageUnit1Cutover.py"
```

The helper is deliberately pinned to those two reviewed evidence packages.
Keep the original Pi preflight and rehearsal directories in place. It checks
the full preflight hash index, accepted report and all 40 rehearsal scripts,
verifies backup contents, and requires all captured production config/code
files still to match the preflight. A mismatch is a stop for fresh review, not
permission to update pins or overwrite live files.

It creates a new private `/home/pi/unit1-cutover-stage.*` directory containing:

- `candidate/scripts/`: the complete accepted 40-file code baseline, including
  the shared plot-annotation helper; no production scripts are overwritten.
- `candidate/config/`: proposed Unit_1-only named USB configuration, a proposed
  `[legacy:Unit_1]` section copied from the current configured 200/100/200/100
  fallback, and the preserved private site configuration. The fallback is
  **provisional pending hardware-settings confirmation**, not an assertion of
  the actual hardware values. The existing `[usb]` and `[legacy]` sections are
  retained, but explicit Unit_1 selection is required in named mode.
- `units/PicoMuon@Unit_1.service`: a production-path-rendered candidate unit,
  checked using `systemd-analyze verify`, never installed or started. Its paths
  intentionally refer to production for later review, not to the staging area.
- Configuration-probe, shell-syntax and systemd validation logs with exit
  statuses, `SHA256SUMS` for candidate files, and `staging-report.json` recording
  proposed script changes and unresolved approval gates.

The helper validates Python syntax and configuration without starting the
collector, processing data, opening the serial device, downloading inputs,
publishing pages, running the installer, or calling `systemctl`. It checks
captured production-file hashes again afterwards. It does not copy raw data
or claim to validate collection continuity or device ownership.

Expect `STAGING COMPLETE (NOT CUTOVER APPROVAL)`. Preserve the staging folder
even on failure and privately download it for independent review. It contains
private configuration. Do not copy its candidate into production or enable its
unit. Hardware settings, exact deployment/recovery steps and the existing daily
cron's change to named processing/publication must still be separately resolved
and approved. No cron or publication change is part of staging.

#### Unit_1 collection trial runner: readiness check only

The original Unit_1 trial and return to single-mode have now been accepted.
The following trial workflow is retained for reference, **not** as the next
production step. Its absence checks deliberately reject the preserved trial
targets. Use the separate permanent readiness workflow below; do not rerun a
trial or delete its data/status/logs.

[`scripts/TrialUnit1Collection.py`](scripts/TrialUnit1Collection.py) prepares
readiness evidence for the fixed, reviewed `unit1-cutover-stage._u8vl_xk`
candidate. It requires the reviewed preflight, staging and rehearsal folders,
plus [`scripts/StageUnit1Cutover.py`](scripts/StageUnit1Cutover.py) beside the
runner. Upload both Python helpers in Binary mode to `/home/pi/`, **not** into
the production scripts directory.

The next authorized step is only the read-only check, as pi:

```bash
sudo -v
python3 -B "$HOME/TrialUnit1Collection.py" --check
```

`sudo -v` refreshes credentials for privileged evidence reads; do not run the
Python runner itself with sudo. Default invocation is also check-only. It
creates private evidence and a singleton lock in pi's home, and briefly takes
the existing PicoMuon cron-wrapper lock while checking that no wrapper job
is running.
The existing lock is opened read-only and exclusively locked using Linux
`flock`; no write access, ownership change, truncation or replacement is needed.
It does not edit production files/crontabs or stop/start units,
open the serial stream, run processing/downloads, or publish anything. It
verifies udev identity, device ownership using fuser, unit/scheduling inventory,
stage hashes/reconstruction, original code/config hashes, archive manifest,
candidate configuration using installed helpers, and advancing live raw/status.
Device-owner parsing accepts fuser's exact requested by-id label or its resolved
device label (for example `/dev/ttyACM0`); diagnostics or unknown labels remain
blocking failures.
Configuration modes must match the reviewed backup exactly: `USB.ini` is
`0644`, and `legacy.ini` is `0664`, both owned by pi's user/group. Publication
and recovery preserve those modes; unexpected permission changes still block
the run. Do not chmod production files merely to satisfy readiness checks.
Use an attended 08:00-18:59 UTC window, away from scheduled tasks or reboot
activity. Missing tools, a busy wrapper lock, stale data or evidence drift are
explicit failures for review, not permission to bypass the check.

On success expect `READY_FOR_REVIEW_NOT_AUTHORIZED`. Privately download the
whole printed evidence directory before any execution approval. Evidence
contains private configuration, recovery copies and scheduling details.

The runner also contains **separately gated, not yet authorized** trial and
interrupted-run recovery modes. A trial holds exactly the daily processing
cron line, stops single-mode, atomically deploys only the two configs and a
no-clobber concrete Unit_1 service, observes for ten minutes, then stops named
collection and restores single-mode. It does not deploy staged processing/
plotting scripts, alter the pilot template, change boot enablement or reboot.
Normal recovery verifies two minutes of single-mode advancement before
restoring cron. Named trial data remain separate and partial; neither layout
is claimed gap-free. Trial failure is distinct from successful restoration.
Startup waits up to 30 seconds for post-start raw and status updates before
applying steady-state freshness checks: a preserved single-mode status file
may legitimately still contain its pre-trial timestamp immediately after restart.

Every mutation is preceded by a durable state intent and commands retain
stdout/stderr/exit evidence. Catchable interruptions attempt guarded recovery.
A failed stop, unknown port owner, third-party edit or unverified restoration
halts progression; it must not start a second collector or blindly restore cron.
Power loss, SIGKILL and reboot cannot guarantee automatic recovery. An
interrupted run must be reviewed and recovered using its existing journal,
never by rerunning a trial; recovery across UTC rollover needs manual review.
This runner has no watchdog that survives power loss. The temporary named
configuration is **not** a supported unattended/reboot state.

Local tests cover disposable-host trial/recovery and injected failures;
they are not native Pi service/port acceptance. Passing `--check` is also not
execution approval. Do not use trial/recovery flags until the exact package,
effects, interruption limits and recovery have been explicitly approved.

#### Unit_1 permanent collection-only runner: readiness only

[`scripts/PermanentUnit1Collection.py`](scripts/PermanentUnit1Collection.py)
is a **separate** runner; it does not turn the temporary trial into a permanent
deployment. Implementation and disposable-host tests are not authorization
to change the Pi. Use a later attended UTC day than **2026-10-22**, in the
08:00-18:59 UTC window. Reconfirm Unit_1's OLED settings remain 200/100 top
and 200/100 bottom, and agree no concurrent edits, jobs or reboot.

Upload these three helpers together, in WinSCP **Binary** mode, beside one
another in `/home/pi/`, not into production:

- [`scripts/PermanentUnit1Collection.py`](scripts/PermanentUnit1Collection.py)
- [`scripts/TrialUnit1Collection.py`](scripts/TrialUnit1Collection.py)
- [`scripts/StageUnit1Cutover.py`](scripts/StageUnit1Cutover.py)

Keep the accepted preflight, stage and processing-rehearsal directories in
pi's home under their original names. Keep the accepted trial evidence too.
The only next step is the check, as pi:

```bash
sudo -v
python3 -B "$HOME/PermanentUnit1Collection.py" --check
```

Default invocation is also check-only. Expect
`PERMANENT_READY_NOT_AUTHORIZED`; privately download the **entire** printed
`unit1-permanent-collection.*` evidence directory for review. No permanent
apply command is authorized here. A failed check means stop and review its
evidence, not change permissions, remove existing data or bypass a pin.

Readiness reuses the pinned reconstruction, code/config/archive, physical
identity, process ownership, scheduling and advancing-collection checks.
It additionally inspects actual boot links and enabled states, validates
original restoration configuration, and preserves existing named status/log
bytes, hashes, permissions, ownership and error-log baseline in private
evidence. The October 22 trial raw/rejected hashes must remain unchanged;
cutover-day named raw/rejected must not exist. Preserved trial status cannot
count as new startup evidence. Checks write only private evidence and the
shared home singleton lock, briefly taking the existing cron-wrapper lock;
they do not alter production, boot state, cron or services, open serial,
process/publish data, or change the archive.

The separately gated apply mode uses a new permanent approval, never the old
trial approval. It holds exactly the daily processing job, disables old boot
enablement before stopping single-mode, publishes only the two configs and a
no-clobber concrete production Unit_1 unit, enables that instance without
starting it, then starts and observes it for ten minutes. Acceptance requires
new raw/status within 30 seconds, the old-last/new-first interval at most
120 seconds, advancing valid named rows/status, no new errors/rejected rows,
stable PID/no restarts, sole device ownership, correct boot links and unchanged
old/trial/historical data.

Successful commit **leaves named collection running and enabled**, single-mode
inactive/disabled with its definition retained, and daily processing held.
Weekly rotation and unrelated cron lines remain scheduled; the wrapper lock
is released after the attended operation. Production scripts, VERSION, user
configuration, pilot template and website are not deployed or changed.
Both cutover-day layouts are partial and remain separate. Existing website
products and old single-mode status will stop refreshing.

Before commit, catchable failures attempt guarded restoration of config,
owned unit publication, old boot state, single-mode health and then cron.
An interrupted operation must use its existing journal, not another apply.
Helper hashes, recovery copies and phase/boot state are checked on resume.
Unknown edits, unit inodes, device ownership, failed stops or restoration
checks halt recovery and keep processing held. Partial named data are retained,
with explicit validation errors and recovery event-spacing evidence.
`--recover` is only for uncommitted, same-UTC-day operations and requires the
separate permanent approval. A committed/commit-ready journal refuses recovery:
`--verify` observes retained collection without redeploying, restarting,
changing boot state or restoring cron. Verification failures do not roll back.
Error-log rotation or unexpected errors require review rather than silently
resetting the preserved baseline.

There is no automatic recovery guarantee for power loss, SIGKILL or reboot
mid-deployment, and no supported post-commit rollback flag. Such rollback
needs a separately reviewed procedure. Native Pi readiness, live acceptance,
next-day rollover and a separately approved reboot test remain required.
Do not resume daily processing/publication until its named-mode effects and
partial-day handling have been separately accepted.

#### Unit_1 processing restore and backfill: readiness only

[`scripts/RestoreUnit1Processing.py`](scripts/RestoreUnit1Processing.py) is a
separate runner for the committed `unit1-permanent-collection.k_xuwdb1`
cutover. It is not authorization to change the Pi. Upload it with the reviewed
[`scripts/processData.sh`](scripts/processData.sh) in WinSCP **Binary** mode
to `/home/pi/`, beside the three collection helpers, not into production.
Run as `pi`, without `sudo`, between 03:00 and 21:00 UTC:

```bash
sudo -v
python3 -B "$HOME/RestoreUnit1Processing.py" --check
```

Expect `RESTORE_READY_NOT_AUTHORIZED` and privately download the whole printed
`unit1-restore-processing.*` directory for review. The check repeats retained
collection and archive validation, then pins the deployment payload (the
rehearsal-validated `ProcessDaily.py`, `ProcessPeriod.py`, six day/week/month
plot scripts, new `plot-annotations.gp` and named-publishing `processData.sh`),
confirms named output trees, current logs and locks are writable by `pi`, and writes
`merge-manifest.json`. The manifest merges October 21-24 single-mode and named
raw into `data/raw/Unit_1` in time order, refusing overlapping segments,
unexpected settings or columns, incomplete rows and unpinned named inputs.
The named `log-PicoMuon.txt-0` through `-3` and `log-error.txt-0` through `-3`
regular-file archives need not be writable: weekly rotation preserves their
ownership, and processing leaves them untouched. Do not change their ownership
or permissions to satisfy readiness.

The separately approved apply (`--apply --approval UNIT1-RESTORE-PROCESSING
--reviewed <check directory>`) must run on the reviewed check's UTC day with an
identical manifest and plan. Holding the cron-wrapper lock, it backs up and
atomically replaces the merged raw and deployed scripts, reprocesses Unit_1
offline from 2026-10-10 to the day before yesterday, then runs the restored
daily `processData.sh` once for yesterday. That run publishes
`/var/www/html/detectors/` and refreshes the existing `temp/ACM0_*` plots from
Unit_1; `/var/www/html/index.html` must not change. Neutron values remain
empty while NMDB is unavailable; that download failure is tolerated. After
collector, pin and publication checks it restores the original crontab.

Failures before `COMMIT_READY` restore raw, scripts, bytecode and mtimes from
the evidence backup and keep processing held. Regenerated products and public
web files are not rolled back. Use `--recover <directory>` with the same
approval to finish or roll back an interrupted run; `--verify <directory>`
re-checks a committed restore, advancing collection and the latest published
day without changes.

For development, prepare a separate, empty pilot copy from the updated code,
without copying or moving the production archive:

```bash
cd ~/UKRAA_PicoMuon
PILOT=$(mktemp -d "$HOME/UKRAA_PicoMuon-pilot.XXXXXX")
cp -a scripts install VERSION "$PILOT/"
mkdir -p "$PILOT/config"
cp install/USB.ini.example "$PILOT/config/USB.ini"
cp install/legacy.ini.example "$PILOT/config/legacy.ini"
cp install/user.ini.example "$PILOT/config/user.ini"
echo "$PILOT"
```

Register each physical unit using its current device path. Registration resolves
the stable by-id alias and records its udev identity without probing the serial
stream. Check that the printed path/identity belongs to the intended unit.
The second registration preserves the first and the existing `[usb]` section:

```bash
PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ConfigureUSB.py" \
    --register East --device /dev/ttyACM0
PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ConfigureUSB.py" \
    --register West --device /dev/ttyACM1
```

Use `--serial-port /dev/serial/by-id/...` if alias discovery is unavailable.
Labels retain case, start with a letter/digit and contain at most 16
letters/digits, underscores or hyphens. `single` and `rejected` are reserved.
Duplicate labels ignoring case, duplicate USB identities and aliases resolving
to the same device are rejected. One or more entries in `[detectors]` selects
named mode; even one named unit requires `--detector LABEL`. An optional
`--detector-name "known current name"` enables cross-unit name checks; USB
identity, not the mutable detector name, remains authoritative.

Edit the pilot's `config/legacy.ini` to add **complete, correct** sections for
each old-firmware unit, for example:

```ini
[legacy:East]
threshold_top = 200
reset_top = 100
threshold_bottom = 200
reset_bottom = 100

[legacy:West]
threshold_top = 250
reset_top = 120
threshold_bottom = 250
reset_bottom = 120
```

These are examples, not measurements. Named units do **not** inherit from
`[legacy]`, another label or `[DEFAULT]`; a missing/incomplete section stops that
collector when an old-format event arrives. Detector-provided settings take
precedence, so new firmware does not require a legacy section. The existing
single-detector mode continues to use `[legacy]`. Public observation details
remain common to the pilot installation for now.

Before live testing, stop any production collector using either device
(`PicoMuon.service`, `PicoMuonACM0.service` or a manually started process).
**Never run production and pilot collectors against the same serial port.**
This introduces an intentional gap in production capture; pilot data will not
automatically merge back into the archive. Keep the test short and preserve
the pilot data for any later explicit migration.

In one terminal, run East in the foreground, saving its log output:

```bash
mkdir -p "$PILOT/logfiles/detectors/East" "$PILOT/logfiles/detectors/West"
PICOMUON_BASE_PATH="$PILOT" python3 -u "$PILOT/scripts/GetDataRaw.py" --detector East \
    >> "$PILOT/logfiles/detectors/East/log-PicoMuon.txt" \
    2>> "$PILOT/logfiles/detectors/East/log-error.txt"
```

In a second terminal, set `PILOT` to the same printed directory and run the
equivalent command with `West`. Use Ctrl+C to stop each foreground collector
before restarting the production service. Expected pilot outputs:

- `data/raw/East/YYYY/YYYY-MM/YYYY-MM-DD.txt` and the equivalent West path.
- `data/raw/East/rejected/YYYY-MM-DD.txt`, independently for each unit.
- `data/status/East/current.json` and `data/status/West/current.json`.
- The correct unit's fallback settings on every event. The folder identifies
  the stable label; a detector-name change does not change that folder.

For a third detector, repeat registration and legacy setup with a third stable
label and its current device node (for example `Third` and `/dev/ttyACM2`), then
run its collector in a third terminal. ACM numbers are only used to register
the devices; subsequent collection uses their stable by-id identities.

An identity mismatch is logged and retried with backoff **without opening the
serial port**. A name registered to another unit stops collection with an
explicit cable-swap error. Serial access is exclusive; disconnecting one unit
must not stop the other. Reconnecting/swapping ACM enumeration must still use
the same stable aliases and folders. Two units may require a powered USB hub.

`install/PicoMuon@.service` supplies a per-label service with separate log paths
and conflicts with the old single-collector services. The installer enables
instances only after the explicit `--activate-services` opt-in described above.
Do not rename labels, move raw files or adopt pilot data into production yet:
historical mapping and same-day transitions remain pending.
Raw data is never migrated by registration.

#### Explicit offline processing in the pilot

After collecting a completed UTC day in the pilot, process each label explicitly:

```bash
PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ProcessDaily.py" \
    --detector East --date 2026-10-18
PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ProcessPeriod.py" \
    --detector East --date 2026-10-18 --period week
PICOMUON_BASE_PATH="$PILOT" bash "$PILOT/scripts/reprocessData.sh" \
    --detector East --from 2026-10-17 --to 2026-10-18 --dry-run
```

Use dates for which that detector has pilot data; repeat for `West` and the
third label. Remove `--dry-run` only when ready to regenerate derived products.
Reprocessing does not copy, move or modify raw data, and excludes today's
partial UTC file. It discovers only the selected detector's date hierarchy,
not rejected files or another detector's archive. This is **not** the
historical archive adoption/mapping tool, which remains deferred.

Named outputs are:

- `data/{cpm,adc,day,week,month,3month,6month,year}/detectors/LABEL/YYYY/YYYY-MM/YYYY-MM-DD.txt`
- `data/hour/detectors/LABEL/YYYY/YYYY-MM/YYYY-MM-DD.csv`
- `data/daily/detectors/LABEL/summary.csv`
- Reprocessing logs in `logfiles/detectors/LABEL/`.

The `detectors/` product namespace prevents even a label such as `ACM0` from
overwriting old single-detector products. Existing single-detector paths are
unchanged. NMDB input remains shared for co-located detectors.

Direct daily/period processing and reprocessing require `--detector LABEL`
even with only one registered unit. Missing named raw input is an error, never a fallback to unlabelled,
legacy ACM0 or another detector's files. Missing period history is logged as
a skip using the existing completeness rule. Missing historical settings use
only `[legacy:LABEL]`, with the assumption logged; recorded settings win.
Daily and period writers share a nonblocking per-detector processing lock,
including across different dates because they share a summary. A busy lock
is an explicit failure; another detector can still process. Reprocessing also
prevents overlapping batches for the same label. Temporary product files live
beside the detector-specific destination.

Named reprocessing now supports `--plot`; it renders only that label's products
and does not publish web pages. Failed named reprocessing never plots stale
products. A named period skipped for insufficient history removes any stale
product for that target date.

#### Named daily plots and web pilot

Run as the installation's file owner, not with `sudo`. Bash, gnuplot and `flock`
are required on the RPi, alongside the existing Python dependencies. First test
one completed day without network downloads:

```bash
PILOT="/home/pi/UKRAA_PicoMuon-pilot.arQgce"  # use your existing pilot directory
PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ProcessDetectors.py" \
    --detector Unit_2 --date 2026-10-19 --skip-downloads
PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ProcessDetectors.py" \
    --detector Unit_3 --date 2026-10-19 --skip-downloads
```

Use your registered labels/dates. `--skip-downloads` uses stored site inputs;
absent NMDB/weather values remain unavailable, not invented. Without that flag,
shared neutron/weather inputs are downloaded once for the requested date,
not once per detector. Weather still requires its configuration opt-in.
Use `--plots-only` to render and publish existing processed products without
reprocessing raw data.

All six plot families show their actual generation date/time in UTC, rather
than a promised daily update time. Daily/week/month muon-flux axes use
`[Observatory] observatory_location` from `config/user.ini`; if blank or absent,
the axis has no location suffix. Transfer `scripts/plot-annotations.gp` together
with the plotters.

Minute and five-minute count products use `nan` for unobserved time bins, so
gnuplot omits them from curves, frequency histograms and count statistics.
Observed bins retain genuine zero counts, including a zero-count channel when
another channel recorded events. Observation is inferred from events and the
existing continuous accounting intervals; resets, name/clock changes and gaps
of at least one hour do not bridge missing bins. This is not proof of full-bin
exposure. ADC spectra and hourly/daily accounting totals retain their numeric
count semantics. Period aggregation preserves missing versus observed-zero
counts without changing product columns.

To correct existing zero-filled products, rerun the full selected-detector
pipeline for the archived day (not `--plots-only`). Raw files are not changed:

```bash
(
    set -e
    for label in Unit_2 Unit_3; do
        PICOMUON_BASE_PATH="$PILOT" python3 "$PILOT/scripts/ProcessDetectors.py" \
            --detector "$label" --date 2026-10-19 --skip-downloads
    done
)
```

Omitting `--detector` attempts **all configured labels** independently. A failed
or busy detector is logged and later detectors continue; the overall command
returns nonzero if any stage fails. In the current three-unit pilot, Unit_1 has
no pilot raw archive while it remains on production: an all-unit run will
therefore report that failure while still processing Unit_2 and Unit_3.

The existing shell entry points also dispatch named configurations:

```bash
PICOMUON_BASE_PATH="$PILOT" bash "$PILOT/scripts/processData.sh" \
    --date 2026-10-19 --detector Unit_2 --skip-downloads
PICOMUON_BASE_PATH="$PILOT" bash "$PILOT/scripts/plots.sh" \
    --date 2026-10-19 --detector Unit_3 --skip-downloads
```

When updating an existing pilot, transfer the updated repository to the RPi
first, run the regression suite from that checkout, and copy the scripts
together so Python, shell and gnuplot interfaces stay aligned:

```bash
cd ~/UKRAA_PicoMuon
python3 -m unittest discover -s tests -p 'test_*.py'
bash tests/test_named_plots.sh
bash tests/test_logging.sh
bash tests/test_publish.sh
# Continue only if the tests above pass.
cp -a scripts/. "$PILOT/scripts/"
```

This does not replace pilot configuration or data, and no collector restart is
needed for the plot/pipeline update. Keep the existing pilot directory rather
than creating another one. Inspect each unit's pipeline/error logs after running.

With no date, the pipeline uses yesterday UTC; today/future dates are rejected.
The daily chain processes day/week/month/3-month products, renders the six plot
families, and publishes the available day/week/month images. Period completeness
rules remain unchanged. All detector-specific outputs are isolated:

- Archived plots: `plots/CATEGORY/detectors/LABEL/DATE_*.png`.
- Latest plots: `temp/detectors/LABEL/yesterday/` and `temp/detectors/LABEL/periods/`.
- Local web index: `WWW/detectors/index.html`.
- Per-unit page/snapshot: `WWW/detectors/LABEL/{index.html,status.json}`.
- Date-qualified images: `WWW/detectors/LABEL/YYYY-MM-DD/`.
- Pipeline/error logs: `logfiles/detectors/LABEL/`; weekly rotation retains
  separate archives for each existing unit.

The page states the processed UTC date and explicitly labels collector status
as a **publication-time snapshot, not a live connection indicator**. Missing
period history is shown as unavailable. Missing/failed plots cannot be reused
as fresh images; publication validates the complete expected image set first.
A failed run leaves the previous dated page rather than claiming a fresh run.
Per-unit pipeline locks prevent overlapping processing/plot jobs; processing
locks also protect plotting from concurrent direct writers. Named shared-input
downloads are serialized.

Local output is **not automatically served by Apache**. An optional
`--web-root /path/to/existing/writable/webroot` also publishes its `detectors/`
subtree, leaving the existing root `index.html` and legacy image URLs untouched.
Do not enable production cron, service migration or the installer yet. These
entry points are scheduler-compatible, but no pilot cron job is installed.

Run `python3 -m unittest discover -s tests -p 'test_*.py'` from the updated
repository. Named-detector tests use isolated data and simulated streams; the
POSIX exclusive-access test uses a local pseudo-terminal, not your detector.
With gnuplot installed, the suite also renders real plots and exercises the
Linux shell pipeline. Run `bash tests/test_named_plots.sh`,
`bash tests/test_logging.sh` and `bash tests/test_publish.sh` for shell regressions.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Raw event columns

Raw files have this header:

```text
RPiTimestamp,Event,EventCount,ADC,Elapsed_ms,Dead_ms,Temp_C,Pres_hPa,DetectorName,threshold_top,reset_top,threshold_bottom,reset_bottom
```

| Column | Meaning |
| --- | --- |
| RPiTimestamp | Raspberry Pi UTC timestamp when the event was received |
| Event | Top (`T`), bottom (`B`), or coincidence/muon (`C`) event |
| EventCount | Detector's event counter |
| ADC | Event pulse ADC value |
| Elapsed_ms | Detector's reported elapsed-time counter, in milliseconds |
| Dead_ms | Detector's reported dead-time counter, in milliseconds |
| Temp_C | Detector temperature in degrees Celsius |
| Pres_hPa | Detector pressure in hectopascals |
| DetectorName | Detector identification string |
| threshold_top | Top detector threshold setting |
| reset_top | Top detector reset setting |
| threshold_bottom | Bottom detector threshold setting |
| reset_bottom | Bottom detector reset setting |

New events always contain these 13 columns, including the Raspberry Pi timestamp. Readers accept old 9-column events and the new 13-column events, with or without headers. Existing event bytes are not rewritten: on the first new write to an old-format or headerless file, the collector appends the extended column header before new events. Such a transition file can contain both row widths and repeated headers. PicoMuon readers ignore both header formats and historical `#` comment lines.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Metadata in processed and shared data

Detector metadata is stored in ordinary CSV columns on every row, not in a JSON preamble. The exact layouts are:

```text
ADC_Value,Count_T,Count_B,Count_C,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom
DateTime,Count_T,Count_B,Count_C,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom
DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom,neutrons,station
DateTime,T,B,C,live_seconds,missing_events,temp,pres,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom,neutrons,station
```

The third layout is shared by day, week, month, 3month, 6month and year files. The hourly layout retains `pres` after `temp`. Neutron columns are lowercase `neutrons,station`; the station identifies the NMDB source (currently OULU), not your local observatory. A CPM example is:

```text
DateTime,Count_T,Count_B,Count_C,detector_name,threshold_top,reset_top,threshold_bottom,reset_bottom
2026-10-17 00:00:00,132,130,18,56/148/627,200,100,200,100
```

Counts, numerical averaging and the number of bins are unchanged. Metadata comes from events contributing to each bin (for ADC, events contributing to that ADC channel). If values differ within a bin, only the differing fields contain `mixed`; counts remain combined in one row. A bin without detector events uses the day's detector/settings combination, or `mixed` if the day itself varies. An entirely empty raw file yields blank detector metadata. A period bin without detector events similarly uses the available period's detector/settings combination. Missing neutron data yields `nan` and a blank station; stations combined within a period bin are marked `mixed`.

Periods read both the new day columns and older seven-column day files, including historical JSON comments. Old day files lack a detector-name column, so that field remains blank unless they are first regenerated from raw events. Their missing settings use the same explicit legacy assumption. Legacy neutron files without a station header are treated as OULU (the existing downloader's fixed station), with that assumption logged.

`data/daily/summary.csv` retains its existing numerical schema and no longer writes JSON comments. Old processing script names delegate to the shared daily/period writers: daily compatibility scripts rebuild all daily products rather than appending duplicate rows. Week/month compatibility scripts use the shared completeness rule.

`EventCount` is independent for T, B and C. Missing-event QC compares successive
counts of the **same event type** within a run segment, not adjacent mixed-type
rows. Positive gaps contribute `current - previous - 1`, including gaps larger
than 1,000. These are inferred counter gaps, not a measurement of events lost
while the detector was powered off; counts before a segment's first observation
are unknown.

Hourly `live_seconds` uses the detector's **shared** elapsed clock once across
successive events of any type, with modulo-32-bit unwrapping. A same-type counter
decrease, detector-name change, elapsed reset/step of at least one hour, UTC gap
of at least one hour or backwards UTC timestamp starts a new accounting segment.
That boundary contributes neither exposure nor missing events; all three
counter baselines are cleared together. Normal segment boundaries are logged.
Intervals crossing UTC hours are split proportionally using receiver timestamps.
No exposure is invented before the first or after the last event in a daily file.
Device/receiver clock differences and USB buffering can yield hourly values
slightly above 3,600 seconds; measured device time is not silently clamped.
No dead-time correction is applied. The existing `ValidHours`/`CoveragePercent`
summary still means hours containing events, **not** elapsed exposure coverage.

After updating the processor, regenerate affected daily products/summaries
from unchanged raw files to correct older missing-event and exposure values.
The collector does not need restarting for this processing-only fix.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Neutron file attribution and headers

New neutron downloads include readable NMDB/source, station, UTC and request-URL comments followed by:

```text
DateTime,Pressure_hPa,Uncorrected,PressureCorrected,EfficiencyCorrected
2026-10-17 00:00:00,1010.59,90.8,98.202,98.388
```

Readers accept both headered and older headerless neutron files. The weather attribution/header is unchanged. Plot orchestration selects neutron column 12 for new day/period files and column 7 for historical files, so existing products can still be viewed before reprocessing.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Upgrading existing data files

Stop the collector before replacing its scripts, copy the updated scripts, plots and tests together, then restart. New raw events no longer emit JSON comments; existing raw files are not automatically rewritten. Regenerate processed files with `reprocessData.sh` to get the new columns and remove their obsolete JSON comments. This leaves raw events untouched. Check the current legacy settings before backfilling, since they are now the explicit assumption for historic events that lack settings.

Optional cleanup removes only `# picomuon_metadata:` lines from existing raw files. Preview first:

```bash
python3 scripts/AddRawHeaders.py --remove-metadata
```

Stop **all** collectors and any other raw-file writers before applying:

```bash
sudo systemctl stop PicoMuon.service
python3 scripts/AddRawHeaders.py --remove-metadata --apply --collectors-stopped
sudo systemctl start PicoMuon.service
```

Use the appropriate service name(s) for your installation. The confirmation flag is not an automatic service check. Each changed raw file gets a byte-exact `*.txt.pre-metadata-removal.bak`; event/header bytes, other comments and timestamps are preserved. Rejected files are excluded. Re-running skips clean files; a conflicting backup stops migration instead of being overwritten. Keep sufficient space for backups and a temporary copy of the largest file.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Adding headers to historic and current raw files

Copy the revised scripts (including `picomuon_common.py`, both raw collectors, the raw readers, and `AddRawHeaders.py`) to the RPi first. Do not run this migration while a collector or another process is writing raw files.

From the installation directory, preview which files need a header:

```bash
cd ~/UKRAA_PicoMuon
python3 scripts/AddRawHeaders.py
```

Stop collection, then confirm it is stopped:

```bash
sudo systemctl stop PicoMuon.service
systemctl is-active PicoMuon.service
```

The status must be `inactive`. If the legacy `PicoMuonACM0.service` is running, stop that too. Also stop any manually launched collectors. Run the migration as the account that owns the data:

```bash
python3 scripts/AddRawHeaders.py --apply --collectors-stopped
```

`--collectors-stopped` is your confirmation, not an automatic service check. The migration includes today's file, historic files and detector-labelled subfolders under `data/raw/`. Files in `data/raw/rejected/` are excluded because malformed serial rows do not have a fixed column schema.

Each changed file gets a byte-exact `*.txt.pre-header.bak` backup alongside it. The original event bytes are preserved unchanged after the new header, and replacement is atomic per file. The migration chooses the old or extended header to match the first event; it does not add missing settings or invent historical metadata. Keep enough free disk space for the backups and a temporary copy of the largest file. Re-running skips files that already have either recognised header. If a backup already exists for a headerless file, the migration stops rather than overwriting it; investigate before retrying.

Only after the migration succeeds, restart collection and check it:

```bash
sudo systemctl start PicoMuon.service
systemctl is-active PicoMuon.service
head -n 2 "data/raw/$(date -u +%Y/%Y-%m/%F).txt"
```

The service should be `active`. If using a detector label (including the legacy `ACM0` layout), include that folder between `raw/` and the year in the last command. Raw data collection pauses during migration; no missed events can be recovered by this procedure. There is no need to reprocess data just because a header was added.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Outdoor temperature on CPM plots

The top, bottom and coincidence CPM plots can overlay **modelled outdoor air
temperature at 2 m** from [Open-Meteo](https://open-meteo.com/), on the right-hand
axis in degrees Celsius. This is not a local thermometer reading, the detector's
internal temperature, or upper-air effective temperature for muon corrections.
Counts remain on the left-hand axis, with the existing colours and PNG filenames.
The temperature axis auto-scales so values outside a fixed seasonal range remain visible.

Use the existing observatory coordinates in `config/user.ini` and add a
`[weather]` section to enable downloads. For the requested location, 51.6 N,
0.10 W, the relevant entries are:

```ini
[Observatory]
observatory_latitude = 51.6
observatory_longitude = -0.10

[weather]
enabled = true
```

Edit the existing `[Observatory]` section rather than adding a duplicate, and
preserve the other observation fields. There is no separate weather configuration
file. If you used the initial `weather.ini` version, transfer its coordinates to
these existing observatory fields and its enabled setting to `[weather]` in
`user.ini`; `weather.ini` is no longer read.

The installer merges a disabled weather default from `install/user.ini.example`
for existing installations and preserves existing coordinates and preferences.
Older user configurations without `[weather]` keep downloads disabled.
The local user configuration is ignored by Git. Coordinates
are sent to Open-Meteo and recorded in the downloaded product; choose appropriate
location precision.

`processData.sh`, `plots.sh` and `reprocessData.sh --plot` fetch weather for their
plot target date. To download or refresh just one UTC day:

```bash
python3 scripts/GetDataWeather.py --date 2026-10-17
bash scripts/plots.sh 2026-10-17
```

Hourly data is written atomically to `data/weather/YYYY/YYYY-MM/YYYY-MM-DD.txt`.
Recent completed days use the Forecast API; dates more than five days old use
the Historical Forecast API (model-dependent coverage, generally from 2021/2022).
No API key or additional Python package is needed for the free, non-commercial
service. Missing hourly temperatures stay as gaps, not zeroes; all-missing or
invalid responses fail explicitly. Download failures reach `log-error.txt` and
make the orchestration exit unsuccessfully, without stopping the other plots.
Previously stored weather for the target date can still be plotted; without it,
the wrapper explicitly logs that CPM plots contain counts only. Disabling downloads
does not delete previously stored weather.

For a WinSCP update, upload `GetDataWeather.py`, `logging.sh`, `processData.sh`,
`plots.sh`, `reprocessData.sh`, the revised CPM/day/week/month gnuplot scripts and
`WWW/index.html`, then update `config/user.ini` as above on the Pi. No raw-data
reprocessing or collector restart is required. Run `plots.sh` for a completed day
to verify the overlay; the next daily run publishes the updated images. Update
the served web page as well if you deploy it separately.

Keep the full NMDB/Oulu acknowledgement below neutron-containing plots on the
website. A short credit is also embedded in day/week/month images so that it
survives downloading and sharing. CPM images with weather contain an Open-Meteo
credit; the web page adds links to the provider and
[CC BY 4.0 licence](https://creativecommons.org/licenses/by/4.0/).
Keep these credits with any exported or republished images.

[Back to Contents](#contents)

---

&nbsp;
<!-- =============================================================================== -->
### Log format

New runtime entries use UTC timestamps and an aligned process name:

```text
2026-10-16 17:44:19 UTC : ProcessDaily.py            : Completed processing for 2026-10-15
2026-10-16 17:44:20 UTC : PlotDataWeekACM0.gp        : Skipped: no week product for 2026-10-15 (see period-processing entries)
2026-10-16 17:44:21 UTC : PlotDataDayACM0.gp         : ERROR: command failed (exit code 1)
```

- `logfiles/log-PicoMuon.txt` contains normal progress, completions, summaries and expected skips.
- `logfiles/log-error.txt` contains errors, warnings and command diagnostics.
- Python uses the shared logging functions in `scripts/picomuon_common.py`. Shell scripts use `scripts/logging.sh`, which also runs external commands, formats each output line and preserves failure exit codes. Already formatted lines are not prefixed a second time. Python tracebacks retain their details with the same prefix on every line.
- The collector service routes stdout/stderr to the two logs. Daily processing, reprocessing, plotting and cron use the shared command wrapper for the same routing, including gnuplot diagnostics.
- Plot Started/Completed/Skipped messages come from the shell wrapper rather than the gnuplot files. Missing week/month products are skipped; missing required daily products and non-zero gnuplot exits are failures. Failure counts and final exit statuses reflect these failures.
- Use `bash scripts/plots.sh [YYYY-MM-DD]` to run plots with logging. Reprocessing with `--plot` uses its requested end date for plot inputs, titles and time ranges.
- Historic log entries are not rewritten.

For a WinSCP update, upload the revised shell and Python scripts together with all six `PlotData*.gp` scripts; the plot scripts and wrapper must be updated together. Restart `PicoMuon.service` after updating `picomuon_common.py` so the running collector loads the revised logging helper. No raw-data migration or reprocessing is needed just for the logging update.

Three plots will be created:
* counts per minute
* frequency of counts per minute
* frequency of ADC values recorded

A request will be made to [NMDB](https://www.nmdb.eu/) via NEST to get the previous days recorded neutron count, this data will be overlaid onto the day / week / month % deviation counts per minute graphs.

These will appear as the required amount of data is recorded by the detector

A simple web server and web page is set up on your RPi so that you can view your detector's results on your desktop PC and/or smart phone when connected to your home network.

To access the webpage on your desktop PC or your smart phone…

1.	Open your preferred web application (Safari, Chrome, Firefox, etc.).

2.	In the search bar type the following and press enter
```
http://rpi4-UKRAA.local
```

This will take you to the web page for your detector, displaying yesterday’s events graphs.

NOTE: if you have a different **hostname** for your RPi, change the search bar entry to…

**http://_hostname_.local**

Where *hostname* is the hostname for your RPi setup.

---

&nbsp;
<!-- =============================================================================== --> 
## Check GetDataRaw.py is running

1. To check the **status** of your service, type the following command and press enter.
```
sudo systemctl status PicoMuon.service
```

&nbsp;

2. To **start** your service, type the following command and press enter.
```
sudo systemctl start PicoMuon.service
```

&nbsp;

3. To **stop** your service, type the following command and press enter.
```
sudo systemctl stop PicoMuon.service
```

&nbsp;

4. To **enable** your service, type the following command and press enter.
```
sudo systemctl enable PicoMuon.service
```

&nbsp;

5. To **disable** your service, type the following command and press enter.
```
sudo systemctl disable PicoMuon.service
```

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
## Updating your software

1. Log into your Raspberry Pi4/5 using VNC.


2. Open your web browser, type the following command into the URL window and press enter
```
https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2FUKradioastro%2FUKRAA_PicoMuon%2Ftree%2Fmain%2Fupdate
```

![img_05](images/RPi_imager_05.PNG)

This will download a zip file of the updated code to your RPi **~/Downloads** folder.

![img_06](images/RPi_imager_06.PNG)

Close your web browser.


3. Open **File Manager** and navigate to **~/Downloads**. You should see the zip file you just downloaded.

![img_07](images/RPi_imager_07.PNG)

4. Double click on the downloaded zip file **UKradioastro UKRAA_PicoMuon main update.zip**.  This will open the RPi **xarchiver** utility.

![img_08](images/RPi_imager_08.PNG)

5. Now click on the **extract** icon on the menu ribbon.

![img_09](images/RPi_imager_09.PNG)

6. Change **Extract to:** from **/tmp** to **~/Downloads**, then click on the **Extract** button

![img_10](images/RPi_imager_10.PNG)

Close the RPi xarchiver utility.

7. You should now see a new unzipped folder in the Downloads folder

![img_11](images/RPi_imager_11.PNG)

8. Select **UKradioastro UKRAA_PicoMuon main update** folder and rename **update** (Right click mouse to bring up function).

![img_12](images/RPi_imager_12.PNG)

9. Select the **update** folder and copy (Right click mouse to bring up function).

10. Navigate to the PicoMuon directory, **~/UKRAA_PicoMuon**, and paste the **update** folder

![img_14](images/RPi_imager_14.PNG)

Close the **File Manager** window

11. Open a terminal window and type the following command and press enter
```
cd ~/UKRAA_PicoMuon/update
```

![img_15](images/RPi_imager_15.PNG)

This will take you to the **update** directory inside **~/UKRAA_PicoMuon**

12. Type the following command and press enter
```
chmod +x *.sh
```

![img_16](images/RPi_imager_16.PNG)

This will make the **update.sh** script executable.


13. Type the following command and press enter
```
sudo bash update.sh
```

![img_17](images/RPi_imager_17.PNG)

This will run the update script.

14. That's it!  You should see the following...

![img_18](images/RPi_imager_18.PNG)

The updated code is now set; it will get the data from the detector, process yesterdays data, plot yesterdays data and post yesterdays plots to your intranet web page once per day, at 9.30am in the morning.

&nbsp;

---

&nbsp;
<!-- =============================================================================== --> 
### License

MIT License

Copyright (c) 2024 UKRAA

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the **Software**), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED **AS IS**, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


---

&nbsp;
<!-- =============================================================================== --> 
### Contact us

Please send an e-mail to picomuon@ukraa.com