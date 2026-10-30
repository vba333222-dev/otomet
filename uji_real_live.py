"""Uji nyata via server live 8000: demo setup + run real + laporan."""
import json, urllib.request, urllib.error
BASE = "http://127.0.0.1:8000"
def call(method, path, body=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE+path, data=data, method=method,
        headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read().decode("utf-8","ignore")
            print(f"{method} {path} -> {r.status} len={len(b)}")
            print(b[:2000])
            return r.status, json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8","ignore")
        print(f"{method} {path} -> HTTP {e.code} {b[:2000]}")
        return e.code, {}
    except Exception as e:
        print(f"{method} {path} EXC {type(e).__name__}: {e}")
        return -1, {}
print("=== SETUP REAL ===")
s, d = call("POST","/api/runs/demo/real-2device",
    {"url":"https://example.com","serial_a":"192.168.100.50:42851",
     "serial_b":"192.168.100.81:37251","pair_label":"pair-real-2hp-gui"},
    timeout=60)
sid = d.get("session_id")
print("SID:", sid)
if not sid:
    raise SystemExit(1)
print("=== RUN REAL (buka Chrome 2 HP, bisa 1-3 menit) ===")
s2, d2 = call("POST", f"/api/runs/sessions/{sid}/run", {"mode":"real"}, timeout=180)
print("HASIL:", json.dumps(d2, ensure_ascii=False)[:3000])
print("=== LAPORAN ===")
call("GET", f"/api/reports/sessions/{sid}/summary", timeout=30)
for u in [f"/api/runs/sessions/{sid}/runs/view",
          f"/api/reports/sessions/{sid}/view",
          f"/api/orchestrator/sessions/{sid}/view"]:
    try:
        with urllib.request.urlopen(BASE+u, timeout=30) as r:
            print(f"GET {u} -> {r.status} len={len(r.read())}")
    except Exception as e:
        print(f"GET {u} EXC {e}")
print("UJI-REAL-DONE SID", sid)
