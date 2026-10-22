# Laporan beban latihan mingguan

Gabungan lari dari Strava (`strava/data/activities.csv`) dan recovery dari Garmin
(`garmin/data/daily.csv`) jadi satu laporan markdown per minggu (Senin–Minggu).

Per minggu: total km, jumlah lari, total relative effort, perubahan km dibanding minggu lalu
(ditandai ⚠️ kalau naik >10%), jumlah hari lari berturut-turut, rata-rata tidur, HRV, dan RHR.

```bash
python3 training/weekly_report.py                      # 8 minggu terakhir ke layar
python3 training/weekly_report.py --weeks 12 --out training/reports/$(date +%F).md
```

Catatan:
- Yang dihitung lari: `Run`, `TrailRun`, `VirtualRun`. Gym dan aktivitas lain diabaikan.
- Lari Senin setelah lari Minggu dihitung sebagai hari berturut-turut.
- Data tidur Garmin baru mulai 15 Okt 2026, jadi minggu sebelumnya kosong (–).
- Minggu yang sedang berjalan diberi tanda *(berjalan)*.

Test: `cd training && python3 -m unittest test_weekly_report`
