# Otomet - Web Automation & Appium System

Sistem analisa komponen website secara generik + automation testing dengan Appium multi-device.

## Project Structure

```
otomet/
├── backend/
│   ├── scanner/          # Phase 1 - DOM Scanner & Scorer
│   ├── db/               # Phase 2 - Database & Repositories
│   ├── backup/           # Phase 2 - Backup System
│   ├── api/              # Phase 3 - FastAPI Routes (+ Phase 5 recalibration, Phase 6 orchestrator/broadcast)
│   ├── recalibration/   # Phase 5 - Matcher 3-sinyal + headless + gate
│   ├── orchestrator/     # Phase 6 - Device pool + pairing sesi + broadcast
│   ├── templates/        # Phase 3 - Jinja2 Templates (+ recalibration/, devices/, sessions/, broadcast/)
│   ├── static/           # Phase 3 - Static Files
│   ├── app.py            # Phase 3 - FastAPI App
│   └── config.py         # Configuration
├── docs/                 # Documentation
├── tests/                # Unit Tests
├── requirements.txt      # Dependencies
└── run_dashboard.py      # Dashboard Entry Point
```

## Current Status

✅ **Phase 1**: DOM Scanner & Scorer - COMPLETED  
✅ **Phase 2**: Database (SQLite + WAL + Backup) - COMPLETED  
✅ **Phase 3**: Dashboard Laporan (Read-Only) - COMPLETED  
✅ **Phase 4**: Input Skenario Manual (Form Builder + Versioning) - COMPLETED  
✅ **Phase 5**: Recalibration Engine (3-sinyal + gate) - COMPLETED
✅ **Phase 6**: Orchestrator (Device Pool + Pairing Sesi + Broadcast safety fail-closed) - COMPLETED
✅ **Phase 7**: Execution Engine Paralel (Appium + FakeDriver simulasi tanpa ADB) - COMPLETED
✅ **Phase 8**: Pelaporan & Export (laporan sesi/klien + tren Chart.js + PDF/Excel valid, tanpa ADB) - COMPLETED

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Initialize Database
```bash
python backend/db/db_cli.py init
```

### 3. Scan a Website (Optional - for sample data)
```bash
python backend/scanner/scan_to_db.py https://example.com --client-name "Example Site"
```

### 4. Start Dashboard
```bash
python run_dashboard.py
```

### 5. Open Browser
Navigate to: **http://127.0.0.1:8000**

## Phase Overview

### Phase 1 - DOM Scanner & Scorer ✅
- DOM tree extraction dengan ARIA + bounding box
- Axe-core integration untuk accessible names
- Selector generation dengan fallback hierarchy
- Confidence scoring untuk elements
- CLI dengan colored output

### Phase 2 - Database & Backup System ✅
- SQLite dengan WAL mode untuk concurrent access
- 12 tables dengan foreign keys & indexes
- Repository pattern (Client, Page, Element)
- Atomic backup system dengan retention policy
- Per-client threshold settings (similarity, position, fallback)

### Phase 3 - Dashboard Laporan (Read-Only) ✅
- FastAPI + htmx + Tailwind CSS + Alpine.js
- View clients, pages, dan elements
- Confidence-based filtering (High/Medium/Low)
- Interactive element approval
- Responsive design

### Phase 5 - Recalibration ✅
- Matching 3-sinyal: selector, teks (rapidfuzz), posisi (bbox/diagonal 720×1650)
- Fail-safe: ambigu/ganda/di bawah ambang = blocked, bukan dipaksa cocok
- Threshold per-klien (S4.3.1) + form GUI + validasi 0.50–0.99
- Headless runner Playwright (bukan device fisik) + multi-pass baseline
- Auto-update manifest (versi+1) + log audit + gate all-or-nothing

### Phase 4 - Input Skenario Manual ✅
- Form Builder Alpine.js (tambah/hapus/reorder, validasi, simpan)
- Fail-closed: hanya role approved milik client yang diterima
- Append-only versioning max+1 anti-fork, rollback = versi baru
- Diff vs versi sebelumnya + riwayat versi di detail

