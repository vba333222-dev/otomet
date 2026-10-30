"""
Unit tests untuk pairing sesi pair (Phase 6, S4.4.2).
DB isolasi + gate recalibration via fresh_override.
"""
import os
import pytest
import pytest_asyncio

from backend.db.database import Database

TEST_DB_PATH = "test_sessions.db"
BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


@pytest_asyncio.fixture
async def test_db(monkeypatch):
    db_uji = Database(TEST_DB_PATH)
    await db_uji.connect()
    await db_uji.initialize_schema()
    from backend.db import database as db_module
    monkeypatch.setattr(db_module, "db", db_uji)
    for mod_nama in ("client_repo", "page_repo", "element_repo",
                     "scenario_repo", "recalibration_repo",
                     "device_repo", "session_repo"):
        mod = __import__(f"backend.db.repositories.{mod_nama}",
                         fromlist=["x"])
        monkeypatch.setattr(mod, "db", db_uji)
    yield db_uji
    await db_uji.close()
    for ext in ["", "-wal", "-shm"]:
        f = f"{TEST_DB_PATH}{ext}"
        if os.path.exists(f):
            os.remove(f)


async def _setup_klien_skenario():
    from backend.db.repositories import (
        ClientRepository, PageRepository, ElementRepository,
        ScenarioRepository,
    )
    from backend.recalibration.service import jalankan_recalibration
    cid = await ClientRepository().create(nama="Klien Sesi", base_url="https://contoh.id")
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
    return cid, pid, sid


async def _dua_device():
    from backend.orchestrator.device_pool import register_device
    a = await register_device("SESI_A")
    b = await register_device("SESI_B")
    return a, b


class TestBuatPair:
    @pytest.mark.asyncio
    async def test_buat_pair_ok_busy(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair
        from backend.db.repositories import DeviceRepository
        cid, _, _ = await _setup_klien_skenario()
        a, b = await _dua_device()
        sesi = await buat_sesi_pair(cid, a["id"], b["id"], "pair-1")
        assert sesi["status"] == "running"
        assert (await DeviceRepository().get_by_id(a["id"]))["status"] == "busy"

    @pytest.mark.asyncio
    async def test_device_sama_ditolak(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair
        cid, _, _ = await _setup_klien_skenario()
        a, _ = await _dua_device()
        with pytest.raises(ValueError):
            await buat_sesi_pair(cid, a["id"], a["id"])

    @pytest.mark.asyncio
    async def test_device_busy_ditolak(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair
        from backend.orchestrator.device_pool import register_device
        cid, _, _ = await _setup_klien_skenario()
        a, b = await _dua_device()
        c = await register_device("SESI_C")
        await buat_sesi_pair(cid, a["id"], b["id"])
        with pytest.raises(ValueError):
            await buat_sesi_pair(cid, a["id"], c["id"])


class TestAssign:
    @pytest.mark.asyncio
    async def test_assign_ok_gate_lolos(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
        cid, _, sid = await _setup_klien_skenario()
        a, b = await _dua_device()
        sesi = await buat_sesi_pair(cid, a["id"], b["id"])
        hasil = await tugaskan_skenario(sesi["id"], a["id"], sid)
        assert hasil["scenario_id"] == sid
        assert hasil["gate"]["boleh_jalan"] is True

    @pytest.mark.asyncio
    async def test_assign_beda_klien_ditolak(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
        from backend.db.repositories import ClientRepository, ScenarioRepository
        cid, _, _ = await _setup_klien_skenario()
        cid2 = await ClientRepository().create(nama="Lain", base_url="https://lain.id")
        sid2 = await ScenarioRepository().create(cid2, "fungsi_lain", [
            {"action": "click", "role_label": "button_masuk", "params": {}}])
        a, b = await _dua_device()
        sesi = await buat_sesi_pair(cid, a["id"], b["id"])
        with pytest.raises(ValueError):
            await tugaskan_skenario(sesi["id"], a["id"], sid2)

    @pytest.mark.asyncio
    async def test_assign_gate_tertahan_ditolak(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair, tugaskan_skenario
        from backend.recalibration.service import jalankan_recalibration
        cid, pid, sid = await _setup_klien_skenario()
        hilang = [{"role": "link", "role_label": "link_bantuan", "text": "Bantuan",
                   "bbox": dict(BBOX),
                   "selectors": {"primary": "#bantuan", "fallbacks": []}}]
        await jalankan_recalibration(pid, fresh_override=hilang)
        a, b = await _dua_device()
        sesi = await buat_sesi_pair(cid, a["id"], b["id"])
        with pytest.raises(ValueError):
            await tugaskan_skenario(sesi["id"], a["id"], sid)


class TestAkhiri:
    @pytest.mark.asyncio
    async def test_selesai_bebaskan_idle(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair, akhiri_sesi
        from backend.db.repositories import DeviceRepository
        cid, _, _ = await _setup_klien_skenario()
        a, b = await _dua_device()
        sesi = await buat_sesi_pair(cid, a["id"], b["id"])
        hasil = await akhiri_sesi(sesi["id"])
        assert hasil["status"] == "completed"
        assert (await DeviceRepository().get_by_id(a["id"]))["status"] == "idle"

    @pytest.mark.asyncio
    async def test_offline_tetap_offline(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair, akhiri_sesi
        from backend.db.repositories import DeviceRepository
        cid, _, _ = await _setup_klien_skenario()
        a, b = await _dua_device()
        sesi = await buat_sesi_pair(cid, a["id"], b["id"])
        await DeviceRepository().update_health(a["id"], "offline")
        await akhiri_sesi(sesi["id"])
        assert (await DeviceRepository().get_by_id(a["id"]))["status"] == "offline"

    @pytest.mark.asyncio
    async def test_device_offline_ditolak(self, test_db):
        from backend.orchestrator.session_manager import buat_sesi_pair
        from backend.orchestrator.device_pool import health_check_device
        cid, _, _ = await _setup_klien_skenario()
        a, b = await _dua_device()
        await health_check_device(a["id"], live_override=set())
        with pytest.raises(ValueError):
            await buat_sesi_pair(cid, a["id"], b["id"])
