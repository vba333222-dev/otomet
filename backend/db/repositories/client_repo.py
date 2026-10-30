"""
Repository untuk operasi CRUD pada tabel clients
"""
from typing import Optional, List
from datetime import datetime

from backend.db.database import db

class ClientRepository:
    """Repository untuk tabel clients"""
    
    async def create(
        self,
        nama: str,
        base_url: str,
        min_delay_ms: int = 1000,
        max_concurrent_actions: int = 5,
        threshold_similarity: float = 0.85,
        threshold_posisi: float = 0.90,
        threshold_tinggi_fallback: float = 0.80
    ) -> int:
        """Buat client baru, return client_id"""
        query = """
            INSERT INTO clients (
                nama, base_url, min_delay_ms, max_concurrent_actions,
                threshold_similarity, threshold_posisi, threshold_tinggi_fallback
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        cursor = await db.execute(query, (
            nama, base_url, min_delay_ms, max_concurrent_actions,
            threshold_similarity, threshold_posisi, threshold_tinggi_fallback
        ))
        return cursor.lastrowid
    
    async def get_by_id(self, client_id: int) -> Optional[dict]:
        """Ambil client berdasarkan ID"""
        query = "SELECT * FROM clients WHERE id = ?"
        row = await db.fetch_one(query, (client_id,))
        return dict(row) if row else None
    
    async def get_by_nama(self, nama: str) -> Optional[dict]:
        """Ambil client berdasarkan nama"""
        query = "SELECT * FROM clients WHERE nama = ?"
        row = await db.fetch_one(query, (nama,))
        return dict(row) if row else None
    
    async def get_all(self) -> List[dict]:
        """Ambil semua clients"""
        query = "SELECT * FROM clients ORDER BY created_at DESC"
        rows = await db.fetch_all(query)
        return [dict(row) for row in rows]
    
    async def update_thresholds(
        self,
        client_id: int,
        threshold_similarity: Optional[float] = None,
        threshold_posisi: Optional[float] = None,
        threshold_tinggi_fallback: Optional[float] = None
    ) -> bool:
        """Update threshold dinamis client"""
        updates = []
        params = []
        
        if threshold_similarity is not None:
            updates.append("threshold_similarity = ?")
            params.append(threshold_similarity)
        
        if threshold_posisi is not None:
            updates.append("threshold_posisi = ?")
            params.append(threshold_posisi)
        
        if threshold_tinggi_fallback is not None:
            updates.append("threshold_tinggi_fallback = ?")
            params.append(threshold_tinggi_fallback)
        
        if not updates:
            return False
        
        params.append(client_id)
        query = f"UPDATE clients SET {', '.join(updates)} WHERE id = ?"
        
        await db.execute(query, tuple(params))
        return True
    
    async def delete(self, client_id: int) -> bool:
        """Hapus client (cascade ke pages & elements)"""
        query = "DELETE FROM clients WHERE id = ?"
        await db.execute(query, (client_id,))
        return True
