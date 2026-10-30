# Two-plus detectors on one Raspberry Pi: implementation and test report

**Project:** UKRAA PicoMuon  
**Report date:** 30 October 2026  
**Evidence cut-off:** 30 October 2026, 12:11 UTC  
**Status:** Two collectors running; separate processing arrangements installed; final multi-detector deployment acceptance remains open.

## 1. Executive summary

The work establishes how multiple PicoMuon detectors can share one Raspberry Pi without mixing their identities, event streams, settings, processing products or published results. It deliberately separates software implementation, disposable rehearsals, live collection acceptance and final production acceptance.

The current installation runs **Unit_1 in production and Unit_2 in a separate pilot installation on the same Raspberry Pi 4**. This is not yet a consolidated production installation managing every detector. Unit_3 has passed a read-only readiness review but remains inactive.

The principal results are:

- Stable USB serial/by-id mappings and explicit detector selection prevent reliance on changing `/dev/ttyACM*` enumeration.
- Independent collectors, raw/rejected files, status snapshots, logs, processed products and web pages have been exercised. A physical Unit_2 reset reconnected without interrupting Unit_1 in the observed interval.
- Genuine complete-day data for 29 October were validated: **417,650 events for Unit_1 and 430,660 for Unit_2**, with no observed counter discontinuities.
- An initial download-inclusive two-unit run took **130.895 seconds**, returned failure because NMDB was unavailable, and did **not** meet the strict **under-120-second** target.
- Profiling identified repeated metadata work. A narrow optimization reduced combined unprofiled daily processing from a mean **92.577 to 68.045 seconds**, approximately **26.5%**, while all ten daily products/summaries remained byte-identical.
- The optimized offline daily/eligible-period/plot/publication chain completed in **78.525 seconds** with zero failures. This excludes downloads and unexercised long-history stages.
- The verified two-file optimization was deployed to both live installations after backup, fault-injection tests, native Linux rehearsal and separate approval. Neither collector was restarted.
- Unit_2's 29 October daily products were seeded and checked. Its incorrect pilot weather coordinates were corrected with approval. A separate **01:30 host-local** daily job now explicitly selects Unit_2, leaving Unit_1's existing **01:15** job unchanged.

**Still pending:** the first actual Unit_2 scheduled run, a successful fresh download-inclusive two-unit timing test, sufficient genuine period history, live ACM-renumbering acceptance, three-unit acceptance and any final consolidation/full-installer acceptance. Passing software and continuity tests does not establish detector efficiency, calibration or scientific accuracy.

## 2. Scope, evidence and acceptance rules

### 2.1 Sources and limitations

This report combines the implementation record, repository tests/source, saved Raspberry Pi evidence directories and operator terminal output supplied during the work. Earlier work is described from dated records; the 28-30 October results include the detailed operating sequence in the current review.

Commands on the Pi were run by the operator through their terminal. The local development environment was Windows; SSH authentication was not available to the assistant. Windows tests with mocked Linux primitives are therefore explicitly distinguished from actual Pi tests.

The older [implementation plan](implementation-plan.md) records development status at several earlier dates. Statements there such as "pending adoption" describe those snapshots, not necessarily the final state recorded here. This report does not retrospectively claim that every earlier pending item has passed.

### 2.2 Rules used throughout

1. Preserve original raw data and keep rejected rows as separate diagnostics.
2. Bind stable labels to verified hardware identities; do not derive archive paths from mutable firmware names or transient ACM numbers.
3. Keep Unit_1's production collection and established history safe while additional units are tested.
4. Require explicit selection for direct named processing. Never fall back silently to another unit's archive.
5. Test completed UTC days. Do not treat partial days as full coverage.
6. Preserve genuine missing observations as missing; do not manufacture history or lower coverage thresholds to obtain a pass.
7. Measure the required complete workload. A single-unit result, profiler duration or offline result cannot prove download-inclusive multi-unit timing.
8. Use separate authorization for readiness, rehearsal and live mutation; retain backups and fail closed on unexpected drift.

The exercised history gates were **7/7 days for week, 28/31 for month and 81/90 for 90-day processing**, under the existing 90% rule. Eligibility and within-day coverage still matter; the existence of files alone is insufficient.

## 3. Hardware, identities and software layout

### 3.1 Verified detector assignments at the cut-off

| Label | Pico USB serial | Current ACM device | Firmware DetectorName | Settings: top threshold/reset; bottom threshold/reset |
|---|---|---|---|---|
| Unit_1 | E660D4A0A7598522 | ttyACM0 | 56/148/627 | 200 / 100; 200 / 100 |
| Unit_2 | E660D4A0A7571639 | ttyACM1 | Unit-2 | 200 / 100; 200 / 200 |
| Unit_3 | E66358986351AF2C | ttyACM2 | Unit-3 | 200 / 100; 200 / 100 |

The stable device path is `/dev/serial/by-id/usb-Raspberry_Pi_Pico_SERIAL-if00`, substituting the serial above. ACM assignments are observations, not permanent identifiers. The operator independently confirmed Unit_2 and Unit_3 firmware settings; copying a legacy default was not accepted as that confirmation.

