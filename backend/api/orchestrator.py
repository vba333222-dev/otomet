"""API Router untuk Orchestrator Phase 6 - devices + sessions."""
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from backend.db.repositories import (
    ClientRepository, DeviceRepository, SessionRepository,
    AssignmentRepository, ScenarioRepository,
)
from backend.orchestrator.device_pool import (
    daftar_perangkat_adb, register_device, heartbeat_device,
    health_check_device, health_check_semua, sinkronkan_adb,
)
from backend.orchestrator import cmdlog as _cmdlog
import time as _waktu
from backend.orchestrator.session_manager import (
    buat_sesi_pair, tugaskan_skenario, akhiri_sesi, daftar_sesi_client,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


class DeviceCreateModel(BaseModel):
    adb_id: str
    ram_gb: Optional[int] = None


class SessionCreateModel(BaseModel):
    client_id: int
    device_a_id: int
    device_b_id: int
    pair_label: Optional[str] = None


class AssignModel(BaseModel):
    device_id: int
    scenario_id: int


@router.get("/devices", response_model=List[dict])
async def list_devices():
    return await DeviceRepository().get_all()


@router.get("/devices/adb", response_model=dict)
async def adb_terdeteksi():
    return {"live": daftar_perangkat_adb()}


@router.post("/devices", response_model=dict)
async def tambah_device(body: DeviceCreateModel):
    try:
        return await register_device(body.adb_id, body.ram_gb)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/devices/{device_id}", response_model=dict)
async def hapus_device(device_id: int):
    """Hapus device manual/sampah (misal 'Redmi 12C' tanpa IP)."""
    d = await DeviceRepository().get_by_id(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    if str(d.get("status")) == "busy":
        raise HTTPException(status_code=400, detail="Device busy, bebaskan sesi dulu.")
    await DeviceRepository().delete(device_id)
    return {"ok": True, "id": device_id}


@router.post("/devices/sync", response_model=dict)
async def sinkron_device_adb():
    """1-klik: daftarkan otomatis semua HP yang hidup di `adb devices`.

    Idempotent: yang sudah terdaftar dilewati, tak pernah duplikat.
    UX: HP terdeteksi = langsung bisa dipakai uji nyata.
    """
    try:
        return await sinkronkan_adb()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/live", response_model=dict)
async def live_terpadu():
    """Satu panggilan untuk GUI live: ADB + DB + info HP (model/baterai/layar).

    Dipoll frontend tiap 3 detik. Tak pernah 500 bila ADB kosong —
    kembalikan live=[] agar kartu bisa tampil "belum ada HP".
    Info diambil paralel + cache 10 dtk agar polling ringan.
    """
    import asyncio as _aio
    from backend.orchestrator import screen as layar
    live = sorted(set(daftar_perangkat_adb()))
    try:
        semua = await DeviceRepository().get_all()
    except Exception:
        semua = []
    by_serial = {str(d.get("adb_id")): d for d in (semua or [])}

    async def _satu(serial: str):
        d = by_serial.get(serial)
        try:
            info = await _aio.to_thread(layar.info_hp, serial)
        except Exception:
            info = {"serial": serial, "model": "-", "layar_nyala": None, "baterai": None}
        return {
            "serial": serial,
            "model": info.get("model") or "-",
            "layar_nyala": info.get("layar_nyala"),
            "baterai": info.get("baterai"),
            "device_id": (d or {}).get("id"),
            "status": (d or {}).get("status") or "belum terdaftar",
            "appium_port": (d or {}).get("appium_port"),
        }

    # Repair busy-yatim: busy tanpa sesi running -> idle (badge tak macet).
    try:
        semua_db = await DeviceRepository().get_all()
        for d0 in (semua_db or []):
            if str(d0.get("status")) == "busy":
                aktif0 = await SessionRepository().get_active_untuk_device(int(d0["id"]))
                if not aktif0:
                    await DeviceRepository().set_status(int(d0["id"]), "idle")
        # Refresh peta serial->row agar badge GUI akurat.
        try:
            semua = await DeviceRepository().get_all()
            by_serial = {str(d.get("adb_id")): d for d in (semua or [])}
        except Exception:
            pass
    except Exception:
        pass
    kartu = list(await _aio.gather(*[_satu(s) for s in live])) if live else []
    return {"live": live, "kartu": kartu, "total": len(live)}


@router.get("/devices/screen")
async def layar_hp(serial: str = Query(..., min_length=1),
                   lebar: int = Query(360, ge=160, le=720),
                   kualitas: int = Query(55, ge=30, le=80)):
    """JPEG screenshot HP untuk <img>. Contoh: /devices/screen?serial=A."""
    from backend.orchestrator import screen as layar
    try:
        data = await _jalan_blocking(layar.ambil_screenshot, serial, lebar, kualitas)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal screenshot: {e}")
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


class AksiHpModel(BaseModel):
    serial: str
    aksi: str


class BukaUrlModel(BaseModel):
    serial: str
    url: str


def _err_input(exc: Exception):
    """Error input -> 400 kode + panduan MIUI."""
    from backend.orchestrator import screen as layar
    pesan = str(exc)
    try:
        kode = layar.kode_error_input(pesan)
    except Exception:
        kode = "lain"
    try:
        panduan = list(layar.PANDUAN_MIUI)
    except Exception:
        panduan = []
    raise HTTPException(status_code=400, detail={
        "error": pesan, "kode": kode,
        "butuh_izin_miui": (kode == "butuh_izin_miui"),
        "panduan": panduan})


class KetukModel(BaseModel):
    serial: str
    x: int
    y: int


class GeserModel(BaseModel):
    serial: str
    sx: int
    sy: int
    ex: int
    ey: int
    dur_ms: Optional[int] = 300


class KetikModel(BaseModel):
    serial: str
    teks: str


class TombolModel(BaseModel):
    serial: str
    tombol: str


async def _jalan_blocking(fn, *a, **k):
    """Jalankan fungsi blocking ADB di thread agar event-loop tak macet."""
    import asyncio as _aio
    return await _aio.to_thread(fn, *a, **k)


@router.post("/devices/action", response_model=dict)
async def aksi_hp_endpoint(body: AksiHpModel):
    """Tombol simpel per kartu: wake/home/back (langsung terlihat di layar)."""
    from backend.orchestrator import screen as layar
    mulai = _waktu.time()
    try:
        hasil = await _jalan_blocking(layar.aksi_hp, body.serial, body.aksi)
    except ValueError as e:
        _cmdlog.catat("action", body.serial, str(body.aksi),
                      ok=False, ms=int((_waktu.time() - mulai) * 1000),
                      error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    ms = int((_waktu.time() - mulai) * 1000)
    _cmdlog.catat("action", body.serial, str(body.aksi), ok=True, ms=ms)
    return {**hasil, "ms": ms}


@router.post("/devices/open-url", response_model=dict)
async def buka_url_endpoint(body: BukaUrlModel):
    """Buka URL di Chrome satu HP via ADB (terlihat live di screenshot)."""
    from backend.orchestrator import screen as layar
    mulai = _waktu.time()
    try:
        hasil = await _jalan_blocking(layar.buka_url, body.serial, body.url)
    except ValueError as e:
        _cmdlog.catat("open", body.serial, (body.url or "")[:80],
                      ok=False, ms=int((_waktu.time() - mulai) * 1000),
                      error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    ms = int((_waktu.time() - mulai) * 1000)
    _cmdlog.catat("open", body.serial, (body.url or "")[:80], ok=True, ms=ms)
    return {**hasil, "ms": ms}


@router.get("/devices/size", response_model=dict)
async def ukuran_hp(serial: str = Query(..., min_length=1)):
    """Ukuran layar asli HP — dipakai GUI memetakan klik ke koordinat."""
    from backend.orchestrator import screen as layar
    try:
        w, h = await _jalan_blocking(layar.ukuran_layar, serial)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"serial": serial, "lebar": w, "tinggi": h}


@router.get("/devices/stream")
async def stream_hp(serial: str = Query(..., min_length=1),
                    lebar: int = Query(320, ge=160, le=540),
                    kualitas: int = Query(40, ge=30, le=70),
                    fps: int = Query(2, ge=1, le=5)):
    """Aliran MJPEG kontinu per HP: <img src=/devices/stream?serial=...>.

    Batas jujur: screenshot ADB ~2-3 dtk/frame via WiFi, jadi efektif
    ~0.3-0.5 fps per HP (bukan video 30fps). MJPEG dipakai agar gambar
    mengalir tanpa reload/kedip, jauh lebih halus dari polling <img>.
    Untuk video realtime penuh gunakan scrcpy (USB) di luar dashboard.
    Pewaktu adaptif: bila ambil frame sudah > jeda, langsung kirim
    frame berikut tanpa sleep tambahan agar latensi minimal.
    """
    from backend.orchestrator import screen as layar
    lebar = max(160, min(540, int(lebar or 320)))
    kualitas = max(30, min(70, int(kualitas or 40)))
    fps = max(1, min(4, int(fps or 2)))
    jeda = 1.0 / float(fps)

    async def gen():
        import asyncio as _aio
        import time as _t
        gagal = 0
        berikut = _t.monotonic()
        while True:
            try:
                # Anti-hitam: frame_terbaik tak pernah raise -
                # live -> cache terakhir -> placeholder abu-abu.
                frame, sumber = await _aio.to_thread(
                    layar.frame_terbaik, serial, lebar, kualitas,
                    "mencoba lagi %d" % (gagal + 1))
                if sumber == "live":
                    gagal = 0
                else:
                    gagal += 1
                yield (b"--OTOMETFRAME\r\nContent-Type: image/jpeg\r\n"
                       b"X-Frame-Source: " + sumber.encode() + b"\r\n"
                       b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                       + frame + b"\r\n")
            except Exception:
                # Jangan pernah putus: kirim placeholder 1x lalu lanjut.
                try:
                    aw = await _aio.to_thread(
                        layar.placeholder_jpeg, lebar, lebar * 2,
                        "koneksi terputus, mencoba lagi...")
                    yield (b"--OTOMETFRAME\r\nContent-Type: image/jpeg\r\n"
                           b"X-Frame-Source: placeholder\r\n"
                           b"Content-Length: " + str(len(aw)).encode() + b"\r\n\r\n"
                           + aw + b"\r\n")
                except Exception:
                    pass
                gagal += 1
            # Pewaktu adaptif: kejar jadwal fps tanpa menumpuk sleep
            # di atas waktu ambil frame (~2-3 dtk via WiFi) agar latensi minimal.
            berikut += jeda
            kini = _t.monotonic()
            if berikut < kini - jeda:
                berikut = kini
            tunggu = berikut - kini
            if tunggu > 0:
                await _aio.sleep(tunggu)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=OTOMETFRAME",
                             headers={"Cache-Control": "no-store", "Connection": "keep-alive"})


@router.get("/devices/scrcpy-status", response_model=dict)
async def status_scrcpy():
    """Status jalur video 30fps (scrcpy H264 via WebSocket) vs MJPEG.

    PRD FR-26 + NFR-3 mewajibkan video asli 30fps 540p (ws-scrcpy-web),
    bukan screenshot-per-frame. Endpoint ini jujur melaporkan kesiapan
    agar GUI tak menjanjikan 30fps dari MJPEG (~0.3-0.5fps via WiFi).
    """
    import shutil as _sh
    import subprocess as _sp
    ada_scrcpy = bool(_sh.which("scrcpy"))
    ada_node = bool(_sh.which("node"))
    versi_scrcpy = None
    if ada_scrcpy:
        try:
            r = _sp.run(["scrcpy", "--version"], capture_output=True,
                        text=True, timeout=5)
            versi_scrcpy = ((r.stdout or "") + (r.stderr or "")).strip()[:120] or None
        except Exception:
            pass
    return {
        "mjpeg": {"fps_efektif": "0.3-0.5 via WiFi (screenshot ADB ~2-4 dtk/frame)",
                  "catatan": "Anti-hitam aktif (last-good + placeholder). Bukan 30fps."},
        "scrcpy": {"terpasang": ada_scrcpy, "versi": versi_scrcpy,
                   "node": ada_node,
                   "cara_30fps": "scrcpy USB: scrcpy --max-size 960 --max-fps 30, "
                                 "lalu ws-scrcpy-web Fase 8 design.md untuk multi-HP di GUI."},
        "siap_30fps": ada_scrcpy,
    }


@router.post("/devices/tap", response_model=dict)
async def ketuk_endpoint(body: KetukModel):
    """Tap di koordinat piksel HP asli (dari klik di gambar GUI)."""
    from backend.orchestrator import screen as layar
    mulai = _waktu.time()
    try:
        hasil = await _jalan_blocking(layar.ketuk, body.serial, body.x, body.y)
    except ValueError as e:
        _cmdlog.catat("tap", body.serial, f"({body.x},{body.y})",
                      ok=False, ms=int((_waktu.time() - mulai) * 1000),
                      error=str(e))
        _err_input(e)
    ms = int((_waktu.time() - mulai) * 1000)
    _cmdlog.catat("tap", body.serial,
                  f"({hasil.get('x')},{hasil.get('y')})",
                  ok=True, ms=ms)
    return {**hasil, "ms": ms}


@router.post("/devices/swipe", response_model=dict)
async def geser_endpoint(body: GeserModel):
    """Swipe/drag di HP (dari drag di gambar GUI)."""
    from backend.orchestrator import screen as layar
    mulai = _waktu.time()
    try:
        hasil = await _jalan_blocking(layar.geser, body.serial, body.sx, body.sy,
                                      body.ex, body.ey, body.dur_ms or 300)
    except ValueError as e:
        _cmdlog.catat("swipe", body.serial,
                      f"({body.sx},{body.sy})->({body.ex},{body.ey})",
                      ok=False, ms=int((_waktu.time() - mulai) * 1000),
                      error=str(e))
        _err_input(e)
    ms = int((_waktu.time() - mulai) * 1000)
    _cmdlog.catat("swipe", body.serial,
                  f"({hasil.get('sx')},{hasil.get('sy')})->({hasil.get('ex')},{hasil.get('ey')})",
                  ok=True, ms=ms)
    return {**hasil, "ms": ms}


@router.post("/devices/type", response_model=dict)
async def ketik_endpoint(body: KetikModel):
    """Ketik teks di HP yang sedang fokus (input text)."""
    from backend.orchestrator import screen as layar
    mulai = _waktu.time()
    try:
        hasil = await _jalan_blocking(layar.ketik, body.serial, body.teks)
    except ValueError as e:
        _cmdlog.catat("type", body.serial, (body.teks or "")[:60],
                      ok=False, ms=int((_waktu.time() - mulai) * 1000),
                      error=str(e))
        _err_input(e)
    ms = int((_waktu.time() - mulai) * 1000)
    _cmdlog.catat("type", body.serial, (body.teks or "")[:60],
                  ok=True, ms=ms)
    return {**hasil, "ms": ms}


@router.post("/devices/key", response_model=dict)
async def tombol_endpoint(body: TombolModel):
    """Remote tombol: back/home/recent/power/vol_up/vol_down/enter/del/dll."""
    from backend.orchestrator import screen as layar
    mulai = _waktu.time()
    try:
        hasil = await _jalan_blocking(layar.tombol, body.serial, body.tombol)
    except ValueError as e:
        _cmdlog.catat("key", body.serial, str(body.tombol),
                      ok=False, ms=int((_waktu.time() - mulai) * 1000),
                      error=str(e))
        _err_input(e)
    ms = int((_waktu.time() - mulai) * 1000)
    _cmdlog.catat("key", body.serial, str(body.tombol),
                  ok=True, ms=ms)
    return {**hasil, "ms": ms}


@router.get("/devices/input-diagnose", response_model=dict)
async def diagnosa_input_endpoint(serial: str = Query(..., min_length=1)):
    """Cek izin INJECT tanpa ubah layar (probe WAKEUP aman)."""
    from backend.orchestrator import screen as layar
    try:
        return layar.diagnosa_input(serial)
    except Exception as e:
        try:
            panduan = list(layar.PANDUAN_MIUI)
        except Exception:
            panduan = []
        return {"serial": serial, "bisa_input": False, "kode": "lain",
                "alasan": str(e)[:300], "solusi": panduan}


@router.get("/devices/stream-info", response_model=dict)
async def info_stream(serial: str = Query(..., min_length=1)):
    """Ukur latensi screenshot sekali (bukti fps jujur MJPEG WiFi)."""
    import time as _t2
    from backend.orchestrator import screen as layar
    mulai = _t2.time()
    try:
        data = await _jalan_blocking(layar.ambil_frame, serial, 240, 30)
        ms = int((_t2.time() - mulai) * 1000)
        fps = round(1000.0 / max(1, ms), 2)
        return {"serial": serial, "ok": True, "ms": ms, "perkiraan_fps": fps,
                "ukuran_bytes": len(data or b""),
                "catatan": "MJPEG WiFi ~2-4 dtk/frame. 30fps butuh scrcpy USB."}
    except Exception as e:
        ms = int((_t2.time() - mulai) * 1000)
        return {"serial": serial, "ok": False, "ms": ms,
                "perkiraan_fps": 0.0, "alasan": str(e)[:300]}


@router.get("/devices/log", response_model=dict)
async def log_perintah(batas: int = Query(60, ge=1, le=200)):
    """Log perintah terakhir (tap/swipe/type/key/open) untuk diagnosa GUI.

    Poll dari GUI tiap 2 detik. Tak pernah 500 — kosong bila belum ada aksi.
    """
    try:
        data = _cmdlog.ambil(batas)
    except Exception:
        data = []
    return {"log": data, "total": len(data)}


@router.post("/devices/log/clear", response_model=dict)
async def log_bersihkan():
    """Kosongkan log perintah (tombol Bersihkan di GUI)."""
    return _cmdlog.bersihkan()


@router.get("/devices/log/text", response_class=PlainTextResponse)
async def log_perintah_teks(batas: int = Query(60, ge=1, le=200)):
    """Log sebagai teks siap-salin (1 baris per perintah).

    Dipakai tombol 'Salin Log' di GUI agar user bisa tempel
    ke chat/laporan tanpa screenshot.
    """
    try:
        return _cmdlog.sebagai_teks(batas)
    except Exception:
        return ""


@router.get("/sessions/active", response_model=dict)
async def sesi_aktif():
    """Daftar sesi running + device busy (untuk badge & tombol Bebaskan)."""
    from backend.db.database import db
    await db.connect()
    data = await db.fetch_all(
        "SELECT s.*, da.adb_id AS adb_a, db2.adb_id AS adb_b "
        "FROM sessions s "
        "LEFT JOIN devices da ON da.id=s.device_a_id "
        "LEFT JOIN devices db2 ON db2.id=s.device_b_id "
        "WHERE s.status='running' ORDER BY s.id DESC")
    rows = [dict(r) for r in (data or [])]
    # Info busy-yatim: busy tanpa sesi running (badge macet).
    yatim = []
    try:
        semua_d = await DeviceRepository().get_all()
        for dd in (semua_d or []):
            if str(dd.get("status")) == "busy":
                ak = await SessionRepository().get_active_untuk_device(int(dd["id"]))
                if not ak:
                    yatim.append({"id": dd["id"], "adb_id": dd.get("adb_id")})
    except Exception:
        pass
    return {"running": rows, "total": len(rows), "busy_yatim": yatim}


@router.post("/sessions/bebaskan", response_model=dict)
async def bebaskan_semua():
    """Selesaikan semua sesi running + kembalikan device ke idle/offline.

    Tombol 'Bebaskan' di GUI: aman dipakai saat sesi macet / HP busy nyangkut.
    Device yang masih hidup -> idle, yang hilang dari ADB -> offline.
    """
    from backend.db.database import db
    await db.connect()
    rows = await db.fetch_all("SELECT id FROM sessions WHERE status='running' ORDER BY id")
    selesai, gagal = [], []
    for r in (rows or []):
        sid = int(dict(r)["id"])
        try:
            out = await akhiri_sesi(sid)
            selesai.append({"id": sid, "status": out.get("status")})
        except Exception as e:
            gagal.append({"id": sid, "alasan": str(e)})
    # Bersihkan busy nyangkut yang tak punya sesi aktif + refresh health.
    try:
        semua = await DeviceRepository().get_all()
        for d in (semua or []):
            if str(d.get("status")) == "busy":
                aktif = await SessionRepository().get_active_untuk_device(int(d["id"]))
                if not aktif:
                    await DeviceRepository().set_status(int(d["id"]), "idle")
        await health_check_semua()
    except Exception:
        pass
    return {"selesai": selesai, "gagal": gagal, "total_running": len(rows or [])}


@router.get("/devices/view", response_class=HTMLResponse)
async def view_devices(request: Request):
    devices = await DeviceRepository().get_all()
    live_list = sorted(set(daftar_perangkat_adb()))
    terdaftar = {str(d.get("adb_id")) for d in (devices or [])}
    belum = [s for s in live_list if s not in terdaftar]
    return templates.TemplateResponse(
        "devices/list.html",
        {"request": request, "devices": devices, "live": live_list,
         "belum": belum, "allowed_ram": [2, 3, 4, 6]},
    )


@router.get("/devices/{device_id}", response_model=dict)
async def get_device(device_id: int):
    d = await DeviceRepository().get_by_id(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    aktif = await SessionRepository().get_active_untuk_device(device_id)
    return {**d, "sesi_aktif": aktif}


@router.post("/devices/{device_id}/heartbeat", response_model=dict)
async def heartbeat(device_id: int):
    try:
        return await heartbeat_device(device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/devices/{device_id}/health", response_model=dict)
async def health_satu(device_id: int):
    try:
        return await health_check_device(device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/devices/health-check", response_model=dict)
async def health_semua():
    hasil = await health_check_semua()
    ringkas = {"total": len(hasil),
               "idle": sum(1 for d in hasil if d["status"] == "idle"),
               "busy": sum(1 for d in hasil if d["status"] == "busy"),
               "offline": sum(1 for d in hasil if d["status"] == "offline")}
    return {"ringkasan": ringkas, "devices": hasil}


@router.post("/sessions", response_model=dict)
async def buat_sesi(body: SessionCreateModel):
    try:
        return await buat_sesi_pair(
            body.client_id, body.device_a_id, body.device_b_id, body.pair_label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}", response_model=dict)
async def get_sesi(session_id: int):
    s = await SessionRepository().get_by_id(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    assignments = await SessionRepository().get_assignments(session_id)
    return {**s, "assignments": assignments}


@router.post("/sessions/{session_id}/assign", response_model=dict)
async def assign_skenario(session_id: int, body: AssignModel):
    try:
        return await tugaskan_skenario(session_id, body.device_id, body.scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/finish", response_model=dict)
async def selesaikan_sesi(session_id: int):
    try:
        return await akhiri_sesi(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/cancel", response_model=dict)
async def batalkan_sesi(session_id: int):
    try:
        return await akhiri_sesi(session_id, batal=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clients/{client_id}/sessions/view", response_class=HTMLResponse)
async def view_sesi_client(request: Request, client_id: int):
    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    sesi = await daftar_sesi_client(client_id)
    devices = await DeviceRepository().get_all()
    skenarios = await ScenarioRepository().get_by_client(client_id)
    terbaru = {}
    for s in skenarios:
        if s["nama_fungsi"] not in terbaru:
            terbaru[s["nama_fungsi"]] = s
    return templates.TemplateResponse(
        "sessions/list.html",
        {"request": request, "client": client, "sesi": sesi,
         "devices": devices, "skenarios": list(terbaru.values())},
    )


@router.get("/sessions/{session_id}/view", response_class=HTMLResponse)
async def view_sesi_detail(request: Request, session_id: int):
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
    dev_repo = DeviceRepository()
    dev_a = await dev_repo.get_by_id(sesi["device_a_id"])
    dev_b = await dev_repo.get_by_id(sesi["device_b_id"])
    return templates.TemplateResponse(
        "sessions/detail.html",
        {"request": request, "sesi": sesi, "client": client,
         "assignments": detail_assign, "dev_a": dev_a, "dev_b": dev_b},
    )

