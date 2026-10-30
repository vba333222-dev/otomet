"""
test_threshold.py - Uji threshold dinamis per klien (Phase 5, S4.3.1).
"""
from backend.recalibration.threshold import (
    ambil_threshold, validasi_threshold,
    hitung_baseline_multi_pass, kalibrasi_threshold_dari_baseline,
    DEFAULT_THRESHOLD_SIMILARITY, DEFAULT_THRESHOLD_POSISI,
    DEFAULT_THRESHOLD_TINGGI_FALLBACK,
)

BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


class TestAmbilThreshold:
    def test_default_bila_tanpa_client(self):
        t = ambil_threshold(None)
        assert t == {"similarity": DEFAULT_THRESHOLD_SIMILARITY,
                     "posisi": DEFAULT_THRESHOLD_POSISI,
                     "tinggi_fallback": DEFAULT_THRESHOLD_TINGGI_FALLBACK}

    def test_milik_klien(self):
        t = ambil_threshold({"threshold_similarity": 0.9, "threshold_posisi": 0.92,
                             "threshold_tinggi_fallback": 0.82})
        assert t == {"similarity": 0.9, "posisi": 0.92, "tinggi_fallback": 0.82}

    def test_rusak_fallback_default(self):
        t = ambil_threshold({"threshold_similarity": 99, "threshold_posisi": None,
                             "threshold_tinggi_fallback": "rusak"})
        assert t["similarity"] == DEFAULT_THRESHOLD_SIMILARITY


class TestValidasi:
    def test_valid_kosong(self):
        assert validasi_threshold(0.85, 0.9, 0.8) == []

    def test_terlalu_longgar_ditolak(self):
        assert len(validasi_threshold(0.2, 0.9, 0.8)) == 1

    def test_bukan_angka_ditolak(self):
        assert len(validasi_threshold("x", 0.9, 0.8)) == 1


class TestBaseline:
    def _elem(self, teks="Masuk", bbox=None):
        return {"role_label": "button_masuk", "text": teks, "bbox": bbox or dict(BBOX)}

    def test_identik_baseline_sempurna(self):
        e = [self._elem()]
        b = hitung_baseline_multi_pass([e, [self._elem()], [self._elem()]])
        assert b["rerata_similaritas"] == 1.0 and b["rerata_posisi"] == 1.0

    def test_kosong_aman(self):
        b = hitung_baseline_multi_pass([])
        assert b["jumlah_elemen"] == 0

    def test_kalibrasi_margin(self):
        k = kalibrasi_threshold_dari_baseline(
            {"rerata_similaritas": 1.0, "rerata_posisi": 1.0}, margin=0.05)
        assert k == {"threshold_similarity": 0.95, "threshold_posisi": 0.95,
                     "threshold_tinggi_fallback": 0.9}

    def test_kalibrasi_tidak_lewat_batas(self):
        k = kalibrasi_threshold_dari_baseline(
            {"rerata_similaritas": 0.4, "rerata_posisi": 0.4}, margin=0.05)
        assert k["threshold_similarity"] >= 0.5