Earlier USB enumeration difficulties were resolved through powered-hub testing. This was a hardware prerequisite; changing software mappings alone could not fix missing enumeration. No claim is made here about a measured power budget or arbitrary additional detector capacity.

### 3.2 Live installations and services

| Purpose | Installation root | Collector |
|---|---|---|
| Unit_1 production | `/home/pi/UKRAA_PicoMuon` | Concrete `PicoMuon@Unit_1.service` |
| Unit_2 pilot | `/home/pi/UKRAA_PicoMuon-pilot.arQgce` | `PicoMuon@Unit_2.service`, using the template |
| Unit_3 readiness only | Existing mapping in the pilot | `PicoMuon@Unit_3.service`, inactive/disabled |

At the last checks, Unit_1 PID was **1614**, Unit_2 PID **216305**, both active with **NRestarts=0**. Unit_3 had PID 0. Unchanged PIDs are service evidence, not sufficient alone to prove uninterrupted raw capture; raw continuity was checked separately.

The pilot contains mappings for all three labels. Running it without an explicit detector selector, or using the installer's general activation flag, could affect more units than intended. Neither is appropriate for the attended Unit_2-only work.

### 3.3 Isolation contract implemented

The [detector configuration module](../scripts/picomuon_detectors.py) validates labels, stable by-id paths, USB identities and duplicate devices/aliases. [ConfigureUSB.py](../scripts/ConfigureUSB.py) supports guarded registration. [GetDataRaw.py](../scripts/GetDataRaw.py) checks identity, uses exclusive serial access, handles reconnects and rolls files at UTC midnight.

Named output namespaces include:

- Raw: `data/raw/LABEL/YYYY/YYYY-MM/YYYY-MM-DD.txt`.
- Rejected diagnostics: `data/raw/LABEL/rejected/`.
- Status: `data/status/LABEL/current.json`.
- Logs: `logfiles/detectors/LABEL/`.
- Daily/period products: `data/CATEGORY/detectors/LABEL/...`.
- Daily summary: `data/daily/detectors/LABEL/summary.csv`.
- Generated images: `temp/detectors/LABEL/`.
- Published pages/assets: `WWW/detectors/LABEL/`, with dated image subdirectories.

Detector counts are not implicitly combined. Legacy single-detector paths remain supported.

Old firmware supplies no threshold/reset suffix. Its named collector must use a complete `[legacy:LABEL]` section, not another label's or the shared default settings. Detector-reported settings take precedence. Historical missing settings are filled only as an explicitly logged assumption; that assumption is not proof of the hardware's past settings.

## 4. Foundation and early multi-detector testing

### 4.1 Why a named pipeline was required

The earlier implementation relied heavily on single-detector assumptions: ACM-based selection, shared output names and expensive repeated raw-file processing. The modernization introduced single-pass daily processing and explicit named collection/processing before expanding live operation.

[ProcessDaily.py](../scripts/ProcessDaily.py) generates minute CPM, five-minute day, ADC, hourly and daily-summary products. [ProcessPeriod.py](../scripts/ProcessPeriod.py) builds longer periods from derived data rather than rescanning the entire raw archive. [ProcessDetectors.py](../scripts/ProcessDetectors.py) orchestrates selected units, shared downloads, plots and separate static pages.

Per-unit nonblocking processing/pipeline locks protect shared writers. Shared site downloads are serialized within an installation. Failed units/downloads produce a nonzero aggregate result, while other eligible work may continue. Plot/publication validation prevents missing outputs from being replaced by apparently successful stale images. Status in a published page is explicitly a snapshot, not a live health indicator.

### 4.2 Automated and native test progression, 19-20 October

| Test group | Intended evidence | Recorded result and limit |
|---|---|---|
| Configuration and concurrent simulated collectors | Independent streams, fallback settings, malformed rows, duplicate identity rejection, reconnect/rollover and swapped ACM enumeration | Early Windows run: 110 tests, 107 passed, 3 platform skips. Pi run: all 110 passed. Simulation does not prove live renumbering. |
| Service opt-in and reversal | Avoid old/new collectors sharing a port; refuse unauthorized transitions | All 33 focused tests passed on Pi; shell transition tests and rendered-service verification passed. Attended real transition/reversal was exercised. Not full-installer acceptance. |
| Live Unit_2/Unit_3 pilot capture | Independent device streams, disconnect recovery and UTC rollover while Unit_1 stayed in production | Concurrent collection, unplug/reconnect both ways and midnight rollover were recorded; supplied files had distinct names/settings and empty rejected files. |
| Counter/exposure correction | Correct accounting for mixed T/B/C records and UTC boundaries | 129 Pi tests passed without skips in 13.121 seconds, including 19 accounting regressions. Independent exposure calculations agreed within output rounding. |
| Plot/web and shell integration | Separate images/pages, Linux locking, missing-data behavior, logging and publication | 143 Pi tests passed without skips in 36.860 seconds. Explicit offline Unit_2/Unit_3 runs published ten images each. |

Test counts describe different snapshots and overlapping suites; they must not be added as independent tests.

### 4.3 Accounting and presentation defects found

