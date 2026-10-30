"""Inspeksi Appium client terpasang: signature Remote + Options. Tulis ke inspect_appium.log."""
import sys, inspect
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
out = []
def log(m):
    print(m, flush=True)
    out.append(str(m))
log("=== INSPECT APPIUM START ===")
try:
    import appium
    log(f"appium pkg file={getattr(appium, '__file__', '?')}")
    try:
        import importlib.metadata as md
        log(f"Appium-Python-Client=={md.version('Appium-Python-Client')}")
    except Exception as e:
        log(f"versi EXC {e}")
    from appium import webdriver
    log(f"Remote signature: {inspect.signature(webdriver.Remote)}")
    log(f"Remote source file: {inspect.getsourcefile(webdriver.Remote)}")
except Exception as e:
    import traceback
    log(f"webdriver EXC {e}")
    log(traceback.format_exc())
try:
    from appium.options.android import UiAutomator2Options
    log(f"UiAutomator2Options methods={[m for m in dir(UiAutomator2Options) if not m.startswith('_')][:60]}")
    o = UiAutomator2Options()
    log(f"has load_capabilities={hasattr(o, 'load_capabilities')}")
    # coba set caps minimal
    try:
        o.udid = "TEST:123"
        o.system_port = 8200
        o.chromedriver_port = 9515
        o.browser_name = "Chrome"
        o.no_reset = True
        o.new_command_timeout = 120
        log("set opts OK")
        try:
            caps = o.to_capabilities() if hasattr(o, 'to_capabilities') else o.to_caps() if hasattr(o, 'to_caps') else None
            log(f"to_capabilities type={type(caps)} keys={list(caps.keys())[:20] if isinstance(caps, dict) else repr(caps)[:500]}")
        except Exception as e:
            log(f"to_capabilities EXC {e}")
    except Exception as e:
        log(f"set opts EXC {e}")
except Exception as e:
    import traceback
    log(f"Options EXC {e}")
    log(traceback.format_exc())
log("=== INSPECT APPIUM DONE ===")
Path(ROOT / "inspect_appium.log").write_text("\n".join(out), encoding="utf-8")
