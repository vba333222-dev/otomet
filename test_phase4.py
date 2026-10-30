"""
Test struktur Phase 4 - Input Skenario Manual.
Verifikasi file, import, dan route terdaftar.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    print("Testing imports Phase 4...")
    try:
        from backend.db.repositories import ScenarioRepository
        print("✓ ScenarioRepository imported")
        from backend.api import scenarios
        print("✓ scenarios router imported")
        from backend.app import app
        print("✓ FastAPI app imported")
        paths = [r.path for r in app.routes]
        assert "/api/scenarios/client/{client_id}" in paths, "route list JSON hilang"
        assert "/api/scenarios/validate" in paths, "route validate hilang"
        print("✓ Route skenario terdaftar")
        print("\n✅ All Phase 4 imports OK!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_structure():
    print("\nTesting file structure Phase 4...")
    required = [
        "backend/db/repositories/scenario_repo.py",
        "backend/api/scenarios.py",
        "backend/templates/scenarios/list.html",
        "backend/templates/scenarios/builder.html",
        "backend/templates/scenarios/detail.html",
        "tests/test_scenarios.py",
    ]
    ok = True
    for f in required:
        if (project_root / f).exists():
            print(f"✓ {f}")
        else:
            print(f"✗ {f} - NOT FOUND")
            ok = False
    return ok


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 4 - Structure Test")
    print("=" * 60)
    a = test_imports()
    b = test_structure()
    print("\n" + "=" * 60)
    print("✅ PHASE 4 READY!" if (a and b) else "❌ PHASE 4 NOT READY")
    print("=" * 60)
