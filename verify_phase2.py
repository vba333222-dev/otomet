#!/usr/bin/env python3
"""
Verify Phase 2 implementation
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.db.database import db
from backend.db.repositories import ClientRepository, PageRepository, ElementRepository
from rich.console import Console
from rich.table import Table

console = Console()

async def verify_phase2():
    """Verify Phase 2 database implementation"""
    
    console.print("\n🔍 Verifying Phase 2 Implementation...\n", style="cyan bold")
    
    try:
        # Connect to database
        await db.connect()
        
        # Get repositories
        client_repo = ClientRepository()
        page_repo = PageRepository()
        element_repo = ElementRepository()
        
        # Get counts
        clients = await client_repo.get_all()
        
        console.print(f"✓ Clients in database: {len(clients)}", style="green")
        
        if clients:
            for client in clients:
                console.print(f"\n  Client: {client['nama']}", style="cyan")
                console.print(f"    ID: {client['id']}", style="white")
                console.print(f"    Base URL: {client['base_url']}", style="white")
                console.print(f"    Threshold Similarity: {client['threshold_similarity']}", style="white")
                console.print(f"    Threshold Posisi: {client['threshold_posisi']}", style="white")
                
                # Get pages for this client
                pages = await page_repo.get_by_client(client['id'])
                console.print(f"    Pages: {len(pages)}", style="yellow")
                
                for page in pages:
                    console.print(f"\n      Page: {page['url']}", style="white")
                    console.print(f"        Status: {page['status']}", style="green")
                    
                    # Get elements for this page
                    elements = await element_repo.get_by_page(page['id'])
                    console.print(f"        Elements: {len(elements)}", style="yellow")
                    
                    # High confidence elements
                    high_conf = [e for e in elements if e['confidence'] >= 0.8]
                    console.print(f"        High confidence (≥0.8): {len(high_conf)}", style="green")
                    
                    if high_conf:
                        # Show top 5
                        table = Table(show_header=True, header_style="bold magenta")
                        table.add_column("Role Label", style="cyan")
                        table.add_column("Confidence", justify="right")
                        table.add_column("Approved", justify="center")
                        
                        for elem in sorted(high_conf, key=lambda x: x['confidence'], reverse=True)[:5]:
                            table.add_row(
                                elem['role_label'],
                                f"{elem['confidence']:.3f}",
                                "✓" if elem['approved'] else "✗"
                            )
                        
                        console.print("\n        Top Elements:", style="cyan")
                        console.print(table)
        else:
            console.print("  No clients found. Run scan_to_db.py to populate database.", style="yellow")
        
        console.print("\n✅ Phase 2 verification complete!", style="green bold")
        
    except Exception as e:
        console.print(f"\n✗ Error: {e}", style="red")
        import traceback
        traceback.print_exc()
    
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(verify_phase2())
