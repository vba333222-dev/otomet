"""
API Router untuk Clients
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List

from backend.db.database import db
from backend.db.repositories import ClientRepository

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

@router.get("/", response_model=List[dict])
async def list_clients():
    """List semua clients (JSON API)"""
    repo = ClientRepository()
    clients = await repo.get_all()
    return clients

@router.get("/view", response_class=HTMLResponse)
async def view_clients(request: Request):
    """View clients (HTML dengan htmx)"""
    repo = ClientRepository()
    clients = await repo.get_all()
    return templates.TemplateResponse(
        "clients/list.html",
        {"request": request, "clients": clients}
    )

@router.get("/{client_id}", response_model=dict)
async def get_client(client_id: int):
    """Get client by ID (JSON API)"""
    repo = ClientRepository()
    client = await repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.get("/{client_id}/view", response_class=HTMLResponse)
async def view_client_detail(request: Request, client_id: int):
    """View client detail (HTML dengan htmx)"""
    from backend.db.repositories import PageRepository
    
    client_repo = ClientRepository()
    page_repo = PageRepository()
    
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    pages = await page_repo.get_by_client(client_id)
    
    return templates.TemplateResponse(
        "clients/detail.html",
        {"request": request, "client": client, "pages": pages}
    )
