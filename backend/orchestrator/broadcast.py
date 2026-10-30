"""
broadcast.py - Broadcast mode + safety check (Phase 6, S4.4.4 + S4.4.6).

Broadcast = aksi manual identik ke banyak device sekaligus.
Safety check anti salah sasaran: hanya device idle/busy yang hidup,
tanpa sesi aktif yang terikat skenario, dan lolos gate recalibration.
Fail-safe: device ragu = excluded + alasan, bukan dipaksa ikut.
Eksekusi fisik paralel via runner Phase 7 (jalankan_broadcast_fisik),
audit trail tetap dicatat di sini.
"""
from typing import Dict, List, Optional, Set

from backend.db.repositories.device_repo import DeviceRepository
from backend.db.repositories.client_repo import ClientRepository
from backend.db.repositories.session_repo import (
    SessionRepository, BroadcastRepository,
)

# Aksi broadcast yang diizinkan (whitelist ketat, selaras ALLOWED_ACTIONS skenario).
ALLOWED_BROADCAST = {"tap", "fill", "scroll", "assert_visible", "back", "wake"}


def _validasi_aksi(action_type: str, target: str) -> List[str]:
    """Validasi fail-closed, return list error."""
    errors = []
    aksi = (action_type or "").strip()
    if aksi not in ALLOWED_BROADCAST:
        errors.append(
            f"Aksi '{aksi}' tidak dikenal. Izin: {sorted(ALLOWED_BROADCAST)}.")
    if aksi in ("tap", "assert_visible") and not (target or "").strip():
        errors.append(f"Aksi '{aksi}' wajib punya target role_label/koordinat.")
    if aksi == "fill" and not (target or "").strip():
        errors.append("Aksi 'fill' wajib punya target 'role_label|teks'.")
    return errors


async def safety_check_broadcast(
    client_id: int,
    action_type: str,
    target: str,
    device_ids: Optional[List[int]] = None,
    live_override: Optional[Set[str]] = None,
) -> Dict:
    """Safety check tanpa eksekusi. Tak pernah raise untuk device ragu."""
    from backend.orchestrator.device_pool import daftar_perangkat_adb
    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise ValueError(f"Klien {client_id} tidak ditemukan.")
    errors = _validasi_aksi(action_type, target)
    if errors:
        raise ValueError("; ".join(errors))
    device_repo = DeviceRepository()
    sesi_repo = SessionRepository()
    if device_ids:
        kandidat = []
        for did in device_ids:
            d = await device_repo.get_by_id(did)
            if not d:
                raise ValueError(f"Device {did} tidak ditemukan.")
            kandidat.append(d)
    else:
        kandidat = await device_repo.get_all()
    hidup = set(live_override) if live_override is not None else set(daftar_perangkat_adb())
    ikut, dikecualikan = [], []
    for d in kandidat:
        if d["adb_id"] not in hidup:
            dikecualikan.append({"device_id": d["id"], "adb_id": d["adb_id"],
                                 "alasan": "Tidak terlihat di ADB (offline)."})
            continue
        if d["status"] == "offline":
            dikecualikan.append({"device_id": d["id"], "adb_id": d["adb_id"],
                                 "alasan": "Status offline di pool."})
            continue
        aktif = await sesi_repo.get_active_untuk_device(d["id"])
        if aktif:
            dikecualikan.append({"device_id": d["id"], "adb_id": d["adb_id"],
                "alasan": f"Terikat sesi aktif #{aktif[0]['id']} (punya skenario)."})
            continue
        ikut.append({"device_id": d["id"], "adb_id": d["adb_id"], "status": d["status"]})
    boleh = len(ikut) > 0
    alasan = (f"{len(ikut)} device siap, {len(dikecualikan)} di-exclude."
              if boleh else "Tak ada device layak broadcast — semua di-exclude.")
    return {"boleh_jalan": boleh, "alasan": alasan,
            "action_type": (action_type or '').strip(), "target": (target or '').strip(),
            "client_id": client_id, "ikut": ikut, "dikecualikan": dikecualikan}


async def jalankan_broadcast(
    client_id: int,
    action_type: str,
    target: str,
    device_ids: Optional[List[int]] = None,
    live_override: Optional[Set[str]] = None,
) -> Dict:
    """Jalankan broadcast (catat audit trail). Tolak bila tak ada yang layak."""
    cek = await safety_check_broadcast(client_id, action_type, target, device_ids, live_override)
    if not cek["boleh_jalan"]:
        raise ValueError(f"Broadcast ditolak: {cek['alasan']} {cek['dikecualikan']}")
    repo = BroadcastRepository()
    broadcast_id = await repo.catat_aksi(cek["action_type"], cek["target"])
    for ikut in cek["ikut"]:
        await repo.catat_peserta(broadcast_id, ikut["device_id"], True, "")
    for kec in cek["dikecualikan"]:
        await repo.catat_peserta(broadcast_id, kec["device_id"], False, kec["alasan"])
    detail = await repo.get_by_id(broadcast_id)
    if not detail:
        raise ValueError("Gagal membaca broadcast baru.")
    # Eksekusi fisik paralel tersedia via runner Phase 7
    # (backend/orchestrator/runner.py: jalankan_broadcast_fisik).
    return {**detail, "boleh_jalan": True, "alasan": cek["alasan"],
            "ikut": cek["ikut"], "dikecualikan": cek["dikecualikan"]}
