from copy import deepcopy
from datetime import date, datetime, timezone
import io
import configparser
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from GetDataWeather import (
    build_weather_path, build_weather_url, download_weather, load_coordinates,
    main, parse_hourly,
)

TARGET = date(2026, 10, 17)
NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def weather_payload():
    return {
        "utc_offset_seconds": 0,
        "hourly_units": {"temperature_2m": "\N{DEGREE SIGN}C"},
        "hourly": {
            "time": [f"{TARGET}T{hour:02d}:00" for hour in range(24)],
            "temperature_2m": [float(hour - 12) for hour in range(24)],
        },
    }


class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        (self.base / "config").mkdir()
        self.config = self.base / "config" / "user.ini"
        self.configure()

    def configure(self, latitude="51.6", longitude="-0.10", enabled="true"):
        self.config.write_text(
            f"[Observatory]\nobservatory_latitude = {latitude}\nobservatory_longitude = {longitude}\n"
            f"\n[weather]\nenabled = {enabled}\n",
            encoding="utf-8",
        )

    def test_disabled_and_unconfigured_do_not_fetch(self):
        for missing in (False, True):
            if missing:
                self.config.unlink()
            else:
                self.configure(enabled="false", latitude="", longitude="")
            with patch("GetDataWeather.urlopen") as request, \
                    patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertIsNone(download_weather(self.base, TARGET))
            request.assert_not_called()
            self.assertIn("Skipped weather download", output.getvalue())

    def test_existing_user_ini_without_weather_settings_is_disabled(self):
        self.config.write_text("[Observatory]\nobservatory_latitude =\nobservatory_longitude =\n", encoding="utf-8")
        with patch("GetDataWeather.urlopen") as request:
            self.assertIsNone(download_weather(self.base, TARGET))
        request.assert_not_called()

    def test_enabled_weather_requires_observatory_coordinates(self):
        self.config.write_text("[weather]\nenabled = true\n", encoding="utf-8")
        with self.assertRaises(configparser.NoSectionError):
            load_coordinates(self.base)

    def test_template_merge_preserves_coordinates_and_weather_preference(self):
        from MergeConfig import merge_missing_options
        merge_missing_options(REPO / "install" / "user.ini.example", self.config)
        self.assertEqual(load_coordinates(self.base), (51.6, -0.1))
        self.config.write_text(
            "[Observatory]\nobservatory_latitude = 51.6\nobservatory_longitude = -0.10\n",
            encoding="utf-8",
        )
        merge_missing_options(REPO / "install" / "user.ini.example", self.config)
        self.assertIsNone(load_coordinates(self.base))

    def test_weather_settings_are_not_copied_into_observation_metadata(self):
        from picomuon_metadata import load_observation
        observation = load_observation(self.base)
        self.assertNotIn("weather", observation)
        self.assertEqual(observation["Observatory"]["observatory_latitude"], "51.6")

    def test_coordinates_validation(self):
        self.assertEqual(load_coordinates(self.base), (51.6, -0.1))
        for latitude, longitude in (("nan", "0"), ("91", "0"), ("0", "-181"), ("0", "inf"), ("", "0")):
            with self.subTest(latitude=latitude, longitude=longitude):
                self.configure(latitude, longitude)
                with self.assertRaises(ValueError):
                    load_coordinates(self.base)

    def test_urls_select_recent_and_historical_apis_in_utc(self):
        for target, hostname in (
            (TARGET, "api.open-meteo.com"),
            (date(2026, 10, 1), "historical-forecast-api.open-meteo.com"),
        ):
            url = urlparse(build_weather_url(target, 51.6, -0.1, NOW.date()))
            self.assertEqual(url.hostname, hostname)
            query = parse_qs(url.query)
            self.assertEqual(query["latitude"], ["51.6"])
            self.assertEqual(query["longitude"], ["-0.1"])
            self.assertEqual(query["timezone"], ["GMT"])
            self.assertEqual(query["hourly"], ["temperature_2m"])
            self.assertEqual(query["temperature_unit"], ["celsius"])
            self.assertEqual(query["start_date"], [str(target)])
            self.assertEqual(query["end_date"], [str(target)])

    def test_parser_preserves_real_values_and_missing_gaps(self):
        payload = weather_payload()
        payload["hourly"]["temperature_2m"][3] = None
        rows = parse_hourly(payload, TARGET)
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows[0], ("2026-10-17 00:00:00", -12.0))
        self.assertEqual(rows[3], ("2026-10-17 03:00:00", None))

    def test_parser_rejects_bad_responses(self):
        original = weather_payload()
        bad = [None, {"error": True, "reason": "invalid request"}]
        for field, value in (
            ("utc_offset_seconds", 3600), ("hourly_units", {}),
            ("hourly", {}), ("hourly", None),
        ):
            payload = deepcopy(original)
            payload[field] = value
            bad.append(payload)
        for values in ([None] * 24, [1] * 23, ["12"] * 24, [True] * 24, [math.nan] * 24, [math.inf] * 24):
            payload = deepcopy(original)
            payload["hourly"]["temperature_2m"] = values
            bad.append(payload)
        payload = deepcopy(original)
        payload["hourly"]["time"].reverse()
        bad.append(payload)
        for payload in bad:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    parse_hourly(payload, TARGET)

    def test_download_writes_atomic_self_describing_product(self):
        payload = weather_payload()
        payload["hourly"]["temperature_2m"][4] = None
        with patch("GetDataWeather.utc_now", return_value=NOW), \
                patch("GetDataWeather.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as request:
            result = download_weather(self.base, TARGET)
        output = build_weather_path(self.base, TARGET)
        self.assertEqual(result, output)
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs["timeout"], 30)
        text = output.read_text(encoding="utf-8")
        self.assertIn("Open-Meteo.com; CC BY 4.0; modelled 2 m", text)
        self.assertIn("longitude=-0.1", text)
        rows = [line for line in text.splitlines() if not line.startswith("#")]
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0], "DateTime,Temperature_2m_C")
        self.assertEqual(rows[5], "2026-10-17 04:00:00,nan")
        self.assertFalse(output.with_suffix(".tmp").exists())

    def test_bad_download_preserves_previous_file_and_reports_failure(self):
        output = build_weather_path(self.base, TARGET)
        output.parent.mkdir(parents=True)
        output.write_text("previous data\n", encoding="utf-8")
        for failure in (URLError("unavailable"), ValueError("invalid response")):
            with patch("GetDataWeather.get_base_path", return_value=self.base), \
                    patch("GetDataWeather.utc_now", return_value=NOW), \
                    patch("GetDataWeather.urlopen", side_effect=failure), \
                    patch("sys.argv", ["GetDataWeather.py", "--date", str(TARGET)]), \
                    patch("sys.stderr", new_callable=io.StringIO) as errors:
                self.assertEqual(main(), 1)
            self.assertIn("ERROR: weather download failed", errors.getvalue())
            self.assertEqual(output.read_text(encoding="utf-8"), "previous data\n")
            self.assertFalse(output.with_suffix(".tmp").exists())

    def test_incomplete_day_is_not_requested(self):
        with patch("GetDataWeather.utc_now", return_value=NOW), \
                patch("GetDataWeather.urlopen") as request:
            with self.assertRaisesRegex(ValueError, "completed UTC day"):
                download_weather(self.base, NOW.date())
        request.assert_not_called()

    def test_failed_replacement_preserves_previous_product_and_cleans_temporary(self):
        output = build_weather_path(self.base, TARGET)
        output.parent.mkdir(parents=True)
        output.write_text("previous data\n", encoding="utf-8")
        with patch("GetDataWeather.utc_now", return_value=NOW), \
                patch("GetDataWeather.urlopen", return_value=io.BytesIO(json.dumps(weather_payload()).encode())), \
                patch.object(Path, "replace", side_effect=OSError("disk error")):
            with self.assertRaisesRegex(OSError, "disk error"):
                download_weather(self.base, TARGET)
        self.assertEqual(output.read_text(encoding="utf-8"), "previous data\n")
        self.assertFalse(output.with_suffix(".tmp").exists())


