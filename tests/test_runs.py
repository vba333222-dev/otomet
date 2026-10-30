"""
Unit tests untuk Execution Engine paralel Phase 7.
DB isolasi + FakeDriver (tanpa Appium fisik).
"""
import os
import pytest
import pytest_asyncio

from backend.db.database import Database

TEST_DB_PATH = "test_runs.db"
BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


@pytest_asyncio.fixture
async def test_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test_runs.db")
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


async def _setup_pair():
    from backend.db.repositories import (
        ClientRepository, PageRepository, ElementRepository,
        ScenarioRepository, TestDataRepository,
    )
    from backend.recalibration.service import jalankan_recalibration
    from backend.orchestrator.device_pool import register_device
    from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
    cid = await ClientRepository().create(nama="Klien Run", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk", "fallbacks": []},
        text_snapshot="Masuk", bbox=dict(BBOX), confidence=0.95, approved=True)
    await ElementRepository().create(
        page_id=pid, role_label="input_nama",
        selectors={"primary": "#nama", "fallbacks": []},
        text_snapshot="Nama", bbox=dict(BBOX), confidence=0.93, approved=True)
    sid = await ScenarioRepository().create(
        cid, "login_valid",
        [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}},
         {"action": "fill", "role_label": "input_nama", "page_id": pid,
          "params": {"text": "{{nama}}"}},
         {"action": "assert_visible", "role_label": "button_masuk",
          "page_id": pid, "params": {}}])
    segar = [{"role": "button", "role_label": "button_masuk", "text": "Masuk",
              "bbox": dict(BBOX), "selectors": {"primary": "#masuk", "fallbacks": []}},
             {"role": "textbox", "role_label": "input_nama", "text": "Nama",
              "bbox": dict(BBOX), "selectors": {"primary": "#nama", "fallbacks": []}}]
    await jalankan_recalibration(pid, fresh_override=segar)
    a = await register_device("RUN_A")
    b = await register_device("RUN_B")
    await TestDataRepository().tambah(sid, {"nama": "Andi"})
    await TestDataRepository().tambah(sid, {"nama": "Budi"})
    sesi = await buat_sesi_pair(cid, a["id"], b["id"], "pair-run")
    ta = await tugaskan_skenario(sesi["id"], a["id"], sid)
    tb = await tugaskan_skenario(sesi["id"], b["id"], sid)
    return {"cid": cid, "sid": sid, "sesi": sesi, "a": a, "b": b,
            "ta": ta, "tb": tb}


def _fake_factory(gagal=None):
    from backend.orchestrator.runner import FakeDriver

    def _buat(device, caps):
        return FakeDriver(device.get("adb_id", "?"), gagal_pada=(gagal or {}))

    return _buat


class TestCaps:
    def test_port_unik(self):
        from backend.orchestrator.runner import bangun_caps
        a = bangun_caps({"adb_id": "A", "appium_port": 4723})
        b = bangun_caps({"adb_id": "B", "appium_port": 4724})
        assert a["systemPort"] != b["systemPort"]
        assert a["chromeDriverPort"] != b["chromeDriverPort"]
        assert a["udid"] == "A"

    def test_klasifikasi(self):
        from backend.orchestrator.runner import klasifikasi_error
        assert klasifikasi_error(TimeoutError("timeout 5s")) == "timeout"
        assert klasifikasi_error(RuntimeError("No such element")) == "mapping_error"
        assert klasifikasi_error(AssertionError("expected tampak")) == "validation_error"


class TestData:
    @pytest.mark.asyncio
    async def test_klaim_atomik_beda_baris(self, test_db):
        ctx = await _setup_pair()
        from backend.db.repositories import TestDataRepository
        repo = TestDataRepository()
        d1 = await repo.klaim_atomik(ctx["sid"], ctx["a"]["id"])
        d2 = await repo.klaim_atomik(ctx["sid"], ctx["b"]["id"])
        assert d1 and d2 and d1["id"] != d2["id"]
        assert d1["assigned_to_device_id"] == ctx["a"]["id"]
        habis = await repo.klaim_atomik(ctx["sid"], ctx["a"]["id"])
        assert habis is None

    @pytest.mark.asyncio
    async def test_tambah_validasi(self, test_db):
        ctx = await _setup_pair()
        from backend.db.repositories import TestDataRepository
        with pytest.raises(ValueError):
            await TestDataRepository().tambah(ctx["sid"], {})

class TestJalankan:
    @pytest.mark.asyncio
    async def test_paralel_dua_device_passed(self, test_db):
        from backend.orchestrator.runner import jalankan_session
        from backend.db.repositories import RunRepository
        ctx = await _setup_pair()
        hasil = await jalankan_session(ctx["sesi"]["id"], _fake_factory())
        assert hasil["ringkasan"]["passed"] == 2
        assert hasil["data_ganda"] is False
        ringkas = await RunRepository().ringkasan_session(ctx["sesi"]["id"])
        assert ringkas["ringkasan"]["passed"] == 2

    @pytest.mark.asyncio
    async def test_satu_gagal_lain_tetap_jalan(self, test_db):
        from backend.orchestrator.runner import jalankan_assignment
        ctx = await _setup_pair()
        gagal = _fake_factory({1: "No such element: input_nama"})
        h1 = await jalankan_assignment(ctx["ta"]["id"], gagal)
        h2 = await jalankan_assignment(ctx["tb"]["id"], _fake_factory())
        assert h1["status"] == "failed"
        assert h1["failure_category"] == "mapping_error"
        assert h2["status"] == "passed"

    @pytest.mark.asyncio
    async def test_data_sama_ditolak(self, test_db):
        from backend.orchestrator.runner import jalankan_session
        from backend.db.repositories import TestDataRepository
        ctx = await _setup_pair()
        repo = TestDataRepository()
        semua = await repo.list_by_skenario(ctx["sid"])
        sama = semua[0]["id"]
        with pytest.raises(ValueError):
            await jalankan_session(
                ctx["sesi"]["id"], _fake_factory(),
                {ctx["ta"]["id"]: sama, ctx["tb"]["id"]: sama})

    @pytest.mark.asyncio
    async def test_gate_tertahan_blocked(self, test_db):
        from backend.orchestrator.runner import jalankan_assignment
        from backend.recalibration.service import jalankan_recalibration
        from backend.db.repositories import PageRepository
        ctx = await _setup_pair()
        pages = await PageRepository().get_by_client(ctx["cid"])
        hilang = [{"role": "link", "role_label": "link_bantuan",
                   "text": "Bantuan", "bbox": dict(BBOX),
                   "selectors": {"primary": "#bantuan", "fallbacks": []}}]
        await jalankan_recalibration(pages[0]["id"], fresh_override=hilang)
        hasil = await jalankan_assignment(ctx["ta"]["id"], _fake_factory())
        assert hasil["status"] == "blocked"


class TestBroadcastFisik:
    @pytest.mark.asyncio
    async def test_fisik_paralel_ok(self, test_db):
        from backend.orchestrator.runner import jalankan_broadcast_fisik
        from backend.orchestrator.session_manager import akhiri_sesi
        ctx = await _setup_pair()
        await akhiri_sesi(ctx["sesi"]["id"])
        hasil = await jalankan_broadcast_fisik(
            ctx["cid"], "wake", "", None, _fake_factory(),
            live_override={"RUN_A", "RUN_B"})
        assert hasil["boleh_jalan"] is True
        assert len(hasil["eksekusi"]) == 2
        assert all(e["ok"] for e in hasil["eksekusi"])
