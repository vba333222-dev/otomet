"""
Test struktur Phase 5 - Recalibration.
Verifikasi file, import, dan route terdaftar.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    print("Testing imports Phase 5...")
    try:
        from backend.recalibration.matcher import skor_teks, skor_posisi, recalibrate_batch
        print("✓ matcher imported")
        from backend.recalibration.threshold import ambil_threshold, validasi_threshold
        print("✓ threshold imported")
        from backend.recalibration.service import jalankan_recalibration, cek_gate_untuk_skenario
        print("✓ service imported")
        from backend.db.repositories import RecalibrationRepository
        print("✓ RecalibrationRepository imported")
        from backend.api import recalibration
        print("✓ recalibration router imported")
        from backend.app import app
        print("✓ FastAPI app imported")
        paths = [r.path for r in app.routes]
        assert "/api/recalibration/pages/{page_id}/run" in paths, "route run hilang"
        assert "/api/recalibration/scenarios/{scenario_id}/gate" in paths, "route gate hilang"
        print("✓ Route recalibration terdaftar")
        print("\n✅ All Phase 5 imports OK!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_structure():
    print("\nTesting file structure Phase 5...")
    required = [
        "backend/recalibration/__init__.py",
        "backend/recalibration/matcher.py",
        "backend/recalibration/threshold.py",
        "backend/recalibration/headless_runner.py",
        "backend/recalibration/service.py",
        "backend/db/repositories/recalibration_repo.py",
        "backend/api/recalibration.py",
        "backend/templates/recalibration/history.html",
        "backend/templates/recalibration/detail.html",
        "tests/test_matcher.py",
        "tests/test_threshold.py",
        "tests/test_recalibration.py",
        "verify_phase5_api.py",
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
    print("Phase 5 - Structure Test")
    print("=" * 60)
    a = test_imports()
    b = test_structure()
    print("\n" + "=" * 60)
    print("✅ PHASE 5 READY!" if (a and b) else "❌ PHASE 5 NOT READY")
    print("=" * 60)
