"""API Router untuk Scenarios (Phase 4 - Input Skenario Manual)."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

from backend.db.repositories import ClientRepository, PageRepository, ScenarioRepository
from backend.db.repositories.scenario_repo import ALLOWED_ACTIONS

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


class StepModel(BaseModel):
    action: str
    role_label: str
    page_id: Optional[int] = None
    params: Optional[dict] = None


class ScenarioCreateModel(BaseModel):
    client_id: int
    nama_fungsi: str
    steps: List[StepModel]


class ScenarioVersionModel(BaseModel):
    steps: List[StepModel]


class ScenarioValidateModel(BaseModel):
    client_id: int
    steps: List[StepModel]


class RollbackModel(BaseModel):
    target_versi: int


def _normalisasi_steps(steps: List[StepModel]) -> list:
    hasil = []
    for s in steps:
        hasil.append({
            "action": s.action.strip(),
            "role_label": s.role_label.strip(),
            "page_id": s.page_id,
            "params": s.params or {},
        })
    return hasil
async def _validasi_steps(client_id: int, steps_raw: list) -> list:
    """Validasi fail-closed, return list error (kosong = valid)."""
    errors = []
    if not steps_raw:
        return ["Skenario kosong: tambahkan minimal 1 step."]
    scenario_repo = ScenarioRepository()
    page_repo = PageRepository()
    try:
        approved_roles = set(await scenario_repo.get_approved_role_labels(client_id))
    except Exception:
        approved_roles = set()
    for idx, step in enumerate(steps_raw, start=1):
        if not isinstance(step, dict):
            errors.append(f"Step {idx}: format tidak valid.")
            continue
        action = (step.get("action") or "").strip()
        role_label = (step.get("role_label") or "").strip()
        params = step.get("params") or {}
        page_id = step.get("page_id")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"Step {idx}: aksi '{action}' tidak dikenal.")
            continue
        # open_url (Phase 7-real): navigasi Chrome, tak butuh role_label.
        # Wajib params.url, lewati cek approved role, lalu lanjut step berikut.
        if action == "open_url":
            url = str((params or {}).get("url") or (params or {}).get("text") or "").strip()
            if not url:
                errors.append(f"Step {idx} (open_url): params.url wajib diisi.")
            if not isinstance(params, dict):
                errors.append(f"Step {idx}: params harus objek.")
                params = {}
            if page_id is not None:
                try:
                    page = await page_repo.get_by_id(int(page_id))
                except (ValueError, TypeError):
                    page = None
                if not page:
                    errors.append(f"Step {idx}: page_id {page_id} tidak ditemukan.")
                elif page["client_id"] != client_id:
                    errors.append(f"Step {idx}: page bukan milik client ini.")
            continue
        if not role_label:
            errors.append(f"Step {idx}: role_label wajib diisi.")
            continue
        if role_label not in approved_roles:
            errors.append(f"Step {idx}: role '{role_label}' belum tervalidasi. Diblokir by-design.")
        if not isinstance(params, dict):
            errors.append(f"Step {idx}: params harus objek.")
            params = {}
        if action == "fill" and not str(params.get("text") or "").strip():
            errors.append(f"Step {idx} (fill): params.text wajib diisi.")
        if action == "scroll":
            arah = str(params.get("direction", "down")).strip().lower()
            if arah not in {"up", "down", "left", "right"}:
                errors.append(f"Step {idx} (scroll): direction harus up/down/left/right.")
        if page_id is not None:
            try:
                page = await page_repo.get_by_id(int(page_id))
            except (ValueError, TypeError):
                page = None
            if not page:
                errors.append(f"Step {idx}: page_id {page_id} tidak ditemukan.")
            elif page["client_id"] != client_id:
                errors.append(f"Step {idx}: page bukan milik client ini.")
    return errors


def _hitung_diff(steps_a: list, steps_b: list) -> list:
    diff = []
    maks = max(len(steps_a), len(steps_b))
    for i in range(maks):
        a = steps_a[i] if i < len(steps_a) else None
        b = steps_b[i] if i < len(steps_b) else None
        if a != b:
            diff.append({"index": i + 1, "lama": a, "baru": b})
    return diff


@router.get("/client/{client_id}", response_model=List[dict])
async def list_scenarios_json(client_id: int):
    client_repo = ClientRepository()
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    repo = ScenarioRepository()
    return await repo.get_by_client(client_id)


@router.get("/approved-roles")
async def get_approved_roles(client_id: int):
    """Daftar role tervalidasi untuk dropdown builder."""
    client_repo = ClientRepository()
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    repo = ScenarioRepository()
    roles = await repo.get_approved_role_labels(client_id)
    return {"client_id": client_id, "roles": roles}


@router.post("/validate")
async def validate_scenario(payload: ScenarioValidateModel):
    steps_raw = _normalisasi_steps(payload.steps)
    errors = await _validasi_steps(payload.client_id, steps_raw)
    return {"valid": len(errors) == 0, "blocked": len(errors) > 0, "errors": errors}


@router.post("/", response_model=dict)
async def create_scenario(payload: ScenarioCreateModel):
    client_repo = ClientRepository()
    client = await client_repo.get_by_id(payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    nama = (payload.nama_fungsi or "").strip()
    if not nama:
        raise HTTPException(status_code=400, detail="nama_fungsi wajib diisi.")
    steps_raw = _normalisasi_steps(payload.steps)
    errors = await _validasi_steps(payload.client_id, steps_raw)
    if errors:
        raise HTTPException(status_code=400, detail={"blocked": True, "errors": errors})
    repo = ScenarioRepository()
    new_id = await repo.create(payload.client_id, nama, steps_raw)
    return await repo.get_by_id(new_id)


@router.post("/{scenario_id}/versions", response_model=dict)
async def create_new_version(scenario_id: int, payload: ScenarioVersionModel):
    repo = ScenarioRepository()
    current = await repo.get_by_id(scenario_id)
    if not current:
        raise HTTPException(status_code=404, detail="Scenario not found")
    steps_raw = _normalisasi_steps(payload.steps)
    errors = await _validasi_steps(current["client_id"], steps_raw)
    if errors:
        raise HTTPException(status_code=400, detail={"blocked": True, "errors": errors})
    new_id = await repo.create_new_version(scenario_id, steps_raw)
    if not new_id:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return await repo.get_by_id(new_id)


@router.post("/{scenario_id}/rollback", response_model=dict)
async def rollback_scenario(scenario_id: int, payload: RollbackModel):
    repo = ScenarioRepository()
    current = await repo.get_by_id(scenario_id)
    if not current:
        raise HTTPException(status_code=404, detail="Scenario not found")
    new_id = await repo.rollback_to_version(scenario_id, payload.target_versi)
    if not new_id:
        raise HTTPException(status_code=404, detail="Versi target tidak ditemukan.")
    result = await repo.get_by_id(new_id)
    return result


@router.get("/client/{client_id}/view", response_class=HTMLResponse)
async def view_scenarios_by_client(request: Request, client_id: int):
    """Daftar skenario per client (HTML)."""
    client_repo = ClientRepository()
    scenario_repo = ScenarioRepository()
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    semua = await scenario_repo.get_by_client(client_id)
    terbaru = {}
    for s in semua:
        if s["nama_fungsi"] not in terbaru:
            terbaru[s["nama_fungsi"]] = s
    return templates.TemplateResponse(
        "scenarios/list.html",
        {"request": request, "client": client,
         "scenarios": list(terbaru.values()), "total_versi": len(semua)},
    )


@router.get("/builder/view", response_class=HTMLResponse)
async def view_builder(request: Request, client_id: int, copy_from: Optional[int] = None):
    """Form builder skenario."""
    client_repo = ClientRepository()
    scenario_repo = ScenarioRepository()
    page_repo = PageRepository()
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    pages = await page_repo.get_by_client(client_id)
    roles = await scenario_repo.get_approved_role_labels(client_id)
    awal_nama = ""
    awal_steps = []
    mode_edit_dari = None
    if copy_from is not None:
        mode_edit_dari = await scenario_repo.get_by_id(copy_from)
        if mode_edit_dari and mode_edit_dari["client_id"] == client_id:
            awal_nama = mode_edit_dari["nama_fungsi"]
            awal_steps = mode_edit_dari.get("steps", [])
    return templates.TemplateResponse(
        "scenarios/builder.html",
        {"request": request, "client": client, "pages": pages, "roles": roles,
         "allowed_actions": sorted(ALLOWED_ACTIONS),
         "awal_nama": awal_nama, "awal_steps": awal_steps,
         "mode_edit_dari": mode_edit_dari},
    )


@router.get("/{scenario_id}/view", response_class=HTMLResponse)
async def view_scenario_detail(request: Request, scenario_id: int):
    """Detail skenario + riwayat versi + diff + rollback."""
    repo = ScenarioRepository()
    client_repo = ClientRepository()
    page_repo = PageRepository()
    scenario = await repo.get_by_id(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    client = await client_repo.get_by_id(scenario["client_id"])
    versions = await repo.get_versions(scenario["client_id"], scenario["nama_fungsi"])
    pages = await page_repo.get_by_client(scenario["client_id"])
    peta_page = {p["id"]: p["url"] for p in pages}
    diff = []
    versi_sebelumnya = None
    for v in versions:
        if v["versi"] < scenario["versi"]:
            versi_sebelumnya = v
            break
    if versi_sebelumnya:
        diff = _hitung_diff(versi_sebelumnya.get("steps", []), scenario.get("steps", []))
    return templates.TemplateResponse(
        "scenarios/detail.html",
        {"request": request, "scenario": scenario, "client": client,
         "versions": versions, "peta_page": peta_page,
         "diff": diff, "versi_sebelumnya": versi_sebelumnya},
    )


@router.get("/{scenario_id}", response_model=dict)
async def get_scenario(scenario_id: int):
    repo = ScenarioRepository()
    scenario = await repo.get_by_id(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario

