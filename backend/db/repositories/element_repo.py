"""
Repository untuk operasi CRUD pada tabel elements
"""
from typing import Optional, List
import json

from backend.db.database import db

class ElementRepository:
    """Repository untuk tabel elements"""
    
    async def create(
        self,
        page_id: int,
        role_label: str,
        selectors: dict,
        text_snapshot: str,
        bbox: dict,
        confidence: float,
        approved: bool = False,
        manifest_version: int = 1
    ) -> int:
        """Buat element baru, return element_id"""
        query = """
            INSERT INTO elements (
                page_id, role_label, selectors_json, text_snapshot,
                bbox_snapshot, confidence, approved, manifest_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = await db.execute(query, (
            page_id, role_label, json.dumps(selectors), text_snapshot,
            json.dumps(bbox), confidence, 1 if approved else 0, manifest_version
        ))
        return cursor.lastrowid
    
    async def bulk_create(self, elements: List[dict]) -> int:
        """Bulk insert elements dari scan result"""
        query = """
            INSERT INTO elements (
                page_id, role_label, selectors_json, text_snapshot,
                bbox_snapshot, confidence, approved, manifest_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_list = [
            (
                elem['page_id'],
                elem['role_label'],
                json.dumps(elem['selectors']),
                elem.get('text_snapshot', ''),
                json.dumps(elem['bbox']),
                elem['confidence'],
                1 if elem.get('approved', False) else 0,
                elem.get('manifest_version', 1)
            )
            for elem in elements
        ]
        
        await db.executemany(query, params_list)
        return len(params_list)
    
    async def get_by_id(self, element_id: int) -> Optional[dict]:
        """Ambil element berdasarkan ID"""
        query = "SELECT * FROM elements WHERE id = ?"
        row = await db.fetch_one(query, (element_id,))
        if not row:
            return None
        
        elem = dict(row)
        elem['selectors'] = json.loads(elem['selectors_json'])
        elem['bbox'] = json.loads(elem['bbox_snapshot'])
        return elem
    
    async def get_by_page(self, page_id: int, approved_only: bool = False) -> List[dict]:
        """Ambil semua elements di page"""
        query = "SELECT * FROM elements WHERE page_id = ?"
        if approved_only:
            query += " AND approved = 1"
        query += " ORDER BY confidence DESC"
        
        rows = await db.fetch_all(query, (page_id,))
        
        result = []
        for row in rows:
            elem = dict(row)
            elem['selectors'] = json.loads(elem['selectors_json'])
            elem['bbox'] = json.loads(elem['bbox_snapshot'])
            result.append(elem)
        
        return result
    
    async def get_by_role_label(self, page_id: int, role_label: str) -> Optional[dict]:
        """Ambil element berdasarkan role_label"""
        query = "SELECT * FROM elements WHERE page_id = ? AND role_label = ?"
        row = await db.fetch_one(query, (page_id, role_label))
        if not row:
            return None
        
        elem = dict(row)
        elem['selectors'] = json.loads(elem['selectors_json'])
        elem['bbox'] = json.loads(elem['bbox_snapshot'])
        return elem
    
    async def update_selectors(
        self,
        element_id: int,
        selectors: dict,
        manifest_version: Optional[int] = None
    ) -> bool:
        """Update selectors (untuk recalibration)"""
        if manifest_version:
            query = """
                UPDATE elements 
                SET selectors_json = ?, manifest_version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            await db.execute(query, (json.dumps(selectors), manifest_version, element_id))
        else:
            query = """
                UPDATE elements 
                SET selectors_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            await db.execute(query, (json.dumps(selectors), element_id))
        
        return True
    
    async def approve(self, element_id: int) -> bool:
        """Approve element untuk digunakan dalam skenario"""
        query = "UPDATE elements SET approved = 1 WHERE id = ?"
        await db.execute(query, (element_id,))
        return True

    async def update_manifest_recalibrated(
        self,
        element_id: int,
        selectors: dict,
        text_snapshot: str,
        bbox: dict,
        confidence: float,
    ) -> bool:
        """Auto-update manifest hasil recalibration (Phase 5).

        Naikkan manifest_version +1, simpan selector/teks/bbox/confidence baru.
        """
        row = await db.fetch_one(
            "SELECT manifest_version FROM elements WHERE id = ?", (element_id,)
        )
        if not row:
            return False
        versi_baru = int(dict(row).get("manifest_version") or 1) + 1
        query = """
            UPDATE elements
            SET selectors_json = ?, text_snapshot = ?, bbox_snapshot = ?,
                confidence = ?, manifest_version = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        await db.execute(
            query,
            (
                json.dumps(selectors), text_snapshot, json.dumps(bbox),
                confidence, versi_baru, element_id,
            ),
        )
        return True
    
    async def get_high_confidence(self, page_id: int, threshold: float = 0.8) -> List[dict]:
        """Ambil elements dengan confidence tinggi"""
        query = """
            SELECT * FROM elements 
            WHERE page_id = ? AND confidence >= ?
            ORDER BY confidence DESC
        """
        rows = await db.fetch_all(query, (page_id, threshold))
        
        result = []
        for row in rows:
            elem = dict(row)
            elem['selectors'] = json.loads(elem['selectors_json'])
            elem['bbox'] = json.loads(elem['bbox_snapshot'])
            result.append(elem)
        
        return result
