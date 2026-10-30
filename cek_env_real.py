"""Cek env real: java, sdk, node, npm, appium (tulis stdout)."""
import os, shutil, subprocess, pathlib, sys
def run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        out = (r.stdout or "") + (r.stderr or "")
        return f"rc={r.returncode} out={out[:600]!r}"
    except Exception as e:
        return f"EXC {type(e).__name__}: {e}"
print("PYTHON", sys.version)
print("JAVA_HOME", os.environ.get("JAVA_HOME"))
print("ANDROID_HOME", os.environ.get("ANDROID_HOME"))
print("ANDROID_SDK_ROOT", os.environ.get("ANDROID_SDK_ROOT"))
for k in ["java","javac","node","npm","appium","adb"]:
    print(f"which {k} =", shutil.which(k))
lp = os.environ.get("LOCALAPPDATA") or ""
sdk = pathlib.Path(lp) / "Android" / "Sdk"
print("SDK dir", str(sdk), "exists", sdk.exists())
if sdk.exists():
    try:
        print("SDK children", [p.name for p in sdk.iterdir()])
    except Exception as e:
        print("SDK list EXC", e)
    adb = sdk / "platform-tools" / "adb.exe"
    print("adb.exe exists", adb.exists())
    if adb.exists():
        print("adb devices:", run([str(adb), "devices"]))
    for cand in [sdk/"cmdline-tools"/"latest"/"bin"/"sdkmanager.bat",
                 sdk/"platform-tools"/"adb.exe"]:
        print(cand, "exists", cand.exists())
# java candidates
for cand in [r"C:\Program Files\Java",
             r"C:\Program Files\Eclipse Adoptium",
             r"C:\Program Files\Microsoft",
             pathlib.Path(lp)/"Programs"]:
    p = pathlib.Path(cand)
    print("cand", cand, "exists", p.exists())
    if p.exists():
        try:
            subs = [x.name for x in p.iterdir()][:10]
            print("  subs", subs)
            for s in p.iterdir():
                j = s/"bin"/"java.exe"
                if j.exists():
                    print("  found java", str(j), run([str(j), "-version"]))
        except Exception as e:
            print("  EXC", e)
print("node:", run(["node","--version"]) if shutil.which("node") else "no node")
print("npm:", run(["npm","--version"]) if shutil.which("npm") else "no npm")
print("appium:", run(["appium","--version"]) if shutil.which("appium") else "no appium (npm i -g appium)")
print("ENV-OK")
