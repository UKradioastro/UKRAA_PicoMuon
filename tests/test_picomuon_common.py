import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from picomuon_common import get_base_path, get_version, utc_yesterday


class PicoMuonCommonTests(unittest.TestCase):
    def test_base_path_defaults_to_repository_root(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_base_path(), Path(__file__).resolve().parents[1])

    def test_base_path_honors_environment_override(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(os.environ, {"PICOMUON_BASE_PATH": temporary_directory}):
                self.assertEqual(get_base_path(), Path(temporary_directory).resolve())

    def test_get_version_reads_calver(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            version_file = Path(temporary_directory) / "VERSION"
            version_file.write_text("2026.10.0\n", encoding="utf-8")
            with patch("picomuon_common.get_base_path", return_value=Path(temporary_directory)):
                self.assertEqual(get_version(), "2026.10.0")

    def test_get_version_rejects_invalid_calver(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            version_file = Path(temporary_directory) / "VERSION"
            version_file.write_text("v2026.10.0\n", encoding="utf-8")
            with patch("picomuon_common.get_base_path", return_value=Path(temporary_directory)):
                with self.assertRaises(ValueError):
                    get_version()

    def test_get_version_rejects_invalid_month(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            version_file = Path(temporary_directory) / "VERSION"
            version_file.write_text("2026.13.0\n", encoding="utf-8")
            with patch("picomuon_common.get_base_path", return_value=Path(temporary_directory)):
                with self.assertRaises(ValueError):
                    get_version()

    def test_utc_yesterday_uses_utc_across_local_date_boundary(self):
        local_time = datetime(2026, 10, 11, 0, 30, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(utc_yesterday(local_time).isoformat(), "2026-10-09")

    def test_utc_yesterday_rejects_naive_datetime(self):
        with self.assertRaises(ValueError):
            utc_yesterday(datetime(2026, 10, 11, 0, 30))


if __name__ == "__main__":
    unittest.main()
