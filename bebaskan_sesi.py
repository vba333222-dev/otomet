"""Bebaskan semua sesi running -> completed (tanpa quoting hell)."""
import asyncio, sys
sys.path.insert(0, "c:/Project/otomet")
async def main():
    from backend.db.database import db
    await db.connect()
    await db.initialize_schema()
    from backend.db.repositories.session_repo import SessionRepository
    from backend.orchestrator.session_manager import akhiri_sesi
    rows = await db.fetch_all("SELECT id FROM sessions WHERE status='running' ORDER BY id")
    print("running:", [dict(r)["id"] for r in rows])
    for r in rows:
        sid = dict(r)["id"]
        try:
            out = await akhiri_sesi(sid)
            print(f"sesi {sid} -> {out.get('status')}")
        except Exception as e:
            print(f"sesi {sid} EXC {e}")
    await db.close()
asyncio.run(main())
