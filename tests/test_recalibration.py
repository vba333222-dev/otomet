"""
Unit tests untuk service recalibration + gate (Phase 5).
Pakai DB isolasi + fresh_override (tanpa browser).
"""
import os
import pytest
import pytest_asyncio

from backend.db.database import Database

TEST_DB_PATH = "test_recalibration.db"
BBOX = {"x": 100, "y": 200, "width": 80, "height": 40}


@pytest_asyncio.fixture
async def test_db(monkeypatch):
    from backend.db import database as db_module
    db_uji = Database(TEST_DB_PATH)
    await db_uji.connect()
    await db_uji.initialize_schema()
    monkeypatch.setattr(db_module, "db", db_uji)
    from backend.db.repositories import client_repo as cr_mod
    from backend.db.repositories import page_repo as pr_mod
    from backend.db.repositories import element_repo as er_mod
    from backend.db.repositories import scenario_repo as sr_mod
    from backend.db.repositories import recalibration_repo as rr_mod
    monkeypatch.setattr(cr_mod, "db", db_uji)
    monkeypatch.setattr(pr_mod, "db", db_uji)
    monkeypatch.setattr(er_mod, "db", db_uji)
    monkeypatch.setattr(sr_mod, "db", db_uji)
    monkeypatch.setattr(rr_mod, "db", db_uji)
    yield db_uji
    await db_uji.close()
    for ext in ["", "-wal", "-shm"]:
        f = f"{TEST_DB_PATH}{ext}"
        if os.path.exists(f):
            os.remove(f)


async def _setup(test_db):
    from backend.db.repositories import ClientRepository, PageRepository, ElementRepository
    cid = await ClientRepository().create(nama="Klien Recal", base_url="https://contoh.id")
    pid = await PageRepository().create(cid, "https://contoh.id/login")
    eid = await ElementRepository().create(
        page_id=pid, role_label="button_masuk",
        selectors={"primary": "#masuk", "fallbacks": []},
        text_snapshot="Masuk", bbox=dict(BBOX), confidence=0.95, approved=True)
    return cid, pid, eid


def _fresh(teks="Masuk", bbox=None, primary="#masuk"):
    return {"role": "button", "role_label": "button_masuk", "text": teks,
            "bbox": bbox or dict(BBOX), "selectors": {"primary": primary, "fallbacks": []}}


class TestJalankan:
    @pytest.mark.asyncio
    async def test_calibrated_boleh_jalan(self, test_db):
        from backend.recalibration.service import jalankan_recalibration
        _, pid, _ = await _setup(test_db)
        hasil = await jalankan_recalibration(pid, run_batch_id="recal-uji1",
                                             fresh_override=[_fresh()])
        assert hasil["boleh_jalan"] is True
        assert hasil["ringkasan"]["calibrated"] == 1
        assert hasil["log_id"] > 0

    @pytest.mark.asyncio
    async def test_blocked_tidak_boleh_jalan(self, test_db):
        from backend.recalibration.service import jalankan_recalibration
        _, pid, _ = await _setup(test_db)
        segar = [{"role": "link", "role_label": "link_bantuan", "text": "Bantuan",
                  "bbox": dict(BBOX), "selectors": {"primary": "#bantuan", "fallbacks": []}}]
        hasil = await jalankan_recalibration(pid, fresh_override=segar)
        assert hasil["boleh_jalan"] is False
        assert hasil["ringkasan"]["blocked"] == 1

    @pytest.mark.asyncio
    async def test_recalibrated_auto_update_manifest(self, test_db):
        from backend.recalibration.service import jalankan_recalibration
        from backend.db.repositories import ElementRepository
        _, pid, eid = await _setup(test_db)
        sebelum = await ElementRepository().get_by_id(eid)
        versi_awal = sebelum["manifest_version"]
        dekat = {"x": 150, "y": 260, "width": 80, "height": 40}
        segar = [_fresh(bbox=dict(dekat), primary="#masuk-baru")]
        hasil = await jalankan_recalibration(pid, fresh_override=segar)
        assert hasil["ringkasan"]["recalibrated"] == 1
        sesudah = await ElementRepository().get_by_id(eid)
        assert sesudah["manifest_version"] == versi_awal + 1
        assert sesudah["selectors"]["primary"] == "#masuk-baru"

    @pytest.mark.asyncio
    async def test_page_hilang_fail_closed(self, test_db):
        from backend.recalibration.service import jalankan_recalibration
        with pytest.raises(ValueError):
            await jalankan_recalibration(9999, fresh_override=[])


class TestGate:
    async def _skenario(self, test_db, cid, pid):
        from backend.db.repositories import ScenarioRepository
        sid = await ScenarioRepository().create(
            cid, "login_valid",
            [{"action": "click", "role_label": "button_masuk", "page_id": pid, "params": {}}])
        return sid

    @pytest.mark.asyncio
    async def test_gate_lolos(self, test_db):
        from backend.recalibration.service import jalankan_recalibration, cek_gate_untuk_skenario
        cid, pid, _ = await _setup(test_db)
        sid = await self._skenario(test_db, cid, pid)
        await jalankan_recalibration(pid, fresh_override=[_fresh()])
        gate = await cek_gate_untuk_skenario(sid)
        assert gate["boleh_jalan"] is True

    @pytest.mark.asyncio
    async def test_gate_tertahan_blocked(self, test_db):
        from backend.recalibration.service import jalankan_recalibration, cek_gate_untuk_skenario
        cid, pid, _ = await _setup(test_db)
        sid = await self._skenario(test_db, cid, pid)
        segar = [{"role": "link", "role_label": "link_bantuan", "text": "Bantuan",
                  "bbox": dict(BBOX), "selectors": {"primary": "#bantuan", "fallbacks": []}}]
        await jalankan_recalibration(pid, fresh_override=segar)
        gate = await cek_gate_untuk_skenario(sid)
        assert gate["boleh_jalan"] is False

    @pytest.mark.asyncio
    async def test_gate_belum_recalibrated(self, test_db):
        from backend.recalibration.service import cek_gate_untuk_skenario
        cid, pid, _ = await _setup(test_db)
        sid = await self._skenario(test_db, cid, pid)
        gate = await cek_gate_untuk_skenario(sid)
        assert gate["boleh_jalan"] is False
