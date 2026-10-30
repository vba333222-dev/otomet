"""
Test struktur Phase 6 - Orchestrator.
Verifikasi file, import, dan route terdaftar.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    print("Testing imports Phase 6...")
    try:
        from backend.orchestrator.device_pool import (
            daftar_perangkat_adb, register_device, heartbeat_device,
            health_check_device, health_check_semua, ambil_device_idle_fifo,
        )
        print("✓ device_pool imported")
        from backend.orchestrator.session_manager import (
            buat_sesi_pair, tugaskan_skenario, akhiri_sesi,
        )
        print("✓ session_manager imported")
        from backend.orchestrator.broadcast import (
            safety_check_broadcast, jalankan_broadcast, ALLOWED_BROADCAST,
        )
        print("✓ broadcast imported")
        from backend.db.repositories import (
            DeviceRepository, SessionRepository,
            AssignmentRepository, BroadcastRepository,
        )
        print("✓ repos imported")
        from backend.api import orchestrator, broadcast
        print("✓ routers imported")
        from backend.app import app
        print("✓ FastAPI app imported")
        paths = [r.path for r in app.routes]
        wajib = [
            "/api/orchestrator/devices",
            "/api/orchestrator/devices/view",
            "/api/orchestrator/devices/{device_id}",
            "/api/orchestrator/devices/health-check",
            "/api/orchestrator/sessions",
            "/api/orchestrator/sessions/{session_id}/assign",
            "/api/orchestrator/sessions/{session_id}/finish",
            "/api/orchestrator/sessions/{session_id}/cancel",
            "/api/broadcast/check",
            "/api/broadcast/run",
            "/api/broadcast/{broadcast_id}",
        ]
        for p in wajib:
            assert p in paths, f"route {p} hilang"
        print("✓ Route orchestrator+broadcast terdaftar")
        assert app.openapi() is not None
        print("✓ OpenAPI terbangun")
        print("\n✅ All Phase 6 imports OK!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_structure():
    print("\nTesting file structure Phase 6...")
    required = [
        "backend/orchestrator/__init__.py",
        "backend/orchestrator/device_pool.py",
        "backend/orchestrator/session_manager.py",
        "backend/orchestrator/broadcast.py",
        "backend/db/repositories/device_repo.py",
        "backend/db/repositories/session_repo.py",
        "backend/api/orchestrator.py",
        "backend/api/broadcast.py",
        "backend/templates/devices/list.html",
        "backend/templates/sessions/list.html",
        "backend/templates/sessions/detail.html",
        "backend/templates/broadcast/panel.html",
        "tests/test_device_pool.py",
        "tests/test_sessions.py",
        "tests/test_broadcast.py",
        "verify_phase6_api.py",
        "docs/PHASE6-NOTES.md",
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
    print("Phase 6 - Structure Test")
    print("=" * 60)
    a = test_imports()
    b = test_structure()
    print("\n" + "=" * 60)
    print("✅ PHASE 6 READY!" if (a and b) else "❌ PHASE 6 NOT READY")
    print("=" * 60)
