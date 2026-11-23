#!/usr/bin/env python3
"""Weekly training load report: Strava runs + Garmin recovery (sleep, HRV).

Usage:
    python3 training/weekly_report.py [--weeks 8] [--today 2026-10-23] [--out FILE]

Reads strava/data/activities.csv (runs, relative effort) and
garmin/data/daily.csv (sleep, HRV, resting HR) and prints a markdown report.
Weeks run Monday to Sunday, using the activity's local date. A Garmin row for
date X holds the night that ended on the morning of X, so it counts toward the
week that contains X.

Per week: km, run count, total relative effort, week-over-week km change
(flagged above +10%), back-to-back run days, average sleep, HRV and resting HR.
"""

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRAVA_CSV = ROOT / "strava" / "data" / "activities.csv"
GARMIN_DAILY_CSV = ROOT / "garmin" / "data" / "daily.csv"

RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}
JUMP_LIMIT_PCT = 10
# Strava start_local and Garmin dates are WIB, so "today" must be too (runs may happen in UTC).
WIB = timezone(timedelta(hours=7))


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    return float(v) if v not in (None, "") else None


def week_start(d):
    return d - timedelta(days=d.weekday())


def load_runs(path):
    runs = []
    for row in read_csv(path):
        if row.get("sport_type") not in RUN_TYPES:
            continue
        runs.append({
            "date": datetime.fromisoformat(row["start_local"]).date(),
            "km": num(row.get("distance_km")) or 0.0,
            "effort": num(row.get("relative_effort")),
        })
    return runs


def load_recovery(path):
    days = {}
    for row in read_csv(path):
        days[date.fromisoformat(row["date"])] = {
            "sleep_min": num(row.get("sleep_total_min")),
            "hrv_ms": num(row.get("hrv_avg_ms")),
            "rhr_bpm": num(row.get("rhr_bpm")),
        }
    return days


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(runs, recovery, weeks, today):
    """Return one dict per week, oldest first, ending with the week of `today`."""
    run_days = defaultdict(list)
    for r in runs:
        run_days[r["date"]].append(r)

    last = week_start(today)
    # One extra week in front so the first shown week has a week-over-week value.
    starts = [last - timedelta(weeks=i) for i in range(weeks, -1, -1)]

    out = []
    prev_km = None
    for start in starts:
        days = [start + timedelta(days=i) for i in range(7)]
        week_runs = [r for d in days for r in run_days[d]]
        km = sum(r["km"] for r in week_runs)
        efforts = [r["effort"] for r in week_runs if r["effort"] is not None]

        # A run on Monday after a run on the previous Sunday also counts.
        b2b = [d for d in days if run_days[d] and run_days[d - timedelta(days=1)]]

        rec = [recovery[d] for d in days if d in recovery]
        change = None
        if prev_km:
            change = (km - prev_km) / prev_km * 100

        out.append({
            "start": start,
            "end": days[-1],
            "in_progress": days[-1] >= today,
            "km": km,
            "runs": len(week_runs),
            "effort": sum(efforts) if efforts else None,
            "change_pct": change,
            "jump": change is not None and change > JUMP_LIMIT_PCT,
            "b2b_days": b2b,
            "sleep_min": mean(r["sleep_min"] for r in rec),
            "sleep_nights": sum(r["sleep_min"] is not None for r in rec),
            "hrv_ms": mean(r["hrv_ms"] for r in rec),
            "rhr_bpm": mean(r["rhr_bpm"] for r in rec),
        })
        prev_km = km
    return out[1:]


def fmt(v, spec, missing="–"):
    return missing if v is None else format(v, spec)


def fmt_sleep(minutes):
    if minutes is None:
        return "–"
    h, m = divmod(round(minutes), 60)
    return f"{h}j {m:02d}m"


def fmt_change(w):
    if w["change_pct"] is None:
        return "–"
    s = f"{w['change_pct']:+.0f}%"
    return f"**{s}** ⚠️" if w["jump"] else s


def week_label(w):
    label = f"{w['start']:%d %b} – {w['end']:%d %b}"
    return label + " *(berjalan)*" if w["in_progress"] else label


def render(weeks, today):
    lines = [
        f"# Laporan beban latihan mingguan",
        "",
        f"Dibuat {today:%d %b %Y}. Lari dari Strava, recovery (tidur, HRV, RHR) dari Garmin.",
        f"Minggu = Senin–Minggu. ⚠️ = jarak naik lebih dari {JUMP_LIMIT_PCT}% dari minggu sebelumnya.",
        "",
        "| Minggu | Km | Lari | Relative effort | Δ km | Lari beruntun | Rata-rata tidur | HRV | RHR |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for w in weeks:
        lines.append(
            f"| {week_label(w)} | {w['km']:.1f} | {w['runs']} | {fmt(w['effort'], '.0f')} "
            f"| {fmt_change(w)} | {len(w['b2b_days'])} | {fmt_sleep(w['sleep_min'])} "
            f"| {fmt(w['hrv_ms'], '.0f')} | {fmt(w['rhr_bpm'], '.0f')} |"
        )

    latest = weeks[-1]
    lines += ["", f"## Minggu ini ({week_label(latest)})", ""]
    lines.append(f"- **{latest['km']:.1f} km** dalam {latest['runs']} lari, "
                 f"relative effort {fmt(latest['effort'], '.0f')}.")
    if latest["change_pct"] is not None:
        note = " Naik lebih dari 10%, pertimbangkan minggu berikutnya lebih ringan." if latest["jump"] else ""
        lines.append(f"- Dibanding minggu lalu: {latest['change_pct']:+.0f}%.{note}")
    if latest["b2b_days"]:
        days = ", ".join(f"{d:%a %d %b}" for d in latest["b2b_days"])
        lines.append(f"- Lari di hari berturut-turut: {days}.")
    else:
        lines.append("- Tidak ada lari di hari berturut-turut.")
    if latest["sleep_nights"]:
        lines.append(f"- Tidur rata-rata {fmt_sleep(latest['sleep_min'])} "
                     f"({latest['sleep_nights']} malam tercatat), HRV {fmt(latest['hrv_ms'], '.0f')} ms, "
                     f"RHR {fmt(latest['rhr_bpm'], '.0f')} bpm.")
    else:
        lines.append("- Belum ada data tidur Garmin untuk minggu ini.")

    jumps = [w for w in weeks if w["jump"]]
    if jumps:
        lines += ["", "## Lonjakan jarak >10%", ""]
        for w in jumps:
            lines.append(f"- {week_label(w)}: {w['km']:.1f} km ({w['change_pct']:+.0f}%)")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--weeks", type=int, default=8, help="number of weeks to show (default 8)")
    p.add_argument("--today", type=date.fromisoformat, default=datetime.now(WIB).date(),
                   help="report date, YYYY-MM-DD (default: today in WIB)")
    p.add_argument("--strava", type=Path, default=STRAVA_CSV)
    p.add_argument("--garmin", type=Path, default=GARMIN_DAILY_CSV)
    p.add_argument("--out", type=Path, help="write the report here instead of stdout")
    args = p.parse_args(argv)

    weeks = summarize(load_runs(args.strava), load_recovery(args.garmin), args.weeks, args.today)
    report = render(weeks, args.today)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        print(f"wrote {args.out}")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
