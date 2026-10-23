import tempfile
import unittest
from datetime import date
from pathlib import Path

import weekly_report as wr

STRAVA = """id,start_local,sport_type,name,distance_km,moving_min,elapsed_min,elev_gain_m,relative_effort,calories,updated_at
1,2026-10-04T05:30:00,Run,Sun,4.0,,,,20,,
2,2026-10-05T05:30:00,Run,Mon,5.0,,,,30,,
3,2026-10-06T05:30:00,Run,Tue,6.0,,,,,,
4,2026-10-06T07:00:00,WeightTraining,Gym,0,,,,8,,
5,2026-10-09T05:30:00,Run,Fri,2.0,,,,10,,
6,2026-10-14T05:30:00,Run,Wed,10.0,,,,40,,
"""

GARMIN = """date,hrv_avg_ms,rhr_bpm,sleep_total_min
2026-10-05,40,52,420.0
2026-10-06,30,56,
2026-10-07,35,54,360.0
"""


class WeeklyReportTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "strava.csv").write_text(STRAVA)
        (tmp / "garmin.csv").write_text(GARMIN)
        runs = wr.load_runs(tmp / "strava.csv")
        rec = wr.load_recovery(tmp / "garmin.csv")
        self.weeks = wr.summarize(runs, rec, 2, date(2026, 10, 15))

    def test_week_totals(self):
        w = self.weeks[0]  # Mon 5 Oct – Sun 11 Oct
        self.assertEqual(w["start"], date(2026, 10, 5))
        self.assertAlmostEqual(w["km"], 13.0)
        self.assertEqual(w["runs"], 3)  # gym session ignored
        self.assertEqual(w["effort"], 40)  # run without effort skipped

    def test_week_over_week_flag(self):
        self.assertAlmostEqual(self.weeks[0]["change_pct"], 225.0)  # 4 km -> 13 km
        self.assertTrue(self.weeks[0]["jump"])
        self.assertAlmostEqual(self.weeks[1]["change_pct"], (10 - 13) / 13 * 100)
        self.assertFalse(self.weeks[1]["jump"])
        self.assertTrue(self.weeks[1]["in_progress"])

    def test_back_to_back_crosses_week_boundary(self):
        self.assertEqual(self.weeks[0]["b2b_days"], [date(2026, 10, 5), date(2026, 10, 6)])
        self.assertEqual(self.weeks[1]["b2b_days"], [])

    def test_recovery_averages_skip_missing(self):
        w = self.weeks[0]
        self.assertAlmostEqual(w["sleep_min"], 390.0)
        self.assertEqual(w["sleep_nights"], 2)
        self.assertAlmostEqual(w["hrv_ms"], 35.0)
        self.assertIsNone(self.weeks[1]["sleep_min"])

    def test_render(self):
        md = wr.render(self.weeks, date(2026, 10, 15))
        self.assertIn("**+225%** ⚠️", md)
        self.assertIn("6j 30m", md)
        self.assertIn("Belum ada data tidur", md)


if __name__ == "__main__":
    unittest.main()
