"""
API Router untuk Elements
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List

from backend.db.database import db
from backend.db.repositories import ElementRepository

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

@router.get("/{element_id}", response_model=dict)
async def get_element(element_id: int):
    """Get element by ID (JSON API)"""
    repo = ElementRepository()
    element = await repo.get_by_id(element_id)
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    return element

@router.get("/{element_id}/view", response_class=HTMLResponse)
async def view_element_detail(request: Request, element_id: int):
    """View element detail (HTML dengan htmx)"""
    repo = ElementRepository()
    element = await repo.get_by_id(element_id)
    
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    
    return templates.TemplateResponse(
        "elements/detail.html",
        {"request": request, "element": element}
    )

@router.post("/{element_id}/approve")
async def approve_element(element_id: int):
    """Approve element untuk digunakan dalam skenario"""
    repo = ElementRepository()
    element = await repo.get_by_id(element_id)
    
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    
    await repo.approve(element_id)
    
    return {"status": "success", "element_id": element_id, "approved": True}
