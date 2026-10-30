"""export_pdf.py - Export laporan Phase 8 ke PDF valid tanpa ADB.

Sengaja tanpa weasyprint (berat di Windows + butuh Pango) — pakai
penulis PDF minimal murni-Python (Helvetica, teks) agar definisi
selesai Phase 8 ("PDF bisa dibuka") tetap terpenuhi di PC master.
Isi: judul + ringkasan + per-kategori + tren (teks).
"""
from typing import Dict, List


def _escape_teks(s: str) -> str:
    s = str(s or "")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(judul: str, baris: List[str]) -> bytes:
    """Bangun PDF 1..N halaman sederhana (A4, Helvetica 11pt)."""
    # Pecah max 45 baris per halaman.
    halaman: List[List[str]] = []
    for i in range(0, max(len(baris), 1), 45):
        halaman.append(baris[i:i + 45] or ["(kosong)"])
    objects: List[bytes] = []
    # 1: catalog, 2: pages (kids diisi belakangan)
    n_halaman = len(halaman)
    # Nomor objek: 1 catalog, 2 pages, lalu per halaman 2 objek (page + content), terakhir 1 font.
    id_font = 3 + n_halaman * 2
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n_halaman))
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = (f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {n_halaman} >>\nendobj\n").encode("latin-1")
    parts = [obj1, obj2]
    for i, lines in enumerate(halaman):
        id_page = 3 + i * 2
        id_content = 4 + i * 2
        # Konten teks.
        txt = ["BT", "/F1 14 Tf", "50 800 Td", f"({_escape_teks(judul)}) Tj", "0 -22 Td", "/F1 11 Tf"]
        for ln in lines:
            # Potong 100 karakter agar muat.
            pot = str(ln)[:100]
            txt.append(f"({_escape_teks(pot)}) Tj")
            txt.append("0 -15 Td")
        txt.append("ET")
        stream = "\n".join(txt).encode("latin-1", errors="replace")
        page = (f"{id_page} 0 obj\n<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 595 842] /Resources << /Font << /F1 {id_font} 0 R >> >> "
                f"/Contents {id_content} 0 R >>\nendobj\n").encode("latin-1")
        content = (f"{id_content} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
                   + stream + b"\nendstream\nendobj\n")
        parts.append(page)
        parts.append(content)
    font = (f"{id_font} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n").encode("latin-1")
    parts.append(font)
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    out = bytearray(header)
    offsets = []
    for p in parts:
        offsets.append(len(out))
        out.extend(p)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(parts) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(f"trailer\n<< /Size {len(parts) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1"))
    return bytes(out)


def _baris_sesi(lap: Dict) -> List[str]:
    sesi = lap.get("sesi") or {}
    client = lap.get("client") or {}
    rg = lap.get("ringkasan") or {}
    baris = [
        f"Klien: {client.get('nama')} ({client.get('base_url')})",
        f"Sesi #{sesi.get('id')} {sesi.get('pair_label') or ''} status={sesi.get('status')}",
        f"Device A={((lap.get('dev_a') or {}).get('adb_id'))} Device B={((lap.get('dev_b') or {}).get('adb_id'))}",
        f"Total={rg.get('total')} Passed={rg.get('passed')} Failed={rg.get('failed')} "
        f"Blocked={rg.get('blocked')} Running={rg.get('running')}",
        f"Pass-rate={lap.get('pass_rate')}",
        f"Per-kategori-gagal: {lap.get('per_kategori_gagal')}",
        f"Per-device: {lap.get('per_device')}",
        f"Per-skenario: {lap.get('per_skenario')}",
        "",
        "Runs:",
    ]
    for r in lap.get("runs") or []:
        baris.append(f"#{(r.get('id'))} assign={r.get('scenario_assignment_id')} "
                     f"dev={r.get('device_id')} status={r.get('status')} "
                     f"kat={r.get('failure_category') or '-'}")
    return baris


def _baris_klien(lap: Dict) -> List[str]:
    client = lap.get("client") or {}
    rg = lap.get("ringkasan") or {}
    baris = [
        f"Klien: {client.get('nama')} ({client.get('base_url')})",
        f"Jumlah sesi: {lap.get('jumlah_sesi')}",
        f"Total={rg.get('total')} Passed={rg.get('passed')} Failed={rg.get('failed')} "
        f"Blocked={rg.get('blocked')} Running={rg.get('running')}",
        f"Pass-rate={lap.get('pass_rate')}",
        f"Per-kategori-gagal: {lap.get('per_kategori_gagal')}",
        "",
        "Per-sesi:",
    ]
    for s in lap.get("per_sesi") or []:
        baris.append(f"sesi #{s.get('session_id')} {s.get('pair_label') or ''} "
                     f"{s.get('status')} total={s.get('total')} passed={s.get('passed')} "
                     f"rate={s.get('pass_rate')}")
    return baris


def buat_pdf_sesi(laporan: Dict) -> bytes:
    """PDF laporan satu sesi."""
    sesi = (laporan.get("sesi") or {}).get("id")
    return _pdf_bytes(f"Laporan Sesi #{sesi} - Otomet", _baris_sesi(laporan))


def buat_pdf_klien(laporan: Dict) -> bytes:
    """PDF laporan satu klien."""
    nama = (laporan.get("client") or {}).get("nama")
    return _pdf_bytes(f"Laporan Klien {nama} - Otomet", _baris_klien(laporan))
