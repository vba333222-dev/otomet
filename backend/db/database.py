"""
Database connection manager dengan aiosqlite + WAL mode
"""
import os
import aiosqlite
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from backend.config import DB_PATH, DB_DIR

class Database:
    """Manager untuk koneksi database SQLite dengan WAL mode"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self) -> aiosqlite.Connection:
        """Buka koneksi database dan enable WAL mode"""
        # Pastikan directory exists
        DB_DIR.mkdir(parents=True, exist_ok=True)
        
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        
        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys = ON")
        
        # Enable WAL mode untuk concurrency
        await self._connection.execute("PRAGMA journal_mode = WAL")
        
        # Optimalkan performa
        await self._connection.execute("PRAGMA synchronous = NORMAL")
        await self._connection.execute("PRAGMA cache_size = -64000")  # 64MB cache
        await self._connection.execute("PRAGMA temp_store = MEMORY")
        
        await self._connection.commit()
        
        return self._connection
    
    async def close(self):
        """Tutup koneksi database"""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager untuk transaksi atomic"""
        if not self._connection:
            await self.connect()
        
        await self._connection.execute("BEGIN")
        try:
            yield self._connection
            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise
    
    async def execute(self, query: str, params: tuple = ()):
        """Execute query tunggal"""
        if not self._connection:
            await self.connect()
        
        cursor = await self._connection.execute(query, params)
        await self._connection.commit()
        return cursor
    
    async def executemany(self, query: str, params_list: list):
        """Execute query batch"""
        if not self._connection:
            await self.connect()
        
        await self._connection.executemany(query, params_list)
        await self._connection.commit()
    
    async def fetch_one(self, query: str, params: tuple = ()):
        """Fetch satu row"""
        if not self._connection:
            await self.connect()
        
        cursor = await self._connection.execute(query, params)
        return await cursor.fetchone()
    
    async def fetch_all(self, query: str, params: tuple = ()):
        """Fetch semua rows"""
        if not self._connection:
            await self.connect()
        
        cursor = await self._connection.execute(query, params)
        return await cursor.fetchall()
    
    async def initialize_schema(self):
        """Inisialisasi schema dari schema.sql"""
        schema_file = Path(__file__).parent / "schema.sql"
        
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file tidak ditemukan: {schema_file}")
        
        schema_sql = schema_file.read_text(encoding='utf-8')
        
        if not self._connection:
            await self.connect()
        
        # Execute schema (split by semicolon untuk multi-statement)
        await self._connection.executescript(schema_sql)
        await self._connection.commit()

# Global database instance
db = Database()
