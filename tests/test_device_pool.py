"""
Unit tests untuk device pool manager (Phase 6, S4.4.2 + S4.4.3).
Pakai DB isolasi, tanpa ADB fisik (live_override).
"""
import os
import pytest
import pytest_asyncio

from backend.db.database import Database

TEST_DB_PATH = "test_device_pool.db"


@pytest_asyncio.fixture
async def test_db(monkeypatch):
    db_uji = Database(TEST_DB_PATH)
    await db_uji.connect()
    await db_uji.initialize_schema()
    from backend.db import database as db_module
    monkeypatch.setattr(db_module, "db", db_uji)
    from backend.db.repositories import device_repo as dr_mod
    from backend.db.repositories import session_repo as sr_mod
    monkeypatch.setattr(dr_mod, "db", db_uji)
    monkeypatch.setattr(sr_mod, "db", db_uji)
    yield db_uji
    await db_uji.close()
    for ext in ["", "-wal", "-shm"]:
        f = f"{TEST_DB_PATH}{ext}"
        if os.path.exists(f):
            os.remove(f)


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_ok(self, test_db):
        from backend.orchestrator.device_pool import register_device
        d = await register_device("R8T123ABC", ram_gb=4)
        assert d["adb_id"] == "R8T123ABC"
        assert d["status"] == "idle"
        assert d["appium_port"] == 4723

    @pytest.mark.asyncio
    async def test_register_duplikat_ditolak(self, test_db):
        from backend.orchestrator.device_pool import register_device
        await register_device("DUPLIKAT1")
        with pytest.raises(ValueError):
            await register_device("DUPLIKAT1")

    @pytest.mark.asyncio
    async def test_register_kosong_ditolak(self, test_db):
        from backend.orchestrator.device_pool import register_device
        with pytest.raises(ValueError):
            await register_device("   ")

    @pytest.mark.asyncio
    async def test_port_bertambah(self, test_db):
        from backend.orchestrator.device_pool import register_device
        a = await register_device("PORT_A")
        b = await register_device("PORT_B")
        assert b["appium_port"] == a["appium_port"] + 1


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_offline_bila_tak_terlihat(self, test_db):
        from backend.orchestrator.device_pool import register_device, health_check_device
        d = await register_device("HILANG1")
        hasil = await health_check_device(d["id"], live_override=set())
        assert hasil["status"] == "offline"

    @pytest.mark.asyncio
    async def test_health_kembali_idle(self, test_db):
        from backend.orchestrator.device_pool import register_device, health_check_device
        d = await register_device("KEMBALI1")
        await health_check_device(d["id"], live_override=set())
        hasil = await health_check_device(d["id"], live_override={"KEMBALI1"})
        assert hasil["status"] == "idle"

    @pytest.mark.asyncio
    async def test_busy_tetap_busy_bila_hidup(self, test_db):
        from backend.db.repositories import DeviceRepository
        from backend.orchestrator.device_pool import register_device, health_check_device
        d = await register_device("SIBUK1")
        await DeviceRepository().set_status(d["id"], "busy")
        hasil = await health_check_device(d["id"], live_override={"SIBUK1"})
        assert hasil["status"] == "busy"

    @pytest.mark.asyncio
    async def test_heartbeat_offline_jadi_idle(self, test_db):
        from backend.orchestrator.device_pool import (
            register_device, health_check_device, heartbeat_device,
        )
        d = await register_device("HEART1")
        await health_check_device(d["id"], live_override=set())
        hasil = await heartbeat_device(d["id"])
        assert hasil["status"] == "idle"


class TestFifo:
    @pytest.mark.asyncio
    async def test_fifo_id_terkecil_dulu(self, test_db):
        from backend.orchestrator.device_pool import register_device, ambil_device_idle_fifo
        a = await register_device("FIFO_A")
        await register_device("FIFO_B")
        await register_device("FIFO_C")
        hasil = await ambil_device_idle_fifo(2)
        assert [d["id"] for d in hasil] == [a["id"], a["id"] + 1]

    @pytest.mark.asyncio
    async def test_fifo_kurang_ditolak(self, test_db):
        from backend.orchestrator.device_pool import ambil_device_idle_fifo
        with pytest.raises(ValueError):
            await ambil_device_idle_fifo(5)

    @pytest.mark.asyncio
    async def test_maksimal_10(self, test_db):
        from backend.orchestrator.device_pool import ambil_device_idle_fifo
        with pytest.raises(ValueError):
            await ambil_device_idle_fifo(11)
