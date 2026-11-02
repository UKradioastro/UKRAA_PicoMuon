import argparse
import configparser
import csv
import datetime as dt
from io import BytesIO
import os
import pandas as pd
from urllib.error import URLError
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, build_opener

from picomuon_common import get_base_path, get_target_date, log_error, log_message
from picomuon_neutrons import write_neutron_header
import nest

PROCESS_NAME = "GetDataNeutron.py"
DOWNLOAD_TIMEOUT_SECONDS = 30
NEST_ORIGIN = "https://nest.nmdb.eu"
NEST_COLUMNS = ("start_date_time", "RPRESS", "RUNCORR", "RCORR_P", "RCORR_E")


def load_nmdb_credentials(base_path):
    path = base_path / "config" / "NMDB.ini"
    if not path.is_file():
        raise FileNotFoundError(f"NMDB credentials file not found: {path}")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise PermissionError(f"NMDB credentials file must be private; run chmod 600 {path}")

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with path.open(encoding="utf-8-sig") as source:
            parser.read_file(source)
        username = parser.get("NMDB", "User_name").strip()
        password = parser.get("NMDB", "Password")
    except configparser.Error as exc:
        raise ValueError(f"Invalid NMDB credentials in {path} ({type(exc).__name__})") from exc
    if not username or not password:
        raise ValueError(f"NMDB username and password must be non-empty in {path}")
    return username, password


def validate_response_window(payload, target):
    query_times = {}
    for line in payload.decode("utf-8-sig", errors="replace").splitlines():
        for label in ("START TIME:", "END TIME:"):
            if label in line:
                value = line.partition(label)[2].split("UTC", 1)[0].strip()
                query_times[label] = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    if set(query_times) != {"START TIME:", "END TIME:"}:
        raise ValueError("NMDB response is missing its query time range")
    start = query_times["START TIME:"]
    end = query_times["END TIME:"]
    if start.date() != target or end.date() != target:
        raise ValueError(f"NMDB returned a different date than requested ({target})")
    if end - start < dt.timedelta(hours=23):
        raise ValueError(f"NMDB response does not cover the full requested day ({start} to {end})")


def prepare_neutron_rows(payload: bytes, target: dt.date) -> bytes:
    lines = []
    timestamps = set()
    for line in payload.decode("utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not lines and tuple(line.split()) == NEST_COLUMNS:
            continue
        row = next(csv.reader([line], delimiter=";"))
        if len(row) != 5:
            raise ValueError("Expected five columns in each NMDB reading")
        timestamp = dt.datetime.strptime(row[0].strip(), "%Y-%m-%d %H:%M:%S")
        if timestamp.date() != target or timestamp.second != 0:
            raise ValueError(f"NMDB returned an unexpected minute: {timestamp}")
        if timestamp in timestamps:
            raise ValueError(f"NMDB returned a duplicate minute: {timestamp}")
        timestamps.add(timestamp)
        lines.append(line)
    if not timestamps:
        raise ValueError(f"NMDB returned no neutron readings for {target}")
    if max(timestamps) - min(timestamps) < dt.timedelta(hours=23):
        raise ValueError("NMDB readings do not cover the full requested day")
    missing = 1440 - len(timestamps)
    if missing:
        log_message(PROCESS_NAME, f"WARNING - NMDB data for {target}: {missing}/1440 minutes missing; gaps retained")
    return ("\n".join(lines) + "\n").encode("utf-8")


def download_neutron_data(base_path, target):
    username, password = load_nmdb_credentials(base_path)
    start = dt.datetime.combine(target, dt.time.min)
    end = dt.datetime.combine(target, dt.time(23, 59, 59))
    station = "oulu"
    data = ["p", "u", "c", "e"]
    download = nest.single(station, "revori", data, start, end)

    password_manager = HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, NEST_ORIGIN, username, password)
    opener = build_opener(HTTPBasicAuthHandler(password_manager))
    with opener.open(download, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        payload = response.read()
    validate_response_window(payload, target)

    names = ["start_date_time", *data]
    rows = prepare_neutron_rows(payload, target)
    df = pd.read_table(BytesIO(rows), sep=";", header=None, names=names)
    if df.empty:
        raise ValueError(f"NMDB returned no neutron readings for {target}")

    output = base_path / "data" / "neutrons" / target.strftime("%Y") / target.strftime("%Y-%m") / f"{target}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".txt.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            write_neutron_header(handle, station, download)
            df.to_csv(handle, sep=",", index=False, header=False)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    log_message(PROCESS_NAME, f"Completed neutron data download for {target} ({len(df)} rows)")
    return output


def main():
    parser = argparse.ArgumentParser(description="Download one completed UTC day of OULU neutron data.")
    parser.add_argument("--date", type=dt.date.fromisoformat, help="UTC date to fetch; defaults to the pipeline target date")
    args = parser.parse_args()
    target = args.date or get_target_date()
    base_path = get_base_path()
    log_message(PROCESS_NAME, f"Started neutron data download for {target}")
    try:
        download_neutron_data(base_path, target)
    except (URLError, OSError, ValueError, configparser.Error) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        log_error(PROCESS_NAME, f"FAILED - NMDB download for {target}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