Captured data exposed an incorrect assumption that event counts could be compared across T/B/C as one sequence. The fix tracks each event type independently, counts the shared elapsed clock once, resets baselines at run boundaries and apportions exposure over UTC hour boundaries.

Temporary reprocessing preserved exact event totals. October 19 exposure totals independently calculated for Unit_2 and Unit_3 were **48,312.758 seconds** and **48,275.746 seconds**; CSV precision explains the rounded recorded sums. Their 14 event-containing hours were not interpreted as full-day exposure.

Visual testing also found hard-coded time/location annotations and zero-filled unobserved intervals. Plotters were changed to UTC generation timestamps and configured location text. Missing observations became `nan`, while observed zero counts remained zero; frequency statistics excluded missing minutes. A blank pilot location was subsequently populated for image annotations. This is separate from the incorrect numeric weather coordinates discovered on 30 October.

Transferred shell tests initially needed CRLF-to-LF normalization on the Pi. Windows lock-command stubs were used only for wiring coverage; unmodified Linux locking was verified on the Pi.

Earlier selected-unit network-enabled runs took **31.038 seconds for Unit_2** and **27.989 seconds for Unit_3**, but used partial October 19 datasets. They were not representative combined full-day acceptance.

## 5. Preserving and converting Unit_1

This was a prerequisite to safely adding units, not an instruction to repeat the migration.

### 5.1 Historical archive adoption

The operator confirmed that production name `56/148/627` and USB serial `E660D4A0A7598522` represented the same detector throughout the archive beginning October 10. The read-only [archive preview](../scripts/PreviewArchiveMigration.py) checked completed files, timestamps, overlaps, destination conflicts and source hashes before adoption.

October 13 was split across old and newer layouts. Apparently consecutive endpoints did not prove valid internal order: a supplied snapshot moved backwards at line 526, from **11:03:58.197230 to 10:39:45.612100 UTC**. The fixed-batch [adoption tool](../scripts/AdoptUnit1Archive.py) therefore used a reviewed, hash-bound ordered-copy exception, with strict event multiplicity and overlap checks. It did not silently deduplicate, invent events or rewrite originals.

Saved live acceptance on **21 October at 15:01 UTC** records **20 original sources verified**, **19 destinations verified**, correct destination inventory/metadata and continuing collection. This supersedes earlier plan entries where adoption was still pending.

### 5.2 Attended trial, permanent collection and processing restoration

- **22 October:** an attended named Unit_1 trial passed and returned to single-mode collection with cron restored.
- **23 October:** a permanent attempt recovered to single-mode with cron restored. Preserved partial trial data/status were incorporated into later readiness rules rather than discarded.
- **24 October:** the successful permanent run committed named Unit_1 collection, with daily processing deliberately held until archive merging and processing readiness were resolved.
- **25 October:** processing restoration merged the reviewed split-day history, deployed the validated processing/publication path, backfilled and restored cron after successful checks. One earlier attempt rolled back and kept processing held.
- **26 October:** the retained verification reports `RESTORED_PROCESSING_VERIFIED`, latest processed day October 25. A Unit_1 reboot baseline was recorded. The inspected local reboot evidence contains that baseline, not a complete retained post-reboot acceptance result; current operation is not substituted for that missing detailed result.

Readiness failures during this work exposed legitimate production ownership/mode conditions and timing races: root-owned systemd logs, existing config modes, read-only cron-lock access, `fuser`'s resolved device label, delayed status after startup, prior trial files and an inactive legacy-service placeholder. Guards were narrowed to the exact reviewed conditions rather than broadly disabled.

A processing-restore attempt also inherited private `077` permissions and created unreadable public pages. It rolled back. The correction used `022` for publication/backfill and normalized public modes, without weakening private evidence permissions. Rotated log archives were excluded from unnecessary write-access requirements. Only the exact reviewed four plotting warnings were admitted into the retry baseline; other unexpected errors remained blocking.

## 6. Unit_2 registration and live isolation, 28 October

### 6.1 Readiness and correction of installation-root confusion

Readiness established the physical detector, stable USB path, firmware name, configured settings, current processes and ownership before activation.

The two service roots were important: Unit_1 ran from production, while the named template selected the separate pilot. An initial Unit_2 registration was mistakenly added to production. That exact addition was removed, restoring production's Unit_1-only mapping. Unit_2's intended pilot configuration was then used.

An initial Unit_2 start used **reset_bottom=100**, whereas independent firmware confirmation required **200**. Only Unit_2 was stopped; its pilot legacy section was corrected and collection restarted at **09:55:57 UTC**, PID 216305.

The incorrect-settings interval, approximately **09:46:25-09:50:05 UTC on October 28**, was preserved unchanged. It remains excluded from acceptance/publication and automatic backfill pending explicit resolution. Later configuration correction did not retroactively make those recorded rows correct.

### 6.2 Physical reset isolation test

**Purpose:** establish that a detector reset/disconnection is handled by that collector without stopping the other unit or losing its observed event sequence.

The operator reset Unit_2 at about **09:59:31 UTC**. USB disconnected and the collector reconnected at about **09:59:41**. Unit_2 retained PID 216305; Unit_1 retained PID 1614; neither registered a systemd restart. Unit_1 raw rows continued without a detected reset-related gap/counter loss in the inspected evidence.

