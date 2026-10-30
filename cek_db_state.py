"""Dump cepat devices+sessions (hindari quoting hell pwsh)."""
import sqlite3
from pathlib import Path
p = Path("backend/db/data/otomet.db")
print("db exists", p.exists(), p.stat().st_size if p.exists() else 0)
con = sqlite3.connect(str(p))
con.row_factory = sqlite3.Row
print("devices", [dict(r) for r in con.execute("SELECT id,adb_id,appium_port,status FROM devices ORDER BY id")])
print("running", [dict(r) for r in con.execute("SELECT id,pair_label,status FROM sessions WHERE status='running'")])
print("last5", [dict(r) for r in con.execute("SELECT id,pair_label,status FROM sessions ORDER BY id DESC LIMIT 5")])
con.close()
print("DB-OK")
