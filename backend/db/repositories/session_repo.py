"""
Repository untuk sessions, scenario_assignments, broadcast (Phase 6).
Satu sesi = satu pair (2 device) untuk satu klien.
"""
from typing import Optional, List

from backend.db.database import db


STATUS_SESI_VALID = {"pending", "running", "completed", "failed"}
# Sesi aktif = status 'running' (ikut CHECK skema sessions).


class SessionRepository:
    """Repository untuk tabel sessions."""

    async def create(
        self, client_id: int, device_a_id: int, device_b_id: int,
        pair_label: Optional[str] = None,
    ) -> int:
        query = """
            INSERT INTO sessions (client_id, pair_label, device_a_id, device_b_id, status)
            VALUES (?, ?, ?, ?, 'running')
        """
        cursor = await db.execute(query, (client_id, pair_label, device_a_id, device_b_id))
        return cursor.lastrowid

    async def get_by_id(self, session_id: int) -> Optional[dict]:
        row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return dict(row) if row else None

    async def get_by_client(self, client_id: int) -> List[dict]:
        rows = await db.fetch_all(
            "SELECT * FROM sessions WHERE client_id = ? ORDER BY id DESC", (client_id,))
        return [dict(r) for r in rows]

    async def get_active_untuk_device(self, device_id: int) -> List[dict]:
        """Sesi aktif (running) yang memakai device ini (untuk free yang aman)."""
        rows = await db.fetch_all(
            """SELECT * FROM sessions
               WHERE status = 'running' AND (device_a_id = ? OR device_b_id = ?)""",
            (device_id, device_id),
        )
        return [dict(r) for r in rows]

    async def set_status(self, session_id: int, status: str) -> bool:
        if status not in STATUS_SESI_VALID:
            raise ValueError(f"Status sesi '{status}' tidak dikenal.")
        sesi = await self.get_by_id(session_id)
        if not sesi:
            return False
        await db.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
        return True

    async def get_assignments(self, session_id: int) -> List[dict]:
        rows = await db.fetch_all(
            "SELECT * FROM scenario_assignments WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        return [dict(r) for r in rows]


class AssignmentRepository:
    """Repository untuk tabel scenario_assignments."""

    async def create(self, session_id: int, device_id: int, scenario_id: int) -> int:
        cursor = await db.execute(
            """INSERT INTO scenario_assignments (session_id, device_id, scenario_id)
               VALUES (?, ?, ?)""",
            (session_id, device_id, scenario_id),
        )
        return cursor.lastrowid

    async def get_by_id(self, assignment_id: int) -> Optional[dict]:
        row = await db.fetch_one(
            "SELECT * FROM scenario_assignments WHERE id = ?", (assignment_id,))
        return dict(row) if row else None

    async def get_detail(self, assignment_id: int) -> Optional[dict]:
        """Detail assignment + nama skenario + adb_id untuk GUI."""
        row = await db.fetch_one(
            """SELECT sa.*, s.nama_fungsi, s.versi, s.client_id, d.adb_id
               FROM scenario_assignments sa
               JOIN scenarios s ON s.id = sa.scenario_id
               JOIN devices d ON d.id = sa.device_id
               WHERE sa.id = ?""",
            (assignment_id,),
        )
        return dict(row) if row else None


class BroadcastRepository:
    """Repository untuk broadcast_actions + broadcast_action_devices."""

    async def catat_aksi(self, action_type: str, target: str) -> int:
        cursor = await db.execute(
            "INSERT INTO broadcast_actions (action_type, target_role_or_coord) VALUES (?, ?)",
            (action_type, target),
        )
        return cursor.lastrowid

    async def catat_peserta(
        self, broadcast_id: int, device_id: int, included: bool, exclude_reason: str = ""
    ) -> int:
        cursor = await db.execute(
            """INSERT INTO broadcast_action_devices
               (broadcast_action_id, device_id, included, exclude_reason)
               VALUES (?, ?, ?, ?)""",
            (broadcast_id, device_id, 1 if included else 0, exclude_reason or ""),
        )
        return cursor.lastrowid

    async def get_by_id(self, broadcast_id: int) -> Optional[dict]:
        row = await db.fetch_one(
            "SELECT * FROM broadcast_actions WHERE id = ?", (broadcast_id,))
        if not row:
            return None
        item = dict(row)
        peserta = await db.fetch_all(
            """SELECT bd.*, d.adb_id, d.status
               FROM broadcast_action_devices bd
               JOIN devices d ON d.id = bd.device_id
               WHERE bd.broadcast_action_id = ? ORDER BY bd.id ASC""",
            (broadcast_id,),
        )
        item["peserta"] = [dict(r) for r in peserta]
        return item

    async def get_terakhir(self, limit: int = 20) -> List[dict]:
        rows = await db.fetch_all(
            "SELECT * FROM broadcast_actions ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]
