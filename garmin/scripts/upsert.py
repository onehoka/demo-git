#!/usr/bin/env python3
"""Upsert Garmin metrics (as returned by the freddy MCP server) into the CSV database.

Usage:
    python3 garmin/scripts/upsert.py garmin/inbox/<file>.json

Input JSON uses freddy's raw metric names, so whoever fetches the data does not
have to convert units:

    {
      "daily": {
        "2026-10-22": {"hrv_lastNightAvg": 30, "sleep_durationInSeconds": 17160, ...}
      },
      "activities": [
        {"start_utc": "2026-10-20T22:05", "utc_offset_s": 25200,
         "activity_activityName": "Interval", "activity_distanceInMeters": 4503.4, ...}
      ]
    }

Rows are keyed by date (daily) and start_utc (activities). An existing row is
updated field by field: a value present in the input replaces the stored one,
a missing value never erases what is already stored.
"""

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_CSV = DATA_DIR / "daily.csv"
ACTIVITIES_CSV = DATA_DIR / "activities.csv"


def ident(v):
    return v


def sec_to_min(v):
    return round(float(v) / 60, 1)


def m_to_km(v):
    return round(float(v) / 1000, 3)


def mm_to_m(v):
    return round(float(v) / 1000, 3)


def r1(v):
    return round(float(v), 1)


def r2(v):
    return round(float(v), 2)


# column -> (freddy metric, converter)
DAILY_COLUMNS = {
    "hrv_avg_ms": ("hrv_lastNightAvg", ident),
    "hrv_5min_high_ms": ("hrv_lastNight5MinHigh", ident),
    "rhr_bpm": ("daily_restingHeartRateInBeatsPerMinute", ident),
    "sleep_score": ("sleep_overallSleepScore", ident),
    "sleep_total_min": ("sleep_durationInSeconds", sec_to_min),
    "sleep_deep_min": ("sleep_deepSleepDurationInSeconds", sec_to_min),
    "sleep_rem_min": ("sleep_remSleepInSeconds", sec_to_min),
    "sleep_light_min": ("sleep_lightSleepDurationInSeconds", sec_to_min),
    "sleep_awake_min": ("sleep_awakeDurationInSeconds", sec_to_min),
    "body_battery_charged": ("dailyBodyBattery_chargedValue", ident),
    "body_battery_drained": ("dailyBodyBattery_drainedValue", ident),
    "stress_avg": ("daily_averageStressLevel", ident),
    "steps": ("daily_steps", ident),
    "active_kcal": ("daily_activeKilocalories", ident),
    "moderate_min": ("daily_moderateIntensityDurationInSeconds", sec_to_min),
    "vigorous_min": ("daily_vigorousIntensityDurationInSeconds", sec_to_min),
    "vo2max": ("userMetrics_vo2Max", ident),
    "fitness_age": ("userMetrics_fitnessAge", ident),
    "skin_temp_dev_c": ("skinTemp_avgDeviationCelsius", r1),
    "spo2_avg_pct": ("pulseOx_avgSpo2InPercent", r1),
}

ACTIVITY_COLUMNS = {
    "type": ("activity_activityType", ident),
    "name": ("activity_activityName", ident),
    "duration_min": ("activity_durationInSeconds", sec_to_min),
    "distance_km": ("activity_distanceInMeters", m_to_km),
    "pace_min_km": ("activity_averagePaceInMinutesPerKilometer", r2),
    "avg_hr": ("activity_averageHeartRateInBeatsPerMinute", ident),
    "max_hr": ("activity_maxHeartRateInBeatsPerMinute", ident),
    "cadence_spm": ("activity_averageRunCadenceInStepsPerMinute", r1),
    "elev_gain_m": ("activity_totalElevationGainInMeters", ident),
    "avg_power_w": ("activityDetail_averagePowerInWatts", ident),
    "norm_power_w": ("activityDetail_normalizedPowerInWatts", ident),
    "gct_ms": ("activity_avgGroundContactTime", r1),
    "vert_osc_mm": ("activity_avgVerticalOscillation", r1),
    "vert_ratio_pct": ("activity_avgVerticalRatio", r2),
    "stride_m": ("activity_avgStrideLength", mm_to_m),
    "air_temp_c": ("activityDetail_averageAirTemperatureCelsius", r1),
    "active_kcal": ("activity_activeKilocalories", ident),
}

DAILY_HEADER = ["date"] + list(DAILY_COLUMNS) + ["updated_at"]
ACTIVITY_HEADER = ["start_utc", "start_local"] + list(ACTIVITY_COLUMNS) + ["updated_at"]


def load(path, key):
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {row[key]: row for row in csv.DictReader(f)}


def save(path, header, rows, key):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for k in sorted(rows):
            writer.writerow({h: rows[k].get(h, "") for h in header})


def convert(raw, columns):
    out = {}
    for col, (metric, fn) in columns.items():
        v = raw.get(metric)
        if v is None or v == "":
            continue
        out[col] = fn(v)
    return out


def merge(existing, new, now):
    changed = any(str(existing.get(k, "")) != str(v) for k, v in new.items())
    if changed:
        existing.update({k: v for k, v in new.items()})
        existing["updated_at"] = now
    return changed


def local_time(start_utc, offset_s):
    if offset_s in (None, ""):
        return ""
    t = datetime.fromisoformat(start_utc) + timedelta(seconds=int(offset_s))
    return t.strftime("%Y-%m-%dT%H:%M")


def main(inbox):
    payload = json.loads(Path(inbox).read_text())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    daily = load(DAILY_CSV, "date")
    added = updated = 0
    for date, raw in payload.get("daily", {}).items():
        new = convert(raw, DAILY_COLUMNS)
        if not new:
            continue
        row = daily.setdefault(date, {"date": date})
        is_new = len(row) == 1
        if merge(row, new, now):
            added += is_new
            updated += not is_new
    save(DAILY_CSV, DAILY_HEADER, daily, "date")
    print(f"daily: {added} added, {updated} updated, {len(daily)} total")

    acts = load(ACTIVITIES_CSV, "start_utc")
    added = updated = 0
    for raw in payload.get("activities", []):
        start = raw["start_utc"]
        new = convert(raw, ACTIVITY_COLUMNS)
        local = local_time(start, raw.get("utc_offset_s"))
        if local:
            new["start_local"] = local
        row = acts.setdefault(start, {"start_utc": start})
        is_new = len(row) == 1
        if merge(row, new, now):
            added += is_new
            updated += not is_new
    save(ACTIVITIES_CSV, ACTIVITY_HEADER, acts, "start_utc")
    print(f"activities: {added} added, {updated} updated, {len(acts)} total")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
