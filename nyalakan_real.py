"""Launcher 2 Appium server (4723+4724) + dashboard 8000 sekaligus."""
import os, subprocess, sys, time, socket
ROOT = os.path.dirname(os.path.abspath(__file__))
LP = os.environ.get("LOCALAPPDATA") or ""
SDK = os.path.join(LP, "Android", "Sdk")
JDK = r"C:\tools\jdk17"
NODE = r"C:\nvm4w\nodejs"
ADB = os.path.join(SDK, "platform-tools", "adb.exe")
APPIUM = os.path.join(NODE, "appium.cmd")

env = dict(os.environ)
env["JAVA_HOME"] = JDK
env["ANDROID_HOME"] = SDK
env["ANDROID_SDK_ROOT"] = SDK
env["PATH"] = os.pathsep.join([os.path.join(JDK, "bin"),
    os.path.join(SDK, "platform-tools"),
    os.path.join(SDK, "emulator"), NODE, env.get("PATH", "")])

def port_sibuk(p):
    s = socket.socket(); s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", p)) == 0
    finally:
        s.close()

print("[1/4] ADB:", ADB, flush=True)
r = subprocess.run([ADB, "devices", "-l"], capture_output=True, text=True, timeout=15, env=env)
print((r.stdout or "")[:800], flush=True)
print("[2/4] Appium 4723 + 4724...", flush=True)
procs = []
for port in (4723, 4724):
    if port_sibuk(port):
        print(f"  port {port} sudah listen, lewati.", flush=True)
        continue
    log = open(os.path.join(ROOT, f"appium-{port}.log"), "a", encoding="utf-8")
    p = subprocess.Popen([APPIUM, "-p", str(port), "--log-timestamp"],
                         cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    procs.append((port, p))
    print(f"  start appium -p {port} pid={p.pid}", flush=True)
time.sleep(6)
for port in (4723, 4724):
    print(f"  port {port} sibuk={port_sibuk(port)}", flush=True)
print("[3/4] Dashboard 8000...", flush=True)
if port_sibuk(8000):
    print("  port 8000 sudah listen, lewati.", flush=True)
else:
    log = open(os.path.join(ROOT, "dashboard.log"), "a", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "run_dashboard.py"],
                         cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    print(f"  start dashboard pid={p.pid}", flush=True)
    time.sleep(4)
    print(f"  port 8000 sibuk={port_sibuk(8000)}", flush=True)
print("[4/4] Selesai. Buka http://127.0.0.1:8000/api/runs/demo/real-2device/view", flush=True)
