# CONTEXT LANJUTAN OTOMET - Tempel ke New Session
## 1. Project
- Dir: `c:/Project/otomet`, win32, VS Code, Python 3.14.0
- App: Otomet Dashboard FastAPI+Jinja2+SQLite untuk Web Automation & Appium
- Entry: `run_dashboard.py` -> `backend.app:app` -> http://127.0.0.1:8000/
- DB: `backend/db/data/otomet.db` + `backend/db/schema.sql`
- Fitur kunci: GUI Uji Nyata Chrome 2HP paralel (Appium) + Simulasi FakeDriver, Sessions, Runs, Reports PDF/XLSX

## 2. Goal Terakhir (90% SELESAI)
Fix dashboard gagal terbuka/startup crash agar GUI real parallel Chrome 2-device bisa dibuka lagi.

## 3. Diagnosa Terakhir (TERBUKTI via TestClient)
Skrip: `c:/Project/otomet/diag_startup2.py` -> `diag_startup2.log`
- IMPORT backend.app OK, routes=74
- GET /health 200, GET / 200 len7979, GET /api/runs/demo/real-2device/view 200 len7174
- Router OK semua: clients,pages,elements,scenarios,recalibration,orchestrator,broadcast,runs,reports
- Orchestrator OK: device_pool,runner,chrome_real + db.database OK
- py_compile app.py,run_dashboard.py,runs.py,chrome_real.py,runner.py = 0
- Tabel ada: clients,devices,pages,elements,scenarios,sessions,scenario_assignments,runs,test_data_pool,dll
- Versi: fastapi 0.135.1, uvicorn 0.41.0, jinja2 3.1.6, aiosqlite 0.20.0, python-multipart 0.0.22
- MISSING (ganggu Real saja): adbutils, Appium-Python-Client
- Template ada: backend/static, templates, runs/demo_real.html, session_runs.html, index.html, base.html

Kesimpulan: Kode TIDAK crash. Gagal terbuka karena launcher+startup rapuh:
1. run_dashboard lama reload=True -> 2 proses di Windows
2. Tak ada autobrowser + cek port -> dikira gagal (ada 127.0.0.1:5037 LISTENING=ADB)
3. app.mount(/static) crash bila folder hilang
4. DB tak di-init saat startup
5. VSCode shell-integration failure -> output tak tampil
6. Missing deps Real -> tombol Real 400 fail-closed, Simulasi tetap jalan

## 4. Fix SUDAH Dipasang (Jangan Diulang)
A. backend/app.py: tambah lifespan db.connect+initialize_schema idempotent, db.close saat shutdown, STATIC_DIR.mkdir+TEMPLATES_DIR.mkdir sebelum mount, 9 router + GET / + GET /health phase 8.
B. run_dashboard.py: reload=False, sys.path root, HOST 127.0.0.1 PORT 8000, port_sibuk() via socket, autobrowser Timer 1.2s, log [otomet] jelas.
C. diag_startup2.py BARU: cek folder, import per-router, list routes, TestClient 3 halaman, sqlite tables, versi pkg.

