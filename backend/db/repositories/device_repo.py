"""
Repository untuk tabel devices (Phase 6).
Satu baris = satu perangkat Android fisik (Redmi 12C) via USB/ADB.
"""
from typing import Optional, List

from backend.db.database import db


STATUS_VALID = {"idle", "busy", "offline"}
PORT_AWAL = 4723


class DeviceRepository:
    """Repository untuk tabel devices."""

    async def create(
        self,
        adb_id: str,
        appium_port: Optional[int] = None,
        ram_gb: Optional[int] = None,
    ) -> int:
        """Daftarkan device baru. adb_id wajib unik, fail-closed bila kosong."""
        adb_bersih = (adb_id or "").strip()
        if not adb_bersih:
            raise ValueError("adb_id wajib diisi.")
        port = appium_port if appium_port else await self.port_berikutnya()
        query = """
            INSERT INTO devices (adb_id, appium_port, status, ram_gb)
            VALUES (?, ?, 'idle', ?)
        """
        cursor = await db.execute(query, (adb_bersih, int(port), ram_gb))
        return cursor.lastrowid

    async def port_berikutnya(self) -> int:
        """Port Appium berikutnya (4723 + jumlah device)."""
        row = await db.fetch_one("SELECT COUNT(*) AS c FROM devices")
        jumlah = int(dict(row).get("c") or 0) if row else 0
        return PORT_AWAL + jumlah

    async def get_by_id(self, device_id: int) -> Optional[dict]:
        row = await db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        return dict(row) if row else None

    async def get_by_adb_id(self, adb_id: str) -> Optional[dict]:
        row = await db.fetch_one("SELECT * FROM devices WHERE adb_id = ?", (adb_id,))
        return dict(row) if row else None

    async def get_all(self) -> List[dict]:
        rows = await db.fetch_all("SELECT * FROM devices ORDER BY id ASC")
        return [dict(r) for r in rows]

    async def get_idle(self, limit: Optional[int] = None) -> List[dict]:
        """Device idle FIFO (id terkecil dulu = paling lama terdaftar)."""
        query = "SELECT * FROM devices WHERE status = 'idle' ORDER BY id ASC"
        if limit:
            query += f" LIMIT {int(limit)}"
        rows = await db.fetch_all(query)
        return [dict(r) for r in rows]

    async def set_status(self, device_id: int, status: str) -> bool:
        """Ubah status. Fail-closed bila status tak dikenal / device hilang."""
        if status not in STATUS_VALID:
            raise ValueError(f"Status '{status}' tidak dikenal.")
        device = await self.get_by_id(device_id)
        if not device:
            return False
        await db.execute(
            "UPDATE devices SET status = ? WHERE id = ?", (status, device_id)
        )
        return True

    async def update_health(self, device_id: int, status: str) -> bool:
        """Health-check: ubah status + cap last_health_check_at."""
        if status not in STATUS_VALID:
            raise ValueError(f"Status '{status}' tidak dikenal.")
        device = await self.get_by_id(device_id)
        if not device:
            return False
        await db.execute(
            """UPDATE devices
               SET status = ?, last_health_check_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, device_id),
        )
        return True

    async def heartbeat(self, device_id: int) -> Optional[dict]:
        """Heartbeat: cap waktu cek + offline -> idle (kembali hidup)."""
        device = await self.get_by_id(device_id)
        if not device:
            return None
        status_baru = "idle" if device["status"] == "offline" else device["status"]
        await db.execute(
            """UPDATE devices
               SET status = ?, last_health_check_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status_baru, device_id),
        )
        return await self.get_by_id(device_id)

    async def delete(self, device_id: int) -> bool:
        await db.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return True
