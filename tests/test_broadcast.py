"""
Unit tests untuk broadcast safety check (Phase 6, S4.4.4 + S4.4.6).
DB isolasi, tanpa ADB fisik (live_override).
"""
import os
import pytest
import pytest_asyncio

from backend.db.database import Database

TEST_DB_PATH = "test_broadcast.db"


@pytest_asyncio.fixture
async def test_db(monkeypatch):
    db_uji = Database(TEST_DB_PATH)
    await db_uji.connect()
    await db_uji.initialize_schema()
    from backend.db import database as db_module
    monkeypatch.setattr(db_module, "db", db_uji)
    for mod_nama in ("client_repo", "device_repo", "session_repo"):
        mod = __import__(f"backend.db.repositories.{mod_nama}",
                         fromlist=["x"])
        monkeypatch.setattr(mod, "db", db_uji)
    yield db_uji
    await db_uji.close()
    for ext in ["", "-wal", "-shm"]:
        f = f"{TEST_DB_PATH}{ext}"
        if os.path.exists(f):
            os.remove(f)


async def _setup():
    from backend.db.repositories import ClientRepository
    from backend.orchestrator.device_pool import register_device
    cid = await ClientRepository().create(nama="Klien BC", base_url="https://contoh.id")
    a = await register_device("BC_A")
    b = await register_device("BC_B")
    return cid, a, b


class TestSafety:
    @pytest.mark.asyncio
    async def test_semua_layak_boleh(self, test_db):
        from backend.orchestrator.broadcast import safety_check_broadcast
        cid, a, b = await _setup()
        hasil = await safety_check_broadcast(
            cid, "tap", "button_masuk",
            live_override={"BC_A", "BC_B"})
        assert hasil["boleh_jalan"] is True
        assert len(hasil["ikut"]) == 2

    @pytest.mark.asyncio
    async def test_offline_di_exclude(self, test_db):
        from backend.orchestrator.broadcast import safety_check_broadcast
        cid, a, b = await _setup()
        hasil = await safety_check_broadcast(
            cid, "tap", "button_masuk", live_override={"BC_A"})
        assert hasil["boleh_jalan"] is True
        assert [x["adb_id"] for x in hasil["ikut"]] == ["BC_A"]
        assert hasil["dikecualikan"][0]["adb_id"] == "BC_B"

    @pytest.mark.asyncio
    async def test_semua_hilang_ditolak(self, test_db):
        from backend.orchestrator.broadcast import safety_check_broadcast
        cid, a, b = await _setup()
        hasil = await safety_check_broadcast(
            cid, "tap", "button_masuk", live_override=set())
        assert hasil["boleh_jalan"] is False

    @pytest.mark.asyncio
    async def test_sesi_aktif_di_exclude(self, test_db):
        from backend.orchestrator.broadcast import safety_check_broadcast
        from backend.orchestrator.session_manager import buat_sesi_pair
        cid, a, b = await _setup()
        await buat_sesi_pair(cid, a["id"], b["id"])
        hasil = await safety_check_broadcast(
            cid, "tap", "button_masuk",
            live_override={"BC_A", "BC_B"})
        assert hasil["boleh_jalan"] is False
        assert len(hasil["dikecualikan"]) == 2

    @pytest.mark.asyncio
    async def test_aksi_tak_dikenal_ditolak(self, test_db):
        from backend.orchestrator.broadcast import safety_check_broadcast
        cid, a, b = await _setup()
        with pytest.raises(ValueError):
            await safety_check_broadcast(
                cid, "hapus_semua", "x", live_override={"BC_A"})

    @pytest.mark.asyncio
    async def test_tap_tanpa_target_ditolak(self, test_db):
        from backend.orchestrator.broadcast import safety_check_broadcast
        cid, a, b = await _setup()
        with pytest.raises(ValueError):
            await safety_check_broadcast(
                cid, "tap", "  ", live_override={"BC_A"})


class TestJalankan:
    @pytest.mark.asyncio
    async def test_run_catat_audit(self, test_db):
        from backend.orchestrator.broadcast import jalankan_broadcast
        cid, a, b = await _setup()
        hasil = await jalankan_broadcast(
            cid, "wake", "", live_override={"BC_A", "BC_B"})
        assert hasil["boleh_jalan"] is True
        assert len(hasil["peserta"]) == 2
        assert all(p["included"] == 1 for p in hasil["peserta"])

    @pytest.mark.asyncio
    async def test_run_ditolak_bila_kosong(self, test_db):
        from backend.orchestrator.broadcast import jalankan_broadcast
        cid, a, b = await _setup()
        with pytest.raises(ValueError):
            await jalankan_broadcast(cid, "wake", "", live_override=set())
