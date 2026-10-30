"""Smoke test API Phase 5 end-to-end dengan DB isolasi (tanpa browser)."""
import asyncio
import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

TEST_DB = "test_phase5_smoke.db"
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
    from backend.db.repositories import client_repo as cr_mod
    from backend.db.repositories import page_repo as pr_mod
    from backend.db.repositories import element_repo as er_mod
    from backend.db.repositories import scenario_repo as sr_mod
    from backend.db.repositories import recalibration_repo as rr_mod
    sr_mod.db = db_uji
    cr_mod.db = db_uji
    pr_mod.db = db_uji
    er_mod.db = db_uji
    rr_mod.db = db_uji
    from backend.db.repositories import ClientRepository, PageRepository, ElementRepository, ScenarioRepository
    cid = await ClientRepository().create(nama="Smoke Recal", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk", "fallbacks": []}, text_snapshot="Masuk",
        bbox=dict(BBOX), confidence=0.95, approved=True)
    sid = await ScenarioRepository().create(
        cid, "login_valid",
        [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}}])
    await db_uji.close()
    return cid, pid, sid

cid, pid, sid = asyncio.run(setup())

from fastapi.testclient import TestClient
from backend.app import app
c = TestClient(app)

print("1. health:", c.get("/health").json())
assert c.get("/health").json()["phase"] == "5"

r_thr = c.post(f"/api/recalibration/clients/{cid}/thresholds", json={
    "threshold_similarity": 0.85, "threshold_posisi": 0.9, "threshold_tinggi_fallback": 0.8})
print("2. thresholds valid:", r_thr.status_code, r_thr.json()["threshold_similarity"])
assert r_thr.status_code == 200

r_bad = c.post(f"/api/recalibration/clients/{cid}/thresholds", json={
    "threshold_similarity": 0.2, "threshold_posisi": 0.9, "threshold_tinggi_fallback": 0.8})
print("3. thresholds longgar ditolak:", r_bad.status_code)
assert r_bad.status_code == 400

segar_cocok = [{"role": "button", "role_label": "button_masuk", "text": "Masuk",
                "bbox": dict(BBOX), "selectors": {"primary": "#masuk", "fallbacks": []}}]
r_run = c.post(f"/api/recalibration/pages/{pid}/run", json={"fresh_override": segar_cocok})
print("4. run calibrated:", r_run.json()["ringkasan"], r_run.json()["boleh_jalan"])
assert r_run.json()["boleh_jalan"] is True
log_id = r_run.json()["log_id"]

r_hist = c.get(f"/api/recalibration/pages/{pid}/history")
print("5. history count:", len(r_hist.json()["logs"]))
assert len(r_hist.json()["logs"]) >= 1

r_log = c.get(f"/api/recalibration/logs/{log_id}")
print("6. log detail status:", r_log.json()["hasil"][0]["status"])
assert r_log.json()["hasil"][0]["status"] == "calibrated"

r_gate = c.get(f"/api/recalibration/scenarios/{sid}/gate")
print("7. gate lolos:", r_gate.json()["boleh_jalan"])
assert r_gate.json()["boleh_jalan"] is True

segar_hilang = [{"role": "link", "role_label": "link_bantuan", "text": "Bantuan",
                 "bbox": dict(BBOX), "selectors": {"primary": "#bantuan", "fallbacks": []}}]
r_block = c.post(f"/api/recalibration/pages/{pid}/run", json={"fresh_override": segar_hilang})
print("8. run blocked:", r_block.json()["ringkasan"], r_block.json()["boleh_jalan"])
assert r_block.json()["boleh_jalan"] is False
log_block = r_block.json()["log_id"]

r_gate2 = c.get(f"/api/recalibration/scenarios/{sid}/gate")
print("9. gate tertahan:", r_gate2.json()["boleh_jalan"], r_gate2.json()["detail"][0]["status"])
assert r_gate2.json()["boleh_jalan"] is False

for url in [f"/api/recalibration/pages/{pid}/view",
            f"/api/recalibration/logs/{log_id}/view",
            f"/api/recalibration/logs/{log_block}/view"]:
    r = c.get(url)
    print("10. HTML", url, r.status_code, len(r.text))
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]

print("SMOKE-PHASE5-OK")

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
