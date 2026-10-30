"""API Router untuk Broadcast Phase 6 - safety check + audit trail."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from backend.db.repositories import (
    ClientRepository, DeviceRepository, BroadcastRepository,
)
from backend.orchestrator.broadcast import (
    safety_check_broadcast, jalankan_broadcast, ALLOWED_BROADCAST,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


class BroadcastModel(BaseModel):
    client_id: int
    action_type: str
    target: Optional[str] = ""
    device_ids: Optional[List[int]] = None


@router.post("/check", response_model=dict)
async def cek_broadcast(body: BroadcastModel):
    try:
        return await safety_check_broadcast(
            body.client_id, body.action_type, body.target or "",
            body.device_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run", response_model=dict)
async def run_broadcast(body: BroadcastModel):
    try:
        return await jalankan_broadcast(
            body.client_id, body.action_type, body.target or "",
            body.device_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clients/{client_id}/view", response_class=HTMLResponse)
async def view_broadcast(request: Request, client_id: int):
    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    devices = await DeviceRepository().get_all()
    riwayat = await BroadcastRepository().get_terakhir(limit=10)
    return templates.TemplateResponse(
        "broadcast/panel.html",
        {"request": request, "client": client, "devices": devices,
         "riwayat": riwayat, "allowed": sorted(ALLOWED_BROADCAST)},
    )


@router.get("/{broadcast_id}", response_model=dict)
async def get_broadcast(broadcast_id: int):
    b = await BroadcastRepository().get_by_id(broadcast_id)
    if not b:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return b
