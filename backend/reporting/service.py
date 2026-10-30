"""service.py - Agregasi laporan Phase 8 (tanpa ADB fisik).

Sumber: SQLite via repository Phase 6-7 + recalibration log Phase 5.
Fail-safe: id hilang = ValueError, bukan tebakan.
"""
from collections import Counter
from typing import Dict, List


async def laporan_sesi(session_id: int) -> Dict:
    """Laporan satu sesi pair: ringkasan + per-device + per-skenario + kategori gagal."""
    from backend.db.repositories.session_repo import SessionRepository, AssignmentRepository
    from backend.db.repositories.run_repo import RunRepository
    from backend.db.repositories.client_repo import ClientRepository
    from backend.db.repositories.device_repo import DeviceRepository

    sesi_repo = SessionRepository()
    sesi = await sesi_repo.get_by_id(session_id)
    if not sesi:
        raise ValueError(f"Sesi {session_id} tidak ditemukan.")
    client = await ClientRepository().get_by_id(sesi["client_id"])
    if not client:
        raise ValueError(f"Klien sesi {session_id} tidak ditemukan.")
    dev_repo = DeviceRepository()
    dev_a = await dev_repo.get_by_id(sesi["device_a_id"])
    dev_b = await dev_repo.get_by_id(sesi["device_b_id"])
    assignments = await sesi_repo.get_assignments(session_id)
    detail_assign: List[Dict] = []
    assign_repo = AssignmentRepository()
    for a in assignments:
        d = await assign_repo.get_detail(a["id"])
        if d:
            detail_assign.append(d)
    ringkas = await RunRepository().ringkasan_session(session_id)
    runs = ringkas.get("runs") or []
    per_device = Counter()
    per_skenario = Counter()
    per_kategori = Counter()
    per_status = Counter()
    for r in runs:
        per_status[r.get("status") or "?"] += 1
        per_device[f"{r.get('device_id') or '-'}"] += 1
        per_skenario[f"{r.get('scenario_id') or '-'}"] += 1
        if r.get("status") == "failed":
            per_kategori[r.get("failure_category") or "tanpa_kategori"] += 1
        if r.get("status") == "blocked":
            per_kategori["blocked_mapping"] += 1
    total = ringkas["ringkasan"]["total"]
    passed = ringkas["ringkasan"]["passed"]
    pass_rate = round(passed / total, 4) if total else 0.0
    return {
        "sesi": sesi, "client": client, "dev_a": dev_a, "dev_b": dev_b,
        "assignments": detail_assign, "ringkasan": ringkas["ringkasan"],
        "runs": runs, "pass_rate": pass_rate,
        "per_device": dict(per_device), "per_skenario": dict(per_skenario),
        "per_kategori_gagal": dict(per_kategori), "per_status": dict(per_status),
    }


async def laporan_klien(client_id: int) -> Dict:
    """Laporan satu klien: agregat semua sesi + tren per sesi."""
    from backend.db.repositories.client_repo import ClientRepository
    from backend.db.repositories.session_repo import SessionRepository
    from backend.db.repositories.run_repo import RunRepository

    client = await ClientRepository().get_by_id(client_id)
    if not client:
        raise ValueError(f"Klien {client_id} tidak ditemukan.")
    sesi_list = await SessionRepository().get_by_client(client_id)
    run_repo = RunRepository()
    total = {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "running": 0}
    per_kategori: Counter = Counter()
    per_sesi: List[Dict] = []
    for s in sorted(sesi_list, key=lambda x: x["id"]):
        rk = await run_repo.ringkasan_session(s["id"])
        rg = rk["ringkasan"]
        for k in total:
            total[k] += int(rg.get(k) or 0)
        for r in rk.get("runs") or []:
            if r.get("status") == "failed":
                per_kategori[r.get("failure_category") or "tanpa_kategori"] += 1
            if r.get("status") == "blocked":
                per_kategori["blocked_mapping"] += 1
        per_sesi.append({
            "session_id": s["id"], "pair_label": s.get("pair_label"),
            "status": s.get("status"), **rg,
            "pass_rate": round(rg["passed"] / rg["total"], 4) if rg["total"] else 0.0,
        })
    tren = await tren_klien(client_id)
    pass_rate = round(total["passed"] / total["total"], 4) if total["total"] else 0.0
    return {
        "client": client, "jumlah_sesi": len(sesi_list),
        "ringkasan": total, "pass_rate": pass_rate,
        "per_kategori_gagal": dict(per_kategori),
        "per_sesi": per_sesi, "tren": tren,
    }


async def tren_klien(client_id: int, limit: int = 20) -> List[Dict]:
    """Tren pass-rate per sesi (urut id ASC, terbaru = belakang). Untuk Chart.js."""
    from backend.db.repositories.session_repo import SessionRepository
    from backend.db.repositories.run_repo import RunRepository

    sesi_list = await SessionRepository().get_by_client(client_id)
    sesi_list = sorted(sesi_list, key=lambda x: x["id"])[-int(limit):]
    run_repo = RunRepository()
    tren: List[Dict] = []
    for s in sesi_list:
        rk = await run_repo.ringkasan_session(s["id"])
        rg = rk["ringkasan"]
        tren.append({
            "session_id": s["id"],
            "label": s.get("pair_label") or f"sesi-{s['id']}",
            "total": rg["total"], "passed": rg["passed"],
            "failed": rg["failed"], "blocked": rg["blocked"],
            "running": rg["running"],
            "pass_rate": round(rg["passed"] / rg["total"], 4) if rg["total"] else 0.0,
        })
    return tren
