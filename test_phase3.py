"""
Test import dan struktur Phase 3 Dashboard
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test all required imports"""
    print("Testing imports...")
    
    try:
        # Test FastAPI imports
        import fastapi
        print("✓ FastAPI imported")
        
        import uvicorn
        print("✓ Uvicorn imported")
        
        import jinja2
        print("✓ Jinja2 imported")
        
        # Test backend imports
        from backend.db.database import db
        print("✓ Database module imported")
        
        from backend.db.repositories import ClientRepository, PageRepository, ElementRepository
        print("✓ Repository modules imported")
        
        # Test API imports
        from backend.api import clients, pages, elements
        print("✓ API modules imported")
        
        # Test app creation
        from backend.app import app
        print("✓ FastAPI app created")
        
        print("\n✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("\nPlease install required packages:")
        print("  pip install fastapi uvicorn[standard] jinja2 python-multipart")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def test_structure():
    """Test file structure"""
    print("\nTesting file structure...")
    
    required_files = [
        "backend/app.py",
        "backend/api/__init__.py",
        "backend/api/clients.py",
        "backend/api/pages.py",
        "backend/api/elements.py",
        "backend/templates/base.html",
        "backend/templates/index.html",
        "backend/templates/clients/list.html",
        "backend/templates/clients/detail.html",
        "backend/templates/pages/detail.html",
        "backend/templates/pages/_element_card.html",
        "backend/templates/elements/detail.html",
        "backend/static/style.css",
        "run_dashboard.py",
    ]
    
    all_exist = True
    for filepath in required_files:
        full_path = project_root / filepath
        if full_path.exists():
            print(f"✓ {filepath}")
        else:
            print(f"✗ {filepath} - NOT FOUND")
            all_exist = False
    
    if all_exist:
        print("\n✅ All required files exist!")
    else:
        print("\n❌ Some files are missing")
    
    return all_exist

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 3 - Dashboard Structure Test")
    print("=" * 60)
    
    imports_ok = test_imports()
    structure_ok = test_structure()
    
    print("\n" + "=" * 60)
    if imports_ok and structure_ok:
        print("✅ PHASE 3 READY!")
        print("\nTo start the dashboard, run:")
        print("  python run_dashboard.py")
        print("\nOr directly:")
        print("  uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000")
    else:
        print("❌ PHASE 3 NOT READY - Please fix errors above")
    print("=" * 60)
