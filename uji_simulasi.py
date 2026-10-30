"""Uji simulasi 2-device sesi running terakhir + laporan. Tulis ke uji_simulasi.log."""
import sys, traceback, sqlite3
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
out = []
def log(m):
    print(m, flush=True)
    out.append(str(m))
log("=== UJI SIMULASI START ===")
try:
    from fastapi.testclient import TestClient
    from backend.app import app
    c = TestClient(app, raise_server_exceptions=False)
    # cari sesi running
    con = sqlite3.connect(str(ROOT / "backend" / "db" / "data" / "otomet.db"))
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT id FROM sessions WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    sid = int(row["id"]) if row else None
    log(f"sid={sid}")
    if not sid:
        log("TIDAK ADA SESI RUNNING - stop")
    else:
        from backend.orchestrator import chrome_real
        chrome_real.pasang_open_url()
        # 1. simulate run
        r = c.post(f"/api/runs/sessions/{sid}/run", json={"mode": "simulate"})
        log(f"POST simulate -> {r.status_code} body[:800]={r.text[:800]}")
        try:
            d = r.json()
            log(f"ringkasan={d.get('ringkasan')} data_ganda={d.get('data_ganda')} alasan={d.get('alasan')}")
        except Exception as e:
            log(f"json EXC {e}")
        # 2. ringkasan runs
        r2 = c.get(f"/api/runs/sessions/{sid}/runs")
        log(f"GET runs -> {r2.status_code} body[:800]={r2.text[:800]}")
        # 3. laporan json/pdf/xlsx/view
        for u in [f"/api/reports/sessions/{sid}/summary", f"/api/reports/sessions/{sid}/pdf",
                  f"/api/reports/sessions/{sid}/xlsx", f"/api/reports/sessions/{sid}/view",
                  f"/api/runs/sessions/{sid}/runs/view"]:
            rr = c.get(u)
            log(f"GET {u} -> {rr.status_code} len={len(rr.content)}")
        # 4. cek data ganda langsung
        con2 = sqlite3.connect(str(ROOT / "backend" / "db" / "data" / "otomet.db"))
        cur = con2.cursor()
        cur.execute("SELECT test_data_id, COUNT(*) c FROM runs WHERE test_data_id IS NOT NULL AND scenario_assignment_id IN (SELECT id FROM scenario_assignments WHERE session_id=?) GROUP BY test_data_id HAVING c>1", (sid,))
        ganda = cur.fetchall()
        log(f"DATA_GANDA sid={sid} rows={len(ganda)} (0=aman) detail={ganda[:5]}")
        cur.execute("SELECT id, scenario_assignment_id, test_data_id, status, failure_category FROM runs WHERE scenario_assignment_id IN (SELECT id FROM scenario_assignments WHERE session_id=?) ORDER BY id DESC LIMIT 10", (sid,))
        for rw in cur.fetchall():
            log(f"RUN {rw}")
        con2.close()
except Exception:
    log("UJI EXC:"); log(traceback.format_exc())
log("=== UJI SIMULASI DONE ===")
Path(ROOT / "uji_simulasi.log").write_text("\n".join(out), encoding="utf-8")
