"""cmdlog.py - Ring buffer log perintah HP untuk diagnosa GUI.

Setiap tap/swipe/type/key dicatat: waktu, serial, aksi,
durasi ADB (ms), hasil OK/GAGAL + detail error.
Disimpan in-memory (max 200) agar GUI bisa poll via
GET /devices/log tanpa baca file.
"""
import time
from collections import deque
from typing import List, Dict

_MAKS = 200
_RIWAYAT: deque = deque(maxlen=_MAKS)


def catat(aksi: str, serial: str, detail: str = "",
          ok: bool = True, ms: int = 0,
          error: str = "") -> dict:
    entri = {
        "jam": time.strftime("%H:%M:%S"),
        "ts": time.time(),
        "aksi": aksi,
        "serial": (serial or "").strip(),
        "detail": detail or "",
        "ok": bool(ok),
        "ms": int(ms or 0),
        "error": (error or "")[:500],
    }
    _RIWAYAT.append(entri)
    return entri


def ambil(batas: int = 60) -> List[Dict]:
    try:
        batas = max(1, min(200, int(batas or 60)))
    except Exception:
        batas = 60
    data = list(_RIWAYAT)[-batas:]
    return list(reversed(data))


def bersihkan() -> dict:
    _RIWAYAT.clear()
    return {"ok": True}


def sebagai_teks(batas: int = 60) -> str:
    """Format log sebagai teks siap-salin (satu baris per perintah).

    Dipakai tombol 'Salin Log' + endpoint /devices/log/text agar user
    bisa tempel ke chat/laporan tanpa screenshot.
    """
    try:
        batas = max(1, min(200, int(batas or 60)))
    except Exception:
        batas = 60
    data = list(_RIWAYAT)[-batas:]
    baris = []
    for e in data:
        try:
            st = f"-> {e.get('ms', 0)}ms OK" if e.get("ok") else f"GAGAL: {e.get('error') or '?'}"
            det = f" {e.get('detail')}" if e.get("detail") else ""
            baris.append(f"{e.get('jam')} [{e.get('aksi')}] {e.get('serial')}{det} {st}")
        except Exception:
            continue
    return "\n".join(baris)
