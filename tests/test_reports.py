"""
Unit tests untuk Pelaporan Phase 8 (tanpa ADB fisik).
DB isolasi + FakeDriver Phase 7 untuk isi runs, lalu uji
agregasi + tren + PDF/Excel valid.
"""
import pytest
import pytest_asyncio

from backend.db.database import Database

BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


@pytest_asyncio.fixture
async def test_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test_reports.db")
    db_uji = Database(db_path)
    await db_uji.connect()
    await db_uji.initialize_schema()
    from backend.db import database as db_module
    monkeypatch.setattr(db_module, "db", db_uji)
    for mod_nama in ("client_repo", "page_repo", "element_repo",
                     "scenario_repo", "recalibration_repo",
                     "device_repo", "session_repo", "run_repo"):
        mod = __import__(f"backend.db.repositories.{mod_nama}",
                         fromlist=["x"])
        monkeypatch.setattr(mod, "db", db_uji)
    yield db_uji
    try:
        await db_uji.close()
    except Exception:
        pass


async def _setup_sesi_dengan_runs():
    from backend.db.repositories import (
        ClientRepository, PageRepository, ElementRepository,
        ScenarioRepository, TestDataRepository,
    )
    from backend.recalibration.service import jalankan_recalibration
    from backend.orchestrator.device_pool import register_device
    from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
    from backend.orchestrator.runner import jalankan_session, FakeDriver

    cid = await ClientRepository().create(nama="Klien Lapor", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk", "fallbacks": []},
        text_snapshot="Masuk", bbox=dict(BBOX), confidence=0.95, approved=True)
    sid = await ScenarioRepository().create(
        cid, "login_valid",
        [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}}])
    segar = [{"role": "button", "role_label": "button_masuk", "text": "Masuk",
              "bbox": dict(BBOX), "selectors": {"primary": "#masuk", "fallbacks": []}}]
    await jalankan_recalibration(pid, fresh_override=segar)
    a = await register_device("LAP_A")
    b = await register_device("LAP_B")
    await TestDataRepository().tambah(sid, {"nama": "Andi"})
    await TestDataRepository().tambah(sid, {"nama": "Budi"})
    sesi = await buat_sesi_pair(cid, a["id"], b["id"], "pair-lapor")
    await tugaskan_skenario(sesi["id"], a["id"], sid)
    await tugaskan_skenario(sesi["id"], b["id"], sid)

    def _buat(device, caps):
        return FakeDriver(device.get("adb_id", "?"))

    hasil = await jalankan_session(sesi["id"], _buat)
    assert hasil["ringkasan"]["passed"] == 2
    return {"cid": cid, "sid": sid, "sesi": sesi}


class TestLaporan:
    @pytest.mark.asyncio
    async def test_laporan_sesi(self, test_db):
        from backend.reporting.service import laporan_sesi
        ctx = await _setup_sesi_dengan_runs()
        lap = await laporan_sesi(ctx["sesi"]["id"])
        assert lap["ringkasan"]["passed"] == 2
        assert lap["pass_rate"] == 1.0
        assert len(lap["runs"]) == 2
        assert lap["per_kategori_gagal"] == {}

    @pytest.mark.asyncio
    async def test_laporan_klien_dan_tren(self, test_db):
        from backend.reporting.service import laporan_klien, tren_klien
        ctx = await _setup_sesi_dengan_runs()
        lap = await laporan_klien(ctx["cid"])
        assert lap["jumlah_sesi"] == 1
        assert lap["ringkasan"]["passed"] == 2
        assert lap["pass_rate"] == 1.0
        tren = await tren_klien(ctx["cid"])
        assert len(tren) == 1
        assert tren[0]["passed"] == 2
        assert tren[0]["pass_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_sesi_hilang_fail_closed(self, test_db):
        from backend.reporting.service import laporan_sesi
        with pytest.raises(ValueError):
            await laporan_sesi(9999)


class TestExport:
    @pytest.mark.asyncio
    async def test_pdf_valid(self, test_db):
        from backend.reporting.service import laporan_sesi, laporan_klien
        from backend.reporting.export_pdf import buat_pdf_sesi, buat_pdf_klien
        ctx = await _setup_sesi_dengan_runs()
        pdf_s = buat_pdf_sesi(await laporan_sesi(ctx["sesi"]["id"]))
        assert pdf_s[:5] == b"%PDF-"
        assert b"%%EOF" in pdf_s
        pdf_k = buat_pdf_klien(await laporan_klien(ctx["cid"]))
        assert pdf_k[:5] == b"%PDF-"
        assert b"%%EOF" in pdf_k

    @pytest.mark.asyncio
    async def test_xlsx_valid(self, test_db, tmp_path):
        from backend.reporting.service import laporan_sesi, laporan_klien
        from backend.reporting.export_xlsx import buat_xlsx_sesi, buat_xlsx_klien
        ctx = await _setup_sesi_dengan_runs()
        xs = buat_xlsx_sesi(await laporan_sesi(ctx["sesi"]["id"]))
        xk = buat_xlsx_klien(await laporan_klien(ctx["cid"]))
        # ZIP header xlsx
        assert xs[:2] == b"PK"
        assert xk[:2] == b"PK"
        # Bisa dibuka openpyxl + sheet wajib ada
        from openpyxl import load_workbook
        p1 = tmp_path / "sesi.xlsx"
        p1.write_bytes(xs)
        wb1 = load_workbook(str(p1))
        assert "Ringkasan" in wb1.sheetnames
        assert "Runs" in wb1.sheetnames
        p2 = tmp_path / "klien.xlsx"
        p2.write_bytes(xk)
        wb2 = load_workbook(str(p2))
        assert "Ringkasan" in wb2.sheetnames
        assert "PerSesi" in wb2.sheetnames
        assert "Tren" in wb2.sheetnames