### Phase 6 - Orchestrator (Device Pool + Pairing Sesi + Broadcast) ✅
- Device Pool Redmi 12C: adbutils + fallback `adb devices`, register/heartbeat/health-check, FIFO idle, port 4723+count
- Pairing sesi 2-device per klien: status skema `running/completed/failed`, busy otomatis, offline tetap offline saat finish
- Assignment skenario: gate recalibration wajib lolos, satu batch = satu klien
- Broadcast safety fail-closed: whitelist `tap, fill, scroll, assert_visible, back, wake`, offline/terikat sesi = exclude + alasan + audit trail
- GUI: Device Pool, Sesi Pair per klien, detail sesi + assign, panel Broadcast + riwayat

## Dashboard Features

- 📊 **Dashboard Home**: Stats overview (clients, pages, elements)
- 🏢 **Clients View**: List all clients with threshold settings
- 📄 **Page Details**: View elements per page with confidence filtering
- 🎯 **Element Details**: Full element information with bounding box
- 🔍 **Interactive Filtering**: Tab-based confidence level filtering
- ✅ **Element Approval**: One-click approval via htmx

## Technology Stack

### Backend
- **Playwright** - Browser automation
- **SQLite + WAL** - Database dengan concurrent access
- **aiosqlite** - Async database operations
- **FastAPI** - Modern Python web framework
- **Jinja2** - Template engine

### Frontend
- **htmx** - HTML-over-the-wire interactions
- **Tailwind CSS** - Utility-first CSS
- **Alpine.js** - Minimal JavaScript framework

### Tools
- **RapidFuzz** - Text similarity scoring
- **Rich** - CLI output formatting
- **pytest** - Unit testing

## Documentation

- **Phase 2**: [docs/PHASE2-NOTES.md](docs/PHASE2-NOTES.md)
- **Phase 3**: [docs/PHASE3-NOTES.md](docs/PHASE3-NOTES.md)
- **Phase 4**: [docs/PHASE4-NOTES.md](docs/PHASE4-NOTES.md)
- **Phase 5**: [docs/PHASE5-NOTES.md](docs/PHASE5-NOTES.md)
- **Quick Start**: [docs/QUICKSTART-PHASE3.md](docs/QUICKSTART-PHASE3.md)
- **Design**: [docs/design.md](docs/design.md)
- **PRD**: [docs/PRD-Web-Automation-Appium-System.md](docs/PRD-Web-Automation-Appium-System.md)
- **ERD**: [docs/ERD-Web-Automation-Appium-System.md](docs/ERD-Web-Automation-Appium-System.md)

## API Endpoints

### Dashboard
- `GET /` - Dashboard home
- `GET /health` - Health check

### Clients
- `GET /api/clients/` - JSON list
- `GET /api/clients/view` - HTML view
- `GET /api/clients/{id}/view` - Client detail

### Pages
- `GET /api/pages/{id}/view` - Page detail with elements

### Elements
- `GET /api/elements/{id}/view` - Element detail
- `POST /api/elements/{id}/approve` - Approve element

### Recalibration (Phase 5)
- POST /api/recalibration/pages/{id}/run - Jalankan recalibration headless
- GET /api/recalibration/pages/{id}/history - JSON riwayat
- GET /api/recalibration/logs/{id} - JSON detail log
- GET /api/recalibration/scenarios/{id}/gate - Gate all-or-nothing
- POST /api/recalibration/clients/{id}/thresholds - Setel threshold
- GET /api/recalibration/pages/{id}/view - HTML riwayat
- GET /api/recalibration/logs/{id}/view - HTML diff

### Scenarios (Phase 4)
- `GET /api/scenarios/client/{client_id}` - JSON semua versi milik client
- `GET /api/scenarios/approved-roles?client_id=` - Dropdown builder
- `GET /api/scenarios/{id}` - JSON detail
- `POST /api/scenarios/validate` - Validasi tanpa simpan
- `POST /api/scenarios/` - Buat baru (nama sama = versi berikutnya)
- `POST /api/scenarios/{id}/versions` - Edit jadi versi baru (max+1 anti-fork)
- `POST /api/scenarios/{id}/rollback` - Body `{"target_versi": N}` → versi baru
- `GET /api/scenarios/client/{id}/view` - HTML daftar
- `GET /api/scenarios/builder/view?client_id=&copy_from=` - HTML builder
- `GET /api/scenarios/{id}/view` - HTML detail + diff + riwayat

