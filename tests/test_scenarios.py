"""
Unit tests untuk ScenarioRepository (Phase 4).
Menutup versioning: create, versi baru, rollback, approved roles.
"""
import os
import pytest
import pytest_asyncio

from backend.db.database import Database
from backend.db.repositories import (
    ClientRepository,
    PageRepository,
    ElementRepository,
    ScenarioRepository,
)


TEST_DB_PATH = "test_scenarios.db"


@pytest_asyncio.fixture
async def test_db(monkeypatch):
    """Isolasi DB uji: arahkan singleton db ke file sementara."""
    from backend.db import database as db_module
    db_uji = Database(TEST_DB_PATH)
    await db_uji.connect()
    await db_uji.initialize_schema()
    monkeypatch.setattr(db_module, "db", db_uji)
    # Repository mengimpor objek db secara langsung, patch juga referensinya
    from backend.db.repositories import scenario_repo as sr_mod
    from backend.db.repositories import client_repo as cr_mod
    from backend.db.repositories import page_repo as pr_mod
    from backend.db.repositories import element_repo as er_mod
    monkeypatch.setattr(sr_mod, "db", db_uji)
    monkeypatch.setattr(cr_mod, "db", db_uji)
    monkeypatch.setattr(pr_mod, "db", db_uji)
    monkeypatch.setattr(er_mod, "db", db_uji)
    yield db_uji
    await db_uji.close()
    for ext in ["", "-wal", "-shm"]:
        f = f"{TEST_DB_PATH}{ext}"
        if os.path.exists(f):
            os.remove(f)


async def _buat_client_page(test_db):
    client_repo = ClientRepository()
    page_repo = PageRepository()
    client_id = await client_repo.create(nama="Klien Skenario", base_url="https://contoh.id")
    page_id = await page_repo.create(client_id, "https://contoh.id/login")
    return client_id, page_id


async def _approve_elemen(test_db, page_id, role="button_masuk"):
    element_repo = ElementRepository()
    await element_repo.create(
        page_id=page_id,
        role_label=role,
        selectors={"primary": "#masuk"},
        text_snapshot="Masuk",
        bbox={"x": 10, "y": 20, "width": 80, "height": 30},
        confidence=0.95,
        approved=True,
    )


class TestScenarioRepository:
    @pytest.mark.asyncio
    async def test_create_versi_pertama(self, test_db):
        client_id, _ = await _buat_client_page(test_db)
        repo = ScenarioRepository()
        sid = await repo.create(client_id, "login_valid", [{"action": "click"}])
        assert sid > 0
        s = await repo.get_by_id(sid)
        assert s["versi"] == 1
        assert s["steps"] == [{"action": "click"}]

    @pytest.mark.asyncio
    async def test_nama_sama_jadi_versi_berikutnya(self, test_db):
        client_id, _ = await _buat_client_page(test_db)
        repo = ScenarioRepository()
        await repo.create(client_id, "login_valid", [{"action": "click"}])
        sid2 = await repo.create(client_id, "login_valid", [{"action": "fill"}])
        s2 = await repo.get_by_id(sid2)
        assert s2["versi"] == 2

    @pytest.mark.asyncio
    async def test_create_new_version_anti_fork(self, test_db):
        client_id, _ = await _buat_client_page(test_db)
        repo = ScenarioRepository()
        sid1 = await repo.create(client_id, "kasir", [{"action": "click"}])
        sid2 = await repo.create_new_version(sid1, [{"action": "fill"}])
        # Edit dari versi lama tetap jadi max+1 (=3), bukan fork v2 ganda
        sid3 = await repo.create_new_version(sid1, [{"action": "scroll"}])
        s3 = await repo.get_by_id(sid3)
        assert s3["versi"] == 3
        semua = await repo.get_versions(client_id, "kasir")
        assert [v["versi"] for v in semua] == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_rollback_membuat_versi_baru(self, test_db):
        client_id, _ = await _buat_client_page(test_db)
        repo = ScenarioRepository()
        sid1 = await repo.create(client_id, "bayar", [{"action": "click"}])
        sid2 = await repo.create_new_version(sid1, [{"action": "fill"}])
        sid3 = await repo.rollback_to_version(sid2, 1)
        s3 = await repo.get_by_id(sid3)
        assert s3["versi"] == 3
        assert s3["steps"] == [{"action": "click"}]

    @pytest.mark.asyncio
    async def test_approved_roles_hanya_milik_client(self, test_db):
        client_id, page_id = await _buat_client_page(test_db)
        await _approve_elemen(test_db, page_id, "button_masuk")
        repo = ScenarioRepository()
        roles = await repo.get_approved_role_labels(client_id)
        assert roles == ["button_masuk"]