## 5. File Kunci
- c:/Project/otomet/run_dashboard.py
- c:/Project/otomet/backend/app.py
- c:/Project/otomet/backend/api/runs.py (POST demo/real-2device, GET view, POST sessions/id/run mode simulate/real)
- c:/Project/otomet/backend/orchestrator/chrome_real.py, runner.py, device_pool.py, session_manager.py
- c:/Project/otomet/backend/db/database.py, db/schema.sql, db/repositories/*.py
- c:/Project/otomet/backend/templates/index.html, base.html, runs/demo_real.html, runs/session_runs.html
- c:/Project/otomet/requirements.txt, jalankan_phase7_real_2device.py, diag_startup2.py, diag_startup2.log

## 6. Verifikasi WAJIB New Session
cd c:/Project/otomet
python -m py_compile backend/app.py run_dashboard.py
python diag_startup2.py (harap IMPORT OK + GET 200 semua)
python run_dashboard.py (harap [otomet] Menyalakan + browser terbuka http://127.0.0.1:8000/)
manual: /health, /, /api/runs/demo/real-2device/view

## 7. Batasan
- Real 2HP butuh: pip install -r requirements.txt, adb connect 192.168.100.50:42851 + 192.168.100.81:37251, adb devices 2 device, appium -p 4723 + -p 4724, Chrome di HP. Tanpa itu Real 400 fail-closed.
- Port 8000 tabrakan -> netstat -ano | findstr 8000 lalu kill PID lama.
- Selalu cd c:/Project/otomet. Shell-integration kadang gagal capture -> baca file .log via read_files.

## 8. Next + Prompt Tempelan
Next: 1) verifikasi ulang diag+run_dashboard bisa buka browser, 2) pip install adbutils Appium-Python-Client + uji ADB+Appium, 3) uji GUI Setup->Real Chrome 2HP->Laporan PDF/XLSX, 4) tambah GET /ready, retry Appium, pesan error ramah, unit test TestClient, 5) rapikan log + tambah static/.gitkeep. Jangan ubah runner.py inti tanpa konfirmasi.

PROMPT:
Lanjutkan perbaikan Otomet di c:/Project/otomet. Dashboard FastAPI sudah difix (app.py lifespan+static mkdir, run_dashboard reload=False+autobrowser+cek port). TestClient: 74 routes, GET /health, /, demo/real-2device/view 200. Missing hanya adbutils+Appium (ganggu Real saja). Tugas: 1) verifikasi diag_startup2.py + run_dashboard.py terbuka di browser, 2) lengkapi deps + uji ADB WiFi 2HP + Appium 4723/4724, 3) uji GUI Setup->Real Chrome->Laporan, 4) sempurnakan error handling + /ready + unit test. Jangan ubah runner.py inti. Validasi py_compile+TestClient+baca log. Pakai absolute paths.

## 9. Rencana Phase Selanjutnya JIKA Uji Real 2HP BERHASIL
Asumsi pemicu: Setup Sesi Real 2HP 200 + klik Real Chrome 2HP passed 2/2 di Riwayat Runs + Laporan PDF/XLSX terunduh + DATA GANDA=False.

### 9.0 Definisi Lulus Uji Real (DoD, cek dulu sebelum lanjut phase)
- [ ] `POST /api/runs/demo/real-2device` 200, health 2 device `healthy`, gate `passed`
- [ ] `POST /api/runs/sessions/{id}/run {"mode":"real"}` 200, ringkasan `passed=2 failed=0 blocked=0`
- [ ] Chrome benar terbuka di 2 HP (visual), URL `https://example.com` ter-load <30 dtk/device
- [ ] `GET /api/runs/sessions/{id}/runs/view` tampil 2 baris + `GET .../reports/sessions/{id}/view` + PDF/XLSX 200
- [ ] Ulang 3x berturut lulus (anti-flaky). Simpan `session_id` lulus sebagai baseline di log.

### Phase 9 - Hardening & Observability (WAJIB pertama, 1-2 hari)
Tujuan: real yang lulus 1x jadi lulus 10x.
- Tambah `GET /health` -> tambah `GET /ready` di `backend/app.py`: cek DB connect + `SELECT 1`, cek templates, cek adb (`adb devices` timeout 5s), cek appium `http://127.0.0.1:4723/status` + `:4724/status`. Return `{ready:bool, checks:{...}}`.
- Retry Appium di `backend/orchestrator/chrome_real.py`: `new_driver` retry 2x backoff 2s/5s, `quit()` di `finally`, screenshot `*_fail.png` ke `backend/static/runs/{run_id}/` saat fail, simpan path ke `runs.failure_category/detail`.
- Timeout eksplisit: ADB 10s, Appium new-session 30s, open_url+assert 60s/device. Fail-closed + `failure_category` konsisten: `appium_down|adb_putus|chrome_crash|timeout|assert_gagal`.
- Log terstruktur: tiap run tulis `[real][sess {id}][dev {adb}][data {id}] start/ok/fail (Xs)` via `logging`, bukan cuma `print`.
- Verifikasi: `py_compile`, `TestClient GET /ready 200`, cabut 1 HP -> Real 1 passed 1 failed (bukan hang), `diag_startup2.py` tetap 200 semua.
- File sentuh: `backend/app.py`, `backend/orchestrator/chrome_real.py`, `backend/orchestrator/runner.py` (tambah try/finally saja), `backend/templates/runs/session_runs.html` (tampil kategori gagal).

### Phase 10 - Scale N-Device + Antrean (2-4 hari, setelah Phase 9 hijau)
- `device_pool.py`: ganti mapping fix A/B + port fix 4723/4724 jadi pool dinamis `{adb_id: appium_url}` dari ENV/DB. `POST /api/orchestrator/devices` terima `appium_url`.
- `runner.py`: `semaphore = min(len(devices), max_parallel)` + stagger start `0.8s * idx` + klaim atomik `test_data_pool` dipertahankan. Dukung 3-4 HP tanpa ubah API.
- Tambah `POST /api/runs/sessions/{id}/run?mode=real&limit=N` + GUI dropdown jumlah device. Antrean: jika device sibuk -> status `queued`, bukan `blocked`.
- Verifikasi: simulasi 4 device passed, real 2HP tetap passed, cek `DATA GANDA=False` via `SELECT test_data_id, COUNT(*) ... HAVING COUNT(*)>1` = 0.
- File sentuh: `device_pool.py`, `runner.py`, `api/runs.py`, `session_runs.html`, `schema.sql` (tambah kolom `queued_at` bila perlu).

### Phase 11 - Skenario Multi-Step & Data-Driven (3-5 hari)
- Perluas `scenarios` dari `open_url` tunggal ke steps JSON: `[{action:open_url|tap|input|assert_text, ...}]`. Validasi di `api/scenarios.py`, versi + rollback tetap jalan.
- `test_data_pool`: generator CSV->pool + klaim atomik per-step, deteksi ganda otomatis.
- Tambah `failure_category=assert_gagal` + simpan `expected_vs_actual` di detail run.
- Verifikasi: 1 skenario 3-step lulus di 2HP real, rollback versi jalan, `GET /api/scenarios/{id}/view` tampil steps.
- File sentuh: `api/scenarios.py`, `db/repositories/scenario_repo.py`, `schema.sql`, `orchestrator/*`, template builder.

### Phase 12 - Regresi, Jadwal & CI (2-3 hari)
- Endpoint `POST /api/broadcast/run` + `POST /api/runs/broadcast/physical` jadi nightly: tambah `cron`/`apscheduler` opsional + flag `is_nightly`.
- Export PDF/XLSX: tambah grafik trend `reports/clients/{id}/trend` + lampiran screenshot fail.
- Tambah `pytest` minimal: `tests/test_health.py`, `test_demo_view.py`, `test_simulate_2device.py` pakai `TestClient`. Gate: semua hijau sebelum merge.
- Verifikasi: `pytest -q` hijau, PDF/XLSX bisa dibuka, trend tampil.
- File sentuh: `backend/reporting/*`, `backend/api/reports.py`, `tests/*`, `requirements.txt` (tambah `pytest-asyncio` sudah ada).

### Phase 13 - UX Operasional & Rilis (1-2 hari)
- Dashboard: badge `/ready`, tombol `Cek Devices`, `Setup 2HP`, `Real Chrome`, `Laporan` dalam 1 alur; toast error ramah (misal `Appium 4724 mati - jalankan appium -p 4724`).
- Operasional: `run_dashboard.py` tambah `--port`, `--no-browser`; `backend/static/.gitkeep`; hapus `diag*.log` kosong; tulis `README_REAL_2HP.md` (prasyarat ADB+Appium+Chrome).
- Tag rilis `v1.0-real2hp-ok` setelah DoD 9.0 + Phase 9 hijau.
- DILARANG tanpa konfirmasi: ubah inti klaim atomik `runner.py`, hapus fail-closed jadi pass-paksa.

### Urutan Eksekusi Anjuran
1. Kunci baseline DoD 9.0 (simpan session_id + log). 2. Phase 9 -> uji cabut-kabel/ matikan 1 Appium. 3. Phase 10 (kalau butuh >2HP) atau loncat ke 11. 4. Phase 11 -> 12 -> 13. Setiap phase tutup dengan `py_compile + diag_startup2.py + pytest + 1x real 2HP`.

