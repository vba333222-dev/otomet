"""
Repository untuk operasi CRUD pada tabel scenarios (Phase 4).
Menangani versioning: setiap simpan = versi baru, versi lama tidak diubah.
"""
import json
from typing import Optional, List

from backend.db.database import db


# Aksi yang diizinkan sesuai design.md §4.2 (whitelist ketat)
# Phase 7-real: tambah open_url untuk Chrome URL test di device fisik
# (navigasi browser sebelum click/fill/assert). Tetap ketat, bukan bebas.
ALLOWED_ACTIONS = {"click", "fill", "assert_visible", "scroll", "open_url"}


class ScenarioRepository:
    """Repository untuk tabel scenarios"""

    async def create(
        self,
        client_id: int,
        nama_fungsi: str,
        steps: list,
    ) -> int:
        """Buat skenario baru, versi otomatis (1 atau lanjutkan nama sama)."""
        # Cari versi terakhir untuk nama_fungsi yang sama di client ini
        latest = await self.get_latest(client_id, nama_fungsi)
        versi = (latest["versi"] + 1) if latest else 1

        query = """
            INSERT INTO scenarios (client_id, nama_fungsi, steps_json, versi)
            VALUES (?, ?, ?, ?)
        """
        cursor = await db.execute(
            query, (client_id, nama_fungsi.strip(), json.dumps(steps), versi)
        )
        return cursor.lastrowid

    async def get_by_id(self, scenario_id: int) -> Optional[dict]:
        """Ambil skenario berdasarkan ID, steps di-parse dari JSON."""
        query = "SELECT * FROM scenarios WHERE id = ?"
        row = await db.fetch_one(query, (scenario_id,))
        if not row:
            return None
        return self._row_to_dict(row)

    async def get_by_client(self, client_id: int) -> List[dict]:
        """Ambil semua skenario milik client (versi terbaru dulu)."""
        query = """
            SELECT * FROM scenarios WHERE client_id = ?
            ORDER BY nama_fungsi ASC, versi DESC
        """
        rows = await db.fetch_all(query, (client_id,))
        return [self._row_to_dict(r) for r in rows]

    async def get_latest(self, client_id: int, nama_fungsi: str) -> Optional[dict]:
        """Ambil versi terbaru untuk pasangan client + nama_fungsi."""
        query = """
            SELECT * FROM scenarios
            WHERE client_id = ? AND nama_fungsi = ?
            ORDER BY versi DESC LIMIT 1
        """
        row = await db.fetch_one(query, (client_id, nama_fungsi))
        return self._row_to_dict(row) if row else None

    async def get_versions(self, client_id: int, nama_fungsi: str) -> List[dict]:
        """Ambil riwayat semua versi untuk rollback (terbaru dulu)."""
        query = """
            SELECT * FROM scenarios
            WHERE client_id = ? AND nama_fungsi = ?
            ORDER BY versi DESC
        """
        rows = await db.fetch_all(query, (client_id, nama_fungsi))
        return [self._row_to_dict(r) for r in rows]

    async def create_new_version(self, scenario_id: int, steps: list) -> int:
        """Buat versi baru dari skenario lama (versi = max+1, anti-fork)."""
        current = await self.get_by_id(scenario_id)
        if not current:
            return 0
        latest = await self.get_latest(current["client_id"], current["nama_fungsi"])
        versi_baru = (latest["versi"] + 1) if latest else (current["versi"] + 1)
        query = """
            INSERT INTO scenarios (client_id, nama_fungsi, steps_json, versi)
            VALUES (?, ?, ?, ?)
        """
        cursor = await db.execute(
            query,
            (
                current["client_id"],
                current["nama_fungsi"],
                json.dumps(steps),
                versi_baru,
            ),
        )
        return cursor.lastrowid

    async def rollback_to_version(
        self, scenario_id: int, target_versi: int
    ) -> int:
        """Rollback: copy steps dari versi target menjadi versi baru."""
        current = await self.get_by_id(scenario_id)
        if not current:
            return 0
        versions = await self.get_versions(current["client_id"], current["nama_fungsi"])
        target = next((v for v in versions if v["versi"] == target_versi), None)
        if not target:
            return 0
        # Buat versi baru dengan steps dari target (audit trail terjaga)
        return await self.create_new_version(scenario_id, target["steps"])

    async def get_approved_role_labels(self, client_id: int) -> List[str]:
        """Ambil daftar role_label tervalidasi (approved=1) milik client."""
        query = """
            SELECT DISTINCT e.role_label
            FROM elements e
            JOIN pages p ON p.id = e.page_id
            WHERE p.client_id = ? AND e.approved = 1
            ORDER BY e.role_label ASC
        """
        rows = await db.fetch_all(query, (client_id,))
        return [r["role_label"] for r in rows]

    def _row_to_dict(self, row) -> dict:
        """Konversi row DB ke dict dengan steps ter-parse."""
        item = dict(row)
        try:
            item["steps"] = json.loads(item["steps_json"])
        except (ValueError, TypeError):
            item["steps"] = []
        return item
