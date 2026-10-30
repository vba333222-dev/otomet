"""API Router untuk Pelaporan Phase 8 - laporan + tren + export PDF/Excel."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from io import BytesIO

from backend.reporting.service import laporan_sesi, laporan_klien, tren_klien
from backend.reporting.export_pdf import buat_pdf_sesi, buat_pdf_klien
from backend.reporting.export_xlsx import buat_xlsx_sesi, buat_xlsx_klien
from backend.db.repositories import ClientRepository, SessionRepository

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/sessions/{session_id}/summary", response_model=dict)
async def ringkasan_sesi_json(session_id: int):
    """Ringkasan JSON satu sesi (tanpa ADB)."""
    try:
        return await laporan_sesi(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/clients/{client_id}/summary", response_model=dict)
async def ringkasan_klien_json(client_id: int):
    """Ringkasan JSON satu klien + tren."""
    try:
        return await laporan_klien(client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/clients/{client_id}/trend", response_model=dict)
async def tren_klien_json(client_id: int, limit: int = 20):
    """Tren pass-rate per sesi (untuk Chart.js)."""
    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"client_id": client_id, "tren": await tren_klien(client_id, limit)}


def _nama_file(prefix: str, nama: str, ext: str) -> str:
    aman = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (nama or "lap"))
    return f"{prefix}_{aman}.{ext}"


@router.get("/sessions/{session_id}/pdf")
async def export_pdf_sesi(session_id: int):
    """Export PDF laporan satu sesi (file valid, bisa dibuka)."""
    try:
        lap = await laporan_sesi(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = buat_pdf_sesi(lap)
    nama = _nama_file("laporan-sesi", str(session_id), "pdf")
    return StreamingResponse(BytesIO(data), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename={nama}"})


@router.get("/sessions/{session_id}/xlsx")
async def export_xlsx_sesi(session_id: int):
    """Export Excel laporan satu sesi."""
    try:
        lap = await laporan_sesi(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = buat_xlsx_sesi(lap)
    nama = _nama_file("laporan-sesi", str(session_id), "xlsx")
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nama}"})


@router.get("/clients/{client_id}/pdf")
async def export_pdf_klien(client_id: int):
    """Export PDF laporan satu klien."""
    try:
        lap = await laporan_klien(client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = buat_pdf_klien(lap)
    nama = _nama_file("laporan-klien", str(client_id), "pdf")
    return StreamingResponse(BytesIO(data), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename={nama}"})


@router.get("/clients/{client_id}/xlsx")
async def export_xlsx_klien(client_id: int):
    """Export Excel laporan satu klien."""
    try:
        lap = await laporan_klien(client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    data = buat_xlsx_klien(lap)
    nama = _nama_file("laporan-klien", str(client_id), "xlsx")
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nama}"})


@router.get("/sessions/{session_id}/view", response_class=HTMLResponse)
async def view_laporan_sesi(request: Request, session_id: int):
    """HTML laporan satu sesi + tombol export."""
    sesi = await SessionRepository().get_by_id(session_id)
    if not sesi:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        lap = await laporan_sesi(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return templates.TemplateResponse(
        "reports/session.html", {"request": request, "lap": lap})


@router.get("/clients/{client_id}/view", response_class=HTMLResponse)
async def view_laporan_klien(request: Request, client_id: int):
    """HTML laporan satu klien + tren Chart.js + tombol export."""
    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    try:
        lap = await laporan_klien(client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return templates.TemplateResponse(
        "reports/client.html", {"request": request, "lap": lap})
