"""Cek lengkap baseline: tools + DB + simulate + reports. Tulis ke cek_lengkap.log."""
import sys, traceback, shutil, subprocess, sqlite3
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
out = []
def log(m):
    print(m, flush=True)
    out.append(str(m))
log("=== CEK LENGKAP START ===")
# A. tools
for t in ["node", "npm", "appium", "adb"]:
    log(f"which {t} = {shutil.which(t)}")
for cmd in [["node", "--version"], ["npm", "--version"], ["appium", "--version"]]:
    if not shutil.which(cmd[0]):
        log(f"skip {' '.join(cmd)} (tak ada di PATH)")
        continue
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        log(f"CMD {' '.join(cmd)} rc={r.returncode} out={repr((r.stdout or '')[:500])} err={repr((r.stderr or '')[:500])}")
    except Exception as e:
        log(f"CMD {' '.join(cmd)} EXC {e}")
# B. DB isi
try:
    dbp = ROOT / "backend" / "db" / "data" / "otomet.db"
    con = sqlite3.connect(str(dbp))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    for tbl in ["devices", "clients", "sessions", "scenario_assignments", "runs", "test_data_pool"]:
        try:
            cur.execute(f"SELECT COUNT(*) c FROM {tbl}")
            n = cur.fetchone()["c"]
            log(f"DB {tbl} count={n}")
        except Exception as e:
            log(f"DB {tbl} EXC {e}")
    try:
        cur.execute("SELECT id, client_id, device_a_id, device_b_id, pair_label, status FROM sessions ORDER BY id DESC LIMIT 5")
        for r in cur.fetchall():
            log(f"SESSION {dict(r)}")
    except Exception as e:
        log(f"SESSION list EXC {e}")
    try:
        cur.execute("SELECT id, adb_id, appium_port, status FROM devices ORDER BY id")
        for r in cur.fetchall():
            log(f"DEVICE {dict(r)}")
    except Exception as e:
        log(f"DEVICE list EXC {e}")
    try:
        cur.execute("SELECT scenario_assignment_id, test_data_id, COUNT(*) c FROM runs WHERE test_data_id IS NOT NULL GROUP BY test_data_id HAVING c>1 LIMIT 5")
        rows = cur.fetchall()
        log(f"DATA_GANDA rows={len(rows)} (0=aman)")
    except Exception as e:
        log(f"DATA_GANDA EXC {e}")
    con.close()
except Exception:
    log("DB EXC:"); log(traceback.format_exc())
# C. TestClient ringan (tanpa ubah DB dulu): health/ready/adb + reports sesi terakhir
try:
    from fastapi.testclient import TestClient
    from backend.app import app
    c = TestClient(app, raise_server_exceptions=False)
    for u in ["/health", "/ready", "/api/orchestrator/devices/adb"]:
        try:
            r = c.get(u)
            log(f"GET {u} -> {r.status_code} body[:300]={r.text[:300]}")
        except Exception as e:
            log(f"GET {u} EXC {e}")
    # sesi running terakhir
    import sqlite3 as s3
    con2 = s3.connect(str(ROOT / "backend" / "db" / "data" / "otomet.db"))
    con2.row_factory = s3.Row
    row = con2.execute("SELECT id FROM sessions WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
    con2.close()
    sid = int(row["id"]) if row else None
    log(f"running_session_id={sid}")
    if sid:
        for u in [f"/api/runs/sessions/{sid}/runs", f"/api/reports/sessions/{sid}/summary",
                  f"/api/reports/sessions/{sid}/pdf", f"/api/reports/sessions/{sid}/xlsx",
                  f"/api/reports/sessions/{sid}/view", f"/api/runs/sessions/{sid}/runs/view"]:
            try:
                r = c.get(u)
                log(f"GET {u} -> {r.status_code} len={len(r.content)}")
            except Exception as e:
                log(f"GET {u} EXC {e}")
except Exception:
    log("TESTCLIENT EXC:"); log(traceback.format_exc())
# D. list tests/
try:
    tdir = ROOT / "tests"
    log(f"tests exists={tdir.exists()}")
    if tdir.exists():
        for p in sorted(tdir.rglob("*")):
            log(f"  tests/{p.relative_to(tdir)}")
except Exception as e:
    log(f"tests list EXC {e}")
log("=== CEK LENGKAP DONE ===")
Path(ROOT / "cek_lengkap.log").write_text("\n".join(out), encoding="utf-8")
