"""
Job backup otomatis untuk SQLite database
Backup incremental dengan rotasi otomatis
"""
import os
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from backend.config import DB_PATH, BACKUP_DIR, BACKUP_RETENTION_DAYS
from backend.db.database import db

class SQLiteBackup:
    """Manager untuk backup & restore SQLite database"""
    
    def __init__(
        self,
        db_path: str = DB_PATH,
        backup_dir: Path = BACKUP_DIR,
        retention_days: int = BACKUP_RETENTION_DAYS
    ):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.retention_days = retention_days
        
        # Pastikan backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_backup_filename(self) -> str:
        """Generate nama file backup dengan timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"otomet_backup_{timestamp}.db"
    
    async def create_backup(self) -> Optional[str]:
        """
        Buat backup database menggunakan file copy
        WAL mode memungkinkan backup saat database sedang digunakan
        Return path ke file backup atau None jika gagal
        """
        backup_path = self.backup_dir / self._generate_backup_filename()
        
        try:
            # Pastikan connection tersedia
            if not db._connection:
                await db.connect()
            
            # Copy database file (safe di WAL mode)
            await asyncio.get_event_loop().run_in_executor(
                None,
                shutil.copy2,
                self.db_path,
                backup_path
            )
            
            # Juga copy WAL dan SHM files jika ada
            wal_path = f"{self.db_path}-wal"
            shm_path = f"{self.db_path}-shm"
            
            if os.path.exists(wal_path):
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    shutil.copy2,
                    wal_path,
                    f"{backup_path}-wal"
                )
            
            if os.path.exists(shm_path):
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    shutil.copy2,
                    shm_path,
                    f"{backup_path}-shm"
                )
            
            print(f"✓ Backup berhasil: {backup_path}")
            return str(backup_path)
        
        except Exception as e:
            print(f"✗ Backup gagal: {e}")
            # Hapus file backup yang corrupt
            if backup_path.exists():
                backup_path.unlink()
            return None
    
    async def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database dari file backup
        WARNING: akan overwrite database yang ada!
        """
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            print(f"✗ File backup tidak ditemukan: {backup_path}")
            return False
        
        try:
            # Tutup connection dulu
            await db.close()
            
            # Backup database saat ini sebagai safety net
            current_backup = f"{self.db_path}.pre-restore"
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, current_backup)
            
            # Copy backup file ke database path
            await asyncio.get_event_loop().run_in_executor(
                None,
                shutil.copy2,
                backup_path,
                self.db_path
            )
            
            # Copy WAL dan SHM jika ada
            wal_backup = f"{backup_path}-wal"
            shm_backup = f"{backup_path}-shm"
            
            if os.path.exists(wal_backup):
                shutil.copy2(wal_backup, f"{self.db_path}-wal")
            
            if os.path.exists(shm_backup):
                shutil.copy2(shm_backup, f"{self.db_path}-shm")
            
            # Reconnect ke database
            await db.connect()
            
            print(f"✓ Restore berhasil dari: {backup_path}")
            print(f"  Backup lama disimpan di: {current_backup}")
            return True
        
        except Exception as e:
            print(f"✗ Restore gagal: {e}")
            # Restore backup safety net jika ada
            if os.path.exists(current_backup):
                shutil.copy2(current_backup, self.db_path)
                print(f"  Database dikembalikan ke state sebelum restore")
            return False
    
    async def cleanup_old_backups(self):
        """Hapus backup yang lebih lama dari retention_days"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        
        try:
            for backup_file in self.backup_dir.glob("otomet_backup_*.db"):
                # Extract timestamp dari filename
                try:
                    # Format: otomet_backup_YYYYMMDD_HHMMSS.db
                    timestamp_str = backup_file.stem.replace("otomet_backup_", "")
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    if file_date < cutoff_date:
                        backup_file.unlink()
                        # Hapus juga WAL dan SHM files
                        wal_file = Path(f"{backup_file}-wal")
                        shm_file = Path(f"{backup_file}-shm")
                        if wal_file.exists():
                            wal_file.unlink()
                        if shm_file.exists():
                            shm_file.unlink()
                        
                        deleted_count += 1
                        print(f"  Dihapus: {backup_file.name}")
                
                except ValueError:
                    # Skip file yang format timestamp-nya tidak valid
                    continue
            
            if deleted_count > 0:
                print(f"✓ Cleanup selesai: {deleted_count} backup dihapus")
            else:
                print("✓ Tidak ada backup lama yang perlu dihapus")
        
        except Exception as e:
            print(f"✗ Cleanup gagal: {e}")
    
    async def list_backups(self) -> list:
        """List semua backup yang tersedia"""
        backups = []
        
        for backup_file in sorted(self.backup_dir.glob("otomet_backup_*.db"), reverse=True):
            try:
                timestamp_str = backup_file.stem.replace("otomet_backup_", "")
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
                
                backups.append({
                    'path': str(backup_file),
                    'filename': backup_file.name,
                    'date': file_date,
                    'size_mb': round(file_size, 2),
                    'age_days': (datetime.now() - file_date).days
                })
            except ValueError:
                continue
        
        return backups

# Scheduled backup job
async def scheduled_backup_job(interval_hours: int = 24):
    """
    Job yang berjalan secara periodik untuk backup otomatis
    Default: setiap 24 jam
    """
    backup_manager = SQLiteBackup()
    
    print(f"🔄 Backup scheduler dimulai (interval: {interval_hours} jam)")
    
    while True:
        try:
            print(f"\n⏰ Menjalankan backup otomatis ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            
            # Buat backup
            backup_path = await backup_manager.create_backup()
            
            if backup_path:
                # Cleanup backup lama
                await backup_manager.cleanup_old_backups()
                
                # Tampilkan list backup
                backups = await backup_manager.list_backups()
                print(f"📦 Total backup tersedia: {len(backups)}")
            
        except Exception as e:
            print(f"✗ Error saat backup: {e}")
        
        # Tunggu interval berikutnya
        await asyncio.sleep(interval_hours * 3600)

