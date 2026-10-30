"""
chrome_real.py - Lapisan real Phase 7 untuk 2 device WiFi (Chrome URL test).

Tanpa mengubah runner.py inti:
- driver_factory_chrome_real: Appium 2.x + Appium-Python-Client 3.x via
  UiAutomator2Options bila ada, fallback dict caps untuk client lama.
- eksekusi_step_real: tambah penanganan aksi open_url (driver.get(url))
  lalu delegasi ke runner.eksekusi_step untuk aksi lain.
- tambal FakeDriver.get bila belum ada (agar unit test open_url jalan).

Pakai dari skrip real:
    from backend.orchestrator import chrome_real
    chrome_real.pasang_open_url()
    hasil = await jalankan_session(sid, chrome_real.driver_factory_chrome_real)
"""
from typing import Dict


def driver_factory_chrome_real(device: dict, caps: dict):
    """Buat Appium session Chrome ke satu device WiFi (client 3.x/6.x)."""
    from backend.orchestrator.runner import server_url_untuk_device
    try:
        from appium import webdriver
    except Exception as e:
        raise RuntimeError(f"Appium-Python-Client belum terpasang: {e}")
    url = server_url_untuk_device(device)
    # Client 6.x wajib keyword-only: Remote(command_executor=..., options=...).
    try:
        from appium.options.android import UiAutomator2Options
        opts = UiAutomator2Options()
        try:
            opts.load_capabilities(dict(caps))
        except Exception:
            # Fallback manual bila load_capabilities tak tersedia.
            try:
                udid = str(caps.get("udid") or caps.get("appium:udid") or device.get("adb_id") or "")
                if udid:
                    opts.udid = udid
            except Exception:
                pass
            try:
                sys_port = caps.get("systemPort", caps.get("appium:systemPort"))
                if sys_port is not None:
                    opts.system_port = int(sys_port)
            except Exception:
                pass
            try:
                chrome_port = caps.get("chromedriverPort", caps.get("appium:chromedriverPort"))
                if chrome_port is None:
                    chrome_port = caps.get("chromeDriverPort")
                if chrome_port is not None:
                    opts.chromedriver_port = int(chrome_port)
            except Exception:
                pass
            try:
                browser = caps.get("browserName") or caps.get("appium:browserName") or "Chrome"
                opts.browser_name = str(browser)
            except Exception:
                pass
        try:
            return webdriver.Remote(command_executor=url, options=opts)
        except TypeError:
            # Client 2.x/3.x positional (url, options).
            return webdriver.Remote(url, opts)
    except Exception as e_opts:
        raise RuntimeError(f"Gagal buat Appium session ke {url}: {e_opts}")


async def eksekusi_step_real(driver, step: dict, data: dict) -> Dict:
    """Eksekusi satu step + dukung open_url, sisanya ke runner asli."""
    from backend.orchestrator import runner as _r
    aksi = (step.get("action") or "").strip()
    if aksi == "open_url":
        params = step.get("params") or {}
        url = str(params.get("url") or params.get("text") or "").strip()
        if not url:
            raise ValueError("Step open_url wajib punya params.url.")
        # Resolusi {{kunci}} bila data uji menyediakan URL dinamis.
        try:
            url = _r._resolusi_teks({"text": url}, data or {})
        except Exception:
            pass
        try:
            out = driver.get(url)
            import asyncio as _aio
            if _aio.iscoroutine(out):
                await out
        except Exception as e:
            raise RuntimeError(f"Gagal buka URL {url}: {e}")
        try:
            driver.current_url = url
        except Exception:
            pass
        # NOTE: jangan append kunjungan di sini bila driver sudah mencatat
        # sendiri (FakeDriver.get sudah append). Real Appium driver tak punya
        # atribut kunjungan sehingga blok ini aman dilewat.
        return {"ok": True, "action": "open_url", "url": url}
    return await _r.eksekusi_step(driver, step, data or {})


def pasang_open_url() -> None:
    """Tambal runner.eksekusi_step agar jalankan_session dukung open_url.

    Idempoten + anti-rekursi: runner inti kini sudah dukung open_url
    (Fake + Appium), jadi patch hanya dipasang sekali dan delegasi ke
    implementasi asli bila aksi bukan open_url khusus.
    """
    from backend.orchestrator import runner as _r
    if getattr(_r.eksekusi_step, "_otomet_open_url_patched", False):
        return
    asli = _r.eksekusi_step

    async def _terpatch(driver, step: dict, data: dict):
        aksi = ((step or {}).get("action") or "").strip()
        if aksi == "open_url":
            return await eksekusi_step_real(driver, step, data or {})
        return await asli(driver, step, data or {})

    _terpatch._otomet_open_url_patched = True  # type: ignore
    _r.eksekusi_step = _terpatch  # type: ignore
    # Tambal FakeDriver.get bila belum ada (untuk simulasi open_url lawas).
    try:
        if not hasattr(_r.FakeDriver, "get"):
            def _fake_get(self, url: str):
                self.kunjungan.append(str(url))
                self.current_url = str(url)
                gagal = (self.gagal_pada or {}).get(len(self.kunjungan))
                if gagal:
                    raise Exception(gagal)
            _r.FakeDriver.get = _fake_get  # type: ignore
    except Exception:
        pass
