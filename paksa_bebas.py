"""Paksa bebaskan via sqlite3 langsung (bypass repo)."""
import sqlite3
from pathlib import Path
p = Path("backend/db/data/otomet.db")
con = sqlite3.connect(str(p))
con.execute("UPDATE sessions SET status='completed' WHERE status='running'")
con.execute("UPDATE devices SET status='idle' WHERE status='busy'")
con.commit()
print("sessions running:", list(con.execute("SELECT id,status FROM sessions WHERE status='running'")))
print("devices:", list(con.execute("SELECT id,adb_id,status FROM devices ORDER BY id")))
con.close()
print("FORCE-FREE-OK")
