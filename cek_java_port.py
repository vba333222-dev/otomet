"""Cek Java/Appium/ports via python (hindari quoting hell pwsh)."""
import os, shutil, socket, subprocess, pathlib, glob
print("=== CEK JAVA ===")
for pat in [r"C:\Program Files\Microsoft\jdk*\bin\java.exe",
            r"C:\Program Files\Java\*\bin\java.exe",
            r"C:\Program Files\Eclipse Adoptium\*\bin\java.exe"]:
    hits = glob.glob(pat)
    print(pat, "->", hits)
    for h in hits:
        try:
            r = subprocess.run([h, "-version"], capture_output=True, text=True, timeout=8)
            print("  ", h, repr((r.stdout or "") + (r.stderr or ""))[:300])
        except Exception as e:
            print("  ", h, "EXC", e)
print("which java", shutil.which("java"))
print("JAVA_HOME", os.environ.get("JAVA_HOME"))
print("=== CEK NODE/APPIUM ===")
print("which node", shutil.which("node"))
for cand in [r"C:\nvm4w\nodejs\npm.cmd", "npm.cmd", "npm"]:
    print("try", cand, shutil.which(cand))
print("=== CEK PORTS ===")
for p in (8000, 4723, 4724, 5037):
    s = socket.socket(); s.settimeout(1)
    try:
        sibuk = s.connect_ex(("127.0.0.1", p)) == 0
        print(f"port {p} sibuk={sibuk}")
    finally:
        s.close()
print("=== CEK ADB ===")
lp = os.environ.get("LOCALAPPDATA") or ""
adb = pathlib.Path(lp) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
print("adb", str(adb), adb.exists())
if adb.exists():
    try:
        r = subprocess.run([str(adb), "devices", "-l"], capture_output=True, text=True, timeout=10)
        print(repr((r.stdout or "")[:800]))
    except Exception as e:
        print("adb EXC", e)
print("CEK-DONE")