This passes the observed two-unit reset-isolation test. It is not proof against every USB/power failure, live ACM-renumbering acceptance, or a measurement of physical detection efficiency.

## 7. Two-unit processing and full-day acceptance

### 7.1 Historical disposable rehearsal

The first two-unit rehearsal used October 19 inputs in `two-unit-rehearsal.MwGccuqD`.

| Unit | Events | T / B / C | Coverage qualification |
|---|---:|---|---|
| Unit_1 | 421,505 | 207,915 / 193,290 / 20,300 | Essentially full-day source |
| Unit_2 | 242,289 | 112,079 / 118,731 / 11,479 | Begins about 10:31; partial day |

The offline chain took **79.391 seconds**, with zero pipeline failures and ten isolated PNGs per unit. Historical settings were retained as recorded, not independently certified for past Unit_2 operation. Because Unit_2 was partial-day and downloads were excluded, this was a rehearsal, not the final timing pass. The decision was to wait for genuine complete days.

### 7.2 Complete October 29 raw validation

Full-row checks used each live installation's completed raw file.

| Measure | Unit_1 | Unit_2 |
|---|---:|---:|
| Total events | 417,650 | 430,660 |
| T | 206,456 | 199,328 |
| B | 191,284 | 210,672 |
| C | 19,910 | 20,660 |
| Observed minutes | 1,440 | 1,440 |
| Maximum timestamp gap | 2.991782 s | 3.029097 s |

Both sources span midnight to the end of day. They had the expected detector names/settings, no observed missing counter increments, repeats, decreases or elapsed drops, and empty rejected files. Raw hashes were recorded and rechecked after processing. These checks establish software/input continuity, not absolute muon detection efficiency.

### 7.3 Download-inclusive acceptance attempt

`two-unit-acceptance.A5XnJ7jD` copied the complete raw files and genuine Unit_1 October 23-28 daily history. Target-day external data were not preseeded.

- Weather download supplied 24/24 UTC hourly values.
- NMDB timed out after approximately 30 seconds; the operator confirmed an external outage.
- The pipeline continued local processing but returned **exit 1**.
- Combined wall time was **130.895 seconds**: the **under-120-second** requirement failed.
- Unit_1 published 11 plots, including week; Unit_2 published 10.
- Unit_1 weekly data were checked over all **1,008 timestamps**, T/B/C sums, paired temperature/pressure means at one-decimal precision, metadata and neutron markers.
- Unit_2 week and both units' month/90-day products skipped correctly for insufficient history.

Absent neutron data remained `nan` with a blank station field. Plots explicitly showed neutron unavailability. Gnuplot's day/week "No valid data points" warnings were traced to absent neutron statistics, not missing muon events. This was validated degraded behavior, not a full successful download chain.

During the inspected 09:52-09:56 processing interval, Unit_1 recorded **1,192 rows** with maximum gap **1.990561 seconds**; Unit_2 recorded **1,179**, maximum **2.013411 seconds**. No counter anomalies were observed and collectors remained unchanged.

### 7.4 Visual defect and correction

Review of all 21 published plots found the bottom-detector ADC title incorrectly saying "top detector". [PlotDataAdcACM0.gp](../scripts/PlotDataAdcACM0.gp) was corrected and a named/legacy rendering regression added to [test_detector_pipeline.py](../tests/test_detector_pipeline.py).

The operator regenerated ADC plots and republished the isolated acceptance pages; raw hashes stayed unchanged and published copies matched generated images. **The later live optimization deployment did not include this plotting fix.** Existing live images/source must not be assumed corrected by that two-file deployment.

## 8. Profiling and verified performance optimization

### 8.1 Profiling question and findings

With both detectors collecting, local processing could be improved without waiting for NMDB. `two-unit-profile.SwTwUJwq` profiled Unit_1's October 29 daily run under Pi **Python 3.13.5**.

The profiled run took **124.591 seconds**, about **66.5 million calls**. Profiler overhead makes this unsuitable as the unprofiled baseline.

| Hotspot | Calls | Cumulative time |
|---|---:|---:|
| BinMetadata.add | 2,088,250 | 38.460 s |
| Timestamp strptime | 417,651 | 29.196 s |
| split_payload | 417,650 | 22.878 s |

Cumulative values overlap and must not be summed. Repeated CSV parsing and timestamp conversion were identified, but deliberately left outside the first narrow optimization.

### 8.2 Change, safeguards and regression checks

[picomuon_products.py](../scripts/picomuon_products.py) gained prepared metadata columns and an unchanged-tuple cache. [ProcessDaily.py](../scripts/ProcessDaily.py) reuses the converted tuple while detector/settings are unchanged and supplies it to the relevant bins. Historical settings resolution still runs as required; mixed metadata behavior, event counts, exposure, product schemas and parsing rules remain intact.

Regression checks in [test_product_columns.py](../tests/test_product_columns.py) cover repeated values, changed/mixed names/settings, fallback and invalid widths. The focused local run recorded **67 tests: 57 passed, 10 skipped**. This is not a native rendering claim. Local output comparisons passed; Windows timing was exploratory, not the Pi result.

