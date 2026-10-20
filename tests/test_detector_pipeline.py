from contextlib import redirect_stdout, redirect_stderr
from datetime import date, datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ProcessDaily import process_daily
from ProcessPeriod import process_period_data
from ProcessDetectors import PLOTS, run_pipeline
from picomuon_common import build_processed_day_path
from picomuon_processing import processing_lock
from picomuon_web import plot_files, publish_detector

REPO = Path(__file__).resolve().parents[1]
TARGET = date(2026, 10, 19)
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 640, 540)
GNUPLOT = os.environ.get("PICOMUON_TEST_GNUPLOT") or shutil.which("gnuplot")


class DetectorPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "project with spaces"
        config = self.base / "config"
        config.mkdir(parents=True)
        self.labels = ("Unit_1", "Unit_2", "Unit_3")
        (config / "USB.ini").write_text(
            "[detectors]\n" + "".join(f"{label}=/dev/serial/by-id/usb-{label}\n" for label in self.labels)
            + "".join(f"[detector:{label}]\nid_serial_short={label}\n" for label in self.labels)
        )
        self.calls = []
        self.now = patch("ProcessDetectors.utc_now", return_value=datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.now.start()
        self.addCleanup(self.now.stop)
        self.environment = patch.dict(os.environ, {"PICOMUON_BASE_PATH": str(self.base)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def raw(self, label):
        path = self.base / "data" / "raw" / label / "2026" / "2026-10" / f"{TARGET}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(
            f"{TARGET} 10:00:{second:02d},{event},1,200,{second * 1000},0,22,1015,"
            f"{label},200,100,200,100\n"
            for second, event in enumerate(("T", "B", "C"))
        ))

    def stage(self, base, target, label, arguments, *, plot=False):
        self.calls.append((label, arguments, plot))
        if plot:
            for path in plot_files(base, label, target):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(PNG)
        return 0

    def pipeline(self, **kwargs):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                patch("ProcessDetectors.run_shell_stage", side_effect=self.stage):
            return run_pipeline(self.base, TARGET, **kwargs)

    def test_all_detectors_publish_separately_without_touching_legacy_web(self):
        external = Path(self.temp.name) / "external"
        external.mkdir()
        (external / "index.html").write_text("legacy website")
        for label in self.labels:
            self.raw(label)
            status = self.base / "data" / "status" / label / "current.json"
            status.parent.mkdir(parents=True)
            status.write_text(json.dumps({"detector_name": '<script>alert("unsafe")</script>', "last_event_utc": "old"}))
        self.assertEqual(self.pipeline(skip_downloads=True, web_root=external), 0)
        self.assertEqual((external / "index.html").read_text(), "legacy website")
        self.assertEqual(len(self.calls), 18)
        for label in self.labels:
            for root in (self.base / "WWW", external):
                directory = root / "detectors" / label
                contents = (directory / "index.html").read_text()
                self.assertIn(str(TARGET), contents)
                self.assertIn(label, contents)
                self.assertIn("&lt;script&gt;", contents)
                self.assertNotIn('<script>alert("unsafe")</script>', contents)
                self.assertIn("not a live connection indicator", contents)
                self.assertEqual(len(list((directory / str(TARGET)).glob("*.png"))), 10)
                snapshot = json.loads((directory / "status.json").read_text())
                self.assertEqual(snapshot["label"], label)
                self.assertEqual(snapshot["collector_status"]["last_event_utc"], "old")
                for other in set(self.labels) - {label}:
                    self.assertNotIn(other + "_", contents)
        index = (external / "detectors" / "index.html").read_text()
        for label in self.labels:
            self.assertIn(f'{label}/index.html', index)

    def test_missing_unit_does_not_stop_healthy_units_or_publish_its_stale_plots(self):
        for label in self.labels[1:]:
            self.raw(label)
        stale = self.base / "temp" / "detectors" / "Unit_1" / "yesterday" / "Unit_1_T-Cpm.png"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(PNG)
        self.assertEqual(self.pipeline(skip_downloads=True), 1)
        self.assertFalse((self.base / "WWW" / "detectors" / "Unit_1" / "index.html").exists())
        for label in self.labels[1:]:
            self.assertTrue((self.base / "WWW" / "detectors" / label / "index.html").is_file())
        errors = self.base / "logfiles" / "detectors" / "Unit_1" / "log-error.txt"
        self.assertIn("Daily processing failed", errors.read_text())
        self.assertFalse(any(call[0] == "Unit_1" for call in self.calls))

    def test_shared_downloads_run_once_and_failure_is_not_silently_successful(self):
        for label in self.labels:
            self.raw(label)
        stage = self.stage

        def failing_download(base, target, label, arguments, *, plot=False):
            if label is None:
                self.calls.append((label, arguments, plot))
                return 7
            return stage(base, target, label, arguments, plot=plot)

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                patch("ProcessDetectors.run_shell_stage", side_effect=failing_download):
            self.assertEqual(run_pipeline(self.base, TARGET), 1)
        self.assertEqual(sum(label is None for label, _, _ in self.calls), 2)
        self.assertEqual(sum(plot for _, _, plot in self.calls), 18)

    def test_selected_detector_and_plot_only_do_not_reprocess_raw(self):
        self.raw("Unit_2")
        with redirect_stdout(io.StringIO()):
            process_daily(TARGET, self.base, "Unit_2")
        with patch("ProcessDetectors.process_daily") as daily, patch("ProcessDetectors.process_period_data") as period:
            self.assertEqual(self.pipeline(detector="Unit_2", skip_downloads=True, plots_only=True), 0)
        daily.assert_not_called()
        period.assert_not_called()
        self.assertEqual({label for label, _, _ in self.calls}, {"Unit_2"})
        page = self.base / "WWW" / "detectors" / "Unit_2" / "index.html"
        self.assertIn("No collector status available", page.read_text())

    @unittest.skipUnless(GNUPLOT, "gnuplot is required for rendering tests")
    def test_sparse_processed_day_renders_and_publishes_without_period_history(self):
        self.raw("Unit_2")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(process_daily(TARGET, self.base, "Unit_2"), 0)
        for category in ("cpm", "freq", "adc", "day"):
            (self.base / "plots" / category / "detectors" / "Unit_2").mkdir(parents=True)
        for group in ("yesterday", "periods"):
            (self.base / "temp" / "detectors" / "Unit_2" / group).mkdir(parents=True)
        for name in PLOTS[:4]:
            script = self.base / name
            script.write_text(portable_plot_source(name, self.base, TARGET), encoding="utf-8")
            result = subprocess.run(
                [GNUPLOT, "-e", "detectorLabel='Unit_2';neutronColumn=12", str(script)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")
        with redirect_stdout(io.StringIO()):
            publish_detector(self.base, "Unit_2", TARGET, self.base / "WWW")
        images = self.base / "WWW" / "detectors" / "Unit_2" / str(TARGET)
        self.assertEqual(len(list(images.glob("*.png"))), 10)

    def test_pipeline_contention_is_reported_and_other_units_still_run(self):
        for label in self.labels:
            self.raw(label)
        with processing_lock(self.base, "Unit_1", pipeline=True):
            self.assertEqual(self.pipeline(skip_downloads=True), 1)
        self.assertFalse(any(label == "Unit_1" for label, _, _ in self.calls))
        self.assertTrue((self.base / "WWW" / "detectors" / "Unit_3" / "index.html").exists())

    def test_plot_failure_preserves_previous_page_and_continues_other_units(self):
        for label in self.labels:
            self.raw(label)
        previous = self.base / "WWW" / "detectors" / "Unit_1" / "index.html"
        previous.parent.mkdir(parents=True)
        previous.write_text("previous dated page")
        stage = self.stage

        def failing_plot(base, target, label, arguments, *, plot=False):
            result = stage(base, target, label, arguments, plot=plot)
            return 9 if label == "Unit_1" else result

        with redirect_stdout(io.StringIO()), patch("ProcessDetectors.run_shell_stage", side_effect=failing_plot):
            self.assertEqual(run_pipeline(self.base, TARGET, skip_downloads=True), 1)
        self.assertEqual(previous.read_text(), "previous dated page")
        self.assertTrue((self.base / "WWW" / "detectors" / "Unit_3" / "index.html").exists())

    def test_publication_rejects_missing_corrupt_images_or_invalid_status_before_replacing_page(self):
        self.raw("Unit_2")
        with redirect_stdout(io.StringIO()):
            process_daily(TARGET, self.base, "Unit_2")
        self.stage(self.base, TARGET, "Unit_2", [], plot=True)
        root = self.base / "WWW"
        page = root / "detectors" / "Unit_2" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text("previous page")
        first = plot_files(self.base, "Unit_2", TARGET)[0]
        first.write_text("not a PNG")
        with self.assertRaisesRegex(ValueError, "PNG"):
            publish_detector(self.base, "Unit_2", TARGET, root)
        self.assertEqual(page.read_text(), "previous page")
        first.write_bytes(PNG)
        status = self.base / "data" / "status" / "Unit_2" / "current.json"
        status.parent.mkdir(parents=True)
        status.write_text("[]")
        with self.assertRaisesRegex(ValueError, "status object"):
            publish_detector(self.base, "Unit_2", TARGET, root)
        self.assertEqual(page.read_text(), "previous page")

    def test_invalid_selection_and_partial_day_are_rejected_before_work(self):
        for kwargs in ({"detector": "Missing"}, {"detector": "../Unit_2"}):
            with self.assertRaises(ValueError):
                self.pipeline(**kwargs)
        with self.assertRaisesRegex(ValueError, "completed UTC day"):
            run_pipeline(self.base, TARGET + timedelta(days=1), skip_downloads=True)
        self.assertFalse(self.calls)

    def test_insufficient_period_history_removes_only_selected_stale_product(self):
        self.raw("Unit_2")
        with redirect_stdout(io.StringIO()):
            process_daily(TARGET, self.base, "Unit_2")
            process_period_data("week", TARGET, self.base, 10, "Unit_2")
        stale = build_processed_day_path(self.base, "week", TARGET, "Unit_2", named_detector=True)
        other = build_processed_day_path(self.base, "week", TARGET, "Unit_3", named_detector=True)
        other.parent.mkdir(parents=True)
        other.write_text("other detector")
        self.assertTrue(stale.exists())
        with redirect_stdout(io.StringIO()):
            process_period_data("week", TARGET, self.base, detector="Unit_2")
        self.assertFalse(stale.exists())
        self.assertEqual(other.read_text(), "other detector")

    def test_neutron_download_uses_pipeline_target_not_current_yesterday(self):
        pandas = MagicMock()
        nest = MagicMock()
        nest.single.return_value = "https://example.invalid/test"
        with patch.dict(sys.modules, {"pandas": pandas, "nest": nest}), \
                patch.dict(os.environ, {"PICOMUON_TARGET_DATE": str(TARGET)}), \
                redirect_stdout(io.StringIO()):
            runpy.run_path(str(REPO / "scripts" / "GetDataNeutron.py"), run_name="__main__")
        arguments = nest.single.call_args.args
        self.assertEqual(arguments[3], datetime(2026, 10, 19))
        self.assertEqual(arguments[4], datetime(2026, 10, 19, 23, 59, 59))
        output = self.base / "data" / "neutrons" / "2026" / "2026-10" / f"{TARGET}.txt"
        self.assertTrue(output.is_file())
        self.assertFalse(output.with_suffix(".txt.tmp").exists())

    @unittest.skipUnless(os.name == "posix" and GNUPLOT, "Linux/RPi and gnuplot required for shell pipeline integration")
    def test_real_shell_pipeline_plots_and_reprocessing_are_consistent(self):
        shutil.copytree(REPO / "scripts", self.base / "scripts")
        for label in self.labels[1:]:
            self.raw(label)
        result = subprocess.run(
            ["bash", str(self.base / "scripts" / "processData.sh"),
             "--date", str(TARGET), "--skip-downloads"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)  # Unit_1 deliberately has no input.
        for label in self.labels[1:]:
            self.assertTrue((self.base / "WWW" / "detectors" / label / "index.html").exists())
        for script, options in (
            ("plots.sh", ["--date", str(TARGET), "--skip-downloads"]),
            ("reprocessData.sh", ["--to", str(TARGET), "--plot"]),
        ):
            run = subprocess.run(
                ["bash", str(self.base / "scripts" / script), "--detector", "Unit_2", *options],
                capture_output=True, text=True,
            )
            self.assertEqual(run.returncode, 0, f"{script}: {run.stdout}\n{run.stderr}")
        logs = self.base / "logfiles" / "detectors" / "Unit_2"
        with (logs / ".pipeline.lock").open("a+b") as lock:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            blocked = subprocess.run(
                ["bash", str(self.base / "scripts" / "plots.sh"), "--detector", "Unit_2",
                 "--date", str(TARGET), "--skip-downloads"], capture_output=True, text=True,
            )
            self.assertEqual(blocked.returncode, 1)


def portable_plot_source(script, base, target):
    source = (REPO / "scripts" / script).read_text(encoding="utf-8")
    source = source.replace(
        'basePath = system("printf \'%s\' \\"$PICOMUON_BASE_PATH\\"")',
        f'basePath = "{base.as_posix()}"',
    ).replace(
        'targetDate = system("date -u -d \\"${PICOMUON_TARGET_DATE:-yesterday}\\" +%F")',
        f'targetDate = "{target}"',
    ).replace(
        'system("date -u -d \'".targetDate."\' +\'%A %d %B %Y\'")', '"Monday 19 October 2026"',
    )
    for delta in (1, -6, -30):
        expression = f'{delta:+d} day' if delta == 1 else f'{delta} days'
        source = source.replace(
            'system("date -u -d \'".targetDate." ' + expression + '\' +%F")',
            f'"{target + timedelta(days=delta)}"',
        )
    if os.name == "nt":
        source = source.replace("DejaVuSansCondensed", "Arial")
    if "system(" in source:
        raise AssertionError("Unsubstituted platform shell in plot test")
    return source


@unittest.skipUnless(GNUPLOT, "gnuplot is required for rendering tests")
class NamedRenderingTests(unittest.TestCase):
    def test_no_muon_or_neutron_data_is_labelled_without_fabricated_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for category, script in (("day", "PlotDataDayACM0.gp"), ("week", "PlotDataWeekACM0.gp"),
                                     ("month", "PlotDataMonthACM0.gp")):
                path = build_processed_day_path(base, category, TARGET, "Unit_2", named_detector=True)
                path.parent.mkdir(parents=True)
                path.write_text("DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,neutrons\n"
                                f"{TARGET} 10:00:00,10,10,nan,22,1015,nan\n")
                (base / "plots" / category / "detectors" / "Unit_2").mkdir(parents=True)
                (base / "temp" / "detectors" / "Unit_2" / "periods").mkdir(parents=True, exist_ok=True)
                source = portable_plot_source(script, base, TARGET)
                source = source.replace("pngcairo enhanced", "svg enhanced").replace(" rounded size", " size")
                temporary = base / script
                temporary.write_text(source)
                result = subprocess.run(
                    [GNUPLOT, "-e", "detectorLabel='Unit_2';neutronColumn=7", str(temporary)],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                output = base / "temp" / "detectors" / "Unit_2" / "periods" / f"Unit_2_{category}_plot.png"
                svg = output.read_text()
                self.assertIn("No muon events in this period", svg)
                self.assertIn("Neutron data unavailable", svg)
                self.assertNotIn("Mean neutron counts", svg)
                self.assertIn("Unit_2", svg)

    def test_all_six_plotters_render_legacy_and_two_named_units_without_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for label in ("", "East", "ACM0"):
                named = bool(label)
                for category in ("cpm", "adc", "day", "week", "month"):
                    path = build_processed_day_path(base, category, TARGET, label or "ACM0", named_detector=named)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if category == "adc":
                        contents = "ADC_Value,Count_T,Count_B,Count_C\n" + "".join(
                            f"{i},{i % 8 + 1},{i % 9 + 1},{i % 5 + 1}\n" for i in range(1024)
                        )
                    else:
                        contents = "DateTime,CPM_T,CPM_B,CPM_C,Mean_Temp,Mean_Pres,neutrons\n" + "".join(
                            f"{TARGET} {i // 60:02d}:{i % 60:02d}:00,{i % 8 + 90},{i % 9 + 80},"
                            f"{i % 5 + 10},22,1015,100\n" for i in range(1440)
                        )
                    path.write_text(contents)
                for category in ("cpm", "adc", "freq", "day", "week", "month"):
                    root = base / "plots" / category
                    (root / "detectors" / label if named else root / "ACM0").mkdir(parents=True)
                temp = base / "temp" / "detectors" / label if named else base / "temp"
                for group in ("yesterday", "periods"):
                    (temp / group).mkdir(parents=True)
                for name in PLOTS:
                    script = base / name
                    script.write_text(portable_plot_source(name, base, TARGET), encoding="utf-8")
                    result = subprocess.run(
                        [GNUPLOT, "-e", f"detectorLabel='{label}';neutronColumn=7", str(script)],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, f"{label} {name}: {result.stderr}")
                latest = list(temp.glob("*/*.png"))
                self.assertEqual(len(latest), 12)
                for image in latest:
                    data = image.read_bytes()
                    self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual(struct.unpack(">II", data[16:24]), (640, 540))
                if named:
                    self.assertTrue(all(image.name.startswith(label + "_") for image in latest))
            self.assertTrue((base / "temp" / "yesterday" / "ACM0_T-Cpm.png").exists())
            self.assertTrue((base / "temp" / "detectors" / "ACM0" / "yesterday" / "ACM0_T-Cpm.png").exists())


if __name__ == "__main__":
    unittest.main()