GNUPLOT = os.environ.get("PICOMUON_TEST_GNUPLOT") or shutil.which("gnuplot")


@unittest.skipUnless(GNUPLOT, "gnuplot is required for rendering tests")
class CpmRenderingTests(unittest.TestCase):
    def test_cpm_images_with_and_without_weather(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            cpm = base / "data" / "cpm" / "ACM0" / "2026" / "2026-10" / f"{TARGET}.txt"
            cpm.parent.mkdir(parents=True)
            cpm.write_text(
                "# metadata comment\nDateTime,Count_T,Count_B,Count_C\n" + "".join(
                    f"{TARGET} {minute // 60:02d}:{minute % 60:02d}:00,"
                    f"{100 + minute % 10},{80 + minute % 8},{10 + minute % 5}\n"
                    for minute in range(1440)
                ), encoding="utf-8",
            )
            (base / "plots" / "cpm" / "ACM0").mkdir(parents=True)
            (base / "temp" / "yesterday").mkdir(parents=True)
            source = (REPO / "scripts" / "PlotDataCpmACM0.gp").read_text(encoding="utf-8")
            if os.name == "nt":
                source = source.replace("DejaVuSansCondensed", "Arial")
            # Avoid platform-specific date/printf shells while testing the plotting code.
            source = source.replace(
                'basePath = system("printf \'%s\' \\"$PICOMUON_BASE_PATH\\"")',
                f'basePath = "{base.as_posix()}"',
            ).replace(
                'targetDate = system("date -u -d \\"${PICOMUON_TARGET_DATE:-yesterday}\\" +%F")',
                f'targetDate = "{TARGET}"',
            ).replace(
                'system("date -u -d \'".targetDate." +1 day\' +%F")',
                '"2026-10-18"',
            ).replace(
                'system("date -u -d \'".targetDate."\' +\'%A %d %B %Y\'")',
                '"Saturday 17 October 2026"',
            )
            self.assertNotIn("system(", source)
            script = base / "plot.gp"
            for enabled in (0, 1):
                with self.subTest(weather=enabled):
                    if enabled:
                        weather = build_weather_path(base, TARGET)
                        weather.parent.mkdir(parents=True)
                        weather.write_text(
                            "# Weather data by Open-Meteo.com\nDateTime,Temperature_2m_C\n" + "".join(
                                f"{TARGET} {hour:02d}:00:00,{hour * 2 - 12}\n"
                                for hour in range(24)
                            ), encoding="utf-8",
                        )
                    for svg in (False, True):
                        contents = source
                        if svg:
                            contents = contents.replace("pngcairo enhanced", "svg enhanced").replace(" rounded size", " size")
                        script.write_text(contents, encoding="utf-8")
                        result = subprocess.run(
                            [GNUPLOT, "-e", f"plotWeather={enabled}", str(script)],
                            capture_output=True, text=True,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr.strip(), "")
                        outputs = list((base / "plots" / "cpm" / "ACM0").glob("*.png"))
                        outputs += list((base / "temp" / "yesterday").glob("*.png"))
                        self.assertEqual(len(outputs), 6)
                        for output in outputs:
                            data = output.read_bytes()
                            if svg:
                                text = data.decode("utf-8")
                                self.assertEqual("Modelled 2 m air temperature" in text, bool(enabled))
                                self.assertEqual("Weather data by Open-Meteo.com" in text, bool(enabled))
                            else:
                                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                                self.assertEqual(struct.unpack(">II", data[16:24]), (640, 540))


if __name__ == "__main__":
    unittest.main()