The first upload accidentally selected old example files. Hash/source checks detected the wrong version before benchmarking. The correct main-script candidates were uploaded and pinned; no inference was made from filenames or displayed modification times alone.

### 8.3 Pi ABBA comparison

`two-unit-comparison.GqXQ1HcO` ran both units sequentially with baseline, candidate, candidate, baseline ordering to reduce a simple order bias.

| Run | Combined daily wall time |
|---|---:|
| Baseline A | 92.448 s |
| Candidate B | 68.230 s |
| Candidate B | 67.859 s |
| Baseline A | 92.705 s |
| Baseline mean | 92.5765 s |
| Candidate mean | 68.0445 s |

The measured reduction was **24.532 seconds, approximately 26.5%**. All **ten final daily products/summaries** were byte-identical. Input hashes and collector PIDs/restart counts remained unchanged. Four trials support this workload comparison, not a universal performance guarantee or confidence interval.

### 8.4 Optimized offline integration

`two-unit-optimized.UGPlu9aI` exercised both daily processors, eligible period processing, plots and publication with stored external inputs and no downloads.

- **78.525 seconds**, exit 0.
- All ten daily products/summaries and Unit_1's weekly product byte-identical to the original results.
- All 21 image copies/page links verified; visual samples checked.
- Raw/history hashes unchanged.
- During 10:53-10:55, Unit_1 had 570 rows, maximum gap 2.001040 seconds; Unit_2 had 628, maximum 2.015997 seconds. No observed counter anomalies.

This passes the exercised offline integration gates. It does not establish successful NMDB retrieval, complete month/90-day workloads, concurrent processing speedup or the final download-inclusive target.

## 9. Guarded live optimization deployment

### 9.1 Preparation and rollback design

The operator first authorized preparation/rehearsal only. `processing-optimization-deploy.4s7Xj7E9` retained original source and matching bytecode archives for production/pilot, exact hashes, ownership/modes, candidate files, config hashes, cron snapshots and collector baselines.

The deployment scope was exactly **ProcessDaily.py and picomuon_products.py in each root**. It excluded plotting fixes, mapping changes, archive migrations, service activation and schedule changes.

A session-specific runner checked pinned bytes, source/cache drift, dependencies, configuration, root/pi cron, exact collector properties and serial-port owners. It refused nearby scheduling windows and active processing. Existing lock inodes were retained; read-only descriptors could acquire Linux flock without changing root-owned permissions. Missing standard processing locks/directories could be created and retained.

Each source replacement was same-directory atomic with ownership/mode preservation, file flush and directory fsync. The four writes were **not one atomic transaction**. Processing locks, a journal and automatic recovery protected the sequence. Relevant bytecode was removed after installation to avoid stale imports; original bytecode was available for rollback.

The runner preserves original bytes and uid/gid/modes, not a promise to restore every filesystem timestamp. Advisory locks require cooperating operators. SIGKILL/power loss is not automatically recoverable by a running exception handler; retained evidence and guarded recovery remain necessary.

### 9.2 Rehearsal evidence

Eight local transaction tests covered normal apply/restore, failure after each replacement, interruption after rename, postcheck failure, source drift, failed pre-import and explicit recovery failure journaling. Linux ownership/flush hooks were substituted on Windows.

The operator then ran the **native Linux rehearsal on disposable roots**. It passed recovery after writes 1-4, failed-postcheck recovery, fresh import/metadata checks, real replacement/fsync, busy-lock refusal, unrelated-edit rollback refusal and explicit restoration of source/cache bytes and Linux ownership/modes. No live sources/caches/services were changed by rehearsal.

The first local test exposed a Windows-path separator mismatch in archive metadata lookup. Portable archive-relative lookup corrected it and all eight tests passed before native rehearsal.

### 9.3 Authorized apply and continuity verification

Only after native rehearsal did the operator explicitly authorize live deployment. The exact plan hash was supplied. The live journal reported **applied, writes=4** and both installations matched the verified candidate hashes.

Fresh import/metadata and protected-state checks passed. Collectors remained active at **1614 / 216305**, with zero restarts. No live processing was invoked by deployment.

A separate raw inspection covered **10:55-11:14 UTC on October 30**:

| Measure | Unit_1 | Unit_2 |
|---|---:|---:|
| Events | 5,551 | 5,812 |
| Maximum gap | 1.999056 s | 2.013657 s |
| Missing increments / repeated / decreased counters | 0 / 0 / 0 | 0 / 0 / 0 |
| Timestamp reversals / elapsed decreases | 0 / 0 | 0 / 0 |
| Empty complete minutes / malformed rows | 0 / 0 | 0 / 0 |

Names/settings were correct throughout. This supports no observed collection interruption in the inspected deployment window; it is stronger evidence than unchanged service status alone.

## 10. Unit_2 daily processing and weather correction

### 10.1 Scheduling gap discovered

The read-only inventory found Unit_1 daily products through October 29, but the live Unit_2 pilot had no October 29 daily product. Its validated outputs existed only in scratch trees. Root cron processed production's Unit_1-only mapping; no pi cron or relevant system/user timer provided Unit_2 processing.

