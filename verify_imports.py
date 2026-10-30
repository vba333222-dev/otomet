"""
verify_imports.py - Verifikasi bahwa semua modul dapat di-import dengan benar.

Script sederhana untuk mengecek integritas kode tanpa dependencies eksternal penuh.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

print("🔍 Memverifikasi imports Phase 1...\n")

try:
    print("1. Import config...", end=" ")
    from config import (
        PLAYWRIGHT_TIMEOUT, WAIT_FOR_STABLE_DOM, 
        VIEWPORT_WIDTH, VIEWPORT_HEIGHT, OUTPUT_DIR
    )
    print("✅ OK")
    print(f"   - Viewport: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}")
    print(f"   - Output dir: {OUTPUT_DIR}")
except Exception as e:
    print(f"❌ GAGAL: {e}")
    sys.exit(1)

try:
    print("\n2. Import selector_gen...", end=" ")
    from scanner.selector_gen import SelectorGenerator, SelectorCandidate
    gen = SelectorGenerator()
    print("✅ OK")
    
    # Test basic functionality
    test_elem = {
        'tagName': 'button',
        'role': 'button',
        'text': 'Test',
        'attributes': {'id': 'test-btn'},
        'selector': 'button.test'
    }
    result = gen.generate_selectors(test_elem)
    print(f"   - Test selector generated: {result['primary']}")
    assert result['primary'] == '#test-btn', "Selector generation failed"
    
except Exception as e:
    print(f"❌ GAGAL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n3. Import scorer...", end=" ")
    from scanner.scorer import ElementScorer, ScoredElement
    scorer = ElementScorer()
    print("✅ OK")
    
    # Test basic scoring
    test_elem = {
        'id': 'elem_0',
        'tagName': 'button',
        'role': 'button',
        'text': 'Submit',
        'interactive': True,
        'bbox': {'x': 100, 'y': 200, 'width': 80, 'height': 40},
        'attributes': {'id': 'submit', 'disabled': False},
        'aria': {}
    }
    scored = scorer.score_element(test_elem, 'Submit', {'primary': '#submit', 'fallbacks': []})
    print(f"   - Test element scored: confidence={scored.confidence:.3f}")
    assert scored.confidence > 0.5, "Scoring failed"
    
except Exception as e:
    print(f"❌ GAGAL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n4. Cek dom_walker.js...", end=" ")
    dom_walker_path = Path(__file__).parent / 'backend' / 'scanner' / 'dom_walker.js'
    assert dom_walker_path.exists(), "dom_walker.js tidak ditemukan"
    with open(dom_walker_path, 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'extractDOMTree' in content, "dom_walker.js tidak valid"
        assert 'getBoundingBox' in content, "getBoundingBox function missing"
    print("✅ OK")
    print(f"   - Size: {len(content)} bytes")
except Exception as e:
    print(f"❌ GAGAL: {e}")
    sys.exit(1)

try:
    print("\n5. Cek struktur file...", end=" ")
    required_files = [
        'backend/config.py',
        'backend/scanner/__init__.py',
        'backend/scanner/dom_walker.js',
        'backend/scanner/axe_bridge.py',
        'backend/scanner/selector_gen.py',
        'backend/scanner/scorer.py',
        'backend/scanner/cli.py',
        'tests/test_scorer.py',
        'tests/test_selector_gen.py',
        'requirements.txt',
        'README.md'
    ]
    
    base = Path(__file__).parent
    missing = []
    for file_path in required_files:
        if not (base / file_path).exists():
            missing.append(file_path)
    
    if missing:
        print(f"❌ GAGAL")
        print("   File yang hilang:")
        for f in missing:
            print(f"   - {f}")
        sys.exit(1)
    
    print("✅ OK")
    print(f"   - Semua {len(required_files)} file utama ada")
    
except Exception as e:
    print(f"❌ GAGAL: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ VERIFIKASI SUKSES - Phase 1 siap digunakan!")
print("="*60)
print("\nNext steps:")
print("1. Tunggu instalasi dependencies selesai (pip install -r requirements.txt)")
print("2. Install Playwright browsers: playwright install chromium")
print("3. Jalankan unit tests: pytest tests/ -v")
print("4. Test dengan website asli: python backend/scanner/cli.py https://example.com")
