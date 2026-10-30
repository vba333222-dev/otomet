"""
headless_runner.py - Recalibration via Playwright headless (Phase 5).

Bukan device fisik (design.md S4.3): hanya verifikasi struktur DOM,
tidak butuh perilaku fisik device. Emulasi mobile viewport Redmi 12C.
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import async_playwright
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import (
    PLAYWRIGHT_TIMEOUT,
    WAIT_FOR_STABLE_DOM,
    USER_AGENT_MOBILE,
    VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT,
)
from backend.scanner.selector_gen import SelectorGenerator
from backend.scanner.scorer import ElementScorer

console = Console()


async def scan_page_fresh(url: str, timeout_ms: int = PLAYWRIGHT_TIMEOUT) -> List[Dict]:
    """Scan ulang satu halaman, kembalikan daftar elemen fresh.

    Format tiap elemen: {role, role_label, text, bbox, selectors{primary,fallbacks}}.
    Komentar & log Bahasa Indonesia, fail-safe: gagal navigasi = raise.
    """
    dom_walker_path = Path(__file__).parent.parent / "scanner" / "dom_walker.js"
    skrip_walker = dom_walker_path.read_text(encoding="utf-8")
    scorer = ElementScorer()
    generator = SelectorGenerator()
    playwright = await async_playwright().start()
    browser = None
    try:
        console.print(f"[blue]Membuka ulang (headless): {url}[/blue]")
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            user_agent=USER_AGENT_MOBILE,
            device_scale_factor=2,
        )
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(WAIT_FOR_STABLE_DOM / 1000.0)
        # Stabilisasi SPA: cek DOM tidak berubah selama 2x sampling.
        try:
            await page.wait_for_function(
                """() => new Promise((selesai) => {
                    let awal = document.body.innerHTML.length;
                    setTimeout(() => selesai(document.body.innerHTML.length === awal), 1000);
                })""",
                timeout=8000,
            )
        except Exception:
            console.print("[yellow]Peringatan: DOM belum stabil, lanjut apa adanya[/yellow]")
        hasil = await page.evaluate(skrip_walker)
        mentah = hasil.get("elements", []) if isinstance(hasil, dict) else []
        segar: List[Dict] = []
        for item in mentah:
            selector_info = generator.generate_selectors(item)
            dinilai = scorer.score_element(item, None, selector_info)
            segar.append({
                "role": item.get("role") or "",
                "role_label": dinilai.role_label,
                "text": item.get("text", ""),
                "bbox": item.get("bbox", {}),
                "selectors": selector_info,
                "tagName": item.get("tagName", ""),
            })
        console.print(f"[green]Scan ulang selesai: {len(segar)} elemen[/green]")
        return segar
    finally:
        if browser:
            await browser.close()
        await playwright.stop()


async def scan_multi_pass(url: str, jumlah_pass: int = 3) -> List[List[Dict]]:
    """Multi-pass scan untuk baseline variasi alami (S4.1 langkah 7 + S4.3.1)."""
    hasil: List[List[Dict]] = []
    for i in range(max(1, jumlah_pass)):
        console.print(f"[blue]Pass {i + 1}/{jumlah_pass}...[/blue]")
        hasil.append(await scan_page_fresh(url))
    return hasil
