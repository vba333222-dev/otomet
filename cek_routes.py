"""Dump routes + cek caps/url tanpa quoting hell."""
from backend.app import app
for r in app.routes:
    try:
        methods = sorted(getattr(r, "methods", set()) or [])
    except Exception:
        methods = []
    print(getattr(r, "path", "?"), methods)
print("---CAPS---")
from backend.orchestrator.runner import bangun_caps, server_url_untuk_device
d = {"adb_id": "192.168.100.50:42851", "appium_port": 4723}
print(bangun_caps(d))
print(server_url_untuk_device(d))
