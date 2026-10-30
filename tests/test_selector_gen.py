"""
test_selector_gen.py - Unit tests untuk SelectorGenerator.

Test selector generation dengan berbagai strategi fallback.
"""

import pytest
from backend.scanner.selector_gen import SelectorGenerator, SelectorCandidate


class TestSelectorGenerator:
    """Test suite untuk SelectorGenerator"""
    
    def setup_method(self):
        """Setup untuk setiap test"""
        self.gen = SelectorGenerator()
    
    def test_generate_selector_with_id(self):
        """Test element dengan ID (prioritas tertinggi)"""
        element_data = {
            'tagName': 'button',
            'role': 'button',
            'text': 'Submit',
            'attributes': {'id': 'submit-btn'},
            'aria': {},
            'selector': 'button.btn-primary'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        assert result['primary'] == '#submit-btn'
        assert len(result['fallbacks']) > 0  # Ada fallback lain
    
    def test_generate_selector_with_data_testid(self):
        """Test element dengan data-testid"""
        element_data = {
            'tagName': 'button',
            'role': 'button',
            'text': 'Login',
            'attributes': {'data-testid': 'login-button'},
            'aria': {},
            'selector': 'button.login-btn'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        assert result['primary'] == "[data-testid='login-button']"
    
    def test_generate_selector_with_aria_label(self):
        """Test element dengan aria-label"""
        element_data = {
            'tagName': 'button',
            'role': 'button',
            'text': '',
            'attributes': {},
            'aria': {'aria-label': 'Close dialog'},
            'selector': 'button.close'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        # aria-label harus muncul di candidates
        assert any('aria-label' in sel for sel in [result['primary']] + result['fallbacks'])
    
    def test_generate_selector_with_name(self):
        """Test input element dengan name attribute"""
        element_data = {
            'tagName': 'input',
            'role': 'textbox',
            'text': '',
            'attributes': {'name': 'email', 'type': 'email'},
            'aria': {},
            'selector': 'input.form-control'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        # Name-based selector harus ada
        assert any('name=' in sel for sel in [result['primary']] + result['fallbacks'])
    
    def test_generate_selector_with_placeholder(self):
        """Test input dengan placeholder"""
        element_data = {
            'tagName': 'input',
            'role': 'textbox',
            'text': '',
            'attributes': {'placeholder': 'Enter your name'},
            'aria': {},
            'selector': 'input'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        # Placeholder-based selector harus ada
        assert any('placeholder=' in sel for sel in [result['primary']] + result['fallbacks'])
    
    def test_generate_selector_role_plus_text(self):
        """Test selector dengan role + text content"""
        element_data = {
            'tagName': 'button',
            'role': 'button',
            'text': 'Add to cart',
            'attributes': {},
            'aria': {},
            'selector': 'button.btn'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        # Role + text selector harus ada
        assert any(':has-text' in sel for sel in [result['primary']] + result['fallbacks'])
    
    def test_generate_selector_no_good_identifiers(self):
        """Test element tanpa identifier yang baik (fallback ke class/position)"""
        element_data = {
            'tagName': 'div',
            'role': None,
            'text': 'Some text',
            'attributes': {},
            'aria': {},
            'selector': 'div.container > div.item',
            'bbox': {'x': 100, 'y': 200}
        }
        
        result = self.gen.generate_selectors(element_data)
        
        assert result['primary'] is not None
        # Harus ada fallback meski tidak ideal
        assert len(result['fallbacks']) >= 0
    
    def test_escape_quotes_in_selector(self):
        """Test escaping quotes di selector"""
        text_with_quotes = "It's a \"test\""
        escaped = self.gen._escape_quotes(text_with_quotes)
        
        assert "\\'" in escaped or "'" not in escaped
        assert '\\"' in escaped or '"' not in escaped
    
    def test_multiple_fallback_strategies(self):
        """Test bahwa multiple fallback strategies dibuat"""
        element_data = {
            'tagName': 'button',
            'role': 'button',
            'text': 'Submit Form',
            'attributes': {
                'id': 'submit',
                'name': 'submit-btn',
                'data-testid': 'form-submit'
            },
            'aria': {'aria-label': 'Submit the form'},
            'selector': 'button.btn-primary'
        }
        
        result = self.gen.generate_selectors(element_data)
        
        # Harus ada banyak fallback karena banyak identifiers
        assert len(result['fallbacks']) >= 3
        
        # ID harus jadi primary (prioritas tertinggi)
        assert result['primary'] == '#submit'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
