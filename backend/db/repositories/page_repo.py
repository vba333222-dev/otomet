"""
Repository untuk operasi CRUD pada tabel pages
"""
from typing import Optional, List
from datetime import datetime

from backend.db.database import db

class PageRepository:
    """Repository untuk tabel pages"""
    
    async def create(self, client_id: int, url: str) -> int:
        """Buat page baru, return page_id"""
        query = """
            INSERT INTO pages (client_id, url, status)
            VALUES (?, ?, 'pending')
        """
        cursor = await db.execute(query, (client_id, url))
        return cursor.lastrowid
    
    async def get_by_id(self, page_id: int) -> Optional[dict]:
        """Ambil page berdasarkan ID"""
        query = "SELECT * FROM pages WHERE id = ?"
        row = await db.fetch_one(query, (page_id,))
        return dict(row) if row else None
    
    async def get_by_url(self, client_id: int, url: str) -> Optional[dict]:
        """Ambil page berdasarkan client & URL"""
        query = "SELECT * FROM pages WHERE client_id = ? AND url = ?"
        row = await db.fetch_one(query, (client_id, url))
        return dict(row) if row else None
    
    async def get_by_client(self, client_id: int) -> List[dict]:
        """Ambil semua pages milik client"""
        query = "SELECT * FROM pages WHERE client_id = ? ORDER BY last_analyzed_at DESC"
        rows = await db.fetch_all(query, (client_id,))
        return [dict(row) for row in rows]
    
    async def update_status(self, page_id: int, status: str) -> bool:
        """Update status page (pending/analyzing/analyzed/failed)"""
        query = """
            UPDATE pages 
            SET status = ?, last_analyzed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        await db.execute(query, (status, page_id))
        return True
    
    async def delete(self, page_id: int) -> bool:
        """Hapus page (cascade ke elements)"""
        query = "DELETE FROM pages WHERE id = ?"
        await db.execute(query, (page_id,))
        return True
