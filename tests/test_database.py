"""
Unit tests untuk Database & Repositories (Phase 2)
"""
import pytest
import pytest_asyncio
import asyncio
import os
from pathlib import Path

from backend.db.database import Database
from backend.db.repositories import ClientRepository, PageRepository, ElementRepository

# Test database path
TEST_DB_PATH = "test_otomet.db"

@pytest_asyncio.fixture
async def test_db():
    """Fixture untuk test database"""
    # Create test database
    db = Database(TEST_DB_PATH)
    await db.connect()
    await db.initialize_schema()
    
    yield db
    
    # Cleanup
    await db.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    # Remove WAL files
    for ext in ['-wal', '-shm']:
        wal_file = f"{TEST_DB_PATH}{ext}"
        if os.path.exists(wal_file):
            os.remove(wal_file)


class TestClientRepository:
    """Test suite untuk ClientRepository"""
    
    @pytest.mark.asyncio
    async def test_create_client(self, test_db):
        """Test create client baru"""
        repo = ClientRepository()
        
        client_id = await repo.create(
            nama="Test Client",
            base_url="https://example.com"
        )
        
        assert client_id > 0
        
        # Verify
        client = await repo.get_by_id(client_id)
        assert client is not None
        assert client['nama'] == "Test Client"
        assert client['base_url'] == "https://example.com"
        assert client['threshold_similarity'] == 0.85
    
    @pytest.mark.asyncio
    async def test_get_by_nama(self, test_db):
        """Test get client by nama"""
        repo = ClientRepository()
        
        await repo.create(nama="Unique Client", base_url="https://test.com")
        
        client = await repo.get_by_nama("Unique Client")
        assert client is not None
        assert client['nama'] == "Unique Client"
    
    @pytest.mark.asyncio
    async def test_update_thresholds(self, test_db):
        """Test update threshold dinamis"""
        repo = ClientRepository()
        
        client_id = await repo.create(nama="Test", base_url="https://test.com")
        
        # Update thresholds
        await repo.update_thresholds(
            client_id,
            threshold_similarity=0.90,
            threshold_posisi=0.95
        )
        
        # Verify
        client = await repo.get_by_id(client_id)
        assert client['threshold_similarity'] == 0.90
        assert client['threshold_posisi'] == 0.95

class TestPageRepository:
    """Test suite untuk PageRepository"""
    
    @pytest.mark.asyncio
    async def test_create_page(self, test_db):
        """Test create page"""
        client_repo = ClientRepository()
        page_repo = PageRepository()
        
        # Create client first
        client_id = await client_repo.create(nama="Test", base_url="https://test.com")
        
        # Create page
        page_id = await page_repo.create(client_id, "https://test.com/page1")
        
        assert page_id > 0
        
        # Verify
        page = await page_repo.get_by_id(page_id)
        assert page is not None
        assert page['url'] == "https://test.com/page1"
        assert page['status'] == 'pending'
    
    @pytest.mark.asyncio
    async def test_update_status(self, test_db):
        """Test update page status"""
        client_repo = ClientRepository()
        page_repo = PageRepository()
        
        client_id = await client_repo.create(nama="Test", base_url="https://test.com")
        page_id = await page_repo.create(client_id, "https://test.com/page1")
        
        # Update status
        await page_repo.update_status(page_id, 'analyzed')
        
        # Verify
        page = await page_repo.get_by_id(page_id)
        assert page['status'] == 'analyzed'
        assert page['last_analyzed_at'] is not None

class TestElementRepository:
    """Test suite untuk ElementRepository"""
    
    @pytest.mark.asyncio
    async def test_create_element(self, test_db):
        """Test create element"""
        client_repo = ClientRepository()
        page_repo = PageRepository()
        element_repo = ElementRepository()
        
        # Setup
        client_id = await client_repo.create(nama="Test", base_url="https://test.com")
        page_id = await page_repo.create(client_id, "https://test.com/page1")
        
        # Create element
        element_id = await element_repo.create(
            page_id=page_id,
            role_label="button_submit",
            selectors={"primary": "#submit", "fallbacks": ["button[type='submit']"]},
            text_snapshot="Submit",
            bbox={"x": 100, "y": 200, "width": 80, "height": 40},
            confidence=0.95,
            approved=True
        )
        
        assert element_id > 0
        
        # Verify
        element = await element_repo.get_by_id(element_id)
        assert element is not None
        assert element['role_label'] == "button_submit"
        assert element['confidence'] == 0.95
        assert element['approved'] == 1
        assert 'primary' in element['selectors']
    
    @pytest.mark.asyncio
    async def test_bulk_create(self, test_db):
        """Test bulk create elements"""
        client_repo = ClientRepository()
        page_repo = PageRepository()
        element_repo = ElementRepository()
        
        # Setup
        client_id = await client_repo.create(nama="Test", base_url="https://test.com")
        page_id = await page_repo.create(client_id, "https://test.com/page1")
        
        # Bulk create
        elements = [
            {
                'page_id': page_id,
                'role_label': f"button_{i}",
                'selectors': {"primary": f"#btn{i}"},
                'text_snapshot': f"Button {i}",
                'bbox': {"x": i*10, "y": i*10, "width": 50, "height": 30},
                'confidence': 0.8 + (i * 0.01),
                'approved': True
            }
            for i in range(5)
        ]
        
        count = await element_repo.bulk_create(elements)
        assert count == 5
        
        # Verify
        all_elements = await element_repo.get_by_page(page_id)
        assert len(all_elements) == 5
    
    @pytest.mark.asyncio
    async def test_get_high_confidence(self, test_db):
        """Test get elements dengan confidence tinggi"""
        client_repo = ClientRepository()
        page_repo = PageRepository()
        element_repo = ElementRepository()
        
        # Setup
        client_id = await client_repo.create(nama="Test", base_url="https://test.com")
        page_id = await page_repo.create(client_id, "https://test.com/page1")
        
        # Create elements dengan berbagai confidence
        elements = [
            {
                'page_id': page_id,
                'role_label': f"elem_{i}",
                'selectors': {"primary": f"#e{i}"},
                'text_snapshot': f"Element {i}",
                'bbox': {"x": 0, "y": 0, "width": 10, "height": 10},
                'confidence': conf,
                'approved': False
            }
            for i, conf in enumerate([0.95, 0.85, 0.75, 0.60, 0.50])
        ]
        
        await element_repo.bulk_create(elements)
        
        # Get high confidence (>= 0.8)
        high_conf = await element_repo.get_high_confidence(page_id, threshold=0.8)
        assert len(high_conf) == 2  # 0.95 dan 0.85
        assert all(e['confidence'] >= 0.8 for e in high_conf)

