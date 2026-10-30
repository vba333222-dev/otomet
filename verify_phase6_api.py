"""Smoke test API Phase 6 end-to-end dengan DB isolasi (tanpa ADB fisik)."""
import asyncio
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

TEST_DB = "test_phase6_smoke.db"
for ext in ["", "-wal", "-shm"]:
    f = f"{TEST_DB}{ext}"
    if os.path.exists(f):
        os.remove(f)

from backend.db.database import Database

BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


async def setup():
    db_uji = Database(TEST_DB)
    await db_uji.connect()
    await db_uji.initialize_schema()
    import backend.db.database as db_module
    db_module.db = db_uji
    mods = []
    for nama in ("client_repo", "page_repo", "element_repo",
                 "scenario_repo", "recalibration_repo",
                 "device_repo", "session_repo"):
        mod = __import__(f"backend.db.repositories.{nama}", fromlist=["x"])
        mod.db = db_uji
        mods.append(mod)
    from backend.db.repositories import (
        ClientRepository, PageRepository, ElementRepository, ScenarioRepository,
    )
    from backend.recalibration.service import jalankan_recalibration
    from backend.orchestrator.device_pool import register_device
    cid = await ClientRepository().create(nama="Smoke P6", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk", "fallbacks": []}, text_snapshot="Masuk",
        bbox=dict(BBOX), confidence=0.95, approved=True)
    sid = await ScenarioRepository().create(
        cid, "login_valid",
        [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}}])
    segar = [{"role": "button", "role_label": "button_masuk", "text": "Masuk",
              "bbox": dict(BBOX), "selectors": {"primary": "#masuk", "fallbacks": []}}]
    await jalankan_recalibration(pid, fresh_override=segar)
    a = await register_device("SMOKE_A")
    b = await register_device("SMOKE_B")
    return db_uji, cid, pid, sid, a, b


db_uji, cid, pid, sid, dev_a, dev_b = asyncio.run(setup())

import backend.orchestrator.device_pool as pool_mod
import backend.api.orchestrator as orch_api
pool_mod.daftar_perangkat_adb = lambda: ["SMOKE_A", "SMOKE_B"]
orch_api.daftar_perangkat_adb = lambda: ["SMOKE_A", "SMOKE_B"]

from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app)

print("1. health:", c.get("/health").json())
assert c.get("/health").json()["phase"] == "6"

r_dev = c.get("/api/orchestrator/devices")
print("2. devices:", len(r_dev.json()))
assert len(r_dev.json()) == 2

r_hc = c.post("/api/orchestrator/devices/health-check")
print("3. health-check:", r_hc.json()["ringkasan"])
assert r_hc.json()["ringkasan"]["idle"] == 2

r_sesi = c.post("/api/orchestrator/sessions", json={
    "client_id": cid, "device_a_id": dev_a["id"],
    "device_b_id": dev_b["id"], "pair_label": "smoke-pair"})
print("4. buat sesi:", r_sesi.status_code, r_sesi.json().get("status"))
assert r_sesi.status_code == 200 and r_sesi.json()["status"] == "running"
sesi_id = r_sesi.json()["id"]

r_sama = c.post("/api/orchestrator/sessions", json={
    "client_id": cid, "device_a_id": dev_a["id"], "device_b_id": dev_a["id"]})
print("5. device sama ditolak:", r_sama.status_code)
assert r_sama.status_code == 400

r_assign = c.post(f"/api/orchestrator/sessions/{sesi_id}/assign", json={
    "device_id": dev_a["id"], "scenario_id": sid})
print("6. assign lolos gate:", r_assign.status_code)
assert r_assign.status_code == 200

r_cek = c.post("/api/broadcast/check", json={
    "client_id": cid, "action_type": "tap",
    "target": "button_masuk", "device_ids": [dev_a["id"], dev_b["id"]]})
print("7. broadcast check (terikat sesi -> tolak):", r_cek.json()["boleh_jalan"])
assert r_cek.json()["boleh_jalan"] is False

r_fin = c.post(f"/api/orchestrator/sessions/{sesi_id}/finish")
print("8. finish:", r_fin.json()["status"])
assert r_fin.json()["status"] == "completed"

r_run = c.post("/api/broadcast/run", json={
    "client_id": cid, "action_type": "wake", "target": ""})
print("9. broadcast run:", r_run.json()["boleh_jalan"], len(r_run.json()["peserta"]))
assert r_run.json()["boleh_jalan"] is True
bid = r_run.json()["id"]

r_b = c.get(f"/api/broadcast/{bid}")
print("10. broadcast detail peserta:", len(r_b.json()["peserta"]))
assert len(r_b.json()["peserta"]) == 2

for url in ["/api/orchestrator/devices/view",
            f"/api/orchestrator/clients/{cid}/sessions/view",
            f"/api/orchestrator/sessions/{sesi_id}/view",
            f"/api/broadcast/clients/{cid}/view"]:
    r = c.get(url)
    print("11. HTML", url, r.status_code, len(r.text))
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]

print("SMOKE-PHASE6-OK")

import backend.db.database as _dbm
try:
    asyncio.run(_dbm.db.close())
except RuntimeError:
    pass

for _ in range(5):
    try:
        for ext in ["", "-wal", "-shm"]:
            f = f"{TEST_DB}{ext}"
            if os.path.exists(f):
                os.remove(f)
        break
    except PermissionError:
        time.sleep(0.5)
