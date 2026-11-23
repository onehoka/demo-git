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

## Cara menjalankan `upsert.py`

Butuh Python 3.9+ saja, tanpa library tambahan. Jalankan dari root repo:

1. Ambil data dari freddy (`query_metrics`) dan simpan sebagai JSON di `garmin/inbox/`
   (folder ini di-ignore git). Formatnya ada di docstring `scripts/upsert.py`; nama
   metric pakai nama asli freddy, konversi satuan dikerjakan script.
2. Jalankan:

   ```bash
   python3 garmin/scripts/upsert.py garmin/inbox/2026-10-27.json
   ```

3. Cek output, lalu commit perubahan di `garmin/data/`:

   ```
   daily: 1 added, 1 updated, 9 total
   daily: no row for 2026-10-25
   activities: 1 added, 0 updated, 7 total
   ```

Hal yang perlu diketahui:

- **Aman dijalankan berulang.** File yang sama dijalankan dua kali tidak mengubah apa-apa;
  `updated_at` hanya berubah kalau ada nilai yang benar-benar berbeda. Jadi tiap sync
  boleh ambil 7 hari penuh, overlap dengan data lama bukan masalah.
- **Nilai kosong tidak menghapus data.** Metric yang tidak ada / `null` di JSON dibiarkan
  seperti yang sudah tersimpan.
- **Hari yang hilang.** Hari tanpa data sama sekali tidak dibuatkan baris. Setelah upsert,
  script menampilkan tanggal yang bolong di `daily.csv` (`no row for ...`). Kalau masih
  dalam 7 hari terakhir, query ulang tanggal itu di freddy; kalau jam memang nggak
  dipakai, biarkan saja.
- Entri dengan tanggal atau `start_utc` yang tidak valid dilewati dengan peringatan,
  bukan bikin script gagal.

Update otomatis jalan tiap pagi lewat scheduled task Claude.
