#!/usr/bin/env python3
"""Compatibility entry point for the shared week CSV writer."""

from picomuon_common import get_target_date
from ProcessPeriod import process_period_data

if __name__ == "__main__":
    result = process_period_data("week", get_target_date())
    if result:
        raise SystemExit(result)
