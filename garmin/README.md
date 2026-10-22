# Garmin performance database

Data harian dan aktivitas dari Garmin Forerunner 265, diambil lewat konektor freddy
dan dikumpulkan di sini supaya riwayatnya numpuk (freddy plan Free cuma bisa query 7 hari terakhir).

## File

- `data/daily.csv` — satu baris per hari: HRV, RHR, sleep, Body Battery, stress, VO2max, skin temp, SpO2.
- `data/activities.csv` — satu baris per aktivitas: jarak, pace, HR, cadence, power, running dynamics.
- `scripts/upsert.py` — masukin JSON hasil freddy ke CSV (update per field, nggak bikin duplikat).

## Catatan data

- `date` di `daily.csv` = tanggal yang dilaporkan Garmin. Data tidur/HRV di tanggal X = tidur malam yang berakhir di pagi tanggal X.
- `start_utc` = jam mulai aktivitas dalam UTC; `start_local` = jam lokal (WIB). Lari pagi jam 05:00 WIB tercatat di tanggal UTC sehari sebelumnya.
- Hari yang sedang berjalan bisa belum lengkap; sync berikutnya akan meng-update barisnya.
- Kolom kosong = Garmin nggak punya data (misal jam nggak dipakai tidur).

## Update manual

```bash
python3 garmin/scripts/upsert.py garmin/inbox/<tanggal>.json
```

Format JSON-nya ada di docstring `scripts/upsert.py`. Update otomatis jalan tiap pagi lewat scheduled task Claude.
