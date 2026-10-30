"""
Script untuk menjalankan FastAPI Dashboard
Jalankan: python run_dashboard.py  (lalu buka http://127.0.0.1:8000)
"""
import socket
import sys
import webbrowser
from pathlib import Path

# Add project root to path (agar `import backend...` jalan dari mana saja)
sys.path.insert(0, str(Path(__file__).parent))

HOST = "127.0.0.1"
PORT = 8000


def port_sibuk(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


if __name__ == "__main__":
    import uvicorn

    if port_sibuk(HOST, PORT):
        print(f"[otomet] Port {PORT} sudah dipakai — kemungkinan dashboard sudah jalan.", flush=True)
        print(f"[otomet] Buka manual: http://{HOST}:{PORT}/health  dan  http://{HOST}:{PORT}/", flush=True)
        try:
            webbrowser.open(f"http://{HOST}:{PORT}/")
        except Exception:
            pass
        sys.exit(0)

    url = f"http://{HOST}:{PORT}/"
    print(f"[otomet] Menyalakan dashboard di {url}", flush=True)
    print(f"[otomet] Health: http://{HOST}:{PORT}/health  |  Uji 2HP: http://{HOST}:{PORT}/api/runs/demo/real-2device/view", flush=True)
    print("[otomet] Browser akan dibuka otomatis. Ctrl+C untuk berhenti.", flush=True)
    try:
        # Buka browser sedikit terlambat agar server sempat listen.
        import threading
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    except Exception:
        pass
    uvicorn.run(
        "backend.app:app",
        host=HOST,
        port=PORT,
        reload=False,  # FIX: reload=True bikin 2 proses + restart liar di Windows
        log_level="info",
    )

