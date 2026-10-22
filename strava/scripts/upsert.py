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
never erases what is already stored.
"""

import csv
import json
import sys
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows.values(), key=lambda r: (r.get("start_local", ""), r["id"])):
            writer.writerow({h: row.get(h, "") for h in HEADER})


def convert(raw):
    out = {k: raw[k] for k in ("start_local", "sport_type", "name") if raw.get(k) not in (None, "")}
    summary = raw.get("summary") or {}
    for col, (field, fn) in SUMMARY_COLUMNS.items():
        v = summary.get(field)
        if v is None or v == "":
            continue
        out[col] = fn(v)
    return out


def merge(existing, new, now):
    changed = any(str(existing.get(k, "")) != str(v) for k, v in new.items())
    if changed:
        existing.update(new)
        existing["updated_at"] = now
    return changed


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
