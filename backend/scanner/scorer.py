"""
scorer.py - Scoring elemen interaktif dengan confidence calculation.

Memberikan score kepada setiap elemen berdasarkan:
- Role & semantic value
- Interaktivitas
- Accessible name quality
- Visual prominence (size, position)
- Selector stability
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

# Rapidfuzz optional - hanya untuk fuzzy matching lanjutan di Phase 5
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


@dataclass
class ScoredElement:
    """Elemen dengan score & metadata"""
    id: str
    role_label: str
    confidence: float
    element_data: Dict
    score_breakdown: Dict


class ElementScorer:
    """
    Scorer untuk menilai kualitas & kepercayaan deteksi elemen.
    Mengikuti prinsip: elemen interaktif dengan metadata lengkap = score tinggi.
    """
    
    def __init__(self):
        # Weight untuk setiap faktor scoring
        self.weights = {
            'role_semantic': 0.25,      # Role jelas & semantic
            'interactivity': 0.20,      # Elemen interaktif
            'accessible_name': 0.20,    # Punya accessible name berkualitas
            'selector_stability': 0.15, # Selector stabil (ID/data-testid)
            'visual_prominence': 0.10,  # Ukuran visible & posisi
            'text_clarity': 0.10        # Text content jelas
        }
    
    def score_element(self, element_data: Dict, accessible_name: Optional[str] = None,
                     selector_info: Optional[Dict] = None) -> ScoredElement:
        """
        Hitung confidence score untuk satu elemen.
        
        Args:
            element_data: Data dari dom_walker.js
            accessible_name: Accessible name dari axe-core
            selector_info: Info selector dari selector_gen.py
            
        Returns:
            ScoredElement dengan score & breakdown
        """
        scores = {}
        
        # 1. Role semantic score
        scores['role_semantic'] = self._score_role_semantic(element_data)
        
        # 2. Interactivity score
        scores['interactivity'] = self._score_interactivity(element_data)
        
        # 3. Accessible name quality
        scores['accessible_name'] = self._score_accessible_name(
            element_data, accessible_name
        )
        
        # 4. Selector stability
        scores['selector_stability'] = self._score_selector_stability(
            element_data, selector_info
        )
        
        # 5. Visual prominence
        scores['visual_prominence'] = self._score_visual_prominence(element_data)
        
        # 6. Text clarity
        scores['text_clarity'] = self._score_text_clarity(element_data)
        
        # Hitung weighted average
        total_confidence = sum(
            scores[key] * self.weights[key]
            for key in scores.keys()
        )
        
        # Generate role label
        role_label = self._generate_role_label(element_data, accessible_name)
        
        return ScoredElement(
            id=element_data.get('id', 'unknown'),
            role_label=role_label,
            confidence=round(total_confidence, 3),
            element_data=element_data,
            score_breakdown=scores
        )
    
    def _score_role_semantic(self, element_data: Dict) -> float:
        """Score berdasarkan kejelasan role semantic"""
        role = element_data.get('role')
        
        # Role eksplisit dengan priority tinggi
        high_value_roles = ['button', 'link', 'textbox', 'combobox', 'checkbox', 'radio']
        medium_value_roles = ['navigation', 'main', 'form', 'heading', 'search']
        
        if role in high_value_roles:
            return 1.0
        elif role in medium_value_roles:
            return 0.7
        elif role:
            return 0.5
        else:
            return 0.2  # Tidak ada role jelas
    
    def _score_interactivity(self, element_data: Dict) -> float:
        """Score berdasarkan interaktivitas"""
        if element_data.get('interactive'):
            # Cek apakah disabled
            if element_data.get('attributes', {}).get('disabled'):
                return 0.3  # Interaktif tapi disabled
            return 1.0
        return 0.0
    
    def _score_accessible_name(self, element_data: Dict, 
                               accessible_name: Optional[str]) -> float:
        """Score berdasarkan kualitas accessible name"""
        # Jika ada accessible name dari axe-core
        if accessible_name and len(accessible_name.strip()) > 0:
            # Nama yang jelas & deskriptif
            if len(accessible_name) >= 3 and len(accessible_name) <= 100:
                return 1.0
            elif len(accessible_name) > 0:
                return 0.6
        
        # Fallback ke aria-label
        aria = element_data.get('aria', {})
        if 'aria-label' in aria and len(aria['aria-label']) > 0:
            return 0.8
        
        # Fallback ke text content
        text = element_data.get('text', '').strip()
        if len(text) >= 3 and len(text) <= 100:
            return 0.6
        elif len(text) > 0:
            return 0.3
        
        return 0.1  # Tidak ada label jelas
    
    def _score_selector_stability(self, element_data: Dict, 
                                  selector_info: Optional[Dict]) -> float:
        """Score berdasarkan stabilitas selector"""
        if not selector_info:
            # Fallback ke element data langsung
            if element_data.get('attributes', {}).get('id'):
                return 1.0
            return 0.3
        
        primary = selector_info.get('primary', '')
        
        # ID selector paling stabil
        if primary.startswith('#'):
            return 1.0
        
        # Data-testid sangat stabil
        if 'data-testid' in primary or 'data-test' in primary:
            return 0.95
        
        # ARIA label stabil
        if 'aria-label' in primary:
            return 0.85
        
        # Name attribute cukup stabil
        if '[name=' in primary:
            return 0.75
        
        # Class + text medium
        if ':has-text' in primary or ':text' in primary:
            return 0.5
        
        # Position-based paling rapuh
        if ':nth-of-type' in primary or ':nth-child' in primary:
            return 0.2
        
        return 0.4  # Default
    
    def _score_visual_prominence(self, element_data: Dict) -> float:
        """Score berdasarkan ukuran & visibility"""
        bbox = element_data.get('bbox', {})
        if not bbox:
            return 0.3
        
        width = bbox.get('width', 0)
        height = bbox.get('height', 0)
        area = width * height
        
        # Elemen terlalu kecil (mungkin hidden/icon kecil)
        if area < 100:
            return 0.2
        
        # Ukuran normal untuk button/input
        if 1000 <= area <= 50000:
            return 1.0
        
        # Terlalu besar (mungkin container)
        if area > 100000:
            return 0.5
        
        return 0.6
    
    def _score_text_clarity(self, element_data: Dict) -> float:
        """Score berdasarkan kejelasan text content"""
        text = element_data.get('text', '').strip()
        
        if not text:
            # Beberapa elemen tidak butuh text (checkbox, icon button)
            role = element_data.get('role')
            if role in ['checkbox', 'radio', 'img']:
                return 0.7  # OK untuk tidak punya text
            return 0.1
        
        # Text terlalu pendek atau terlalu panjang
        if len(text) < 2:
            return 0.3
        if len(text) > 200:
            return 0.4  # Mungkin paragraph, bukan label
        
        # Text ideal untuk label/button
        if 2 <= len(text) <= 50:
            return 1.0
        
        return 0.6
    
    def _generate_role_label(self, element_data: Dict, 
                            accessible_name: Optional[str]) -> str:
        """
        Generate human-readable role label untuk elemen.
        Format: {role}_{identifier}
        
        Contoh: button_submit, link_homepage, input_email
        """
        role = element_data.get('role', 'unknown')
        
        # Cari identifier terbaik
        identifier = None
        
        # Priority 1: ID attribute
        if element_data.get('attributes', {}).get('id'):
            identifier = element_data['attributes']['id']
        
        # Priority 2: Name attribute
        elif element_data.get('attributes', {}).get('name'):
            identifier = element_data['attributes']['name']
        
        # Priority 3: Accessible name (cleaned)
        elif accessible_name:
            identifier = self._clean_identifier(accessible_name)
        
        # Priority 4: Text content (cleaned)
        elif element_data.get('text'):
            identifier = self._clean_identifier(element_data['text'])
        
        # Priority 5: Placeholder
        elif element_data.get('attributes', {}).get('placeholder'):
            identifier = self._clean_identifier(element_data['attributes']['placeholder'])
        
        # Fallback: gunakan elem_id
        if not identifier:
            identifier = element_data.get('id', 'unknown')
        
        return f"{role}_{identifier}"
    
    def _clean_identifier(self, text: str) -> str:
        """Clean text untuk dijadikan identifier yang valid"""
        # Ambil 30 karakter pertama, lowercase, replace spasi dengan underscore
        cleaned = text.strip()[:30].lower()
        cleaned = ''.join(c if c.isalnum() or c == '_' else '_' for c in cleaned)
        # Remove multiple underscores
        while '__' in cleaned:
            cleaned = cleaned.replace('__', '_')
        return cleaned.strip('_')