**Finding:** raw history was accumulating, but waiting alone would not create the daily products needed by weekly processing.

### 10.2 Controlled October 29 seed

`unit2-daily-setup.wmnFkWVZ` backed up existing pilot products, shared external inputs, plots/pages, configuration hashes and schedules before a pi-owned, explicitly selected Unit_2 run.

The pilot's neutron downloader was older than the scratch version and lacked the 30-second timeout. The difference was inspected rather than silently copying another script. It remained unchanged in this work. The seed NMDB attempt took approximately **136 seconds**, failed with a connection timeout, and the complete pipeline returned **1**.

Nevertheless, detector processing completed with **430,660 events**, 24/24 valid hours and zero missing events, and published ten plots. All four daily products were byte-identical to accepted scratch outputs; the October 29 summary row also matched exactly. The summary retained the separate partial October 19 row. Raw hashes, configuration, root cron and collector identities were preserved.

The NMDB failure remained visible; the run was not reclassified as a full success. A zero from a later plots-only run does not erase it.

### 10.3 Incorrect modelled-weather coordinates

Seed logs revealed pilot latitude **-0.1**, longitude **51.0**, while production/accepted scratch used **51.6, -0.1**. The modelled outdoor-temperature overlay was therefore for the wrong location. This did not alter detector counts, measured detector temperature or the checked daily products.

After the operator confirmed the intended coordinates, a dedicated helper backed up config/weather/plots/pages and changed only the two pilot coordinate values. It refused unexpected configuration drift. It then downloaded corrected weather, with **24/24 hourly values**, and regenerated Unit_2 plots/pages without raw reprocessing or neutron download.

Verification checked request-coordinate provenance, unchanged four products/summary, all ten PNG signatures, generated/published byte equality and page links. It passed. Both collectors remained unchanged.

An initial check returned zero images because it searched for dates in PNG filenames; dates are directory names. The check was corrected to inspect the dated directory and actual page links. Publication itself had not failed.

**Rollback consequence:** this approved configuration change intentionally invalidates the optimization runner's old pilot-config baseline. Preserve both evidence sets. Any later optimization rollback must explicitly account for this change; do not overwrite old evidence or bypass the guard.

### 10.4 Installed daily arrangement

A new dedicated `/etc/cron.d/picomuon-unit2` file, **root:root 0644**, schedules:

- **01:30 host-local**, user **pi**.
- Explicit `--detector Unit_2`.
- Previous completed UTC day, determined at invocation; no fixed date.
- Explicit pilot root, UTC runtime and existing pilot cron lock.
- Pipeline output plus per-unit/shared logs, retaining nonzero failures.
- Pilot publication only; no `/var/www/html` publication.

Unit_1's existing root-crontab jobs remained unchanged: daily processing at **01:15 host-local** and weekly log rotation. No service restart or processing run occurred during schedule installation.

Cron was active, installed-file integrity passed, and a minimal cron-like environment correctly selected Unit_2, the previous UTC day and approved weather coordinates. After a 65-second observation there were no recent cron journal entries. **Silence is not proof of execution or schedule acceptance.**

The first actual run is expected **October 31 at 01:30 host-local**, processing October 30. Its execution/output checks are pending. It will not automatically backfill October 28 or other missed dates. The pilot's longer NMDB timeout and independent log-retention arrangements remain operational considerations.

## 11. Unit_3 read-only readiness, October 30

The final readiness review did not open a serial port, reset/unplug hardware, edit configuration or activate a service.

The stable by-id link resolved to `/dev/ttyACM2`. Udev reported serial **E66358986351AF2C**; no process held the port. The pilot mapping matched, and Unit_3's service was inactive/disabled. The operator confirmed physical Unit-3 identification and independently read firmware name/settings.

The old status file was dated **October 20**, with old raw files for October 19/20. These are historical evidence, not present collection. They were left untouched.

**Result:** ready for a separately approved activation plan, not currently collecting. Three simultaneously named live collectors, their scheduled throughput and their recovery behavior have not been accepted by this readiness check.

## 12. Defect and correction register

