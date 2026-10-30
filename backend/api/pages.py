"""
API Router untuk Pages
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List

from backend.db.database import db
from backend.db.repositories import PageRepository, ClientRepository

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

@router.get("/{page_id}", response_model=dict)
async def get_page(page_id: int):
    """Get page by ID (JSON API)"""
    repo = PageRepository()
    page = await repo.get_by_id(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.get("/{page_id}/view", response_class=HTMLResponse)
async def view_page_detail(request: Request, page_id: int):
    """View page detail dengan elements (HTML dengan htmx)"""
    from backend.db.repositories import ElementRepository
    
    page_repo = PageRepository()
    client_repo = ClientRepository()
    element_repo = ElementRepository()
    
    page = await page_repo.get_by_id(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    client = await client_repo.get_by_id(page['client_id'])
    elements = await element_repo.get_by_page(page_id)
    
    # Group by confidence level
    high_conf = [e for e in elements if e['confidence'] >= 0.8]
    medium_conf = [e for e in elements if 0.6 <= e['confidence'] < 0.8]
    low_conf = [e for e in elements if e['confidence'] < 0.6]
    
    return templates.TemplateResponse(
        "pages/detail.html",
        {
            "request": request,
            "page": page,
            "client": client,
            "elements": elements,
            "high_conf": high_conf,
            "medium_conf": medium_conf,
            "low_conf": low_conf,
            "total": len(elements)
        }
    )
