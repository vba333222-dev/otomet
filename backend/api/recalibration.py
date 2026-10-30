"""API Router untuk Recalibration (Phase 5 - gate all-or-nothing)."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from backend.db.repositories import (
    ClientRepository, PageRepository, RecalibrationRepository,
)
from backend.recalibration.threshold import validasi_threshold
from backend.recalibration.service import jalankan_recalibration, cek_gate_untuk_skenario

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


class FreshElemen(BaseModel):
    role: Optional[str] = ""
    role_label: Optional[str] = ""
    text: Optional[str] = ""
    bbox: Optional[dict] = None
    selectors: Optional[dict] = None


class RunModel(BaseModel):
    fresh_override: Optional[List[FreshElemen]] = None
    run_batch_id: Optional[str] = None


class ThresholdModel(BaseModel):
    threshold_similarity: float
    threshold_posisi: float
    threshold_tinggi_fallback: float


@router.post("/pages/{page_id}/run", response_model=dict)
async def run_recalibration(page_id: int, body: Optional[RunModel] = None):
    """Jalankan recalibration headless untuk satu halaman."""
    segar = None
    batch = None
    if body:
        batch = body.run_batch_id
        if body.fresh_override is not None:
            segar = [f.model_dump() for f in body.fresh_override]
    try:
        return await jalankan_recalibration(page_id, batch, segar)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/pages/{page_id}/history", response_model=dict)
async def history_json(page_id: int, limit: int = 20):
    """Riwayat recalibration satu halaman (JSON)."""
    page = await PageRepository().get_by_id(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    logs = await RecalibrationRepository().get_by_page(page_id, limit)
    return {"page_id": page_id, "logs": logs}


@router.get("/logs/{log_id}", response_model=dict)
async def get_log(log_id: int):
    """Detail satu log recalibration (JSON)."""
    log = await RecalibrationRepository().get_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.get("/scenarios/{scenario_id}/gate", response_model=dict)
async def gate_skenario(scenario_id: int):
    """Gate all-or-nothing untuk satu skenario."""
    try:
        return await cek_gate_untuk_skenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/clients/{client_id}/thresholds", response_model=dict)
async def simpan_threshold(client_id: int, body: ThresholdModel):
    """Setel manual threshold per klien (S4.3.1, bisa dari GUI)."""
    repo = ClientRepository()
    client = await repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    errors = validasi_threshold(
        body.threshold_similarity, body.threshold_posisi, body.threshold_tinggi_fallback)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    await repo.update_thresholds(
        client_id, body.threshold_similarity, body.threshold_posisi,
        body.threshold_tinggi_fallback)
    return await repo.get_by_id(client_id)


@router.get("/pages/{page_id}/view", response_class=HTMLResponse)
async def view_history(request: Request, page_id: int):
    """Riwayat recalibration satu halaman (HTML)."""
    page_repo = PageRepository()
    client_repo = ClientRepository()
    log_repo = RecalibrationRepository()
    page = await page_repo.get_by_id(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    client = await client_repo.get_by_id(page["client_id"])
    logs = await log_repo.get_by_page(page_id)
    terakhir = logs[0] if logs else None
    return templates.TemplateResponse(
        "recalibration/history.html",
        {"request": request, "page": page, "client": client,
         "logs": logs, "terakhir": terakhir},
    )


@router.get("/logs/{log_id}/view", response_class=HTMLResponse)
async def view_log(request: Request, log_id: int):
    """Detail satu log recalibration (HTML + diff)."""
    log_repo = RecalibrationRepository()
    page_repo = PageRepository()
    client_repo = ClientRepository()
    log = await log_repo.get_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    page = await page_repo.get_by_id(log["page_id"])
    client = await client_repo.get_by_id(page["client_id"]) if page else None
    hasil = log.get("hasil") or []
    ringkasan = {"total": len(hasil),
                 "calibrated": sum(1 for h in hasil if h.get("status") == "calibrated"),
                 "recalibrated": sum(1 for h in hasil if h.get("status") == "recalibrated"),
                 "blocked": sum(1 for h in hasil if h.get("status") == "blocked")}
    return templates.TemplateResponse(
        "recalibration/detail.html",
        {"request": request, "log": log, "page": page, "client": client,
         "hasil": hasil, "ringkasan": ringkasan},
    )
