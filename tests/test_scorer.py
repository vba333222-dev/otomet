"""
test_scorer.py - Unit tests untuk ElementScorer.

Test scoring logic untuk berbagai tipe elemen dan edge cases.
"""

import pytest
from backend.scanner.scorer import ElementScorer


class TestElementScorer:
    """Test suite untuk ElementScorer"""
    
    def setup_method(self):
        """Setup untuk setiap test"""
        self.scorer = ElementScorer()
    
    def test_score_button_with_id(self):
        """Test scoring button dengan ID (confidence tinggi)"""
        element_data = {
            'id': 'elem_0',
            'tagName': 'button',
            'role': 'button',
            'text': 'Submit',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 80, 'height': 40},
            'attributes': {'id': 'submit-btn', 'disabled': False},
            'aria': {}
        }
        
        selector_info = {
            'primary': '#submit-btn',
            'fallbacks': []
        }
        
        result = self.scorer.score_element(element_data, 'Submit', selector_info)
        
        assert result.confidence >= 0.8  # Harus high confidence
        assert result.role_label == 'button_submit-btn'
        assert result.score_breakdown['role_semantic'] == 1.0
        assert result.score_breakdown['interactivity'] == 1.0
    
    def test_score_disabled_button(self):
        """Test button yang disabled (score lebih rendah)"""
        element_data = {
            'id': 'elem_1',
            'tagName': 'button',
            'role': 'button',
            'text': 'Disabled Button',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 80, 'height': 40},
            'attributes': {'disabled': True},
            'aria': {}
        }
        
        result = self.scorer.score_element(element_data, 'Disabled Button', None)
        
        # Interactivity score harus rendah karena disabled
        assert result.score_breakdown['interactivity'] == 0.3
        assert result.confidence < 0.8  # Tidak high confidence
    
    def test_score_input_with_placeholder(self):
        """Test input field dengan placeholder"""
        element_data = {
            'id': 'elem_2',
            'tagName': 'input',
            'role': 'textbox',
            'text': '',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 200, 'height': 30},
            'attributes': {
                'name': 'email',
                'type': 'email',
                'placeholder': 'Enter your email',
                'disabled': False
            },
            'aria': {}
        }
        
        selector_info = {
            'primary': 'input[name="email"]',
            'fallbacks': []
        }
        
        result = self.scorer.score_element(element_data, None, selector_info)
        
        assert result.confidence >= 0.6  # Minimal medium confidence
        assert 'email' in result.role_label.lower()
    
    def test_score_link_with_aria_label(self):
        """Test link dengan aria-label (good accessibility)"""
        element_data = {
            'id': 'elem_3',
            'tagName': 'a',
            'role': 'link',
            'text': 'Read more',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 100, 'height': 20},
            'attributes': {'href': '/article'},
            'aria': {'aria-label': 'Read more about this topic'}
        }
        
        result = self.scorer.score_element(
            element_data, 
            'Read more about this topic',
            None
        )
        
        assert result.score_breakdown['accessible_name'] >= 0.8
        assert result.confidence >= 0.7
    
    def test_score_element_without_text(self):
        """Test elemen tanpa text (icon button)"""
        element_data = {
            'id': 'elem_4',
            'tagName': 'button',
            'role': 'button',
            'text': '',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 40, 'height': 40},
            'attributes': {'id': 'close-btn'},
            'aria': {'aria-label': 'Close'}
        }
        
        result = self.scorer.score_element(element_data, 'Close', None)
        
        # Acceptable karena ada aria-label
        assert result.score_breakdown['accessible_name'] >= 0.8
        assert result.role_label == 'button_close-btn'
    
    def test_score_very_small_element(self):
        """Test elemen yang terlalu kecil (mungkin hidden)"""
        element_data = {
            'id': 'elem_5',
            'tagName': 'div',
            'role': 'button',
            'text': 'X',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 5, 'height': 5},
            'attributes': {},
            'aria': {}
        }
        
        result = self.scorer.score_element(element_data, None, None)
        
        # Visual prominence score harus rendah
        assert result.score_breakdown['visual_prominence'] <= 0.3
    
    def test_score_position_based_selector(self):
        """Test elemen dengan selector berbasis posisi (rapuh)"""
        element_data = {
            'id': 'elem_6',
            'tagName': 'button',
            'role': 'button',
            'text': 'Click me',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 80, 'height': 40},
            'attributes': {},
            'aria': {}
        }
        
        selector_info = {
            'primary': 'button:nth-of-type(3)',
            'fallbacks': []
        }
        
        result = self.scorer.score_element(element_data, None, selector_info)
        
        # Selector stability harus rendah (checked - ini yang penting)
        assert result.score_breakdown['selector_stability'] <= 0.3
        # Overall confidence bisa tinggi jika faktor lain bagus (role, interactive, text, visual)
        # Jadi kita hanya pastikan selector stability yang rendah
        assert result.confidence >= 0.5  # Masih reasonable karena faktor lain bagus
    
    def test_generate_role_label_with_special_chars(self):
        """Test role label generation dengan karakter spesial"""
        element_data = {
            'id': 'elem_7',
            'tagName': 'button',
            'role': 'button',
            'text': 'Submit & Continue →',
            'interactive': True,
            'bbox': {'x': 100, 'y': 200, 'width': 80, 'height': 40},
            'attributes': {},
            'aria': {}
        }
        
        result = self.scorer.score_element(element_data, None, None)
        
        # Role label harus di-sanitize
        assert result.role_label.startswith('button_')
        assert '&' not in result.role_label
        assert '→' not in result.role_label
    
    def test_score_element_very_long_text(self):
        """Test elemen dengan text sangat panjang (paragraph)"""
        long_text = "This is a very long text " * 20  # 500+ chars
        element_data = {
            'id': 'elem_8',
            'tagName': 'p',
            'role': None,
            'text': long_text,
            'interactive': False,
            'bbox': {'x': 100, 'y': 200, 'width': 300, 'height': 200},
            'attributes': {},
            'aria': {}
        }
        
        result = self.scorer.score_element(element_data, None, None)
        
        # Text clarity score harus rendah untuk text terlalu panjang
        assert result.score_breakdown['text_clarity'] <= 0.5
        # Overall confidence rendah karena bukan interaktif + tidak ada role
        assert result.confidence < 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

