"""
test_matcher.py - Uji wajib Phase 5: kasus "elemen sengaja diubah".
S4.3: sistem harus blocked/berhenti, bukan lanjut asal-asalan.
"""
from backend.recalibration.matcher import (
    skor_teks, skor_posisi, nilai_kecocokan,
    cari_by_selector, recalibrate_satu_elemen, recalibrate_batch,
)

THR_SIM = 0.85
THR_POS = 0.90
THR_TINGGI = 0.80
BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


def _lama(role="button_masuk", teks="Masuk", bbox=None, primary="#masuk"):
    return {"id": 1, "role_label": role, "role": role.split("_")[0],
            "text_snapshot": teks, "bbox_snapshot": bbox or dict(BBOX),
            "selectors": {"primary": primary, "fallbacks": []}}


def _fresh(role="button", label="button_masuk", teks="Masuk", bbox=None, primary="#masuk"):
    return {"role": role, "role_label": label, "text": teks,
            "bbox": bbox or dict(BBOX),
            "selectors": {"primary": primary, "fallbacks": []}}


class TestSkorDasar:
    def test_teks_identik(self):
        assert skor_teks("Masuk", "Masuk") == 1.0

    def test_teks_kosong_keduanya(self):
        assert skor_teks("", "") == 1.0

    def test_teks_satu_kosong(self):
        assert skor_teks("Masuk", "") == 0.0

    def test_teks_beda_rendah(self):
        assert skor_teks("Masuk", "Keluar Sekarang Total") < 0.6

    def test_posisi_sama(self):
        assert skor_posisi(dict(BBOX), dict(BBOX)) == 1.0

    def test_posisi_tanpa_bbox(self):
        assert skor_posisi({}, dict(BBOX)) == 0.0

    def test_posisi_geser_kecil_tinggi(self):
        dekat = {"x": 105, "y": 205, "width": 80, "height": 40}
        assert skor_posisi(dict(BBOX), dekat) >= 0.95

    def test_posisi_jauh_rendah(self):
        jauh = {"x": 600, "y": 1500, "width": 80, "height": 40}
        assert skor_posisi(dict(BBOX), jauh) < THR_POS


class TestSelectorMatch:
    def test_ditemukan_unik_calibrated(self):
        lama = _lama()
        cocok, alasan = cari_by_selector(lama, [_fresh()])
        assert alasan == "ditemukan_unik" and cocok is not None
        nilai = nilai_kecocokan(lama, cocok, THR_SIM, THR_POS)
        assert nilai["lolos"] and nilai["status_awal"] == "calibrated"

    def test_tidak_ditemukan(self):
        _, alasan = cari_by_selector(_lama(primary="#hilang"), [_fresh(primary="#lain")])
        assert alasan == "tidak_ditemukan"

    def test_ambigu_ganda_fail_safe(self):
        lama = _lama(primary="#ganda")
        segar = [_fresh(primary="#ganda", label="button_a"),
                 _fresh(primary="#ganda", label="button_b")]
        _, alasan = cari_by_selector(lama, segar)
        assert alasan == "ambigu_ganda"


class TestElemenSengajaDiubah:
    """Kasus inti S4.3: diubah -> mencurigakan/hilang -> fallback/blocked."""

    def test_match_tidak_berubah(self):
        h = recalibrate_satu_elemen(_lama(), [_fresh()], THR_SIM, THR_POS, THR_TINGGI)
        assert h["status"] == "calibrated" and h["tahap_awal"] == "ditemukan_unik"

    def test_teks_diubah_total_blocked(self):
        lama = _lama(teks="Masuk", primary="#masuk")
        segar = [_fresh(teks="Keluar Sekarang Juga Ya", primary="#masuk"),
                 _fresh(label="button_lain", teks="Bantuan Pusat Info", primary="#bantuan")]
        h = recalibrate_satu_elemen(lama, segar, THR_SIM, THR_POS, THR_TINGGI)
        assert h["tahap_awal"] == "mencurigakan"
        assert h["status"] == "blocked"

    def test_pindah_jauh_fallback_recalibrated(self):
        # Geser dekat + selector hilang: teks sama, posisi dekat -> fallback recalibrated
        lama = _lama(bbox=dict(BBOX), primary="#pindah")
        dekat = {"x": 150, "y": 260, "width": 80, "height": 40}
        segar = [_fresh(bbox=dict(dekat), primary="#pindah-baru")]
        h = recalibrate_satu_elemen(lama, segar, THR_SIM, THR_POS, THR_TINGGI)
        assert h["tahap_awal"] == "hilang"
        assert h["status"] == "recalibrated"

    def test_pindah_sangat_jauh_dipaksa_blocked(self):
        # Fail-safe: pindah sangat jauh (teks sama tapi posisi jauh) -> blocked
        lama = _lama(bbox=dict(BBOX), primary="#pindah")
        jauh = {"x": 500, "y": 1200, "width": 80, "height": 40}
        segar = [_fresh(bbox=dict(jauh), primary="#pindah-baru")]
        h = recalibrate_satu_elemen(lama, segar, THR_SIM, THR_POS, THR_TINGGI)
        assert h["tahap_awal"] == "hilang"
        assert h["status"] == "blocked"

    def test_hilang_total_blocked(self):
        lama = _lama()
        segar = [_fresh(role="link", label="link_bantuan", teks="Bantuan", primary="#bantuan")]
        h = recalibrate_satu_elemen(lama, segar, THR_SIM, THR_POS, THR_TINGGI)
        assert h["tahap_awal"] == "hilang"
        assert h["status"] == "blocked"

    def test_fallback_ambigu_dipaksa_blocked(self):
        lama = _lama(primary="#hilang")
        segar = [_fresh(label="button_masuk", teks="Masuk", primary="#a"),
                 _fresh(label="button_masuk", teks="Masuk", primary="#b")]
        h = recalibrate_satu_elemen(lama, segar, THR_SIM, THR_POS, THR_TINGGI)
        assert h["status"] == "blocked"

    def test_perubahan_kecil_masih_calibrated(self):
        h = recalibrate_satu_elemen(_lama(teks="Masuk"), [_fresh(teks="Masuk!", primary="#masuk")], THR_SIM, THR_POS, THR_TINGGI)
        assert h["status"] == "calibrated"


class TestBatchAllOrNothing:
    def test_boleh_jalan_tanpa_blocked(self):
        hasil = recalibrate_batch([_lama()], [_fresh()], THR_SIM, THR_POS, THR_TINGGI)
        assert hasil["boleh_jalan"] is True
        assert hasil["ringkasan"] == {"total": 1, "calibrated": 1, "recalibrated": 0, "blocked": 0}

    def test_satu_blocked_menahan_semua(self):
        lama2 = _lama(role="button_keluar", teks="Keluar", primary="#keluar")
        lama2["id"] = 2
        hasil = recalibrate_batch([_lama(), lama2], [_fresh()], THR_SIM, THR_POS, THR_TINGGI)
        assert hasil["ringkasan"]["blocked"] == 1
        assert hasil["boleh_jalan"] is False