### Orchestrator (Phase 6)
- `GET /api/orchestrator/devices` - JSON list
- `GET /api/orchestrator/devices/adb` - Serial ADB hidup
- `POST /api/orchestrator/devices` - Body `{"adb_id": "...", "ram_gb": 4?}`
- `GET /api/orchestrator/devices/view` - HTML pool
- `GET /api/orchestrator/devices/{id}` - JSON + sesi_aktif
- `POST /api/orchestrator/devices/{id}/heartbeat` - Offline jadi idle
- `POST /api/orchestrator/devices/{id}/health` - Cek satu
- `POST /api/orchestrator/devices/health-check` - Cek semua + ringkasan
- `POST /api/orchestrator/sessions` - Body `{client_id, device_a_id, device_b_id, pair_label?}`
- `GET /api/orchestrator/sessions/{id}` - JSON + assignments
- `POST /api/orchestrator/sessions/{id}/assign` - Body `{device_id, scenario_id}` (gate wajib lolos)
- `POST /api/orchestrator/sessions/{id}/finish` - Selesai (completed)
- `POST /api/orchestrator/sessions/{id}/cancel` - Batal (failed)
- `GET /api/orchestrator/clients/{id}/sessions/view` - HTML sesi per klien
- `GET /api/orchestrator/sessions/{id}/view` - HTML detail + assign

### Broadcast (Phase 6)
- `POST /api/broadcast/check` - Safety check tanpa eksekusi
- `POST /api/broadcast/run` - Jalankan (catat audit, tolak bila kosong)
- `GET /api/broadcast/{id}` - JSON detail + peserta
- `GET /api/broadcast/clients/{id}/view` - HTML panel + riwayat

### Reports (Phase 8 - tanpa ADB)
- `GET /api/reports/sessions/{id}/summary` - JSON laporan satu sesi + pass_rate + per-kategori
- `GET /api/reports/clients/{id}/summary` - JSON laporan satu klien + per_sesi + tren
- `GET /api/reports/clients/{id}/trend?limit=20` - Tren pass-rate per sesi (Chart.js)
- `GET /api/reports/sessions/{id}/pdf` - Unduh PDF sesi (bisa dibuka)
- `GET /api/reports/sessions/{id}/xlsx` - Unduh Excel sesi (Ringkasan + Runs)
- `GET /api/reports/clients/{id}/pdf` - Unduh PDF klien
- `GET /api/reports/clients/{id}/xlsx` - Unduh Excel klien (Ringkasan + PerSesi + Tren)
- `GET /api/reports/sessions/{id}/view` - HTML laporan sesi + tombol export
- `GET /api/reports/clients/{id}/view` - HTML laporan klien + tren Chart.js + tombol export

## Testing

### Run Unit Tests
```bash
pytest tests/ -v
```

### Verify Phase 4-6 Structure
```bash
python test_phase4.py
python test_phase5.py
python verify_phase4_api.py
python verify_phase5_api.py
python test_phase6.py
python verify_phase6_api.py
```

### Verify Phase 4-5 Structure
```bash
python test_phase4.py
python test_phase5.py
python verify_phase4_api.py
python verify_phase5_api.py
```

## CLI Tools

### Scanner
```bash
# Basic scan
python backend/scanner/cli.py https://example.com

# Scan to database
python backend/scanner/scan_to_db.py https://example.com --client-name "Client Name"
```

### Database Management
```bash
# Initialize database
python backend/db/db_cli.py init

# Create backup
python backend/db/db_cli.py backup

# List backups
python backend/db/db_cli.py list-backups

# Restore backup
python backend/db/db_cli.py restore <timestamp>
```

## Troubleshooting

**No data in dashboard?**
```bash
python backend/scanner/scan_to_db.py <url> --client-name "Test Client"
```

**Database not found?**
```bash
python backend/db/db_cli.py init
```

**Port already in use?**
```bash
uvicorn backend.app:app --port 8001
```

**Import errors?**
```bash
pip install -r requirements.txt
```

## Next Steps

- [x] Phase 4: Input Skenario Manual (Form builder)
- [x] Phase 5: Recalibration Engine (3-sinyal + gate)
- [x] Phase 6: Device Management & Orchestration (pool + pair + broadcast)
- [x] Phase 7: Execution Engine (Appium + FakeDriver simulasi tanpa ADB)
- [x] Phase 8: Reporting & Analytics (laporan sesi/klien + tren Chart.js + PDF/Excel, tanpa ADB)

## License

Internal project for Angga - Single operator system

## Author

Developed by Kiro AI  
Last Updated: 2026-09-26

