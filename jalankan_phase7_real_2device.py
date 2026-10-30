"""Skrip real Phase 7 - Chrome URL test paralel di 2 HP WiFi (bagian 1/2).

Prasyarat: ADB WiFi connect (50:42851 + 81:37251), 2 Appium server
(p 4723 + p 4724), Chrome di kedua HP, pip install -r requirements.txt.
Jalankan: python jalankan_phase7_real_2device.py [--url https://example.com]
"""
import argparse
import asyncio
import sys

sys.path.insert(0, "c:/Project/otomet")

SERIAL_A = "192.168.100.50:42851"
SERIAL_B = "192.168.100.81:37251"
BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


async def siapkan_pair(url_uji: str):
    from backend.db.database import db
    await db.connect()
    await db.initialize_schema()
    from backend.db.repositories import (
        ClientRepository, PageRepository, ElementRepository,
        ScenarioRepository, TestDataRepository, DeviceRepository,
    )
    from backend.recalibration.service import jalankan_recalibration
    from backend.orchestrator.device_pool import (
        daftar_perangkat_adb, register_device, health_check_semua,
    )
    from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
    from backend.orchestrator.runner import bangun_caps

    print("[1/7] Cek ADB live...")
    live = daftar_perangkat_adb()
    print(f"      live: {live}")
    kurang = [s for s in (SERIAL_A, SERIAL_B) if s not in set(live)]
    if kurang:
        print(f"      GAGAL: serial tak terlihat: {kurang}")
        await db.close()
        sys.exit(2)

    async def _pastikan(serial: str):
        sudah = await DeviceRepository().get_by_adb_id(serial)
        if sudah:
            print(f"      sudah: id={sudah['id']} {serial} {sudah['status']}")
            return sudah
        baru = await register_device(serial)
        print(f"      baru: id={baru['id']} {serial} port={baru['appium_port']}")
        return baru

    print("[2/7] Register + health 2 device...")
    await _pastikan(SERIAL_A)
    await _pastikan(SERIAL_B)
    hasil_hc = await health_check_semua()
    ringkas = {d["adb_id"]: d["status"] for d in hasil_hc
               if d["adb_id"] in (SERIAL_A, SERIAL_B)}
    print(f"      health: {ringkas}")
    dev_a = await DeviceRepository().get_by_adb_id(SERIAL_A)
    dev_b = await DeviceRepository().get_by_adb_id(SERIAL_B)
    print(f"      caps A: {bangun_caps(dev_a)}")
    print(f"      caps B: {bangun_caps(dev_b)}")

    print("[3/7] Klien + skenario open_url...")
    cid = await ClientRepository().create(
        nama="Klien Chrome Real 2HP", base_url=url_uji)
    pid = await PageRepository().create(cid, url_uji)
    await ElementRepository().create(
        page_id=pid, role_label="halaman_utama",
        selectors={"primary": "body", "fallbacks": []},
        text_snapshot="Halaman", bbox=dict(BBOX), confidence=0.90, approved=True)
    sid = await ScenarioRepository().create(
        cid, "buka_chrome_real",
        [{"action": "open_url", "role_label": "", "page_id": pid,
          "params": {"url": "{{url}}"}}])
    segar = [{"role": "document", "role_label": "halaman_utama", "text": "Halaman",
              "bbox": dict(BBOX),
              "selectors": {"primary": "body", "fallbacks": []}}]
    gate = await jalankan_recalibration(pid, fresh_override=segar)
    print(f"      gate={gate['boleh_jalan']} {gate['ringkasan']}")
    if not gate["boleh_jalan"]:
        await db.close()
        sys.exit(3)

    print("[4/7] Test data 2 baris...")
    await TestDataRepository().tambah(sid, {"url": url_uji, "nama": "HP-A"})
    await TestDataRepository().tambah(sid, {"url": url_uji, "nama": "HP-B"})

    print("[5/7] Pair + assign...")
    if dev_a["status"] != "idle" or dev_b["status"] != "idle":
        print(f"      Tidak idle: A={dev_a['status']} B={dev_b['status']}.")
        print("      Selesaikan sesi lama dulu via dashboard.")
        await db.close()
        sys.exit(4)
    sesi = await buat_sesi_pair(cid, dev_a["id"], dev_b["id"], "pair-real-2hp")
    ta = await tugaskan_skenario(sesi["id"], dev_a["id"], sid)
    tb = await tugaskan_skenario(sesi["id"], dev_b["id"], sid)
    print(f"      sesi={sesi['id']} tugas A={ta['id']} B={tb['id']}")
    return sesi


async def jalankan_paralel(sesi, url_uji: str):
    from backend.db.database import db
    from backend.db.repositories import RunRepository
    from backend.orchestrator.session_manager import akhiri_sesi
    from backend.orchestrator.runner import jalankan_session
    from backend.orchestrator import chrome_real

    print("[6/7] Jalankan paralel Chrome (butuh 2 Appium server)...")
    chrome_real.pasang_open_url()
    hasil = await jalankan_session(
        sesi["id"], chrome_real.driver_factory_chrome_real)
    print(f"      SESSION: {hasil['ringkasan']} data_ganda={hasil['data_ganda']}")
    for h in hasil["hasil"]:
        print(f"        assign={h['assignment_id']} status={h['status']} "
              f"cat={h.get('failure_category')} alasan={str(h.get('alasan'))[:160]}")
    ringkas_db = await RunRepository().ringkasan_session(sesi["id"])
    print(f"[7/7] Ringkasan DB: {ringkas_db['ringkasan']}")
    print(f"      GUI: /api/runs/sessions/{sesi['id']}/runs/view")
    print(f"      Laporan: /api/reports/sessions/{sesi['id']}/view")
    await akhiri_sesi(sesi["id"])
    print("      Sesi diakhiri (completed).")
    await db.close()
    if hasil["data_ganda"]:
        print("GAGAL: data ganda (anti-race jebol).")
        sys.exit(5)
    if hasil["ringkasan"]["passed"] == 0:
        print("GAGAL: 0 passed. Cek: appium -p 4723 & appium -p 4724 jalan?")
        sys.exit(6)
    print(f"OK Phase 7 real: {hasil['ringkasan']['passed']}/"
          f"{hasil['ringkasan']['total']} passed.")


async def main(url_uji: str):
    sesi = await siapkan_pair(url_uji)
    await jalankan_paralel(sesi, url_uji)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Phase 7 real 2-device Chrome test")
    ap.add_argument("--url", default="https://example.com")
    args = ap.parse_args()
    asyncio.run(main(args.url))
