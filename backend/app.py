"""FastAPI application untuk Dashboard Phase 3"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from contextlib import asynccontextmanager

from backend.api import clients, pages, elements, scenarios, recalibration, orchestrator, broadcast, runs, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB schema saat startup (idempotent, CREATE IF NOT EXISTS).
    # Agar dashboard tetap bisa dibuka walau otomet.db belum ada / korup partial.
    try:
        from backend.db.database import db
        await db.connect()
        await db.initialize_schema()
    except Exception as e:
        # Jangan gagalkan startup — halaman tetap render, API akan 500 parsial.
        print(f"[startup] init DB gagal (tetap jalan): {e}", flush=True)
    yield
    try:
        from backend.db.database import db
        await db.close()
    except Exception:
        pass

# Inisialisasi FastAPI
app = FastAPI(
    title="Otomet Dashboard",
    description="Dashboard untuk Web Automation & Appium System",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup templates dan static files
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# FIX gagal-terbuka: StaticFiles(mount) crash bila folder tak ada.
# Pastikan selalu ada sebelum mount.
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
app.include_router(pages.router, prefix="/api/pages", tags=["pages"])
app.include_router(elements.router, prefix="/api/elements", tags=["elements"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(recalibration.router, prefix="/api/recalibration", tags=["recalibration"])
app.include_router(orchestrator.router, prefix="/api/orchestrator", tags=["orchestrator"])
app.include_router(broadcast.router, prefix="/api/broadcast", tags=["broadcast"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - Dashboard utama"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "phase": "8"}


@app.get("/ready")
async def readiness_check():
    """Readiness: DB bisa dibuka + skema inti ada. 503 bila belum siap."""
    from fastapi.responses import JSONResponse
    try:
        from backend.db.database import db
        await db.connect()
        rows = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'")
        nama = {str(dict(r).get("name")) for r in (rows or [])}
        wajib = {"devices", "clients", "sessions",
                 "scenario_assignments", "runs", "test_data_pool"}
        kurang = sorted(wajib - nama)
        if kurang:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready",
                         "alasan": f"Tabel kurang: {kurang}"})
        return {"status": "ready", "phase": "8", "tables": sorted(nama)}
    except Exception as e:
        from fastapi.responses import JSONResponse as _JR
        return _JR(status_code=503,
                   content={"status": "not_ready", "alasan": str(e)})

