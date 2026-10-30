"""Smoke test API Phase 4 end-to-end dengan DB isolasi."""
import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

TEST_DB = "test_phase4_smoke.db"
for ext in ["", "-wal", "-shm"]:
    f = f"{TEST_DB}{ext}"
    if os.path.exists(f):
        os.remove(f)

from backend.db.database import Database

async def setup():
    db_uji = Database(TEST_DB)
    await db_uji.connect()
    await db_uji.initialize_schema()
    # patch singleton + referensi modul repo
    import backend.db.database as db_module
    db_module.db = db_uji
    from backend.db.repositories import scenario_repo as sr_mod
    from backend.db.repositories import client_repo as cr_mod
    from backend.db.repositories import page_repo as pr_mod
    from backend.db.repositories import element_repo as er_mod
    sr_mod.db = db_uji
    cr_mod.db = db_uji
    pr_mod.db = db_uji
    er_mod.db = db_uji
    from backend.db.repositories import ClientRepository, PageRepository, ElementRepository
    cid = await ClientRepository().create(nama="Smoke Client", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk"}, text_snapshot="Masuk",
        bbox={"x": 1, "y": 2, "width": 80, "height": 30},
        confidence=0.95, approved=True,
    )
    await db_uji.close()
    return cid, pid

cid, pid = asyncio.run(setup())

# Reconnect untuk TestClient (modul sudah ter-patch ke file TEST_DB)
from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app)

print("1. approved-roles:", c.get("/api/scenarios/approved-roles", params={"client_id": cid}).json())
assert c.get("/api/scenarios/approved-roles", params={"client_id": cid}).json() == {"client_id": cid, "roles": ["button_masuk"]}

print("2. validate valid:", c.post("/api/scenarios/validate", json={
    "client_id": cid,
    "steps": [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}}]
}).json())

r_bad = c.post("/api/scenarios/validate", json={
    "client_id": cid,
    "steps": [{"action": "click", "role_label": "belum_approved", "page_id": pid, "params": {}}]
})
print("3. validate bad (harus invalid):", r_bad.json())
assert r_bad.json()["valid"] is False

r_fill = c.post("/api/scenarios/validate", json={
    "client_id": cid,
    "steps": [{"action": "fill", "role_label": "button_masuk", "page_id": pid, "params": {}}]
})
print("4. validate fill tanpa text (harus invalid):", r_fill.json())
assert r_fill.json()["valid"] is False

r_create = c.post("/api/scenarios/", json={
    "client_id": cid, "nama_fungsi": "login_valid",
    "steps": [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}}]
})
print("5. create:", r_create.status_code, r_create.json())
assert r_create.status_code == 200 and r_create.json()["versi"] == 1
sid = r_create.json()["id"]

r_v2 = c.post(f"/api/scenarios/{sid}/versions", json={
    "steps": [{"action": "fill", "role_label": "button_masuk", "page_id": pid, "params": {"text": "halo"}}]
})
print("6. new version:", r_v2.json())
assert r_v2.json()["versi"] == 2

r_rb = c.post(f"/api/scenarios/{sid}/rollback", json={"target_versi": 1})
print("7. rollback -> v3:", r_rb.json())
assert r_rb.json()["versi"] == 3

r_get = c.get(f"/api/scenarios/{sid}")
print("8. get json:", r_get.status_code)
assert r_get.status_code == 200

r_list = c.get(f"/api/scenarios/client/{cid}")
print("9. list json count:", len(r_list.json()))
assert len(r_list.json()) == 3

for url in [f"/api/scenarios/client/{cid}/view",
            f"/api/scenarios/builder/view?client_id={cid}",
            f"/api/scenarios/{sid}/view"]:
    r = c.get(url)
    print("10. HTML", url, r.status_code, len(r.text))
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]

print("SMOKE-API-OK")

import backend.db.database as _dbm
try:
    asyncio.run(_dbm.db.close())
except RuntimeError:
    pass

import time
for _ in range(5):
    try:
        for ext in ["", "-wal", "-shm"]:
            f = f"{TEST_DB}{ext}"
            if os.path.exists(f):
                os.remove(f)
        break
    except PermissionError:
        time.sleep(0.5)
