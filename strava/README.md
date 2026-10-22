# Strava activity database

Aktivitas Strava (lari, gym) diambil lewat konektor Strava dan disimpan di sini supaya
laporan mingguan bisa dibuat tanpa query ulang.

## File

- `data/activities.csv` — satu baris per aktivitas: tanggal lokal, jenis, jarak, waktu, elevasi, relative effort, kalori.
- `scripts/upsert.py` — masukin JSON hasil `list_activities` ke CSV (key = id Strava, update per field, nggak bikin duplikat).

## Update manual

```bash
python3 strava/scripts/upsert.py strava/inbox/<tanggal>.json
```

`start_local` = jam lokal (WIB) dari Strava, jadi lari pagi tercatat di tanggal yang benar.
