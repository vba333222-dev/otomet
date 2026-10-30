"""
matcher.py - Matching 3-sinyal untuk recalibration (Phase 5).
Mengikuti design.md S4.3: selector, teks (rapidfuzz), posisi (bbox).
Fail-safe: ragu/ambigu/ganda = BLOCKED, bukan dipaksa cocok.
"""
from typing import Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    HAS_RAPIDFUZZ = False
    class _FuzzFallback:
        @staticmethod
        def ratio(a: str, b: str) -> float:
            return 100.0 if (a or "") == (b or "") else 0.0
    fuzz = _FuzzFallback()  # type: ignore

VIEWPORT_WIDTH = 720
VIEWPORT_HEIGHT = 1650
AMBIGUITY_EPSILON = 0.05


def _viewport_diagonal() -> float:
    return (VIEWPORT_WIDTH ** 2 + VIEWPORT_HEIGHT ** 2) ** 0.5


def skor_teks(teks_lama: Optional[str], teks_baru: Optional[str]) -> float:
    """Kemiripan teks 0.0-1.0 via rapidfuzz.ratio."""
    lama = (teks_lama or "").strip()
    baru = (teks_baru or "").strip()
    if not lama and not baru:
        return 1.0
    if not lama or not baru:
        return 0.0
    return round(float(fuzz.ratio(lama, baru)) / 100.0, 4)


def _titik_tengah(bbox: Dict) -> Tuple[float, float]:
    x = float(bbox.get("x", bbox.get("left", 0)) or 0)
    y = float(bbox.get("y", bbox.get("top", 0)) or 0)
    w = float(bbox.get("width", 0) or 0)
    h = float(bbox.get("height", 0) or 0)
    return (x + w / 2.0, y + h / 2.0)


def skor_posisi(bbox_lama: Optional[Dict], bbox_baru: Optional[Dict]) -> float:
    """Skor posisi 1 - jarak_ternormalisasi (diagonal viewport)."""
    if not bbox_lama or not bbox_baru:
        return 0.0
    try:
        x1, y1 = _titik_tengah(bbox_lama)
        x2, y2 = _titik_tengah(bbox_baru)
    except (TypeError, ValueError):
        return 0.0
    diag = _viewport_diagonal()
    if diag <= 0:
        return 0.0
    jarak = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
    norm = min(max(jarak / diag, 0.0), 1.0)
    return round(1.0 - norm, 4)


def _kandidat_selector_tersimpan(elem: Dict) -> List[str]:
    """Uraikan kandidat selector tersimpan (primary + fallbacks)."""
    import json as _json
    sel = elem.get("selectors") or elem.get("selectors_json") or {}
    if isinstance(sel, str):
        try:
            sel = _json.loads(sel)
        except Exception:
            return []
    if not isinstance(sel, dict):
        return []
    out: List[str] = []
    if sel.get("primary"):
        out.append(str(sel.get("primary")))
    fb = sel.get("fallbacks") or []
    if isinstance(fb, list):
        out.extend(str(s) for s in fb if s)
    unik, lihat = [], set()
    for k in out:
        if k not in lihat:
            lihat.add(k)
            unik.append(k)
    return unik


def _ambil_role(elem: Dict) -> str:
    role = (elem.get("role") or "").strip()
    if role:
        return role
    label = (elem.get("role_label") or "").strip()
    if "_" in label:
        return label.split("_", 1)[0]
    return label or "unknown"


def _ambil_teks(elem: Dict) -> str:
    for kunci in ("text", "text_snapshot", "teks"):
        val = elem.get(kunci)
        if isinstance(val, str) and val.strip():
            return val
    for kunci in ("text", "text_snapshot", "teks"):
        val = elem.get(kunci)
        if isinstance(val, str):
            return val
    return ""


def _ambil_bbox(elem: Dict) -> Dict:
    for kunci in ("bbox", "bbox_snapshot"):
        val = elem.get(kunci)
        if isinstance(val, dict) and val:
            return val
    return {}


def cari_by_selector(elem_lama: Dict, daftar_fresh: List[Dict]) -> Tuple[Optional[Dict], str]:
    """Cari fresh via kandidat selector. Ganda = ambigu (fail-safe)."""
    kandidat = set(_kandidat_selector_tersimpan(elem_lama))
    if not kandidat:
        return None, "tidak_ditemukan"
    cocok = [f for f in daftar_fresh if kandidat & set(_kandidat_selector_tersimpan(f))]
    if len(cocok) == 1:
        return cocok[0], "ditemukan_unik"
    if len(cocok) > 1:
        return None, "ambigu_ganda"
    return None, "tidak_ditemukan"


def nilai_kecocokan(elem_lama: Dict, elem_fresh: Dict, thr_sim: float, thr_pos: float) -> Dict:
    """Nilai pasangan lama vs fresh dengan 2 ambang per-klien."""
    s_teks = skor_teks(_ambil_teks(elem_lama), _ambil_teks(elem_fresh))
    s_pos = skor_posisi(_ambil_bbox(elem_lama), _ambil_bbox(elem_fresh))
    lolos = s_teks >= thr_sim and s_pos >= thr_pos
    return {"skor_teks": s_teks, "skor_posisi": s_pos,
            "lolos": lolos, "status_awal": "calibrated" if lolos else "mencurigakan"}


