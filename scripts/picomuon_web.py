"""Publish isolated, date-labelled static detector views without changing legacy URLs."""

from __future__ import annotations

from datetime import date, datetime, timezone
import html
import json
from pathlib import Path
import tempfile
from typing import Optional

from picomuon_common import build_processed_day_path, log_message
from picomuon_detectors import get_detectors
from picomuon_processing import processing_label


def plot_files(base: Path, label: str, target: date) -> list[Path]:
    root = base / "temp" / "detectors" / label
    files = [
        root / "yesterday" / f"{label}_{event}-{kind}.png"
        for kind in ("Cpm", "Freq", "Adc") for event in ("T", "B", "C")
    ]
    for period in ("day", "week", "month"):
        product = build_processed_day_path(base, period, target, label, named_detector=True)
        if period == "day" or product.is_file():
            files.append(root / "periods" / f"{label}_{period}_plot.png")
    return files


def atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
        temporary.chmod(0o644)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def page(title: str, body: str) -> bytes:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2em auto;padding:0 1em}"
        "img{max-width:100%;height:auto}figure{display:inline-block;margin:1em 0}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}nav a{margin-right:1em}</style>"
        f"</head><body>{body}</body></html>\n"
    ).encode("utf-8")


def publish_detector(base: Path, label: str, target: date, web_root: Path) -> None:
    processing_label(base, label)
    # Validate the complete set before changing any published page.
    images = {}
    for path in plot_files(base, label, target):
        contents = path.read_bytes()
        if not contents.startswith(b"\x89PNG\r\n\x1a\n") or len(contents) < 24:
            raise ValueError(f"Invalid or empty PNG plot: {path}")
        images[path.name] = contents
    status_file = base / "data" / "status" / label / "current.json"
    status = None
    if status_file.exists():
        status = json.loads(status_file.read_text(encoding="utf-8"))
        if not isinstance(status, dict):
            raise ValueError(f"Invalid detector status object: {status_file}")
    destination = web_root / "detectors" / label
    dated = destination / str(target)
    for name, contents in images.items():
        atomic_write(dated / name, contents)
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    snapshot = {"label": label, "snapshot_utc": captured, "collector_status": status}
    atomic_write(destination / "status.json", (json.dumps(snapshot, indent=2) + "\n").encode("utf-8"))
    escaped = html.escape(label)
    figures = "".join(
        f'<figure><figcaption>{html.escape(name)}</figcaption>'
        f'<img src="{target}/{html.escape(name, quote=True)}" alt="{html.escape(name, quote=True)}" loading="lazy"></figure>'
        for name in images
    )
    unavailable = [
        period for period in ("week", "month")
        if not build_processed_day_path(base, period, target, label, named_detector=True).is_file()
    ]
    body = (
        '<nav><a href="../index.html">All detectors</a></nav>'
        f"<h1>PicoMuon detector: {escaped}</h1>"
        f"<p>Plots for UTC day ending <strong>{target}</strong>. Counts are not combined with other detectors.</p>"
        "<p>No accuracy is claimed for published data. A partial day is not full-day coverage.</p>"
        f"<p>Not available for this date: {html.escape(', '.join(unavailable) or 'none')}.</p>"
        f"<h2>Collector status snapshot</h2><p>Captured {captured}; not a live connection indicator. "
        "Check the last-event timestamp; an old snapshot does not prove collection is running.</p>"
        f'<p><a href="status.json">Status snapshot JSON</a></p>'
        f"<pre>{html.escape(json.dumps(status, indent=2) if status is not None else 'No collector status available')}</pre>"
        f"<h2>Plots</h2>{figures}"
        '<p>Neutron data: <a href="https://www.nmdb.eu/">NMDB</a> / Oulu neutron monitor, University of Oulu. '
        "We acknowledge the NMDB database (www.nmdb.eu), founded under the European Union's FP7 programme "
        "(contract no. 213007), and the Oulu neutron monitor data providers.</p>"
        '<p>Optional modelled 2 m air temperature: <a href="https://open-meteo.com/">Open-Meteo</a>, '
        '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>; not a local thermometer measurement.</p>'
    )
    atomic_write(destination / "index.html", page(f"PicoMuon {label} - {target}", body))
    publish_index(base, web_root)
    log_message(f"Publish[{label}]", f"Published {len(images)} plots for {target} to {destination}")


def publish_index(base: Path, web_root: Path) -> None:
    entries = []
    for label in get_detectors(base):
        text = html.escape(label)
        if (web_root / "detectors" / label / "index.html").is_file():
            entries.append(f'<li><a href="{text}/index.html">{text}</a></li>')
        else:
            entries.append(f"<li>{text} - no published run yet</li>")
    atomic_write(
        web_root / "detectors" / "index.html",
        page("PicoMuon detectors", "<h1>PicoMuon detectors</h1>"
             "<p>Separate detector views. Each page states its processed UTC date and status snapshot time.</p>"
             "<ul>" + "".join(entries) + "</ul>"),
    )
