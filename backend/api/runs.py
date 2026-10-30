"""API Router untuk Execution Engine Phase 7 - test data + runs paralel."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from backend.db.repositories import (
    ClientRepository, DeviceRepository, SessionRepository,
    AssignmentRepository, ScenarioRepository,
    TestDataRepository, RunRepository,
)
from backend.orchestrator.runner import (
    jalankan_assignment, jalankan_session, jalankan_broadcast_fisik,
    driver_factory_fake,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


class DataTambahModel(BaseModel):
    scenario_id: int
    data_json: dict
    assigned_to_device_id: Optional[int] = None


class SessionRunModel(BaseModel):
    test_data_ids: Optional[Dict[int, int]] = None
    mode: Optional[str] = None


class AssignRunModel(BaseModel):
    test_data_id: Optional[int] = None
    klaim_otomatis: bool = True
    mode: Optional[str] = None


class BroadcastFisikModel(BaseModel):
    client_id: int
    action_type: str
    target: Optional[str] = ""
    device_ids: Optional[List[int]] = None


class DemoRealModel(BaseModel):
    url: Optional[str] = "https://example.com"
    serial_a: Optional[str] = None
    serial_b: Optional[str] = None
    pair_label: Optional[str] = "pair-real-2hp"


@router.post("/demo/real-2device", response_model=dict)
async def demo_real_2device(body: Optional[DemoRealModel] = None):
    """Setup sekali-klik untuk uji nyata 2 HP WiFi + Chrome (tampil di GUI).

    Langkah = skrip jalankan_phase7_real_2device.py siapkan_pair():
    cek ADB live -> register+health -> klien+page+element+skenario open_url
    -> gate recalibration -> 2 baris data -> pair+assign.
    Return session_id + link GUI runs/report/sesi/devices.
    Fail-closed: ADB hilang / gate tertahan / device busy -> 400.
    """
    from backend.db.repositories import PageRepository, ElementRepository
    from backend.recalibration.service import jalankan_recalibration
    from backend.orchestrator.device_pool import (
        daftar_perangkat_adb, register_device, health_check_semua,
    )
    from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
    from backend.orchestrator.runner import bangun_caps

    url_uji = ((body.url if body and body.url else "") or "").strip() or "https://example.com"
    label = ((body.pair_label if body and body.pair_label else "") or "").strip() or "pair-real-2hp"
    try:
        # UX baru: serial boleh kosong -> pakai 2 HP pertama yang hidup di ADB.
        # Device terdeteksi `adb devices` = langsung bisa dipakai, tanpa ketik manual.
        live_awal = sorted(set(daftar_perangkat_adb()))
        serial_a = ((body.serial_a if body and body.serial_a else "") or "").strip()
        serial_b = ((body.serial_b if body and body.serial_b else "") or "").strip()
        if not serial_a or not serial_b:
            if len(live_awal) < 2:
                raise ValueError(
                    f"Butuh 2 HP hidup di ADB, terdeteksi {len(live_awal)}: {live_awal}. "
                    "Hubungkan WiFi ADB dulu: adb connect <ip>:<port>.")
            serial_a, serial_b = live_awal[0], live_awal[1]
        if serial_a == serial_b:
            # Bila user pilih sama / hanya 1 HP: cari pasangan lain otomatis.
            sisa = [s for s in live_awal if s != serial_a]
            if not sisa:
                raise ValueError(
                    "serial_a dan serial_b harus beda (butuh 2 HP).")
            serial_b = sisa[0]
        kurang = [s for s in (serial_a, serial_b) if s not in set(live_awal)]
        if kurang:
            raise ValueError(
                f"ADB tak terlihat: {kurang}. live={live_awal}. "
                "Hubungkan WiFi ADB dulu: adb connect <serial>.")
        live = live_awal
        for serial in (serial_a, serial_b):
            sudah = await DeviceRepository().get_by_adb_id(serial)
            if not sudah:
                await register_device(serial)
        hasil_hc = await health_check_semua()
        ringkas_hc = {d["adb_id"]: d["status"] for d in hasil_hc
                      if d["adb_id"] in (serial_a, serial_b)}
        dev_a = await DeviceRepository().get_by_adb_id(serial_a)
        dev_b = await DeviceRepository().get_by_adb_id(serial_b)
        if not dev_a or not dev_b:
            raise ValueError("Registrasi device gagal.")
        if dev_a["status"] == "offline" or dev_b["status"] == "offline":
            raise ValueError(f"Device offline: {ringkas_hc}. Health-check dulu.")
        if dev_a["status"] != "idle" or dev_b["status"] != "idle":
            raise ValueError(
                f"Device tidak idle: A={dev_a['status']} B={dev_b['status']}. "
                "Selesaikan sesi lama dulu via GUI.")
        bbox = {"x": 100, "y": 200, "width": 80, "height": 40}
        cid = await ClientRepository().create(
            nama="Klien Chrome Real 2HP", base_url=url_uji)
        pid = await PageRepository().create(cid, url_uji)
        await ElementRepository().create(
            page_id=pid, role_label="halaman_utama",
            selectors={"primary": "body", "fallbacks": []},
            text_snapshot="Halaman", bbox=dict(bbox),
            confidence=0.90, approved=True)
        sid = await ScenarioRepository().create(
            cid, "buka_chrome_real",
            [{"action": "open_url", "role_label": "", "page_id": pid,
              "params": {"url": "{{url}}"}}])
        segar = [{"role": "document", "role_label": "halaman_utama",
                  "text": "Halaman", "bbox": dict(bbox),
                  "selectors": {"primary": "body", "fallbacks": []}}]
        gate = await jalankan_recalibration(pid, fresh_override=segar)
        if not gate.get("boleh_jalan"):
            raise ValueError(f"Gate tertahan: {gate.get('ringkasan')}")
        await TestDataRepository().tambah(sid, {"url": url_uji, "nama": "HP-A"})
        await TestDataRepository().tambah(sid, {"url": url_uji, "nama": "HP-B"})
        sesi = await buat_sesi_pair(cid, dev_a["id"], dev_b["id"], label)
        ta = await tugaskan_skenario(sesi["id"], dev_a["id"], sid)
        tb = await tugaskan_skenario(sesi["id"], dev_b["id"], sid)
        return {
            "session_id": sesi["id"], "client_id": cid, "scenario_id": sid,
            "page_id": pid, "device_a": dev_a, "device_b": dev_b,
            "caps_a": bangun_caps(dev_a), "caps_b": bangun_caps(dev_b),
            "health": ringkas_hc, "gate": gate.get("ringkasan"),
            "assignment_a": ta["id"], "assignment_b": tb["id"],
            "gui_runs": f"/api/runs/sessions/{sesi['id']}/runs/view",
            "gui_laporan": f"/api/reports/sessions/{sesi['id']}/view",
            "gui_sesi": f"/api/orchestrator/sessions/{sesi['id']}/view",
            "gui_devices": "/api/orchestrator/devices/view",
            "cara_real": f"POST /api/runs/sessions/{sesi['id']}/run "
                         "{\"mode\":\"real\"} atau klik [Real Chrome 2 HP] di GUI runs",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/test-data", response_model=dict)
async def tambah_data(body: DataTambahModel):
    """Tambah satu baris data uji untuk satu skenario."""
    try:
        data_id = await TestDataRepository().tambah(
            body.scenario_id, body.data_json, body.assigned_to_device_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    hasil = await TestDataRepository().get_by_id(data_id)
    if not hasil:
        raise HTTPException(status_code=400, detail="Gagal membaca data baru.")
    return hasil


@router.get("/test-data/scenario/{scenario_id}", response_model=dict)
async def daftar_data(scenario_id: int):
    """Daftar baris data uji satu skenario + yang tersedia."""
    skenario = await ScenarioRepository().get_by_id(scenario_id)
    if not skenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    semua = await TestDataRepository().list_by_skenario(scenario_id)
    tersedia = await TestDataRepository().get_tersedia(scenario_id)
    return {"scenario_id": scenario_id, "semua": semua,
            "tersedia": tersedia, "jumlah_tersedia": len(tersedia)}


@router.post("/test-data/scenario/{scenario_id}/claim", response_model=dict)
async def klaim_data(scenario_id: int, device_id: int):
    """Klaim atomik satu baris available untuk satu device."""
    try:
        hasil = await TestDataRepository().klaim_atomik(scenario_id, device_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not hasil:
        raise HTTPException(status_code=400, detail="Stok data available habis.")
    return hasil


@router.get("/test-data/{data_id}", response_model=dict)
async def get_data(data_id: int):
    """Detail satu baris data uji."""
    hasil = await TestDataRepository().get_by_id(data_id)
    if not hasil:
        raise HTTPException(status_code=404, detail="Test data not found")
    return hasil
@router.post("/assignments/{assignment_id}/run", response_model=dict)
async def run_assignment(assignment_id: int, body: Optional[AssignRunModel] = None):
    """Jalankan satu assignment (satu device) sampai tuntas."""
    tug = await AssignmentRepository().get_by_id(assignment_id)
    if not tug:
        raise HTTPException(status_code=404, detail="Assignment not found")
    try:
        mode = ((body.mode if body and body.mode else "") or "simulate").strip().lower()
        if mode in ("real", "chrome_real", "chrome-real", "real_chrome"):
            from backend.orchestrator import chrome_real
            chrome_real.pasang_open_url()
            return await jalankan_assignment(
                assignment_id,
                chrome_real.driver_factory_chrome_real,
                test_data_id=(body.test_data_id if body else None),
                klaim_otomatis=(body.klaim_otomatis if body else True))
        return await jalankan_assignment(
            assignment_id,
            driver_factory_fake,
            test_data_id=(body.test_data_id if body else None),
            klaim_otomatis=(body.klaim_otomatis if body else True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.post("/sessions/{session_id}/run", response_model=dict)
async def run_session(session_id: int, body: Optional[SessionRunModel] = None):
    """Jalankan semua assignment satu sesi paralel (satu pair).

    Mode:
    - kosong/simulate (default): FakeDriver, tanpa Appium/kabel.
    - "real": Chrome nyata via Appium 2 HP WiFi
      (driver_factory_chrome_real + patch open_url).
    """
    sesi = await SessionRepository().get_by_id(session_id)
    if not sesi:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        peta = {}
        if body and body.test_data_ids:
            peta = {int(k): int(v) for k, v in body.test_data_ids.items()}
        mode = ((body.mode if body and body.mode else "") or "").strip().lower()
        if mode in ("real", "chrome_real", "chrome-real", "real_chrome"):
            from backend.orchestrator import chrome_real
            chrome_real.pasang_open_url()
            return await jalankan_session(
                session_id, chrome_real.driver_factory_chrome_real,
                test_data_ids=peta or None)
        # Default simulate: FakeDriver eksplisit (jangan Appium).
        return await jalankan_session(
            session_id, driver_factory_fake, test_data_ids=peta or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/runs", response_model=dict)
async def ringkasan_runs(session_id: int):
    """Ringkasan runs satu sesi (passed/failed/blocked/running)."""
    sesi = await SessionRepository().get_by_id(session_id)
    if not sesi:
        raise HTTPException(status_code=404, detail="Session not found")
    return await RunRepository().ringkasan_session(session_id)


@router.get("/runs/{run_id}", response_model=dict)
async def get_run(run_id: int):
    """Detail satu run."""
    hasil = await RunRepository().get_by_id(run_id)
    if not hasil:
        raise HTTPException(status_code=404, detail="Run not found")
    return hasil


@router.get("/assignments/{assignment_id}/runs", response_model=dict)
async def runs_assignment(assignment_id: int):
    """Riwayat run satu assignment."""
    tug = await AssignmentRepository().get_by_id(assignment_id)
    if not tug:
        raise HTTPException(status_code=404, detail="Assignment not found")
    hasil = await RunRepository().get_by_assignment(assignment_id)
    return {"assignment_id": assignment_id, "runs": hasil}
@router.post("/broadcast/physical", response_model=dict)
async def run_broadcast_fisik(body: BroadcastFisikModel):
    """Eksekusi fisik broadcast paralel (safety check + kirim Appium)."""
    try:
        return await jalankan_broadcast_fisik(
            body.client_id, body.action_type, body.target or "",
            body.device_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/demo/real-2device/view", response_class=HTMLResponse)
async def view_demo_real(request: Request):
    """Halaman setup sekali-klik uji nyata 2 HP WiFi (tanpa terminal)."""
    return templates.TemplateResponse("runs/demo_real.html", {"request": request})


@router.get("/sessions/{session_id}/runs/view", response_class=HTMLResponse)
async def view_runs(request: Request, session_id: int):
    """HTML ringkasan runs satu sesi + tombol jalankan paralel."""
    sesi_repo = SessionRepository()
    sesi = await sesi_repo.get_by_id(session_id)
    if not sesi:
        raise HTTPException(status_code=404, detail="Session not found")
    client = await ClientRepository().get_by_id(sesi["client_id"])
    assignments = await sesi_repo.get_assignments(session_id)
    detail_assign = []
    assign_repo = AssignmentRepository()
    for a in assignments:
        d = await assign_repo.get_detail(a["id"])
        if d:
            detail_assign.append(d)
    ringkas = await RunRepository().ringkasan_session(session_id)
    dev_repo = DeviceRepository()
    dev_a = await dev_repo.get_by_id(sesi["device_a_id"])
    dev_b = await dev_repo.get_by_id(sesi["device_b_id"])
    return templates.TemplateResponse(
        "runs/session_runs.html",
        {"request": request, "sesi": sesi, "client": client,
         "assignments": detail_assign, "ringkas": ringkas,
         "dev_a": dev_a, "dev_b": dev_b},
    )



