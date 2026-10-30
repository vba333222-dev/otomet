"""
Repository untuk test_data_pool (Phase 7 - Execution Engine).

Data uji dialokasikan atomic agar dua device tidak rebutan
baris yang sama (anti race antar device satu pair).
"""
import json
from typing import Optional, List

from backend.db.database import db


STATUS_DATA_VALID = {"available", "assigned", "used"}
class TestDataRepository:
    """Repository untuk tabel test_data_pool."""

    async def tambah(self, scenario_id: int, data_json: dict,
                    assigned_to_device_id: Optional[int] = None) -> int:
        """Tambah satu baris data uji, status awal available."""
        from backend.db.repositories.scenario_repo import ScenarioRepository
        skenario = await ScenarioRepository().get_by_id(scenario_id)
        if not skenario:
            raise ValueError(f"Skenario {scenario_id} tidak ditemukan.")
        if not isinstance(data_json, dict) or not data_json:
            raise ValueError("data_json wajib objek tak kosong.")
        status = "available"
        dev = None
        if assigned_to_device_id is not None:
            from backend.db.repositories.device_repo import DeviceRepository
            dev_row = await DeviceRepository().get_by_id(assigned_to_device_id)
            if not dev_row:
                raise ValueError(f"Device {assigned_to_device_id} tidak ditemukan.")
            status = "assigned"
            dev = assigned_to_device_id
        cursor = await db.execute(
            """INSERT INTO test_data_pool (scenario_id, data_json, status, assigned_to_device_id)
               VALUES (?, ?, ?, ?)""",
            (scenario_id, json.dumps(data_json, ensure_ascii=False), status, dev),
        )
        return cursor.lastrowid

    async def get_by_id(self, data_id: int) -> Optional[dict]:
        """Ambil satu baris + data ter-parse."""
        row = await db.fetch_one("SELECT * FROM test_data_pool WHERE id = ?", (data_id,))
        if not row:
            return None
        item = dict(row)
        try:
            item["data"] = json.loads(item["data_json"])
        except (ValueError, TypeError):
            item["data"] = {}
        return item

    async def get_tersedia(self, scenario_id: int, limit: int = 50) -> List[dict]:
        """Baris available untuk satu skenario (FIFO id ASC)."""
        rows = await db.fetch_all(
            """SELECT * FROM test_data_pool WHERE scenario_id = ?
               AND status = 'available' ORDER BY id ASC LIMIT ?""",
            (scenario_id, int(limit)),
        )
        hasil = []
        for r in rows:
            item = dict(r)
            try:
                item["data"] = json.loads(item["data_json"])
            except (ValueError, TypeError):
                item["data"] = {}
            hasil.append(item)
        return hasil

    async def list_by_skenario(self, scenario_id: int) -> List[dict]:
        """Semua baris satu skenario (terbaru dulu)."""
        rows = await db.fetch_all(
            "SELECT * FROM test_data_pool WHERE scenario_id = ? ORDER BY id DESC",
            (scenario_id,),
        )
        hasil = []
        for r in rows:
            item = dict(r)
            try:
                item["data"] = json.loads(item["data_json"])
            except (ValueError, TypeError):
                item["data"] = {}
            hasil.append(item)
        return hasil

    async def klaim_atomik(self, scenario_id: int, device_id: int) -> Optional[dict]:
        """Klaim satu baris available secara atomic untuk satu device."""
        from backend.db.repositories.device_repo import DeviceRepository
        dev = await DeviceRepository().get_by_id(device_id)
        if not dev:
            raise ValueError(f"Device {device_id} tidak ditemukan.")
        kandidat = await db.fetch_one(
            """SELECT id FROM test_data_pool WHERE scenario_id = ?
               AND status = 'available' ORDER BY id ASC LIMIT 1""",
            (scenario_id,),
        )
        if not kandidat:
            return None
        data_id = int(dict(kandidat)["id"])
        cursor = await db.execute(
            """UPDATE test_data_pool SET status = 'assigned',
               assigned_to_device_id = ? WHERE id = ? AND status = 'available'""",
            (device_id, data_id),
        )
        if cursor.rowcount == 0:
            return None
        return await self.get_by_id(data_id)

    async def tandai_used(self, data_id: int) -> bool:
        """Tandai baris sudah dipakai (used). Idempoten."""
        row = await self.get_by_id(data_id)
        if not row:
            return False
        await db.execute("UPDATE test_data_pool SET status = 'used' WHERE id = ?", (data_id,))
        return True

    async def bebaskan(self, data_id: int) -> bool:
        """Kembalikan ke available (run dibatalkan sebelum jalan)."""
        row = await self.get_by_id(data_id)
        if not row:
            return False
        await db.execute(
            """UPDATE test_data_pool SET status = 'available',
               assigned_to_device_id = NULL WHERE id = ?""",
            (data_id,),
        )
        return True
