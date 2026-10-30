"""Cari implementasi setDefaultHiddenApiPolicy di folder appium."""
import pathlib
base = pathlib.Path("C:/Users/USER/.appium")
hits = []
for f in base.rglob("adb-commands.js"):
    try:
        t = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if "setDefaultHiddenApiPolicy" in t:
        hits.append(str(f))
        i = t.find("setDefaultHiddenApiPolicy")
        print("FILE:", f)
        print(t[max(0,i-400):i+1500])
        print("="*60)
print("HITS:", hits)
