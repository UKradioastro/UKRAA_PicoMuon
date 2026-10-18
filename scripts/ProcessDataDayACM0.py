#!/usr/bin/env python3
"""Compatibility entry point; regenerate daily products with the shared CSV schema."""

from picomuon_common import get_target_date
from ProcessDaily import process_daily

if __name__ == "__main__":
    result = process_daily(get_target_date())
    if result:
        raise SystemExit(result)
