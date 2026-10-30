"""
axe_bridge.py - Injeksi axe-core untuk analisa aksesibilitas & ekstraksi accessible names.

Module ini menginjeksikan library axe-core ke halaman, menjalankan audit aksesibilitas,
dan mengekstrak accessible name untuk setiap elemen yang dianalisa.
"""

from typing import Dict, Any, List, Optional
import json


class AxeBridge:
    """Bridge untuk integrasi axe-core via Playwright"""
    
    def __init__(self, page):
        """
        Args:
            page: Playwright page object
        """
        self.page = page
        self.axe_injected = False
    
    async def inject_axe_core(self) -> bool:
        """
        Injeksikan axe-core library ke halaman via CDN.
        
        Returns:
            bool: True jika berhasil diinjeksikan
        """
        try:
            # Injeksi axe-core dari CDN
            await self.page.add_script_tag(
                url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
            )
            
            # Tunggu sampai axe tersedia
            await self.page.wait_for_function("typeof axe !== 'undefined'", timeout=5000)
            
            self.axe_injected = True
            return True
            
        except Exception as e:
            print(f"Error injeksi axe-core: {e}")
            return False
    
    async def run_axe_audit(self) -> Optional[Dict[str, Any]]:
        """
        Jalankan axe audit penuh untuk analisa aksesibilitas.
        
        Returns:
            Dict dengan hasil audit (violations, passes, incomplete, inapplicable)
        """
        if not self.axe_injected:
            await self.inject_axe_core()
        
        try:
            # Jalankan axe.run()
            result = await self.page.evaluate("""
                async () => {
                    try {
                        const results = await axe.run();
                        return results;
                    } catch (error) {
                        return { error: error.message };
                    }
                }
            """)
            
            return result
            
        except Exception as e:
            print(f"Error menjalankan axe audit: {e}")
            return None
    
    async def get_accessible_name(self, selector: str) -> Optional[str]:
        """
        Dapatkan accessible name untuk elemen tertentu menggunakan axe.
        
        Args:
            selector: CSS selector untuk elemen target
            
        Returns:
            Accessible name atau None jika gagal
        """
        if not self.axe_injected:
            await self.inject_axe_core()
        
        try:
            accessible_name = await self.page.evaluate(f"""
                () => {{
                    const element = document.querySelector('{selector}');
                    if (!element) return null;
                    
                    // Gunakan axe.commons.text.accessibleText
                    if (axe.commons && axe.commons.text && axe.commons.text.accessibleText) {{
                        return axe.commons.text.accessibleText(element);
                    }}
                    
                    // Fallback ke label/aria-label/textContent
                    return element.getAttribute('aria-label') || 
                           element.getAttribute('aria-labelledby') ||
                           element.textContent.trim().substring(0, 100);
                }}
            """)
            
            return accessible_name
            
        except Exception as e:
            print(f"Error mendapatkan accessible name untuk '{selector}': {e}")
            return None
    
    async def get_accessible_names_bulk(self, selectors: List[str]) -> Dict[str, Optional[str]]:
        """
        Dapatkan accessible names untuk banyak elemen sekaligus (lebih efisien).
        
        Args:
            selectors: List of CSS selectors
            
        Returns:
            Dict mapping selector -> accessible name
        """
        if not self.axe_injected:
            await self.inject_axe_core()
        
        try:
            selectors_json = json.dumps(selectors)
            
            result = await self.page.evaluate(f"""
                () => {{
                    const selectors = {selectors_json};
                    const results = {{}};
                    
                    for (const selector of selectors) {{
                        try {{
                            const element = document.querySelector(selector);
                            if (!element) {{
                                results[selector] = null;
                                continue;
                            }}
                            
                            if (axe.commons && axe.commons.text && axe.commons.text.accessibleText) {{
                                results[selector] = axe.commons.text.accessibleText(element);
                            }} else {{
                                results[selector] = element.getAttribute('aria-label') || 
                                                   element.textContent.trim().substring(0, 100);
                            }}
                        }} catch (err) {{
                            results[selector] = null;
                        }}
                    }}
                    
                    return results;
                }}
            """)
            
            return result
            
        except Exception as e:
            print(f"Error bulk get accessible names: {e}")
            return {}
    
    async def get_violations_summary(self) -> List[Dict[str, Any]]:
        """
        Dapatkan ringkasan violations dari axe audit (untuk reporting).
        
        Returns:
            List of violation objects dengan impact & node count
        """
        audit_result = await self.run_axe_audit()
        
        if not audit_result or 'violations' not in audit_result:
            return []
        
        violations = audit_result['violations']
        summary = []
        
        for violation in violations:
            summary.append({
                'id': violation.get('id'),
                'impact': violation.get('impact'),
                'description': violation.get('description'),
                'help': violation.get('help'),
                'helpUrl': violation.get('helpUrl'),
                'nodeCount': len(violation.get('nodes', []))
            })
        
        return summary



