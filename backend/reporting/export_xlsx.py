"""export_xlsx.py - Export laporan Phase 8 ke Excel valid (openpyxl).

Satu workbook multi-sheet: Ringkasan + Runs/PerSesi + Tren.
Fail-closed: laporan kosong tetap menghasilkan file valid berisi ringkasan nol.
"""
from typing import Dict
from io import BytesIO


def _wb_sesi(laporan: Dict):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Ringkasan"
    sesi = laporan.get("sesi") or {}
    client = laporan.get("client") or {}
    rg = laporan.get("ringkasan") or {}
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    baris = [
        ("Klien", client.get("nama")),
        ("Base URL", client.get("base_url")),
        ("Sesi ID", sesi.get("id")),
        ("Pair Label", sesi.get("pair_label")),
        ("Status Sesi", sesi.get("status")),
        ("Device A", ((laporan.get("dev_a") or {}).get("adb_id"))),
        ("Device B", ((laporan.get("dev_b") or {}).get("adb_id"))),
        ("Total", rg.get("total")),
        ("Passed", rg.get("passed")),
        ("Failed", rg.get("failed")),
        ("Blocked", rg.get("blocked")),
        ("Running", rg.get("running")),
        ("Pass-rate", laporan.get("pass_rate")),
        ("Per-kategori-gagal", str(laporan.get("per_kategori_gagal"))),
    ]
    ws.append(["Kunci", "Nilai"])
    for c in ws[1]:
        c.font = header_font
        c.fill = header_fill
    for k, v in baris:
        ws.append([k, v])
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 50

    ws2 = wb.create_sheet("Runs")
    ws2.append(["id", "assignment", "device_id", "scenario_id",
                "test_data_id", "status", "failure_category",
                "started_at", "completed_at"])
    for c in ws2[1]:
        c.font = header_font
        c.fill = header_fill
    for r in laporan.get("runs") or []:
        ws2.append([r.get("id"), r.get("scenario_assignment_id"),
                    r.get("device_id"), r.get("scenario_id"),
                    r.get("test_data_id"), r.get("status"),
                    r.get("failure_category") or "",
                    r.get("started_at") or "", r.get("completed_at") or ""])
    ws2.column_dimensions["G"].width = 20
    return wb


def _wb_klien(laporan: Dict):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Ringkasan"
    client = laporan.get("client") or {}
    rg = laporan.get("ringkasan") or {}
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    baris = [
        ("Klien", client.get("nama")),
        ("Base URL", client.get("base_url")),
        ("Jumlah sesi", laporan.get("jumlah_sesi")),
        ("Total", rg.get("total")),
        ("Passed", rg.get("passed")),
        ("Failed", rg.get("failed")),
        ("Blocked", rg.get("blocked")),
        ("Running", rg.get("running")),
        ("Pass-rate", laporan.get("pass_rate")),
        ("Per-kategori-gagal", str(laporan.get("per_kategori_gagal"))),
    ]
    ws.append(["Kunci", "Nilai"])
    for c in ws[1]:
        c.font = header_font
        c.fill = header_fill
    for k, v in baris:
        ws.append([k, v])
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 50

    ws2 = wb.create_sheet("PerSesi")
    ws2.append(["session_id", "pair_label", "status", "total",
                "passed", "failed", "blocked", "running", "pass_rate"])
    for c in ws2[1]:
        c.font = header_font
        c.fill = header_fill
    for s in laporan.get("per_sesi") or []:
        ws2.append([s.get("session_id"), s.get("pair_label") or "",
                    s.get("status"), s.get("total"), s.get("passed"),
                    s.get("failed"), s.get("blocked"), s.get("running"),
                    s.get("pass_rate")])

    ws3 = wb.create_sheet("Tren")
    ws3.append(["session_id", "label", "total", "passed", "pass_rate"])
    for c in ws3[1]:
        c.font = header_font
        c.fill = header_fill
    for t in laporan.get("tren") or []:
        ws3.append([t.get("session_id"), t.get("label"),
                    t.get("total"), t.get("passed"), t.get("pass_rate")])
    return wb


def buat_xlsx_sesi(laporan: Dict) -> bytes:
    """Return bytes .xlsx laporan satu sesi."""
    wb = _wb_sesi(laporan)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def buat_xlsx_klien(laporan: Dict) -> bytes:
    """Return bytes .xlsx laporan satu klien."""
    wb = _wb_klien(laporan)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
