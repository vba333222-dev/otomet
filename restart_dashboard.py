"""Restart dashboard 8000 agar caps baru kepakai (Appium tetap jalan)."""
import subprocess, time, socket, os, sys, signal
def port_pid(port):
    try:
        r = subprocess.run(["netstat","-ano"], capture_output=True, text=True, timeout=10)
        for line in (r.stdout or "").splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid.isdigit():
                    return int(pid)
    except Exception as e:
        print("netstat EXC", e)
    return None
def port_sibuk(p):
    s = socket.socket(); s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", p)) == 0
    finally:
        s.close()
ROOT = os.path.dirname(os.path.abspath(__file__))
pid = port_pid(8000)
print("pid8000:", pid)
if pid:
    try:
        subprocess.run(["taskkill","/PID",str(pid),"/F"], capture_output=True, text=True, timeout=10)
        print("killed", pid)
    except Exception as e:
        print("kill EXC", e)
    time.sleep(3)
print("8000 sibuk?", port_sibuk(8000))
LP = os.environ.get("LOCALAPPDATA") or ""
SDK = os.path.join(LP, "Android", "Sdk")
env = dict(os.environ)
env["JAVA_HOME"] = r"C:\tools\jdk17"
env["ANDROID_HOME"] = SDK
env["ANDROID_SDK_ROOT"] = SDK
env["PATH"] = os.pathsep.join([r"C:\tools\jdk17\bin",
    os.path.join(SDK,"platform-tools"), r"C:\nvm4w\nodejs", env.get("PATH","")])
log = open(os.path.join(ROOT,"dashboard.log"),"a",encoding="utf-8")
p = subprocess.Popen([sys.executable,"run_dashboard.py"], cwd=ROOT, env=env,
                     stdout=log, stderr=subprocess.STDOUT)
print("start dashboard pid", p.pid)
for i in range(10):
    time.sleep(1)
    if port_sibuk(8000):
        print("dashboard UP")
        break
    print("tunggu...", i)
print("4723", port_sibuk(4723), "4724", port_sibuk(4724), "8000", port_sibuk(8000))
