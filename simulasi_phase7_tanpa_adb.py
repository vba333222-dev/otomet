"""Smoke simulasi Phase 7 tanpa kabel ADB / tanpa Appium fisik.

Jalankan: python simulasi_phase7_tanpa_adb.py
Hasil: DB simulasi_phase7.db + sesi paralel 2 device virtual via FakeDriver.
Tanpa kabel: daftar_perangkat_adb() -> [] (fail-safe), broadcast pakai live_override.
"""
import asyncio
import os
import sys

sys.path.insert(0, "c:/Project/otomet")

TEST_DB = "simulasi_phase7.db"
for ext in ("", "-wal", "-shm"):
    p = TEST_DB + ext
    if os.path.exists(p):
        try:
            os.remove(p)
        except Exception:
            pass

from backend.db.database import Database

BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


async def main():
    db_uji = Database(TEST_DB)
    await db_uji.connect()
    await db_uji.initialize_schema()
    import backend.db.database as dbm
    dbm.db = db_uji
    for n in ("client_repo", "page_repo", "element_repo", "scenario_repo",
              "recalibration_repo", "device_repo", "session_repo", "run_repo"):
        m = __import__(f"backend.db.repositories.{n}", fromlist=["x"])
        m.db = db_uji

    from backend.db.repositories import (
        ClientRepository, PageRepository, ElementRepository,
        ScenarioRepository, TestDataRepository, RunRepository,
    )
    from backend.recalibration.service import jalankan_recalibration
    from backend.orchestrator.device_pool import daftar_perangkat_adb, register_device
    from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario, akhiri_sesi
    from backend.orchestrator.runner import FakeDriver, jalankan_session, jalankan_broadcast_fisik

    print("ADB live (harusnya [] tanpa kabel):", daftar_perangkat_adb())

    cid = await ClientRepository().create(nama="Klien Simulasi", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk", "fallbacks": []},
        text_snapshot="Masuk", bbox=dict(BBOX), confidence=0.95, approved=True)
    await ElementRepository().create(
        page_id=pid, role_label="input_nama",
        selectors={"primary": "#nama", "fallbacks": []},
        text_snapshot="Nama", bbox=dict(BBOX), confidence=0.93, approved=True)
    sid = await ScenarioRepository().create(
        cid, "login_valid",
        [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}},
         {"action": "fill", "role_label": "input_nama", "page_id": pid, "params": {"text": "{{nama}}"}},
         {"action": "assert_visible", "role_label": "button_masuk", "page_id": pid, "params": {}}])
    segar = [
        {"role": "button", "role_label": "button_masuk", "text": "Masuk",
         "bbox": dict(BBOX), "selectors": {"primary": "#masuk", "fallbacks": []}},
        {"role": "textbox", "role_label": "input_nama", "text": "Nama",
         "bbox": dict(BBOX), "selectors": {"primary": "#nama", "fallbacks": []}},
    ]
    gate = await jalankan_recalibration(pid, fresh_override=segar)
    print("Gate boleh_jalan:", gate["boleh_jalan"])

    a = await register_device("SIM_A")
    b = await register_device("SIM_B")
    print("Device virtual:", a["id"], a["adb_id"], "|", b["id"], b["adb_id"])

    await TestDataRepository().tambah(sid, {"nama": "Andi"})
    await TestDataRepository().tambah(sid, {"nama": "Budi"})
    sesi = await buat_sesi_pair(cid, a["id"], b["id"], "pair-simulasi")
    ta = await tugaskan_skenario(sesi["id"], a["id"], sid)
    tb = await tugaskan_skenario(sesi["id"], b["id"], sid)
    print("Sesi:", sesi["id"], "tugas:", ta["id"], tb["id"])

    def fac(device, caps):
        return FakeDriver(device.get("adb_id", "?"))

    hasil = await jalankan_session(sesi["id"], fac)
    print("SESSION:", hasil["ringkasan"], "data_ganda:", hasil["data_ganda"])
    assert hasil["ringkasan"]["passed"] == 2, hasil
    assert hasil["data_ganda"] is False, hasil

    ringkas = await RunRepository().ringkasan_session(sesi["id"])
    print("RINGKASAN DB:", ringkas["ringkasan"])
    assert ringkas["ringkasan"]["passed"] == 2

    # Broadcast fisik simulasi: akhiri sesi dulu agar device bebas, lalu live_override
    await akhiri_sesi(sesi["id"])
    bcast = await jalankan_broadcast_fisik(
        cid, "wake", "", None, fac, live_override={"SIM_A", "SIM_B"})
    print("BROADCAST:", bcast["alasan"], "eksekusi:", len(bcast["eksekusi"]))
    assert bcast["boleh_jalan"] is True
    assert len(bcast["eksekusi"]) == 2
    assert all(e["ok"] for e in bcast["eksekusi"])

    await db_uji.close()
    print("OK simulasi tanpa kabel lolos.")


if __name__ == "__main__":
    asyncio.run(main())
