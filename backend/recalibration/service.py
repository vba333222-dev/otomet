"""
service.py - Orkestrasi recalibration + gate all-or-nothing (Phase 5).
Alur S4.3: threshold per-klien -> scan headless -> matching ->
auto-update manifest -> catat log -> gate boleh_jalan.
"""
import uuid
from typing import Dict, List, Optional
from backend.db.repositories.client_repo import ClientRepository
from backend.db.repositories.page_repo import PageRepository
from backend.db.repositories.element_repo import ElementRepository
from backend.db.repositories.recalibration_repo import RecalibrationRepository
from backend.recalibration.matcher import recalibrate_batch
from backend.recalibration.threshold import ambil_threshold


def buat_run_batch_id() -> str:
    """ID batch unik untuk satu proses recalibration."""
    return "recal-" + uuid.uuid4().hex[:12]


def _ringkas_untuk_log(hasil: List[Dict]) -> List[Dict]:
    """Buang kandidat_fresh agar log JSON ringkas."""
    out = []
    for h in hasil:
        out.append({"element_id": h.get("element_id"), "role_label": h.get("role_label"),
            "status": h.get("status"), "tahap_awal": h.get("tahap_awal"),
            "skor_teks": h.get("skor_teks"), "skor_posisi": h.get("skor_posisi"),
            "confidence_baru": h.get("confidence_baru"),
            "old_selector": h.get("old_selector"), "new_selector": h.get("new_selector"),
            "alasan": h.get("alasan")})
    return out


async def jalankan_recalibration(page_id: int, run_batch_id: Optional[str] = None, fresh_override: Optional[List[Dict]] = None) -> Dict:
    """Recalibration penuh satu halaman. Fail-closed bila page/client hilang."""
    page_repo = PageRepository()
    client_repo = ClientRepository()
    element_repo = ElementRepository()
    log_repo = RecalibrationRepository()
    page = await page_repo.get_by_id(page_id)
    if not page:
        raise ValueError(f"Halaman {page_id} tidak ditemukan.")
    client = await client_repo.get_by_id(page["client_id"])
    if not client:
        raise ValueError(f"Klien halaman {page_id} tidak ditemukan.")
    thr = ambil_threshold(client)
    tersimpan = await element_repo.get_by_page(page_id)
    batch = run_batch_id or buat_run_batch_id()
    kosong = {"total": 0, "calibrated": 0, "recalibrated": 0, "blocked": 0}
    if not tersimpan:
        log_id = await log_repo.catat(batch, page_id, [])
        return {"boleh_jalan": True, "ringkasan": kosong, "log_id": log_id,
                "run_batch_id": batch, "page_id": page_id, "threshold": thr, "hasil": []}
    if fresh_override is not None:
        segar = fresh_override
    else:
        from backend.recalibration.headless_runner import scan_page_fresh
        segar = await scan_page_fresh(page["url"])
    hasil = recalibrate_batch(tersimpan, segar, thr["similarity"], thr["posisi"], thr["tinggi_fallback"])
    for h in hasil["hasil_per_elemen"]:
        if h["status"] != "recalibrated":
            continue
        kand = h.get("kandidat_fresh") or {}
        sel_baru = {"primary": h.get("new_selector"), "fallbacks": []}
        sel_kand = kand.get("selectors") or {}
        if isinstance(sel_kand, dict) and sel_kand.get("primary"):
            sel_baru = sel_kand
        teks_baru = str(kand.get("text", kand.get("text_snapshot", "")))
        bbox_baru = dict(kand.get("bbox", kand.get("bbox_snapshot", {})))
        await element_repo.update_manifest_recalibrated(
            h["element_id"], sel_baru, teks_baru, bbox_baru,
            float(h.get("confidence_baru") or 0.0))
    ringkas = _ringkas_untuk_log(hasil["hasil_per_elemen"])
    log_id = await log_repo.catat(batch, page_id, ringkas)
    return {"boleh_jalan": hasil["boleh_jalan"], "ringkasan": hasil["ringkasan"],
            "log_id": log_id, "run_batch_id": batch, "page_id": page_id,
            "threshold": thr, "hasil": ringkas}


async def cek_gate_untuk_skenario(scenario_id: int) -> Dict:
    """Gate all-or-nothing: boleh jalan bila tiap halaman terkait tanpa blocked."""
    from backend.db.repositories.scenario_repo import ScenarioRepository
    scenario_repo = ScenarioRepository()
    page_repo = PageRepository()
    log_repo = RecalibrationRepository()
    skenario = await scenario_repo.get_by_id(scenario_id)
    if not skenario:
        raise ValueError(f"Skenario {scenario_id} tidak ditemukan.")
    steps = skenario.get("steps") or []
    roles = {(s.get("role_label") or "").strip() for s in steps if isinstance(s, dict)}
    roles.discard("")
    page_ids = {s.get("page_id") for s in steps if isinstance(s, dict) and s.get("page_id")}
    if not page_ids:
        semua = await page_repo.get_by_client(skenario["client_id"])
        page_ids = {p["id"] for p in semua}
    if not page_ids:
        return {"boleh_jalan": False, "alasan": "Tak ada halaman terkait.",
                "detail": [], "scenario_id": scenario_id}
    detail = []
    boleh = True
    for pid in sorted(page_ids):
        log = await log_repo.get_terakhir(pid)
        if not log:
            boleh = False
            detail.append({"page_id": pid, "status": "belum_recalibrated",
                           "alasan": "Belum ada recalibration."})
            continue
        hasil = log.get("hasil") or []
        blocked = [h for h in hasil if h.get("status") == "blocked"
                   and (not roles or h.get("role_label") in roles)]
        if blocked:
            boleh = False
            detail.append({"page_id": pid, "status": "blocked", "log_id": log["id"],
                "elemen_blocked": [h.get("role_label") for h in blocked],
                "alasan": f"{len(blocked)} elemen skenario blocked."})
        else:
            detail.append({"page_id": pid, "status": "ok", "log_id": log["id"],
                           "alasan": "Recalibration terakhir tanpa blocked."})
    return {"boleh_jalan": boleh, "scenario_id": scenario_id,
            "nama_fungsi": skenario.get("nama_fungsi"), "versi": skenario.get("versi"),
            "detail": detail,
            "alasan": "Semua halaman lolos gate." if boleh else "Gate tertahan."}

