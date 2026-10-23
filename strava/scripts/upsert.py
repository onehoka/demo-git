#!/usr/bin/env python3
"""Upsert Strava activities (as returned by the Strava MCP list_activities tool) into a CSV.

Usage:
    python3 strava/scripts/upsert.py strava/inbox/<file>.json

Input is the list_activities response as-is, either the whole object or just
its "activities" list:

    {"activities": [
      {"id": "20667634258", "name": "Morning Run", "sport_type": "Run",
       "start_local": "2026-10-21T05:05:34",
       "summary": {"distance": 4503.4, "moving_time": 2674, "relative_effort": 39, ...}}
    ]}

Rows are keyed by Strava activity id. An existing row is updated field by
field: a value present in the input replaces the stored one, a missing value
never erases what is already stored. Running the same file twice is a no-op:
updated_at only moves when a stored value actually changes.
"""

import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ACTIVITIES_CSV = DATA_DIR / "activities.csv"


def ident(v):
    return v


def sec_to_min(v):
    return round(float(v) / 60, 1)


def m_to_km(v):
    return round(float(v) / 1000, 3)


def r1(v):
    return round(float(v), 1)


# column -> (field in the activity summary, converter)
SUMMARY_COLUMNS = {
    "distance_km": ("distance", m_to_km),
    "moving_min": ("moving_time", sec_to_min),
    "elapsed_min": ("elapsed_time", sec_to_min),
    "elev_gain_m": ("elevation_gain", r1),
    "relative_effort": ("relative_effort", ident),
    "calories": ("total_calories", ident),
}

HEADER = ["id", "start_local", "sport_type", "name"] + list(SUMMARY_COLUMNS) + ["updated_at"]


def load(path):
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def save(path, rows):
    # Write to a temp file and swap it in, so a crash never leaves a half-written CSV.
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    # mkstemp creates 0600; keep the CSV's existing mode instead.
    os.chmod(tmp, path.stat().st_mode & 0o777 if path.exists() else 0o644)
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
            writer.writeheader()
            for row in sorted(rows.values(), key=lambda r: (r.get("start_local", ""), r["id"])):
                writer.writerow({h: row.get(h, "") for h in HEADER})
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def convert(raw):
    out = {k: raw[k] for k in ("start_local", "sport_type", "name") if raw.get(k) not in (None, "")}
    summary = raw.get("summary") or {}
    for col, (field, fn) in SUMMARY_COLUMNS.items():
        v = summary.get(field)
        if v is None or v == "":
            continue
        out[col] = fn(v)
    return out


def same(stored, v):
    # CSV values come back as strings; compare numbers by value so 139 == "139.0".
    if str(stored) == str(v):
        return True
    try:
        return float(stored) == float(v)
    except (TypeError, ValueError):
        return False


def merge(existing, new, now):
    diff = {k: v for k, v in new.items() if not same(existing.get(k, ""), v)}
    if diff:
        existing.update(diff)
        existing["updated_at"] = now
    return bool(diff)


def main(inbox):
    payload = json.loads(Path(inbox).read_text())
    activities = payload.get("activities", []) if isinstance(payload, dict) else payload
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    rows = load(ACTIVITIES_CSV)
    added = updated = 0
    for raw in activities:
        key = str(raw["id"])
        row = rows.setdefault(key, {"id": key})
        is_new = len(row) == 1
        if merge(row, convert(raw), now):
            added += is_new
            updated += not is_new
    save(ACTIVITIES_CSV, rows)
    print(f"activities: {added} added, {updated} updated, {len(rows)} total")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
