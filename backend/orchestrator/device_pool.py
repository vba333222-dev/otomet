"""
device_pool.py - Device pool manager (Phase 6, S4.4.2 + S4.4.3).

Wrapper deteksi ADB (adbutils bila ada, fallback `adb devices`),
registrasi, heartbeat, health-check, dan alokasi FIFO.
Fail-safe: device ragu/offline = di-exclude, bukan dipaksa ikut.
"""
import shutil
import subprocess
from typing import List, Optional, Set

from backend.db.repositories.device_repo import DeviceRepository


def _daftar_via_adbutils() -> Optional[List[str]]:
    """Coba via adbutils, return None bila lib tak tersedia."""
    try:
        import adbutils  # type: ignore
    except Exception:
        return None
    try:
        adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        return [d.serial for d in adb.device_list()]
    except Exception:
        return []


def _kandidat_adb_exe() -> List[str]:
    """Kandidat perintah ADB di Windows + PATH (2 HP WiFi user di SDK default)."""
    import os
    kandidat = []
    try:
        lokal = os.environ.get("LOCALAPPDATA") or ""
        if lokal:
            kandidat.append(os.path.join(
                lokal, "Android", "Sdk", "platform-tools", "adb.exe"))
    except Exception:
        pass
    kandidat.append("adb")
    # Unik, jaga urutan.
    unik = []
    for k in kandidat:
        if k and k not in unik:
            unik.append(k)
    return unik


def _daftar_via_cli() -> List[str]:
    """Fallback `adb devices`. Kosong bila adb tak terpasang / gagal."""
    import os
    for adb_cmd in _kandidat_adb_exe():
        if adb_cmd != "adb" and not os.path.exists(adb_cmd):
            continue
        if adb_cmd == "adb" and not shutil.which("adb"):
            continue
        try:
            out = subprocess.run(
                [adb_cmd, "devices"], capture_output=True, text=True, timeout=10
            )
        except Exception:
            continue
        hasil = []
        for baris in (out.stdout or "").splitlines()[1:]:
            baris = baris.strip()
            if not baris or "offline" in baris and "\t" not in baris:
                continue
            if "\tdevice" in baris:
                hasil.append(baris.split("\t")[0].strip())
        # Kembalikan hasil perintah pertama yang berhasil jalan,
        # walau kosong (bedakan gagal vs memang tak ada device).
        return hasil
    return []


def daftar_perangkat_adb() -> List[str]:
    """Daftar serial ADB yang hidup. Tak pernah raise (fail-safe kosong)."""
    via_lib = _daftar_via_adbutils()
    if via_lib is not None:
        return via_lib
    return _daftar_via_cli()


async def register_device(adb_id: str, ram_gb: Optional[int] = None) -> dict:
    """Daftarkan device fisik. Fail-closed bila duplikat / adb_id kosong."""
    repo = DeviceRepository()
    adb_bersih = (adb_id or "").strip()
    if not adb_bersih:
        raise ValueError("adb_id wajib diisi.")
    sudah = await repo.get_by_adb_id(adb_bersih)
    if sudah:
        raise ValueError(f"Device '{adb_bersih}' sudah terdaftar (id {sudah['id']}).")
    if ram_gb is not None and ram_gb not in (2, 3, 4, 6, 8, 12):
        raise ValueError("ram_gb varian Redmi 12C: 2/3/4/6 (8/12 longgar).")
    device_id = await repo.create(adb_bersih, ram_gb=ram_gb)
    hasil = await repo.get_by_id(device_id)
    if not hasil:
        raise ValueError("Gagal membaca device baru.")
    return hasil


async def heartbeat_device(device_id: int) -> dict:
    """Heartbeat: cap waktu cek, offline -> idle (kembali hidup)."""
    repo = DeviceRepository()
    hasil = await repo.heartbeat(device_id)
    if not hasil:
        raise ValueError(f"Device {device_id} tidak ditemukan.")
    return hasil


async def health_check_device(
    device_id: int, live_override: Optional[Set[str]] = None
) -> dict:
    """Health-check satu device. Offline bila serial tak terlihat di ADB."""
    repo = DeviceRepository()
    device = await repo.get_by_id(device_id)
    if not device:
        raise ValueError(f"Device {device_id} tidak ditemukan.")
    hidup = set(live_override) if live_override is not None else set(daftar_perangkat_adb())
    status_baru = "offline" if device["adb_id"] not in hidup else (
        device["status"] if device["status"] in ("idle", "busy") else "idle"
    )
    # Device busy yang masih hidup tetap busy; yang hilang -> offline.
    if device["adb_id"] not in hidup:
        status_baru = "offline"
    elif device["status"] == "offline" and device["adb_id"] in hidup:
        status_baru = "idle"
    await repo.update_health(device_id, status_baru)
    hasil = await repo.get_by_id(device_id)
    if not hasil:
        raise ValueError(f"Device {device_id} hilang setelah health-check.")
    return hasil


async def health_check_semua(
    live_override: Optional[List[str]] = None
) -> List[dict]:
    """Health-check seluruh pool, kembalikan status terbaru."""
    repo = DeviceRepository()
    semua = await repo.get_all()
    hidup = set(live_override) if live_override is not None else set(daftar_perangkat_adb())
    hasil = []
    for d in semua:
        hasil.append(await health_check_device(d["id"], live_override=hidup))
    return hasil


async def sinkronkan_adb(ram_default: Optional[int] = None) -> dict:
    """Daftarkan otomatis semua serial ADB hidup yang belum terdaftar.

    UX: `adb devices` = langsung bisa dipakai. Idempotent, tak pernah duplikat.
    Return {"live": [...], "baru": [...], "semua": [...]}.
    """
    repo = DeviceRepository()
    live = sorted(set(daftar_perangkat_adb()))
    baru = []
    for serial in live:
        sudah = await repo.get_by_adb_id(serial)
        if sudah:
            continue
        try:
            did = await repo.create(serial, ram_gb=ram_default)
            d = await repo.get_by_id(did)
            if d:
                baru.append(d)
        except Exception:
            continue
    semua = await repo.get_all()
    # Segarkan status health agar badge GUI akurat.
    try:
        await health_check_semua(live_override=live)
        semua = await repo.get_all()
    except Exception:
        pass
    return {"live": live, "baru": baru, "semua": semua}


async def ambil_device_idle_fifo(jumlah: int) -> List[dict]:
    """Ambil N device idle FIFO (id terkecil dulu). Fail-closed bila kurang."""
    if jumlah < 1:
        raise ValueError("jumlah minimal 1.")
    if jumlah > 10:
        raise ValueError("Maksimal 10 device per batch (satu klien).")
    repo = DeviceRepository()
    idle = await repo.get_idle(limit=jumlah)
    if len(idle) < jumlah:
        raise ValueError(
            f"Device idle kurang: butuh {jumlah}, tersedia {len(idle)}. "
            "Bebaskan sesi / hubungkan device dulu."
        )
    return idle
