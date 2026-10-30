"""
threshold.py - Threshold dinamis per klien (Phase 5, design.md S4.3.1).
Threshold disimpan di tabel clients, bukan konstanta global.
"""
from typing import Dict, List, Optional

DEFAULT_THRESHOLD_SIMILARITY = 0.85
DEFAULT_THRESHOLD_POSISI = 0.90
DEFAULT_THRESHOLD_TINGGI_FALLBACK = 0.80

BATAS_BAWAH_SIMILARITY = 0.50
BATAS_BAWAH_POSISI = 0.50
BATAS_BAWAH_TINGGI = 0.50
BATAS_ATAS = 0.99


def validasi_threshold(sim: float, pos: float, tinggi: float) -> List[str]:
    """Validasi fail-closed: kembalikan daftar error (kosong = valid)."""
    errors = []
    for nama, nilai, bawah in (
        ("threshold_similarity", sim, BATAS_BAWAH_SIMILARITY),
        ("threshold_posisi", pos, BATAS_BAWAH_POSISI),
        ("threshold_tinggi_fallback", tinggi, BATAS_BAWAH_TINGGI),
    ):
        try:
            v = float(nilai)
        except (TypeError, ValueError):
            errors.append(f"{nama} harus angka.")
            continue
        if not (bawah <= v <= BATAS_ATAS):
            errors.append(f"{nama} harus {bawah}..{BATAS_ATAS} (dapat {v}).")
    return errors


def ambil_threshold(client: Optional[Dict]) -> Dict[str, float]:
    """Ambil threshold milik klien dengan fallback ke default."""
    if not client:
        return {"similarity": DEFAULT_THRESHOLD_SIMILARITY,
                "posisi": DEFAULT_THRESHOLD_POSISI,
                "tinggi_fallback": DEFAULT_THRESHOLD_TINGGI_FALLBACK}
    def _aman(kunci: str, default: float) -> float:
        try:
            v = float(client.get(kunci, default))
        except (TypeError, ValueError):
            return default
        return v if 0.0 < v <= 1.0 else default
    return {"similarity": _aman("threshold_similarity", DEFAULT_THRESHOLD_SIMILARITY),
            "posisi": _aman("threshold_posisi", DEFAULT_THRESHOLD_POSISI),
            "tinggi_fallback": _aman("threshold_tinggi_fallback", DEFAULT_THRESHOLD_TINGGI_FALLBACK)}


def hitung_baseline_multi_pass(daftar_pass: List[List[Dict]]) -> Dict[str, float]:
    """Hitung baseline variasi alami dari multi-pass scan (S4.3.1 + S4.1 langkah 7).

    Args:
        daftar_pass: list per pass, tiap pass = list elemen fresh
            (dict dengan role_label/text/bbox). Pass 0 dianggap acuan.

    Returns:
        {"rerata_similaritas": 0..1, "rerata_posisi": 0..1, "jumlah_elemen": int}
    """
    from backend.recalibration.matcher import skor_teks as _st, skor_posisi as _sp
    if not daftar_pass or not daftar_pass[0]:
        return {"rerata_similaritas": 1.0, "rerata_posisi": 1.0, "jumlah_elemen": 0}
    acuan = daftar_pass[0]
    peta_acuan = {(e.get("role_label") or ""): e for e in acuan}
    kumpul_sim, kumpul_pos = [], []
    for hasil_pass in daftar_pass[1:]:
        peta = {(e.get("role_label") or ""): e for e in hasil_pass}
        for role_label, elem0 in peta_acuan.items():
            elem1 = peta.get(role_label)
            if not elem1:
                continue
            t0 = elem0.get("text_snapshot", elem0.get("text", ""))
            t1 = elem1.get("text_snapshot", elem1.get("text", ""))
            b0 = elem0.get("bbox_snapshot", elem0.get("bbox", {}))
            b1 = elem1.get("bbox_snapshot", elem1.get("bbox", {}))
            kumpul_sim.append(_st(t0, t1))
            kumpul_pos.append(_sp(b0, b1))
    if not kumpul_sim:
        return {"rerata_similaritas": 1.0, "rerata_posisi": 1.0,
                "jumlah_elemen": len(acuan)}
    return {"rerata_similaritas": round(sum(kumpul_sim) / len(kumpul_sim), 4),
            "rerata_posisi": round(sum(kumpul_pos) / len(kumpul_pos), 4),
            "jumlah_elemen": len(acuan)}


def kalibrasi_threshold_dari_baseline(baseline: Dict[str, float], margin: float = 0.05) -> Dict[str, float]:
    """Threshold awal klien = baseline variasi + margin aman (S4.3.1).

    Baseline tinggi (stabil) -> threshold ketat; baseline rendah -> longgar,
    tapi tidak pernah di bawah batas aman 0.50 / di atas 0.99.
    """
    try:
        margin_f = float(margin)
    except (TypeError, ValueError):
        margin_f = 0.05
    margin_f = min(max(margin_f, 0.0), 0.20)
    sim = float(baseline.get("rerata_similaritas", 1.0))
    pos = float(baseline.get("rerata_posisi", 1.0))
    sim_thr = min(max(sim - margin_f, BATAS_BAWAH_SIMILARITY), BATAS_ATAS)
    pos_thr = min(max(pos - margin_f, BATAS_BAWAH_POSISI), BATAS_ATAS)
    # Fallback tinggi: sedikit di bawah similarity agar auto-update tidak terlalu mudah.
    tinggi = min(max(sim_thr - 0.05, BATAS_BAWAH_TINGGI), BATAS_ATAS)
    return {"threshold_similarity": round(sim_thr, 3),
            "threshold_posisi": round(pos_thr, 3),
            "threshold_tinggi_fallback": round(tinggi, 3)}

