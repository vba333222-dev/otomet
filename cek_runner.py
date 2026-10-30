import sys
sys.path.insert(0, "c:/Project/otomet")
import pathlib
p = pathlib.Path("c:/Project/otomet/backend/orchestrator/runner.py")
lines = p.read_text(encoding="utf-8").splitlines()
print(len(lines))
for i, l in enumerate(lines):
    if l.startswith("async def ") or l.startswith("def "):
        print(i+1, l)

