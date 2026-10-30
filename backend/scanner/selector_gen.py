"""
selector_gen.py - Generator CSS selector yang robust dengan fallback hierarchy.

Mengimplementasikan strategi selector ala Cypress 'finder' - mencoba berbagai
kombinasi selector dari yang paling spesifik ke yang lebih general, dengan
fallback jika selector utama gagal.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SelectorCandidate:
    """Kandidat selector dengan priority score"""
    selector: str
    priority: int  # Semakin rendah semakin baik (1 = paling spesifik)
    type: str  # 'id', 'data-testid', 'aria', 'class', 'text', 'position'


class SelectorGenerator:
    """
    Generator selector CSS yang robust dengan fallback hierarchy.
    Mengikuti best practice Cypress untuk selector yang stabil.
    """
    
    def __init__(self):
        # Priority order (dari paling stabil ke paling rapuh)
        self.priority_order = [
            'id',
            'data-testid',
            'data-test',
            'data-cy',
            'aria-label',
            'name',
            'placeholder',
            'type+text',
            'class+text',
            'text',
            'class',
            'position'
        ]
    
    def generate_selectors(self, element_data: Dict) -> Dict[str, List[str]]:
        """
        Generate semua kandidat selector untuk satu elemen.
        
        Args:
            element_data: Dict dari dom_walker.js hasil
            
        Returns:
            Dict dengan 'primary' dan 'fallbacks' list of selectors
        """
        candidates = []
        
        # 1. ID selector (paling stabil)
        if element_data.get('attributes', {}).get('id'):
            elem_id = element_data['attributes']['id']
            candidates.append(SelectorCandidate(
                selector=f"#{elem_id}",
                priority=1,
                type='id'
            ))
        
        # 2. Data-testid dan variants
        for attr in ['data-testid', 'data-test', 'data-cy']:
            if attr in element_data.get('attributes', {}):
                value = element_data['attributes'][attr]
                candidates.append(SelectorCandidate(
                    selector=f"[{attr}='{value}']",
                    priority=2,
                    type=attr
                ))
        
        # 3. ARIA label (sangat stabil untuk interaksi)
        aria = element_data.get('aria', {})
        if 'aria-label' in aria:
            label = aria['aria-label']
            candidates.append(SelectorCandidate(
                selector=f"[aria-label='{self._escape_quotes(label)}']",
                priority=3,
                type='aria-label'
            ))
        
        # 4. Name attribute (untuk form inputs)
        if element_data.get('attributes', {}).get('name'):
            name = element_data['attributes']['name']
            tag = element_data['tagName']
            candidates.append(SelectorCandidate(
                selector=f"{tag}[name='{name}']",
                priority=4,
                type='name'
            ))
        
        # 5. Placeholder (untuk inputs)
        if element_data.get('attributes', {}).get('placeholder'):
            placeholder = element_data['attributes']['placeholder']
            candidates.append(SelectorCandidate(
                selector=f"[placeholder='{self._escape_quotes(placeholder)}']",
                priority=5,
                type='placeholder'
            ))
        
        # 6. Role + text content (semantic + konten)
        role = element_data.get('role')
        text = element_data.get('text', '').strip()
        if role and text and len(text) > 0 and len(text) <= 50:
            # Text pendek lebih stabil
            candidates.append(SelectorCandidate(
                selector=f"[role='{role}']:has-text('{self._escape_quotes(text[:30])}')",
                priority=6,
                type='role+text'
            ))
        
        # 7. Tag + class + text (lebih spesifik)
        if text and len(text) > 0 and len(text) <= 50:
            tag = element_data['tagName']
            # Ambil class pertama jika ada
            selector_base = element_data.get('selector', tag)
            if '.' in selector_base:
                candidates.append(SelectorCandidate(
                    selector=f"{selector_base}:has-text('{self._escape_quotes(text[:30])}')",
                    priority=7,
                    type='class+text'
                ))
        
        # 8. Text saja (rapuh tapi kadang perlu)
        if text and len(text) > 3 and len(text) <= 50:
            candidates.append(SelectorCandidate(
                selector=f":text('{self._escape_quotes(text[:30])}')",
                priority=8,
                type='text'
            ))
        
        # 9. Simple selector dari dom_walker (class-based)
        if element_data.get('selector'):
            candidates.append(SelectorCandidate(
                selector=element_data['selector'],
                priority=9,
                type='class'
            ))
        
        # 10. Position-based (paling rapuh, last resort)
        bbox = element_data.get('bbox', {})
        if bbox:
            tag = element_data['tagName']
            candidates.append(SelectorCandidate(
                selector=f"{tag}:nth-of-type({self._estimate_position(element_data)})",
                priority=10,
                type='position'
            ))
        
        # Sort by priority
        candidates.sort(key=lambda x: x.priority)
        
        # Return primary + fallbacks
        if len(candidates) == 0:
            return {'primary': None, 'fallbacks': []}
        
        return {
            'primary': candidates[0].selector,
            'fallbacks': [c.selector for c in candidates[1:]]
        }
    
    def _escape_quotes(self, text: str) -> str:
        """Escape single quotes untuk CSS selector"""
        return text.replace("'", "\\'").replace('"', '\\"')
    
    def _estimate_position(self, element_data: Dict) -> int:
        """
        Estimasi posisi elemen (placeholder - di production perlu info dari DOM tree).
        Untuk Phase 1 ini return default.
        """
        return 1

