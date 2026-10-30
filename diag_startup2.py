"""Diagnosa startup dashboard - tulis hasil ke file log."""
import sys, traceback
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
out = []
def log(msg):
    print(msg, flush=True)
    out.append(str(msg))

log("=== DIAG START ===")
import platform
log(f"python={platform.python_version()} exe={sys.executable}")

# 1. cek folder penting
for p in ["backend/static", "backend/templates", "backend/templates/runs",
          "backend/templates/runs/demo_real.html", "backend/templates/runs/session_runs.html",
          "backend/templates/index.html", "backend/templates/base.html",
          "backend/db/data/otomet.db", "backend/db/schema.sql"]:
    log(f"exists {p} = {(ROOT/p).exists()}")

# 2. cek import backend.app
try:
    import backend.app as appmod
    log("IMPORT backend.app OK")
    log(f"routes={len(appmod.app.routes)}")
    for r in appmod.app.routes:
        try:
            log(f"  route path={getattr(r,'path',r)} methods={getattr(r,'methods',None)}")
        except Exception as e:
            log(f"  route err {e}")
except Exception:
    log("IMPORT backend.app GAGAL:")
    log(traceback.format_exc())

# 3. cek tiap router import satu-satu
for mod in ["backend.api.clients","backend.api.pages","backend.api.elements",
            "backend.api.scenarios","backend.api.recalibration",
            "backend.api.orchestrator","backend.api.broadcast",
            "backend.api.runs","backend.api.reports",
            "backend.orchestrator.device_pool","backend.orchestrator.runner",
            "backend.orchestrator.chrome_real","backend.db.database"]:
    try:
        __import__(mod)
        log(f"IMPORT {mod} OK")
    except Exception:
        log(f"IMPORT {mod} GAGAL:")
        log(traceback.format_exc())

# 4. cek TestClient GET / dan /health
try:
    from fastapi.testclient import TestClient
    from backend.app import app
    c = TestClient(app, raise_server_exceptions=False)
    for url in ["/health", "/", "/api/runs/demo/real-2device/view"]:
        try:
            r = c.get(url)
            log(f"GET {url} -> {r.status_code} len={len(r.content)}")
            if r.status_code >= 400:
                log(f"  body[:500]={r.text[:500]}")
        except Exception:
            log(f"GET {url} EXC:")
            log(traceback.format_exc())
except Exception:
    log("TESTCLIENT GAGAL:")
    log(traceback.format_exc())

# 5. cek tabel DB
try:
    import sqlite3
    dbp = ROOT/"backend"/"db"/"data"/"otomet.db"
    con = sqlite3.connect(str(dbp))
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    log(f"tables={ [r[0] for r in cur.fetchall()] }")
    con.close()
except Exception:
    log("DB CHECK GAGAL:")
    log(traceback.format_exc())

# 6. cek versi paket
try:
    import importlib.metadata as md
    for pkg in ["fastapi","uvicorn","jinja2","aiosqlite","python-multipart",
                "adbutils","Appium-Python-Client","openpyxl","starlette","pydantic"]:
        try:
            log(f"pkg {pkg}=={md.version(pkg)}")
        except Exception as e:
            log(f"pkg {pkg} MISSING ({e})")
except Exception:
    log(traceback.format_exc())

log("=== DIAG DONE ===")
Path(ROOT/"diag_startup2.log").write_text("\n".join(out), encoding="utf-8")
