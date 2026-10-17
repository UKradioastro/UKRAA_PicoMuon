from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from picomuon_common import _log_uncaught_exception, format_log_entry, log_error, log_message


class LoggingTests(unittest.TestCase):
    def test_timestamp_converted_to_utc(self):
        timestamp = datetime(2026, 10, 16, 19, 30, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(
            format_log_entry(timestamp, "test.py", "message"),
            f"2026-10-16 17:30:00 UTC : {'test.py':<26} : message",
        )

    def test_each_message_line_gets_prefix_and_correct_stream(self):
        for logger, stream in ((log_message, "stdout"), (log_error, "stderr")):
            with self.subTest(stream=stream):
                with patch(f"sys.{stream}", new_callable=io.StringIO) as output:
                    logger("test.py", "first\nsecond\r\nthird")
                lines = output.getvalue().splitlines()
                self.assertEqual(len(lines), 3)
                for line, message in zip(lines, ("first", "second", "third")):
                    self.assertRegex(line, rf"^\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}} UTC : test.py +: {message}$")

    def test_traceback_lines_formatted_without_losing_details(self):
        try:
            raise ValueError("first\nsecond")
        except ValueError:
            info = sys.exc_info()
        with patch("sys.stderr", new_callable=io.StringIO) as output, \
                patch("sys.argv", ["example.py"]):
            _log_uncaught_exception(*info)
        lines = output.getvalue().splitlines()
        self.assertTrue(any("Traceback" in line for line in lines))
        self.assertTrue(any("ValueError: first" in line for line in lines))
        self.assertTrue(any(line.endswith(": second") for line in lines))
        for line in lines:
            self.assertRegex(line, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC : example.py +: ")


if __name__ == "__main__":
    unittest.main()