def cari_kandidat_fallback(elem_lama: Dict, daftar_fresh: List[Dict], thr_tinggi: float) -> Dict:
    """Fallback generik: role sama, skor = 0.6*teks + 0.4*posisi.

    Ambigu (2 teratas selisih <= EPSILON) = blocked. Di bawah ambang = blocked.
    """
    role_cari = _ambil_role(elem_lama)
    teks_lama = _ambil_teks(elem_lama)
    bbox_lama = _ambil_bbox(elem_lama)
    dinilai = []
    for f in daftar_fresh:
        if _ambil_role(f) != role_cari:
            continue
        st = skor_teks(teks_lama, _ambil_teks(f))
        sp = skor_posisi(bbox_lama, _ambil_bbox(f))
        dinilai.append({"fresh": f, "skor_teks": st, "skor_posisi": sp,
                        "confidence_baru": round(0.6 * st + 0.4 * sp, 4)})
    dinilai.sort(key=lambda d: d["confidence_baru"], reverse=True)
    if not dinilai:
        return {"status": "blocked", "alasan": "fallback: tak ada kandidat se-role",
                "confidence_baru": 0.0, "kandidat": None}
    terbaik = dinilai[0]
    if len(dinilai) > 1:
        selisih = round(terbaik["confidence_baru"] - dinilai[1]["confidence_baru"], 4)
        if selisih <= AMBIGUITY_EPSILON:
            return {"status": "blocked",
                    "alasan": f"fallback ambigu: selisih {selisih}<= {AMBIGUITY_EPSILON}",
                    "confidence_baru": terbaik["confidence_baru"], "kandidat": None,
                    "skor_teks": terbaik["skor_teks"], "skor_posisi": terbaik["skor_posisi"]}
    if terbaik["confidence_baru"] >= thr_tinggi:
        return {"status": "recalibrated",
                "alasan": f"fallback cocok unik ({terbaik['confidence_baru']}>= {thr_tinggi})",
                "confidence_baru": terbaik["confidence_baru"], "kandidat": terbaik["fresh"],
                "skor_teks": terbaik["skor_teks"], "skor_posisi": terbaik["skor_posisi"]}
    return {"status": "blocked",
            "alasan": f"fallback confidence {terbaik['confidence_baru']}< {thr_tinggi}",
            "confidence_baru": terbaik["confidence_baru"], "kandidat": None,
            "skor_teks": terbaik["skor_teks"], "skor_posisi": terbaik["skor_posisi"]}


def _rakit_hasil(elem_lama: Dict, tahap: str, fb: Dict, catatan: str) -> Dict:
    sel_lama = (_kandidat_selector_tersimpan(elem_lama)[:1] or [None])[0]
    kand = fb.get("kandidat")
    sel_baru = (_kandidat_selector_tersimpan(kand)[:1] or [None])[0] if kand else None
    return {"element_id": elem_lama.get("id"), "role_label": elem_lama.get("role_label", "?"),
            "status": fb["status"], "tahap_awal": tahap,
            "skor_teks": fb.get("skor_teks"), "skor_posisi": fb.get("skor_posisi"),
            "confidence_baru": fb.get("confidence_baru"),
            "old_selector": sel_lama, "new_selector": sel_baru,
            "alasan": f"{catatan} -> {fb.get('alasan', '')}", "kandidat_fresh": kand}


def recalibrate_satu_elemen(elem_lama: Dict, daftar_fresh: List[Dict], thr_sim: float, thr_pos: float, thr_tinggi: float) -> Dict:
    """Algoritma S4.3 penuh untuk satu elemen tersimpan."""
    sel_lama = (_kandidat_selector_tersimpan(elem_lama)[:1] or [None])[0]
    cocok, alasan = cari_by_selector(elem_lama, daftar_fresh)
    if alasan == "ambigu_ganda":
        fb = cari_kandidat_fallback(elem_lama, daftar_fresh, thr_tinggi)
        return _rakit_hasil(elem_lama, "mencurigakan", fb, "selector ambigu (>1); fallback")
    if cocok is not None:
        nilai = nilai_kecocokan(elem_lama, cocok, thr_sim, thr_pos)
        if nilai["lolos"]:
            return {"element_id": elem_lama.get("id"), "role_label": elem_lama.get("role_label", "?"),
                    "status": "calibrated", "tahap_awal": "ditemukan_unik",
                    "skor_teks": nilai["skor_teks"], "skor_posisi": nilai["skor_posisi"],
                    "confidence_baru": None, "old_selector": sel_lama,
                    "new_selector": (_kandidat_selector_tersimpan(cocok)[:1] or [None])[0],
                    "alasan": f"selector cocok; teks {nilai['skor_teks']}>= {thr_sim}, posisi {nilai['skor_posisi']}>= {thr_pos}",
                    "kandidat_fresh": cocok}
        fb = cari_kandidat_fallback(elem_lama, daftar_fresh, thr_tinggi)
        return _rakit_hasil(elem_lama, "mencurigakan", fb,
            f"ditemukan tapi skor rendah (teks {nilai['skor_teks']}, posisi {nilai['skor_posisi']}); fallback")
    fb = cari_kandidat_fallback(elem_lama, daftar_fresh, thr_tinggi)
    return _rakit_hasil(elem_lama, "hilang", fb, "selector tak ditemukan; fallback")


def recalibrate_batch(daftar_lama: List[Dict], daftar_fresh: List[Dict], thr_sim: float, thr_pos: float, thr_tinggi: float) -> Dict:
    """Recalibration all-or-nothing satu halaman. boleh_jalan=True bila tanpa blocked."""
    hasil = [recalibrate_satu_elemen(e, daftar_fresh, thr_sim, thr_pos, thr_tinggi) for e in daftar_lama]
    ringkasan = {"total": len(hasil),
                 "calibrated": sum(1 for h in hasil if h["status"] == "calibrated"),
                 "recalibrated": sum(1 for h in hasil if h["status"] == "recalibrated"),
                 "blocked": sum(1 for h in hasil if h["status"] == "blocked")}
    return {"hasil_per_elemen": hasil, "ringkasan": ringkasan, "boleh_jalan": ringkasan["blocked"] == 0}



