"""
session_manager.py - Pairing & assignment sesi (Phase 6, S4.4.2 + Phase 7 runner).

Satu sesi = satu pair (2 device) untuk satu klien.
Fail-safe: device tidak idle / sudah dipakai sesi aktif / gate tertahan = tolak.
Anti race antar device satu pair ditangani runner paralel
(backend/orchestrator/runner.py): klaim data atomik + stagger + semaphore.
"""
from typing import Dict, List, Optional

from backend.db.repositories.device_repo import DeviceRepository
from backend.db.repositories.client_repo import ClientRepository
from backend.db.repositories.scenario_repo import ScenarioRepository
from backend.db.repositories.session_repo import (
    SessionRepository, AssignmentRepository,
)


async def buat_sesi_pair(
    client_id: int,
    device_a_id: int,
    device_b_id: int,
    pair_label: Optional[str] = None,
) -> Dict:
    """Buat sesi pair baru. Device A dan B jadi busy."""
    if device_a_id == device_b_id:
        raise ValueError("Device A dan B harus berbeda (satu pair = 2 device).")
    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise ValueError(f"Klien {client_id} tidak ditemukan.")
    device_repo = DeviceRepository()
    sesi_repo = SessionRepository()
    dev_a = await device_repo.get_by_id(device_a_id)
    dev_b = await device_repo.get_by_id(device_b_id)
    if not dev_a:
        raise ValueError(f"Device A ({device_a_id}) tidak ditemukan.")
    if not dev_b:
        raise ValueError(f"Device B ({device_b_id}) tidak ditemukan.")
    for dev, nama in ((dev_a, "A"), (dev_b, "B")):
        if dev["status"] == "offline":
            raise ValueError(f"Device {nama} ({dev['adb_id']}) offline. Ganti device lain.")
        if dev["status"] != "idle":
            raise ValueError(
                f"Device {nama} ({dev['adb_id']}) status '{dev['status']}', harus idle.")
        aktif = await sesi_repo.get_active_untuk_device(dev["id"])
        if aktif:
            raise ValueError(
                f"Device {nama} ({dev['adb_id']}) masih dipakai sesi aktif #{aktif[0]['id']}.")
    label = (pair_label or "").strip() or f"pair-{dev_a['adb_id']}-{dev_b['adb_id']}"
    session_id = await sesi_repo.create(client_id, device_a_id, device_b_id, label)
    await device_repo.set_status(device_a_id, "busy")
    await device_repo.set_status(device_b_id, "busy")
    sesi = await sesi_repo.get_by_id(session_id)
    if not sesi:
        raise ValueError("Gagal membaca sesi baru.")
    return sesi


async def tugaskan_skenario(session_id: int, device_id: int, scenario_id: int) -> Dict:
    """Tugaskan satu skenario ke satu device dalam sesi.

    Fail-closed: sesi harus running, device harus anggota pair,
    skenario harus milik klien yang sama, gate recalibration wajib lolos.
    """
    from backend.recalibration.service import cek_gate_untuk_skenario
    sesi_repo = SessionRepository()
    assign_repo = AssignmentRepository()
    sesi = await sesi_repo.get_by_id(session_id)
    if not sesi:
        raise ValueError(f"Sesi {session_id} tidak ditemukan.")
    if sesi["status"] != "running":
        raise ValueError(f"Sesi {session_id} status '{sesi['status']}', harus running.")
    if device_id not in (sesi["device_a_id"], sesi["device_b_id"]):
        raise ValueError(f"Device {device_id} bukan anggota sesi {session_id}.")
    skenario_repo = ScenarioRepository()
    skenario = await skenario_repo.get_by_id(scenario_id)
    if not skenario:
        raise ValueError(f"Skenario {scenario_id} tidak ditemukan.")
    if skenario["client_id"] != sesi["client_id"]:
        raise ValueError("Skenario beda klien dengan sesi. Satu batch = satu klien.")
    device = await DeviceRepository().get_by_id(device_id)
    if not device:
        raise ValueError(f"Device {device_id} tidak ditemukan.")
    if device["status"] == "offline":
        raise ValueError(f"Device {device['adb_id']} offline, tidak bisa ditugaskan.")
    gate = await cek_gate_untuk_skenario(scenario_id)
    if not gate.get("boleh_jalan"):
        raise ValueError(
            f"Gate recalibration tertahan: {gate.get('alasan')} "
            f"{gate.get('detail')}. Jalankan recalibration dulu.")
    assignment_id = await assign_repo.create(session_id, device_id, scenario_id)
    detail = await assign_repo.get_detail(assignment_id)
    if not detail:
        raise ValueError("Gagal membaca assignment baru.")
    return {**detail, "gate": gate}


async def akhiri_sesi(session_id: int, batal: bool = False) -> Dict:
    """Akhiri sesi. Bebaskan device yang tak dipakai sesi aktif lain.

    Device offline tetap offline (jangan paksa idle).
    """
    sesi_repo = SessionRepository()
    device_repo = DeviceRepository()
    sesi = await sesi_repo.get_by_id(session_id)
    if not sesi:
        raise ValueError(f"Sesi {session_id} tidak ditemukan.")
    if sesi["status"] != "running":
        raise ValueError(f"Sesi {session_id} sudah '{sesi['status']}'.")
    status_baru = "failed" if batal else "completed"
    await sesi_repo.set_status(session_id, status_baru)
    for dev_id in (sesi["device_a_id"], sesi["device_b_id"]):
        dev = await device_repo.get_by_id(dev_id)
        if not dev:
            continue
        if dev["status"] == "offline":
            continue
        masih = await sesi_repo.get_active_untuk_device(dev_id)
        # Sesi ini sudah non-active, jadi bila masih ada = dipakai sesi lain.
        if not masih:
            await device_repo.set_status(dev_id, "idle")
    sesi_akhir = await sesi_repo.get_by_id(session_id)
    assignments = await sesi_repo.get_assignments(session_id)
    return {**(sesi_akhir or {}), "assignments": assignments}


async def daftar_sesi_client(client_id: int) -> List[Dict]:
    """Daftar sesi milik satu klien (terbaru dulu)."""
    return await SessionRepository().get_by_client(client_id)
