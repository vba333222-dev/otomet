#!/usr/bin/env python3
"""
Integration CLI - Scanner Phase 1 + Database Phase 2
Scan website dan simpan hasilnya ke database

Usage:
    python backend/scanner/scan_to_db.py <url> --client-name "Client Name"
"""
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.scanner.cli import Scanner
from backend.db.database import db
from backend.db.repositories import ClientRepository, PageRepository, ElementRepository
from rich.console import Console

console = Console()

async def scan_and_save(url: str, client_name: str):
    """Scan URL dan simpan hasil ke database"""
    
    # Initialize database
    await db.connect()
    
    # Repositories
    client_repo = ClientRepository()
    page_repo = PageRepository()
    element_repo = ElementRepository()
    
    console.print(f"\n🔍 Scanning: {url}", style="cyan bold")
    console.print(f"📋 Client: {client_name}", style="cyan")
    
    # 1. Get or create client
    client = await client_repo.get_by_nama(client_name)
    if not client:
        console.print(f"  Creating new client: {client_name}", style="yellow")
        client_id = await client_repo.create(
            nama=client_name,
            base_url=url.split('/')[0:3]  # Extract base URL
        )
        client = await client_repo.get_by_id(client_id)
        console.print(f"  ✓ Client created (ID: {client_id})", style="green")
    else:
        console.print(f"  ✓ Using existing client (ID: {client['id']})", style="green")
    
    # 2. Create or update page
    page = await page_repo.get_by_url(client['id'], url)
    if not page:
        page_id = await page_repo.create(client['id'], url)
        console.print(f"  ✓ Page created (ID: {page_id})", style="green")
    else:
        page_id = page['id']
        console.print(f"  ✓ Using existing page (ID: {page_id})", style="green")
    
    # Update page status
    await page_repo.update_status(page_id, 'analyzing')
    
    # 3. Run scanner
    console.print("\n🚀 Running scanner...", style="cyan")
    scanner = Scanner(url, headless=True)
    
    try:
        result = await scanner.run()
        
        if not result or 'elements' not in result:
            console.print("✗ Scan failed or no elements found", style="red")
            await page_repo.update_status(page_id, 'failed')
            return
        
        console.print(f"✓ Scan completed: {len(result['elements'])} elements found", style="green")
        
        # 4. Save elements to database
        console.print("\n💾 Saving elements to database...", style="cyan")
        
        elements_to_insert = []
        for elem in result['elements']:
            # Extract data dari scan result
            element_data = elem['element']
            
            elements_to_insert.append({
                'page_id': page_id,
                'role_label': elem['role_label'],
                'selectors': elem['selectors'],
                'text_snapshot': element_data.get('text', ''),
                'bbox': element_data.get('bbox', {}),
                'confidence': elem['confidence'],
                'approved': elem['confidence'] >= 0.8,  # Auto-approve high confidence
                'manifest_version': 1
            })
        
        # Bulk insert
        count = await element_repo.bulk_create(elements_to_insert)
        console.print(f"✓ Saved {count} elements to database", style="green")
        
        # Update page status
        await page_repo.update_status(page_id, 'analyzed')
        
        # 5. Display summary
        console.print("\n📊 Summary:", style="cyan bold")
        console.print(f"  Client ID: {client['id']}", style="white")
        console.print(f"  Page ID: {page_id}", style="white")
        console.print(f"  Total elements: {count}", style="white")
        
        # High confidence elements
        high_conf = [e for e in result['elements'] if e['confidence'] >= 0.8]
        console.print(f"  High confidence (≥0.8): {len(high_conf)}", style="green")
        console.print(f"  Auto-approved: {len(high_conf)}", style="green")
        
    except Exception as e:
        console.print(f"✗ Error: {e}", style="red")
        await page_repo.update_status(page_id, 'failed')
        raise
    
    finally:
        await db.close()

async def main():
    """Main CLI handler"""
    if len(sys.argv) < 2:
        console.print("\n❌ Usage:", style="red")
        console.print("  python backend/scanner/scan_to_db.py <url> --client-name \"Client Name\"")
        console.print("\nExample:")
        console.print("  python backend/scanner/scan_to_db.py https://example.com --client-name \"Example Corp\"")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Parse client name
    client_name = "Default Client"
    if "--client-name" in sys.argv:
        idx = sys.argv.index("--client-name")
        if idx + 1 < len(sys.argv):
            client_name = sys.argv[idx + 1]
    
    await scan_and_save(url, client_name)

if __name__ == "__main__":
    asyncio.run(main())
