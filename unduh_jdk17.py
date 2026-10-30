"""Unduh JDK 17 portable (Microsoft Build) + ekstrak ke C:/tools/jdk17."""
import pathlib, urllib.request, zipfile, sys
URL = "https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.zip"
DST_DIR = pathlib.Path("C:/tools")
DST_ZIP = DST_DIR / "jdk17.zip"
TARGET = DST_DIR / "jdk17"
print("DST", DST_DIR, flush=True)
DST_DIR.mkdir(parents=True, exist_ok=True)
if TARGET.exists() and (TARGET / "bin" / "java.exe").exists():
    print("JDK sudah ada:", TARGET / "bin" / "java.exe", flush=True)
    sys.exit(0)
print("Unduh", URL, flush=True)
def _hook(block, bs, total):
    if block % 50 == 0:
        print(f"  {block*bs//1024//1024}MB / {total//1024//1024 if total>0 else '?'}MB", flush=True)
urllib.request.urlretrieve(URL, str(DST_ZIP), reporthook=_hook)
print("Unduh selesai:", DST_ZIP.stat().st_size, flush=True)
print("Ekstrak...", flush=True)
with zipfile.ZipFile(str(DST_ZIP)) as z:
    z.extractall(str(DST_DIR))
# cari folder hasil ekstrak
kandidat = [p for p in DST_DIR.iterdir() if p.is_dir() and "jdk" in p.name.lower()]
print("kandidat", kandidat, flush=True)
# normalisasi ke C:/tools/jdk17
import shutil
src = None
for k in kandidat:
    if k.resolve() == TARGET.resolve():
        continue
    if (k / "bin" / "java.exe").exists():
        src = k
        break
if src:
    if TARGET.exists():
        shutil.rmtree(str(TARGET))
    shutil.move(str(src), str(TARGET))
    print("dipindah ke", TARGET, flush=True)
print("java:", (TARGET / "bin" / "java.exe").exists(), flush=True)
