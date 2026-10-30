#!/usr/bin/env python3
"""
CLI tool untuk database management
Usage:
    python backend/db/db_cli.py init          # Inisialisasi schema
    python backend/db/db_cli.py backup        # Buat backup manual
    python backend/db/db_cli.py restore <file> # Restore dari backup
    python backend/db/db_cli.py list-backups  # List semua backup
    python backend/db/db_cli.py cleanup       # Hapus backup lama
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.db.database import db
from backend.backup.sqlite_backup import SQLiteBackup
from rich.console import Console
from rich.table import Table

console = Console()

async def init_database():
    """Inisialisasi database schema"""
    console.print("\n🔧 Inisialisasi database schema...", style="cyan")
    
    try:
        await db.connect()
        await db.initialize_schema()
        console.print("✓ Schema berhasil diinisialisasi", style="green")
        
        # Verify tables created
        tables = await db.fetch_all("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        
        console.print(f"\n📊 Tabel yang dibuat: {len(tables)}", style="cyan")
        for row in tables:
            console.print(f"  • {row['name']}", style="white")
        
    except Exception as e:
        console.print(f"✗ Error: {e}", style="red")
    finally:
        await db.close()

async def create_backup():
    """Buat backup manual"""
    console.print("\n💾 Membuat backup...", style="cyan")
    
    backup_manager = SQLiteBackup()
    backup_path = await backup_manager.create_backup()
    
    if backup_path:
        console.print(f"✓ Backup berhasil dibuat", style="green")
        console.print(f"  Path: {backup_path}", style="white")

async def restore_backup(backup_path: str):
    """Restore dari backup"""
    console.print(f"\n⚠️  PERHATIAN: Restore akan overwrite database saat ini!", style="yellow")
    confirm = input("Lanjutkan? (yes/no): ")
    
    if confirm.lower() != 'yes':
        console.print("✗ Restore dibatalkan", style="yellow")
        return
    
    console.print(f"\n🔄 Restore dari: {backup_path}", style="cyan")
    
    backup_manager = SQLiteBackup()
    success = await backup_manager.restore_backup(backup_path)
    
    if success:
        console.print("✓ Restore berhasil", style="green")
    else:
        console.print("✗ Restore gagal", style="red")

async def list_backups():
    """List semua backup tersedia"""
    console.print("\n📦 Daftar Backup Tersedia", style="cyan")
    
    backup_manager = SQLiteBackup()
    backups = await backup_manager.list_backups()
    
    if not backups:
        console.print("  Tidak ada backup ditemukan", style="yellow")
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("No", style="dim", width=4)
    table.add_column("Filename")
    table.add_column("Date", style="cyan")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Age (days)", justify="right", style="yellow")
    
    for idx, backup in enumerate(backups, 1):
        table.add_row(
            str(idx),
            backup['filename'],
            backup['date'].strftime('%Y-%m-%d %H:%M:%S'),
            str(backup['size_mb']),
            str(backup['age_days'])
        )
    
    console.print(table)
    console.print(f"\nTotal: {len(backups)} backup(s)", style="cyan")

async def cleanup_backups():
    """Hapus backup lama"""
    console.print("\n🧹 Cleanup backup lama...", style="cyan")
    
    backup_manager = SQLiteBackup()
    await backup_manager.cleanup_old_backups()

async def main():
    """Main CLI handler"""
    if len(sys.argv) < 2:
        console.print("\n❌ Usage:", style="red")
        console.print("  python backend/db/db_cli.py init")
        console.print("  python backend/db/db_cli.py backup")
        console.print("  python backend/db/db_cli.py restore <backup_file>")
        console.print("  python backend/db/db_cli.py list-backups")
        console.print("  python backend/db/db_cli.py cleanup")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        await init_database()
    
    elif command == "backup":
        await create_backup()
    
    elif command == "restore":
        if len(sys.argv) < 3:
            console.print("❌ Error: Backup file path required", style="red")
            console.print("Usage: python backend/db/db_cli.py restore <backup_file>")
            sys.exit(1)
        await restore_backup(sys.argv[2])
    
    elif command == "list-backups":
        await list_backups()
    
    elif command == "cleanup":
        await cleanup_backups()
    
    else:
        console.print(f"❌ Unknown command: {command}", style="red")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