STATUS_RUN_VALID = {"running", "passed", "failed", "blocked"}
FAILURE_VALID = {"mapping_error", "timeout", "server_rejected", "infra_error", "validation_error"}


class RunRepository:
    """Repository untuk tabel runs."""

    async def mulai(self, scenario_assignment_id: int,
                   test_data_id: Optional[int] = None) -> int:
        """Buat baris run baru status running."""
        from backend.db.repositories.session_repo import AssignmentRepository
        tugasan = await AssignmentRepository().get_by_id(scenario_assignment_id)
        if not tugasan:
            raise ValueError(f"Assignment {scenario_assignment_id} tidak ditemukan.")
        if test_data_id is not None:
            data = await TestDataRepository().get_by_id(test_data_id)
            if not data:
                raise ValueError(f"Data uji {test_data_id} tidak ditemukan.")
        cursor = await db.execute(
            """INSERT INTO runs (scenario_assignment_id, test_data_id, status)
               VALUES (?, ?, 'running')""",
            (scenario_assignment_id, test_data_id),
        )
        return cursor.lastrowid

    async def selesaikan(self, run_id: int, status: str,
                         failure_category: Optional[str] = None,
                         log_path: Optional[str] = None,
                         screenshot_dir: Optional[str] = None,
                         video_path: Optional[str] = None) -> bool:
        """Tutup run: passed/failed/blocked + kategori granular."""
        if status not in STATUS_RUN_VALID or status == "running":
            raise ValueError("Status akhir wajib passed/failed/blocked.")
        if failure_category is not None and failure_category not in FAILURE_VALID:
            raise ValueError(f"failure_category '{failure_category}' tidak dikenal.")
        if status == "passed" and failure_category is not None:
            raise ValueError("Run passed tidak boleh punya failure_category.")
        if status == "failed" and not failure_category:
            raise ValueError("Run failed wajib punya failure_category granular.")
        row = await self.get_by_id(run_id)
        if not row:
            return False
        await db.execute(
            """UPDATE runs SET status = ?, failure_category = ?, log_path = ?,
               screenshot_dir = ?, video_path = ?,
               completed_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, failure_category, log_path, screenshot_dir, video_path, run_id),
        )
        return True

    async def get_by_id(self, run_id: int) -> Optional[dict]:
        """Ambil satu run."""
        row = await db.fetch_one("SELECT * FROM runs WHERE id = ?", (run_id,))
        return dict(row) if row else None

    async def get_by_assignment(self, assignment_id: int) -> List[dict]:
        """Riwayat run satu assignment (terbaru dulu)."""
        rows = await db.fetch_all(
            "SELECT * FROM runs WHERE scenario_assignment_id = ? ORDER BY id DESC",
            (assignment_id,),
        )
        return [dict(r) for r in rows]

    async def get_by_session(self, session_id: int) -> List[dict]:
        """Semua run dalam satu sesi (join assignments)."""
        rows = await db.fetch_all(
            """SELECT r.*, sa.device_id, sa.scenario_id FROM runs r
               JOIN scenario_assignments sa ON sa.id = r.scenario_assignment_id
               WHERE sa.session_id = ? ORDER BY r.id ASC""",
            (session_id,),
        )
        return [dict(r) for r in rows]

    async def ringkasan_session(self, session_id: int) -> dict:
        """Ringkasan passed/failed/blocked/running untuk satu sesi."""
        semua = await self.get_by_session(session_id)
        ringkas = {"total": len(semua), "passed": 0, "failed": 0,
                   "blocked": 0, "running": 0}
        for r in semua:
            st = r.get("status")
            if st in ringkas:
                ringkas[st] += 1
        return {"session_id": session_id, "ringkasan": ringkas, "runs": semua}


