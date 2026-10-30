"""screen.py - Screenshot + info realtime HP via ADB (adbutils).

Dipakai GUI "HP Terhubung" agar semua HP yang terdeteksi
`adb devices` langsung tampil gambar layarnya (live preview).

Fail-safe: gagal ambil gambar = raise ValueError informatif,
bukan crash. Cache singkat 2 detik agar polling GUI tiap
3-4 detik tidak menghantam ADB berulang untuk serial sama.
"""
import io
import time
from typing import Dict, List, Optional, Tuple

_CACHE_IMG: Dict[str, Tuple[float, bytes]] = {}
_CACHE_INFO: Dict[str, Tuple[float, dict]] = {}
# Frame bagus terakhir per serial (tanpa kunci lebar/kualitas) — dipakai
# stream MJPEG agar tak pernah hitam/blank saat screenshot gagal sesaat.
_CACHE_LAST_GOOD: Dict[str, bytes] = {}
TTL_IMG = 2.0
TTL_INFO = 10.0


def placeholder_jpeg(lebar: int = 320, tinggi: int = 480,
                     pesan: str = "menyambungkan...") -> bytes:
    """JPEG placeholder abu-abu agar <img>/MJPEG tak pernah hitam polos.

    Selalu berhasil (tak pernah raise) — fallback terakhir stream.
    """
    try:
        from PIL import Image, ImageDraw
        lebar = max(160, min(540, int(lebar or 320)))
        tinggi = max(240, min(960, int(tinggi or 480)))
        img = Image.new("RGB", (lebar, tinggi), (31, 41, 55))
        dr = ImageDraw.Draw(img)
        teks = (pesan or "menyambungkan...")[:48]
        # Tengah kasar tanpa font eksternal.
        dr.text((12, tinggi // 2 - 20), "OTOMET", fill=(156, 163, 175))
        dr.text((12, tinggi // 2), teks, fill=(229, 231, 235))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=55)
        data = buf.getvalue()
        if data:
            return data
    except Exception:
        pass
    # JPEG 1px super-minimal bila PIL gagal (tetap valid, bukan hitam stream).
    return (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01"
            b"\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07"
            b"\x09\x09\x08\x0a\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d"
            b"\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xd9")


def _client():
    try:
        from adbutils import AdbClient
    except Exception as e:
        raise ValueError(f"adbutils tak tersedia: {e}")
    return AdbClient(host="127.0.0.1", port=5037)


def ambil_screenshot(serial: str, lebar: int = 360, kualitas: int = 55) -> bytes:
    """Ambil screenshot HP -> JPEG bytes (thumbnail hemat bandwidth).

    lebar: 240/360/480. kualitas: 40-70.
    Cache 2 detik per serial agar polling GUI ringan.
    """
    serial = (serial or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    lebar = max(160, min(720, int(lebar or 360)))
    kualitas = max(30, min(80, int(kualitas or 55)))
    kunci = f"{serial}|{lebar}|{kualitas}"
    kini = time.time()
    hit = _CACHE_IMG.get(kunci)
    if hit and (kini - hit[0]) < TTL_IMG:
        return hit[1]
    c = _client()
    try:
        d = c.device(serial=serial)
    except Exception as e:
        raise ValueError(f"HP {serial} tak terjangkau ADB: {e}")
    try:
        img = d.screenshot()
    except Exception as e:
        raise ValueError(f"Gagal screenshot {serial}: {e}")
    try:
        img.thumbnail((lebar, lebar * 3))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=kualitas)
        data = buf.getvalue()
    except Exception as e:
        raise ValueError(f"Gagal encode JPEG {serial}: {e}")
    if not data:
        raise ValueError(f"Screenshot kosong {serial}.")
    _CACHE_IMG[kunci] = (kini, data)
    # Simpan frame bagus terakhir (kunci hanya serial) agar stream
    # tak pernah hitam saat ambil berikutnya gagal sesaat.
    try:
        _CACHE_LAST_GOOD[serial] = data
    except Exception:
        pass
    return data


def frame_terbaik(serial: str, lebar: int = 320, kualitas: int = 40,
                  pesan: str = "menyambungkan...") -> Tuple[bytes, str]:
    """Frame anti-hitam untuk stream: bagus -> terakhir -> placeholder.

    Return (jpeg_bytes, sumber) dengan sumber salah satu dari
    'live' / 'cache' / 'placeholder'. Tak pernah raise.
    """
    serial = (serial or "").strip()
    lebar = max(160, min(540, int(lebar or 320)))
    kualitas = max(30, min(70, int(kualitas or 40)))
    if not serial:
        return placeholder_jpeg(lebar, lebar * 2, "serial kosong"), "placeholder"
    try:
        return ambil_screenshot(serial, lebar, kualitas), "live"
    except Exception:
        pass
    try:
        lama = _CACHE_LAST_GOOD.get(serial)
        if lama:
            return lama, "cache"
    except Exception:
        pass
    return placeholder_jpeg(lebar, lebar * 2, pesan), "placeholder"


def info_hp(serial: str) -> dict:
    """Info ringan HP: model + layar nyala + baterai. Cache 10 detik."""
    serial = (serial or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    kini = time.time()
    hit = _CACHE_INFO.get(serial)
    if hit and (kini - hit[0]) < TTL_INFO:
        return {**hit[1]}
    c = _client()
    try:
        d = c.device(serial=serial)
    except Exception as e:
        raise ValueError(f"HP {serial} tak terjangkau ADB: {e}")
    model: Optional[str] = None
    layar: Optional[bool] = None
    baterai: Optional[int] = None
    try:
        model = str(d.shell("getprop ro.product.model") or "").strip() or None
    except Exception:
        pass
    try:
        layar = bool(d.is_screen_on()) if hasattr(d, "is_screen_on") else None
    except Exception:
        pass
    try:
        out = str(d.shell("dumpsys battery | grep level") or "")
        for tok in out.replace(":", " ").split():
            if tok.strip().isdigit():
                baterai = int(tok.strip())
                break
    except Exception:
        pass
    hasil = {"serial": serial, "model": model or "-", "layar_nyala": layar, "baterai": baterai}
    _CACHE_INFO[serial] = (kini, hasil)
    return {**hasil}


def aksi_hp(serial: str, aksi: str) -> dict:
    """Aksi simpel 1-klik: wake / home / back. Untuk fungsi lengkap tanpa ribet."""
    serial = (serial or "").strip()
    aksi = (aksi or "").strip().lower()
    if aksi not in ("wake", "home", "back"):
        raise ValueError("aksi harus: wake/home/back.")
    c = _client()
    try:
        d = c.device(serial=serial)
    except Exception as e:
        raise ValueError(f"HP {serial} tak terjangkau ADB: {e}")
    try:
        if aksi == "wake":
            try:
                _shell_cek(serial, ["input", "keyevent", "224"], "Tombol wake")
            except Exception:
                pass
            try:
                _shell_cek(serial, ["input", "keyevent", "82"], "Tombol menu")
            except ValueError as ve:
                # Wake/menu diblokir izin inject -> teruskan agar log merah jujur.
                raise ve
        elif aksi == "home":
            _shell_cek(serial, ["input", "keyevent", "3"], "Tombol home")
        else:
            _shell_cek(serial, ["input", "keyevent", "4"], "Tombol back")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Gagal {aksi} di {serial}: {e}")
    # Invalidate info cache agar badge layar refresh.
    _CACHE_INFO.pop(serial, None)
    return {"ok": True, "serial": serial, "aksi": aksi}


def buka_url(serial: str, url: str) -> dict:
    """Buka URL di Chrome HP via ADB (tanpa Appium, langsung terlihat di layar).

    Dipakai untuk "fungsi lengkap": uji cepat 1-klik terlihat live
    di screenshot. Untuk uji formal tercatat, pakai /demo/real-2device.
    """
    from urllib.parse import urlparse

    serial = (serial or "").strip()
    url = (url or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    if not url:
        raise ValueError("url kosong.")
    p = urlparse(url if "://" in url else "http://" + url)
    if not p.netloc:
        raise ValueError(f"URL tidak valid: {url}")
    url_fix = url if "://" in url else "http://" + url
    c = _client()
    try:
        d = c.device(serial=serial)
    except Exception as e:
        raise ValueError(f"HP {serial} tak terjangkau ADB: {e}")
    try:
        # Bangunkan (best-effort, boleh gagal) + buka Chrome ke URL.
        # `am start` tak butuh INJECT_EVENTS -> tetap lolos walau tap diblokir.
        aman = url_fix.replace('"', "")
        try:
            _shell_cek(serial, ["input", "keyevent", "224"], "Tombol wake")
        except Exception:
            pass
        _shell_cek(serial,
                   ["am", "start", "-a", "android.intent.action.VIEW",
                    "-d", aman, "com.android.chrome"],
                   f"Buka {aman}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Gagal buka {url_fix} di {serial}: {e}")
    _CACHE_INFO.pop(serial, None)
    # Invalidate screenshot cache agar gambar baru langsung diambil.
    for k in [k for k in _CACHE_IMG if k.startswith(serial + "|")]:
        _CACHE_IMG.pop(k, None)
    return {"ok": True, "serial": serial, "url": url_fix}


_CACHE_UKURAN: Dict[str, Tuple[float, Tuple[int, int]]] = {}
TTL_UKURAN = 60.0


def _perangkat(serial: str):
    serial = (serial or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    c = _client()
    try:
        return c.device(serial=serial)
    except Exception as e:
        raise ValueError(f"HP {serial} tak terjangkau ADB: {e}")


def _pesan_inject(aksi: str, serial: str, keluaran: str) -> str:
    """Pesan ramah saat MIUI/HyperOS menolak `input tap/swipe/keyevent`.

    Penyebab umum: 'USB debugging (Security settings)' belum ON di
    Opsi Pengembang, sehingga shell ADB tak punya INJECT_EVENTS.
    `am start` (open-url) tetap lolos karena tak butuh izin itu —
    persis gejala user: hanya buka-URL yang jalan.
    """
    baris1 = ""
    try:
        for b in (keluaran or "").splitlines():
            b = b.strip()
            if b:
                baris1 = b[:160]
                break
    except Exception:
        pass
    return (
        f"{aksi} ditolak HP {serial} (INJECT_EVENTS). "
        f"Di HP: Setelan > Opsi Pengembang > aktifkan "
        f"'USB debugging (Security settings)' (+ 'USB debugging' tetap ON), "
        f"lalu di PC: adb disconnect + adb connect ulang, coba lagi. "
        f"[{baris1}]"
    )


PANDUAN_MIUI = [
    "Di HP: Setelan > Tentang Ponsel > ketuk Versi MIUI 7x.",
    "Opsi Pengembang > USB debugging ON + USB debugging Security ON.",
    "MIUI butuh login Akun Xiaomi + SIM; bila abu-abu login dulu.",
    "PC: adb disconnect + adb connect ulang lalu Cek Izin Input.",
]


def kode_error_input(pesan_error: str) -> str:
    err = (pesan_error or "").lower()
    if "inject" in err or "inject_events" in err or "securityexception" in err:
        return "butuh_izin_miui"
    if ("tak terjangkau" in err or "not found" in err or "unauthorized" in err
            or "offline" in err or "no device" in err or "tak ada respons" in err):
        return "adb_putus"
    return "lain"


def diagnosa_input(serial: str) -> dict:
    serial = (serial or "").strip()
    if not serial:
        return {"serial": "", "bisa_input": False, "kode": "adb_putus",
                "alasan": "serial kosong.", "solusi": list(PANDUAN_MIUI)}
    try:
        c = _client()
        try:
            d = c.device(serial=serial)
            d.shell("echo ok")
        except Exception as e:
            err = str(e)
            return {"serial": serial, "bisa_input": False,
                    "kode": kode_error_input(err),
                    "alasan": "HP tak terjangkau ADB: " + err[:300],
                    "solusi": list(PANDUAN_MIUI)}
    except Exception as e:
        return {"serial": serial, "bisa_input": False, "kode": "adb_putus",
                "alasan": "adbutils/daemon mati: " + str(e)[:200],
                "solusi": list(PANDUAN_MIUI)}
    miui = None
    model = None
    android = None
    try:
        d = c.device(serial=serial)
        try:
            miui = (d.shell("getprop ro.miui.ui.version.name") or "").strip() or None
        except Exception:
            pass
        try:
            model = (d.shell("getprop ro.product.model") or "").strip() or None
        except Exception:
            pass
        try:
            android = (d.shell("getprop ro.build.version.release") or "").strip() or None
        except Exception:
            pass
    except Exception:
        pass
    try:
        d = c.device(serial=serial)
        out = d.shell("input keyevent 224")
        err = str(out or "")
        if "inject" in err.lower() or "securityexception" in err.lower():
            return {"serial": serial, "bisa_input": False,
                    "kode": "butuh_izin_miui", "miui": miui,
                    "model": model, "android": android,
                    "alasan": "HP menolak injeksi (INJECT_EVENTS). Aktifkan Security settings lalu reconnect.",
                    "solusi": list(PANDUAN_MIUI)}
        return {"serial": serial, "bisa_input": True, "kode": "ok",
                "miui": miui, "model": model, "android": android,
                "alasan": "Probe WAKEUP lolos - tap/swipe seharusnya bisa.",
                "solusi": []}
    except Exception as e:
        kode = kode_error_input(str(e))
        if kode == "butuh_izin_miui":
            return {"serial": serial, "bisa_input": False, "kode": kode,
                    "miui": miui, "model": model, "android": android,
                    "alasan": "Menolak injeksi: " + str(e)[:300],
                    "solusi": list(PANDUAN_MIUI)}
        return {"serial": serial, "bisa_input": False, "kode": kode,
                "miui": miui, "model": model, "android": android,
                "alasan": "Belum pasti: " + str(e)[:300],
                "solusi": list(PANDUAN_MIUI)}

def _shell_cek(serial: str, args, label: str) -> str:
    """Jalankan shell via shell2 + cek returncode.

    `d.shell()` tak pernah raise saat `input ...` gagal (rc=255
    dibungkus jadi string), sehingga tap gagal tercatat OK palsu.
    `shell2` mengembalikan returncode -> GAGAL terdeteksi jujur.
    """
    serial = (serial or "").strip()
    d = _perangkat(serial)
    try:
        r = d.shell2(list(args))
    except Exception as e:
        raise ValueError(f"{label} gagal terkirim ke {serial}: {e}")
    try:
        rc = int(getattr(r, "returncode", 0) or 0)
    except Exception:
        rc = 0
    keluar = ""
    try:
        keluar = str(getattr(r, "output", "") or "")
    except Exception:
        keluar = ""
    if rc != 0 or "SecurityException" in keluar or "INJECT_EVENTS" in keluar:
        # Khusus izin inject -> pesan aksi + cara betulkan.
        if "SecurityException" in keluar or "INJECT_EVENTS" in keluar or rc == 255:
            raise ValueError(_pesan_inject(label, serial, keluar))
        pot = (keluar.strip().splitlines() or [""])[0][:200]
        raise ValueError(f"{label} gagal di {serial} (rc={rc}): {pot}")
    return keluar
    """Objek device adbutils utk serial. Raise ValueError bila tak terjangkau."""
    serial = (serial or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    c = _client()
    try:
        return c.device(serial=serial)
    except Exception as e:
        raise ValueError(f"HP {serial} tak terjangkau ADB: {e}")


def ukuran_layar(serial: str) -> Tuple[int, int]:
    """Ukuran layar asli HP (lebar, tinggi) piksel. Cache 60 dtk."""
    serial = (serial or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    kini = time.time()
    hit = _CACHE_UKURAN.get(serial)
    if hit and (kini - hit[0]) < TTL_UKURAN:
        return hit[1]
    d = _perangkat(serial)
    w, h = 720, 1650
    try:
        uk = d.window_size()
        if uk and len(uk) >= 2:
            w, h = int(uk[0]), int(uk[1])
    except Exception:
        try:
            import re as _re
            out = str(d.shell("wm size") or "")
            m = _re.search(r"(\d+)\s*x\s*(\d+)", out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
        except Exception:
            pass
    if w <= 0 or h <= 0:
        w, h = 720, 1650
    _CACHE_UKURAN[serial] = (kini, (w, h))
    return (w, h)


def ambil_frame(serial: str, lebar: int = 320, kualitas: int = 40) -> bytes:
    """1 frame JPEG segar TANPA cache (untuk aliran MJPEG)."""
    serial = (serial or "").strip()
    if not serial:
        raise ValueError("serial kosong.")
    lebar = max(160, min(540, int(lebar or 320)))
    kualitas = max(30, min(70, int(kualitas or 40)))
    d = _perangkat(serial)
    try:
        img = d.screenshot()
    except Exception as e:
        raise ValueError(f"Gagal screenshot {serial}: {e}")
    try:
        img.thumbnail((lebar, lebar * 3))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=kualitas)
        data = buf.getvalue()
    except Exception as e:
        raise ValueError(f"Gagal encode JPEG {serial}: {e}")
    if not data:
        raise ValueError(f"Screenshot kosong {serial}.")
    try:
        _CACHE_LAST_GOOD[serial] = data
    except Exception:
        pass
    return data
def _jepit(v, bawah, atas):
    try:
        v = int(v)
    except Exception:
        v = bawah
    return max(bawah, min(atas, v))


def ketuk(serial: str, x: int, y: int) -> dict:
    """Tap di koordinat piksel HP asli."""
    w, h = ukuran_layar(serial)
    x = _jepit(x, 0, w - 1)
    y = _jepit(y, 0, h - 1)
    _shell_cek(serial, ["input", "tap", str(x), str(y)], f"Tap ({x},{y})")
    for k in [k for k in _CACHE_IMG if k.startswith(serial + "|")]:
        _CACHE_IMG.pop(k, None)
    return {"ok": True, "serial": serial, "x": x, "y": y}


def geser(serial: str, sx: int, sy: int, ex: int, ey: int, dur_ms: int = 300) -> dict:
    """Swipe dari (sx,sy) ke (ex,ey), durasi ms."""
    w, h = ukuran_layar(serial)
    sx = _jepit(sx, 0, w - 1)
    sy = _jepit(sy, 0, h - 1)
    ex = _jepit(ex, 0, w - 1)
    ey = _jepit(ey, 0, h - 1)
    dur_ms = _jepit(dur_ms, 50, 3000)
    _shell_cek(serial,
              ["input", "swipe", str(sx), str(sy), str(ex), str(ey),
               str(int(dur_ms))],
              f"Swipe ({sx},{sy})->({ex},{ey})")
    for k in [k for k in _CACHE_IMG if k.startswith(serial + "|")]:
        _CACHE_IMG.pop(k, None)
    return {"ok": True, "serial": serial, "sx": sx, "sy": sy,
            "ex": ex, "ey": ey, "dur_ms": dur_ms}

def ketik(serial: str, teks: str) -> dict:
    """Ketik teks via `input text`. Batasi 200 char, sanitasi shell."""
    serial = (serial or "").strip()
    teks = (teks or "")
    if not serial:
        raise ValueError("serial kosong.")
    if not teks.strip():
        raise ValueError("teks kosong.")
    teks = teks[:200]
    aman = teks.replace("\n", " ").replace("\r", " ")
    aman = aman.replace('"', "").replace("'", "").replace("`", "")
    aman = aman.replace("&", "").replace(";", "").replace("|", "")
    aman = aman.replace("$", "").replace(" ", "%s")
    if not aman.replace("%s", "").strip():
        raise ValueError("teks kosong setelah dibersihkan.")
    _shell_cek(serial, ["input", "text", aman], "Ketik teks")
    for k in [k for k in _CACHE_IMG if k.startswith(serial + "|")]:
        _CACHE_IMG.pop(k, None)
    return {"ok": True, "serial": serial, "teks": teks}


TOMBOL = {
    "back": 4, "home": 3, "recent": 187, "power": 26, "wake": 224,
    "menu": 82, "enter": 66, "tab": 61, "esc": 111,
    "vol_up": 24, "vol_down": 25, "mute": 164,
    "dpad_up": 19, "dpad_down": 20, "dpad_left": 21, "dpad_right": 22,
    "dpad_center": 23, "del": 67, "space": 62,
}


def tombol(serial: str, nama: str) -> dict:
    """Tekan tombol by nama allowlist."""
    serial = (serial or "").strip()
    nama = (nama or "").strip().lower()
    if nama not in TOMBOL:
        raise ValueError(f"tombol harus salah satu: {sorted(TOMBOL)}.")
    _shell_cek(serial, ["input", "keyevent", str(TOMBOL[nama])],
               f"Tombol {nama}")
    _CACHE_INFO.pop(serial, None)
    return {"ok": True, "serial": serial, "tombol": nama}