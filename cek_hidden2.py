"""Cari hidden api di semua js appium (tahan permission error)."""
import pathlib
bases = [pathlib.Path("C:/Users/USER/.appium"),
         pathlib.Path("C:/nvm4w/nodejs/node_modules/appium")]
for base in bases:
    print("BASE:", base, base.exists())
    if not base.exists():
        continue
    n = 0
    for f in base.rglob("*.js"):
        n += 1
        if n % 20000 == 0:
            print("  scan", n, str(f)[:120])
        try:
            if f.stat().st_size > 2000000:
                continue
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "setDefaultHiddenApiPolicy" in t or "ignoreHiddenApiPolicyError" in t:
            print("HIT:", f)
            i = t.find("setDefaultHiddenApiPolicy")
            if i < 0:
                i = t.find("ignoreHiddenApiPolicyError")
            print(t[max(0,i-500):i+1800][:2500])
            print("="*70)
    print("scan selesai", n)