| Issue | What established it | Correction or disposition |
|---|---|---|
| USB enumeration difficulty | Hardware/hub investigation | Powered-hub testing resolved enumeration; do not confuse this with software identity validation. |
| Mixed T/B/C accounting | Real pilot data and independent exposure calculation | Per-type counters, shared elapsed accounting and UTC-boundary regression tests. |
| Missing intervals shown as zero; hard-coded annotations | Plot/page review | Preserve missing values, retain true zeros, use UTC generation time/configured location; reprocess/replot as appropriate. |
| October 13 historical timestamp reversal | Full interior-file validation | Reviewed hash-bound ordered copy; originals and event multiplicity preserved. |
| Cutover readiness/restore compatibility failures | Native trials and journaled failures | Narrow corrections for reviewed ownership/modes, lock access, status timing, prior data and placeholder state; later trial/commit succeeded. |
| Unreadable public pages | Restore acceptance failure | Rollback; correct publication umask/modes; later committed restore verified. |
| Unit_2 registered in wrong root | Service ExecStart/environment inspection | Remove exact production addition; operate Unit_2 in pilot. |
| Wrong Unit_2 reset_bottom | Independent firmware confirmation | Stop only Unit_2, set 200, restart; preserve/exclude incorrect interval. |
| NMDB outage / long wait | Failed download logs | Preserve nonzero failure and missing-data markers; final acceptance open. Timeout fix exists in repository but not the older pilot downloader. |
| Bottom ADC title says top | Visual inspection | Generator/regression fix, scratch replot verified; not part of live two-file deployment. |
| Old candidate files uploaded | Hash/source preflight | Refuse benchmark, upload correct files, verify exact hashes. |
| Excess metadata overhead | cProfile plus unprofiled ABBA runs | Prepared/cached metadata; exact output equality and native timing improvement. |
| Archive-relative separator bug in deployment tests | First local transaction run | Portable archive lookup; all eight tests subsequently passed. |
| Unit_2 lacks daily scheduling | Cron/timer and product inventory | Verified seed plus separate explicitly selected cron entry; first execution pending. |
| Incorrect pilot weather coordinates | Seed log and config comparison | Approved two-value correction, redownload/replot; products unchanged. |
| PNG count falsely zero | Filename-pattern check contradicted publication layout | Validate dated directory, image bytes and HTML links. |

## 13. Acceptance position at the cut-off

| Gate | Position |
|---|---|
| Named configuration, collector and processing isolation | Implemented; automated and selected live tests passed |
| Unit_1 named adoption and processing restoration | Recorded committed/verified; original data protected |
| Unit_1 detailed reboot acceptance | Baseline inspected; complete retained result not established in this report |
| Unit_1 + Unit_2 live capture and Unit_2 reset isolation | Passed for observed windows |
| Genuine two-unit completed-day input validation | Passed for October 29 |
| Daily and eligible weekly numeric parity | Passed |
| Separate plot/page validation | Passed for exercised outputs; separate live ADC-title deployment outstanding |
| Optimization output equivalence and offline timing | Passed for stated workload |
| Guarded live optimization installation | Applied and verified in both roots |
| Unit_2 seed and separate schedule installation | Verified; actual scheduled execution pending |
| Successful downloads plus combined runtime under 120 seconds | Not passed; NMDB outage and earlier 130.895-second result |
| Unit_2 full-week / month / 90-day acceptance | Pending genuine eligible history |
| Live swapped ACM enumeration / three active named collectors | Not established by the current two-unit tests |
| Consolidated all-unit production rollout/full installer | Not accepted; requires a separate plan and approval |

## 14. Next steps to complete deployment

### 14.1 First priority: October 31 scheduled-run review

After both jobs have finished, inspect scheduler evidence and logs, not just file presence:

1. Confirm Unit_1's 01:15 and Unit_2's 01:30 invocations actually occurred and selected October 30.
2. Inspect return status and shared/per-unit logs. Separate NMDB failure from local processing or publication failure.
3. Validate event totals, coverage, settings, separate summaries and dated page/image links.
4. Confirm collector port ownership, active state/restarts and raw continuity across processing.
5. Verify Unit_1 mapping/schedule and Unit_3 inactive status remain unchanged.

Do not treat cron's active state, a quiet journal or an old published status snapshot as proof of this gate.

### 14.2 Complete the network-inclusive performance gate

When NMDB is available, repeat a fresh isolated two-unit run with genuine full-day inputs and required history, without preseeded target external data.

Require successful weather/NMDB retrieval, correct data provenance, correct separate products/pages, unchanged source hashes and a measured combined runtime **strictly below 120 seconds**. Retain all logs and timing context.

If it fails, profile the actual failing workload. Do not subtract timeout duration, substitute cached data, lower history thresholds or infer success from the 78.525-second offline run. Review deployment of the existing timeout/error-reporting fix to the pilot separately, with backup and validation; that does not make an unavailable NMDB source available.

### 14.3 Accumulate and validate genuine history

Verify Unit_2 daily production on every completed day. If eligible October 29-November 4 data are complete, the earliest new seven-day window ends **November 4**, processed November 5. This is conditional, not a guaranteed calendar pass.

Validate week, month and 90-day numerics/plots when sufficient history exists. Keep the October 28 incorrect-settings interval and other partial days explicitly managed. Do not fabricate clean history or automatically reinterpret historical settings.

### 14.4 Finish controlled operational items

- Deploy/replot the bottom-ADC title correction separately if required; verify current live versions first.
- Plan Unit_2 shared/per-unit/scheduler log retention, disk-space monitoring and failure visibility. The new job does not itself establish a complete operational alerting/retention policy.
- Preserve off-Pi copies of backups/evidence, and reconcile rollback prerequisites with the approved coordinate and schedule changes before any rollback.
- Review longer-run stability, recovery and boot behavior with explicit criteria. Recover any missing Unit_1 reboot result or repeat an approved check; do not infer multi-unit reboot behavior from Unit_1 alone.
- Continue developing/tests/documentation from version-controlled sources; session-specific runners are evidence-bound operational helpers, not a general release installer.

### 14.5 Unit_3 and consolidated deployment

