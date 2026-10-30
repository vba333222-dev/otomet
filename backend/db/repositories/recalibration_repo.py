"""
Repository untuk tabel recalibration_log (Phase 5).
Mencatat riwayat audit tiap proses recalibration per halaman.
"""
import json
from typing import Optional, List

from backend.db.database import db


class RecalibrationRepository:
    """Repository untuk tabel recalibration_log."""

    async def catat(
        self,
        run_batch_id: str,
        page_id: int,
        hasil_per_elemen: list,
    ) -> int:
        """Simpan satu baris log, return log_id."""
        query = """
            INSERT INTO recalibration_log (run_batch_id, page_id, hasil_per_elemen)
            VALUES (?, ?, ?)
        """
        cursor = await db.execute(
            query, (run_batch_id, page_id, json.dumps(hasil_per_elemen, ensure_ascii=False))
        )
        return cursor.lastrowid

    async def get_by_id(self, log_id: int) -> Optional[dict]:
        """Ambil satu log + hasil_per_elemen ter-parse."""
        row = await db.fetch_one("SELECT * FROM recalibration_log WHERE id = ?", (log_id,))
        if not row:
            return None
        item = dict(row)
        try:
            item["hasil"] = json.loads(item["hasil_per_elemen"])
        except (ValueError, TypeError):
            item["hasil"] = []
        return item

    async def get_by_page(self, page_id: int, limit: int = 20) -> List[dict]:
        """Riwayat log satu halaman (terbaru dulu)."""
        rows = await db.fetch_all(
            "SELECT * FROM recalibration_log WHERE page_id = ? ORDER BY id DESC LIMIT ?",
            (page_id, limit),
        )
        hasil = []
        for row in rows:
            item = dict(row)
            try:
                item["hasil"] = json.loads(item["hasil_per_elemen"])
            except (ValueError, TypeError):
                item["hasil"] = []
            hasil.append(item)
        return hasil

    async def get_terakhir(self, page_id: int) -> Optional[dict]:
        """Log terakhir satu halaman (untuk gate skenario)."""
        rows = await self.get_by_page(page_id, limit=1)
        return rows[0] if rows else None
