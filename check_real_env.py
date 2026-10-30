"""Cek lingkungan Real 2HP: ADB + Appium 4723/4724 + TestClient simulate. Tulis ke check_real.log."""
import sys, traceback, socket, json
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
out = []
def log(m):
    print(m, flush=True)
    out.append(str(m))
log("=== CHECK REAL ENV START ===")
# 1. ADB via device_pool
try:
    from backend.orchestrator.device_pool import daftar_perangkat_adb
    live = daftar_perangkat_adb()
    log(f"ADB live via pool = {live}")
except Exception:
    log("ADB pool EXC:"); log(traceback.format_exc())
# 2. adb CLI langsung
import shutil, subprocess
log(f"which adb = {shutil.which('adb')}")
for cmd in [["adb", "devices"], [r"C:\Users\USER\AppData\Local\Android\Sdk\platform-tools\adb.exe", "devices"]]:
    try:
        p = Path(cmd[0])
        if cmd[0] != "adb" and not p.exists():
            log(f"skip {cmd[0]} (tak ada file)")
            continue
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        log(f"CMD {' '.join(cmd)} rc={r.returncode} out={repr(r.stdout[:800])} err={repr((r.stderr or '')[:400])}")
    except Exception as e:
        log(f"CMD {' '.join(cmd)} EXC {e}")
# 3. Appium status 4723/4724
import urllib.request
for port in (4723, 4724):
    url = f"http://127.0.0.1:{port}/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read(2000).decode("utf-8", "ignore")
            log(f"APPIUM {port} UP http={resp.status} body[:300]={body[:300]}")
    except Exception as e:
        log(f"APPIUM {port} DOWN ({type(e).__name__}: {e}) -> jalankan: appium -p {port}")
# 3b. port 8000
s = socket.socket(); s.settimeout(1)
try:
    log(f"port8000_sibuk={s.connect_ex(('127.0.0.1', 8000)) == 0}")
finally:
    s.close()
# 4. TestClient: /health, /, demo view + simulate 2device (tanpa ADB)
try:
    from fastapi.testclient import TestClient
    from backend.app import app
    c = TestClient(app, raise_server_exceptions=False)
    for u in ["/health", "/", "/api/runs/demo/real-2device/view", "/api/orchestrator/devices/adb"]:
        r = c.get(u)
        log(f"GET {u} -> {r.status_code} len={len(r.content)}")
    # simulate: cari sesi running terakhir, atau buat sesi dummy? cukup cek POST sessions/{id}/run butuh sesi.
    # Kita uji service laporan + orchestrator devices list saja (tanpa ubah DB).
    r = c.get("/api/orchestrator/devices")
    log(f"GET /api/orchestrator/devices -> {r.status_code} body[:400]={r.text[:400]}")
    # cek POST demo/real-2device fail-closed tanpa ADB (harap 400, bukan 500/crash)
    r = c.post("/api/runs/demo/real-2device", json={"url": "https://example.com", "serial_a": "192.168.100.50:42851", "serial_b": "192.168.100.81:37251", "pair_label": "cek-env"})
    log(f"POST demo/real-2device -> {r.status_code} body[:600]={r.text[:600]}")
except Exception:
    log("TESTCLIENT EXC:"); log(traceback.format_exc())
log("=== CHECK REAL ENV DONE ===")
Path(ROOT / "check_real.log").write_text("\n".join(out), encoding="utf-8")