After the outstanding two-unit gates pass, seek separate authorization for Unit_3 activation using its confirmed identity/settings. Observe independent raw/status/log output, reset/reconnect isolation and a real complete UTC day with all three collectors active.

Measure the actual three-unit processing/download/publication workload against an explicitly agreed target; two-unit timings do not certify three-unit capacity. Exercise live renumbering and selected boot/service transitions without sharing ports.

For consolidation into one production root, define the final configured labels, historical source mapping, shared-download policy, schedules, web destinations and rollback boundary. Rehearse the full installer/service transition and real publication under that exact configuration. Do not run broad activation against a pilot listing three labels as a shortcut.

**Release decision:** approve a broader production rollout only when the required gates are evidenced, known limitations accepted explicitly, and preservation/recovery verified. Two active collectors and passing offline tests alone are insufficient.

## 15. Evidence index and reproducibility

Paths below are evidence identifiers, not instructions to rerun old deployment commands. Many snapshots are outside tracked source. Keep originals and corresponding hashes together.

### 15.1 Principal retained evidence

Pi evidence lives under `/home/pi/`; available local copies use the same directory names under `examples/`.

| Evidence directory | Main content |
|---|---|
| `UKRAA_PicoMuon-pilot.arQgce` | Early Unit_2/Unit_3 pilot capture, processing and service evidence |
| `unit1-production-adoption.3HWI5R` | Live archive acceptance: 20 sources, 19 destinations |
| `unit1-collection-trial.rur107hp` | Passed attended trial and single-mode restoration |
| `unit1-permanent-collection.34qvz5jc` | Recovered October 23 permanent attempt |
| `unit1-permanent-collection.k_xuwdb1` | October 24 permanent named commit, processing held |
| `unit1-restore-processing.nofawly0` | Rolled-back processing restoration |
| `unit1-restore-processing.llg47v77` | Committed restore and October 26 verification |
| `unit1-reboot-check.3cti60sb` | Inspected pre-reboot baseline |
| `two-unit-rehearsal.MwGccuqD` | Historical/partial-day two-unit offline rehearsal |
| `two-unit-acceptance.A5XnJ7jD` | October 29 download-inclusive attempt, numeric/visual checks |
| `two-unit-profile.SwTwUJwq` | Pi cProfile and candidate preparation |
| `two-unit-comparison.GqXQ1HcO` | Unprofiled ABBA timings and output comparison |
| `two-unit-optimized.UGPlu9aI` | Optimized offline integration and pages |
| `processing-optimization-deploy.4s7Xj7E9` | Backups, candidate pins, rehearsal receipt, apply journal/logs |
| `unit2-daily-setup.wmnFkWVZ` | Seed/output backup, approved weather repair and dedicated schedule evidence |

Live deployment/scheduling conclusions additionally use the operator's pasted terminal results; a local copy made before the latest action may not contain the final receipt. No new Pi action was performed to prepare this report.

### 15.2 Important exact-byte SHA-256 pins

These are raw-byte hashes, not LF-normalized source hashes. Upload line-ending changes can alter hashes without changing displayed code.

**October 29 raw inputs**

```text
Unit_1
a7f7909d80dacc867a7223fcc54881740925c3c36d7f1f6959e626ddd2d06c21
Unit_2
6240ef2c7b2dd8ab5105bc6f8474fce0d06a74a8b202f9f1533f7763e26b8f2d
```

**Original live files before optimization, both roots**

```text
ProcessDaily.py
452d7c17bbf0394be45c4e902f5c3b7f1b3ce3bbf46b1b7c4aadebeb58c466a9
picomuon_products.py
17fc7e143996ec8acbc2b4f9bcd04cfa75cfc1141280d580ca2e4d35a4c5581d
```

**Verified and deployed candidates, both roots**

```text
ProcessDaily.py
4559508b5c8bed1d6e445d4dad91c7b1b6c1ade41d7c5aa0e088a73af0dd5193
picomuon_products.py
930c556f32334afcba32fd3f300ecda6d35fe5180a3d19c0006760c4eb7cdfe0
```

### 15.3 Related tracked records

- [Changelog](../CHANGELOG.md): implementation changes and correction history.
- [Implementation plan](implementation-plan.md): original architecture, dated test records and staged rollout rationale.
- [Detector configuration](../scripts/picomuon_detectors.py), [collector](../scripts/GetDataRaw.py) and [processing locks](../scripts/picomuon_processing.py).
- [Daily processor](../scripts/ProcessDaily.py), [period processor](../scripts/ProcessPeriod.py), [metadata helper](../scripts/picomuon_products.py) and [named orchestrator](../scripts/ProcessDetectors.py).
- [Web publisher](../scripts/picomuon_web.py), [cron wrapper](../scripts/runCronJob.sh), [weather downloader](../scripts/GetDataWeather.py) and [repository neutron downloader](../scripts/GetDataNeutron.py). Repository contents do not prove which version is live in each root.
- [Metadata/product regression tests](../tests/test_product_columns.py) and [pipeline/rendering tests](../tests/test_detector_pipeline.py).

The companion PDF is generated from this Markdown report. This report records the evidence position at its stated cut-off; later scheduled execution, new history and external-service recovery require additional results.
