"""Verifikasi GUI + DB counts tanpa quoting hell."""
import sqlite3
from pathlib import Path
p = Path("backend/db/data/otomet.db")
con = sqlite3.connect(str(p))
for t in ["clients","pages","elements","scenarios","devices","sessions","scenario_assignments","runs","test_data_pool"]:
    try:
        c = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(t, c)
    except Exception as e:
        print(t, "ERR", e)
con.close()
print("---GUI---")
from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app, raise_server_exceptions=False)
for u in ["/","/health","/ready","/api/clients/view","/api/orchestrator/devices/view","/api/runs/demo/real-2device/view","/api/reports/sessions/1/view","/api/orchestrator/sessions/1/view","/api/scenarios/client/137/view"]:
    try:
        r = c.get(u)
        print(u, r.status_code, len(r.content))
    except Exception as e:
        print(u, "EXC", e)
print("---PYCOMPILE---")
import py_compile
for f in ["backend/orchestrator/runner.py","backend/orchestrator/chrome_real.py","backend/api/runs.py","backend/app.py","backend/api/scenarios.py"]:
    try:
        py_compile.compile(f, doraise=True)
        print(f, "OK")
    except Exception as e:
        print(f, "FAIL", e)
