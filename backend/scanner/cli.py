"""
cli.py - Command-line interface untuk DOM Scanner Phase 1.

Entry point untuk menjalankan analisa website:
1. Launch Playwright browser (headless, mobile emulation)
2. Injeksi dom_walker.js
3. Injeksi axe-core & ekstrak accessible names
4. Generate selectors untuk setiap elemen
5. Score semua elemen
6. Output JSON manifest + colored terminal log
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from playwright.async_api import async_playwright, Browser, Page
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import modules internal
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    PLAYWRIGHT_TIMEOUT, WAIT_FOR_STABLE_DOM, USER_AGENT_MOBILE,
    VIEWPORT_WIDTH, VIEWPORT_HEIGHT, OUTPUT_DIR, MIN_CONFIDENCE_THRESHOLD
)
from scanner.axe_bridge import AxeBridge
from scanner.selector_gen import SelectorGenerator
from scanner.scorer import ElementScorer


console = Console()


class DOMScanner:
    """Scanner utama untuk analisa DOM website"""
    
    def __init__(self, url: str, output_file: str = None):
        self.url = url
        self.output_file = output_file or self._generate_output_filename()
        self.browser: Browser = None
        self.page: Page = None
        self.dom_walker_script = None
    
    def _generate_output_filename(self) -> str:
        """Generate nama file output berdasarkan timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Clean URL untuk dijadikan filename yang valid
        safe_url = self.url.replace('https://', '').replace('http://', '').replace('file:///', '')
        # Remove invalid filename characters
        safe_url = ''.join(c if c.isalnum() or c in '-_' else '_' for c in safe_url)
        # Truncate to reasonable length
        safe_url = safe_url[:50]
        return str(OUTPUT_DIR / f"scan_{safe_url}_{timestamp}.json")
    
    async def initialize(self):
        """Initialize browser & load scripts"""
        console.print("[blue]🔧 Inisialisasi scanner...[/blue]")
        
        # Load dom_walker.js
        dom_walker_path = Path(__file__).parent / "dom_walker.js"
        with open(dom_walker_path, 'r', encoding='utf-8') as f:
            self.dom_walker_script = f.read()
        
        # Launch browser
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        
        # Create context dengan mobile emulation
        context = await self.browser.new_context(
            viewport={'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT},
            user_agent=USER_AGENT_MOBILE,
            device_scale_factor=2
        )
        
        self.page = await context.new_page()
        self.page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        
        console.print("[green]✓ Browser initialized[/green]")
    
    async def scan(self) -> Dict:
        """Jalankan proses scanning lengkap"""
        try:
            # 1. Navigate ke URL
            console.print(f"[blue]🌐 Membuka URL: {self.url}[/blue]")
            await self.page.goto(self.url, wait_until='networkidle')
            
            # 2. Tunggu DOM stabil (untuk SPA)
            console.print(f"[blue]⏳ Menunggu DOM stabil ({WAIT_FOR_STABLE_DOM}ms)...[/blue]")
            await asyncio.sleep(WAIT_FOR_STABLE_DOM / 1000)
            
            # 3. Injeksi & jalankan dom_walker.js
            console.print("[blue]🔍 Ekstraksi struktur DOM...[/blue]")
            dom_result = await self.page.evaluate(self.dom_walker_script)
            
            if 'error' in dom_result:
                console.print(f"[red]✗ Error ekstraksi DOM: {dom_result['error']}[/red]")
                return {'error': dom_result['error']}
            
            elements = dom_result.get('elements', [])
            console.print(f"[green]✓ Ditemukan {len(elements)} elemen relevan[/green]")
            
            # 4. Injeksi axe-core & ekstrak accessible names
            console.print("[blue]♿ Ekstraksi accessible names (axe-core)...[/blue]")
            axe_bridge = AxeBridge(self.page)
            await axe_bridge.inject_axe_core()
            
            # Bulk get accessible names
            selectors = [elem.get('selector') for elem in elements if elem.get('selector')]
            accessible_names = await axe_bridge.get_accessible_names_bulk(selectors)
            console.print(f"[green]✓ Accessible names diambil untuk {len(accessible_names)} elemen[/green]")
            
            # 5. Generate selectors untuk semua elemen
            console.print("[blue]🎯 Generate selectors...[/blue]")
            selector_gen = SelectorGenerator()
            
            # 6. Score semua elemen
            console.print("[blue]📊 Scoring elemen...[/blue]")
            scorer = ElementScorer()
            scored_elements = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Processing elements...", total=len(elements))
                
                for elem in elements:
                    selector_info = selector_gen.generate_selectors(elem)
                    accessible_name = accessible_names.get(elem.get('selector'))
                    
                    scored = scorer.score_element(elem, accessible_name, selector_info)
                    
                    scored_elements.append({
                        'id': scored.id,
                        'role_label': scored.role_label,
                        'confidence': scored.confidence,
                        'score_breakdown': scored.score_breakdown,
                        'selectors': selector_info,
                        'accessible_name': accessible_name,
                        'element': {
                            'tagName': elem.get('tagName'),
                            'role': elem.get('role'),
                            'text': elem.get('text', '')[:100],
                            'bbox': elem.get('bbox'),
                            'interactive': elem.get('interactive'),
                            'attributes': elem.get('attributes')
                        }
                    })
                    
                    progress.update(task, advance=1)
            
            console.print(f"[green]✓ Scoring selesai untuk {len(scored_elements)} elemen[/green]")
            
            # 7. Compile hasil
            result = {
                'metadata': {
                    'url': self.url,
                    'timestamp': datetime.now().isoformat(),
                    'viewport': dom_result.get('viewport'),
                    'total_elements': len(scored_elements)
                },
                'elements': scored_elements,
                'statistics': self._calculate_statistics(scored_elements)
            }
            
            return result
            
        except Exception as e:
            console.print(f"[red]✗ Error saat scanning: {e}[/red]")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def _calculate_statistics(self, elements: List[Dict]) -> Dict:
        """Kalkulasi statistik untuk reporting"""
        if not elements:
            return {}
        
        confidences = [e['confidence'] for e in elements]
        high_conf = sum(1 for c in confidences if c >= 0.8)
        medium_conf = sum(1 for c in confidences if 0.6 <= c < 0.8)
        low_conf = sum(1 for c in confidences if c < 0.6)
        
        roles = {}
        for e in elements:
            role = e['element'].get('role', 'unknown')
            roles[role] = roles.get(role, 0) + 1
        
        return {
            'confidence_distribution': {
                'high': high_conf,
                'medium': medium_conf,
                'low': low_conf
            },
            'average_confidence': round(sum(confidences) / len(confidences), 3),
            'roles_detected': roles,
            'interactive_elements': sum(1 for e in elements if e['element'].get('interactive'))
        }
    
    async def save_results(self, result: Dict):
        """Simpan hasil ke file JSON"""
        console.print(f"[blue]💾 Menyimpan hasil ke {self.output_file}...[/blue]")
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓ Hasil disimpan di: {self.output_file}[/green]")
    
    async def display_summary(self, result: Dict):
        """Display summary hasil scanning di terminal"""
        if 'error' in result:
            console.print(f"[red]❌ Scanning gagal: {result['error']}[/red]")
            return
        
        # Summary table
        stats = result.get('statistics', {})
        
        console.print("\n[bold cyan]📊 Ringkasan Hasil Scanning[/bold cyan]")
        console.print(f"URL: {result['metadata']['url']}")
        console.print(f"Total elemen: {result['metadata']['total_elements']}")
        console.print(f"Average confidence: {stats.get('average_confidence', 0)}")
        
        # Confidence distribution
        table = Table(title="Distribusi Confidence")
        table.add_column("Level", style="cyan")
        table.add_column("Count", style="magenta")
        
        conf_dist = stats.get('confidence_distribution', {})
        table.add_row("High (≥0.8)", str(conf_dist.get('high', 0)))
        table.add_row("Medium (0.6-0.8)", str(conf_dist.get('medium', 0)))
        table.add_row("Low (<0.6)", str(conf_dist.get('low', 0)))
        
        console.print(table)
        
        # Top elements by confidence
        elements = result.get('elements', [])
        top_elements = sorted(elements, key=lambda x: x['confidence'], reverse=True)[:10]
        
        table2 = Table(title="Top 10 Elemen (by Confidence)")
        table2.add_column("Role Label", style="cyan")
        table2.add_column("Confidence", style="green")
        table2.add_column("Text", style="yellow")
        
        for elem in top_elements:
            table2.add_row(
                elem['role_label'],
                f"{elem['confidence']:.3f}",
                elem['element']['text'][:40]
            )
        
        console.print(table2)
    
    async def cleanup(self):
        """Cleanup browser resources"""
        if self.browser:
            await self.browser.close()
            console.print("[green]✓ Browser closed[/green]")


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        console.print("[red]Usage: python cli.py <URL>[/red]")
        console.print("Example: python cli.py https://example.com")
        sys.exit(1)
    
    url = sys.argv[1]
    
    scanner = DOMScanner(url)
    
    try:
        await scanner.initialize()
        result = await scanner.scan()
        await scanner.save_results(result)
        await scanner.display_summary(result)
    finally:
        await scanner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


