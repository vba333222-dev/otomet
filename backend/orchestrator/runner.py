"""
runner.py - Execution Engine paralel Appium (Phase 7, S4.5 + S5 Fase 7).

Tiap device menjalankan skenarionya sendiri secara independen
dengan data ujinya masing-masing. Gagal satu device tidak
menghentikan device lain. Anti-race antar device satu pair:
klaim data atomik + stagger start (jitter) + semaphore
max_concurrent_actions per klien.

Fail-safe: gate recalibration dicek ulang sebelum jalan,
driver/APPIUM hilang = infra_error, bukan dipaksa lolos.
Tanpa device fisik, pakai driver_factory injeksi (FakeDriver
untuk unit test / smoke). Eksekusi nyata butuh Appium server
per device (port 4723+count) + Appium-Python-Client.
"""
import asyncio
import random
import time
from typing import Dict, List, Optional, Callable, Any

from backend.db.repositories.device_repo import DeviceRepository
from backend.db.repositories.client_repo import ClientRepository
from backend.db.repositories.scenario_repo import ScenarioRepository
from backend.db.repositories.session_repo import SessionRepository, AssignmentRepository
from backend.db.repositories.run_repo import TestDataRepository, RunRepository


# Kategori gagal granular (ikut CHECK skema runs).
FAILURE_MAPPING = "mapping_error"
FAILURE_TIMEOUT = "timeout"
FAILURE_SERVER = "server_rejected"
FAILURE_INFRA = "infra_error"
FAILURE_VALIDATION = "validation_error"

# Aksi skenario yang didukung runner (selaras ALLOWED_ACTIONS).
# back/wake hanya untuk broadcast fisik.
# open_url khusus Phase 7-real: navigasi Chrome ke URL uji.
RUNNABLE_ACTIONS = {"click", "fill", "assert_visible", "scroll", "back", "wake", "open_url"}


def bangun_caps(device: dict, appium_port: Optional[int] = None,
               browser_nama: str = "Chrome") -> dict:
    """Susun desired capabilities Appium untuk satu device.

    Mode real 2-device WiFi: Chrome browser test (Appium 2.x + UiAutomator2).
    Port unik per device: systemPort & chromedriverPort diturunkan
    dari appium_port agar 10 sesi paralel tak tabrakan.

    Kompatibel ganda:
    - Kunci polos (systemPort, chromedriverPort, ...) untuk unit test lama.
    - Kunci W3C ber-prefix (appium:systemPort, ...) untuk Appium 2.x nyata.
    - Alias lawas chromeDriverPort tetap diisi (salah kapital tapi dipakai
      beberapa tutorial) agar tak ada kode lama yang KeyError.
    """
    port = int(appium_port or device.get("appium_port") or 4723)
    basis = port - 4723
    system_port = 8200 + basis
    chrome_port = 9515 + basis
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "appium:automationName": "UiAutomator2",
        "deviceName": device.get("adb_id") or "Android",
        "appium:deviceName": device.get("adb_id") or "Android",
        "udid": device.get("adb_id"),
        "appium:udid": device.get("adb_id"),
        # Kunci polos (dipakai test_port_unik + kode lama).
        "systemPort": system_port,
        "chromedriverPort": chrome_port,
        # Alias lawas (kapital D) — jangan dihapus, hanya alias.
        "chromeDriverPort": chrome_port,
        # Kunci W3C resmi untuk Appium 2.x.
        "appium:systemPort": system_port,
        "appium:chromedriverPort": chrome_port,
        "browserName": browser_nama,
        "appium:browserName": browser_nama,
        "newCommandTimeout": 120,
        "appium:newCommandTimeout": 120,
        "noReset": True,
        "appium:noReset": True,
        "autoGrantPermissions": True,
        "appium:autoGrantPermissions": True,
        # Chrome di device fisik: biarkan chromedriver autodownload
        # bila versi Chrome HP beda dengan driver bawaan server.
        "appium:chromedriver_autodownload": True,
        # Redmi 12C non-root: perintah hidden_api_policy butuh
        # WRITE_SECURE_SETTINGS -> gagal 255. Abaikan agar sesi tetap jalan.
        "appium:ignoreHiddenApiPolicyError": True,
        "appium:skipUnlock": True,
        "appium:noSign": True,
    }
    return caps


def server_url_untuk_device(device: dict) -> str:
    """URL Appium server lokal untuk satu device.

    Appium 2.x default listen di `/` (tanpa `/wd/hub`).
    Client 6.x `Remote(command_executor=...)` wajib root URL,
    `/wd/hub` hanya bila server dijalankan dengan `--base-path=/wd/hub`.
    """
    port = int(device.get("appium_port") or 4723)
    return f"http://127.0.0.1:{port}"


def klasifikasi_error(exc: Exception) -> str:
    """Petakan exception ke failure_category granular."""
    nama = type(exc).__name__.lower()
    pesan = str(exc).lower()
    teks = nama + " " + pesan
    if "timeout" in teks or "wait" in teks and "expired" in teks:
        return FAILURE_TIMEOUT
    if "nosuchelement" in teks or "no such element" in teks or "mapping" in teks:
        return FAILURE_MAPPING
    if "stale" in teks or "not interactable" in teks or "not visible" in teks:
        return FAILURE_MAPPING
    if "session" in teks and ("not created" in teks or "refused" in teks or "connect" in teks):
        return FAILURE_INFRA
    if "adb" in teks or "device" in teks and ("offline" in teks or "disconnect" in teks):
        return FAILURE_INFRA
    if "server" in teks or "rejected" in teks or "rate" in teks or "5xx" in teks or "400" in teks:
        return FAILURE_SERVER
    if "assert" in teks or "validation" in teks or "expected" in teks:
        return FAILURE_VALIDATION
    return FAILURE_INFRA


def _jitter_ms(client: Optional[dict]) -> int:
    """Jitter stagger antar device satu pair (hindari race serentak)."""
    basis = 1000
    try:
        if client and client.get("min_delay_ms"):
            basis = int(client["min_delay_ms"])
    except (TypeError, ValueError):
        basis = 1000
    basis = min(max(basis, 200), 5000)
    return basis + random.randint(0, 500)


_SEMAPHORES: Dict[int, asyncio.Semaphore] = {}


def _semaphore_untuk_klien(client: Optional[dict]) -> asyncio.Semaphore:
    """Semaphore max_concurrent_actions per klien (default 5)."""
    cid = 0
    maks = 5
    try:
        if client:
            cid = int(client.get("id") or 0)
            maks = int(client.get("max_concurrent_actions") or 5)
    except (TypeError, ValueError):
        maks = 5
    maks = min(max(maks, 1), 10)
    key = cid or -1
    sem = _SEMAPHORES.get(key)
    if sem is None:
        sem = asyncio.Semaphore(maks)
        _SEMAPHORES[key] = sem
    return sem


class FakeDriver:
    """Driver palsu untuk unit test / smoke tanpa device fisik."""

    def __init__(self, adb_id: str = "FAKE", gagal_pada=None):
        self.adb_id = adb_id
        self.gagal_pada = dict(gagal_pada or {})
        self.aksi: List[Dict] = []
        self._step = -1
        self.kunjungan: List[str] = []
        self.current_url: str = ""

    def get(self, url: str):
        """Navigasi Fake (untuk aksi open_url simulasi)."""
        self._naik()
        self.kunjungan.append(str(url))
        self.current_url = str(url)
        gagal = (self.gagal_pada or {}).get(self._step)
        if gagal:
            raise Exception(gagal)
        self.aksi.append({"action": "open_url", "url": str(url)})

    def _naik(self) -> int:
        self._step += 1
        return self._step

    def klik(self, target: str):
        idx = self._naik()
        if idx in self.gagal_pada:
            raise RuntimeError(self.gagal_pada[idx])
        self.aksi.append({"action": "click", "target": target})

    def isi(self, target: str, teks: str):
        idx = self._naik()
        if idx in self.gagal_pada:
            raise RuntimeError(self.gagal_pada[idx])
        self.aksi.append({"action": "fill", "target": target, "text": teks})

    def assert_tampak(self, target: str):
        idx = self._naik()
        if idx in self.gagal_pada:
            raise AssertionError(self.gagal_pada[idx])
        self.aksi.append({"action": "assert_visible", "target": target})

    def gulir(self, arah: str = "down"):
        idx = self._naik()
        if idx in self.gagal_pada:
            raise RuntimeError(self.gagal_pada[idx])
        self.aksi.append({"action": "scroll", "direction": arah})

    def kembali(self):
        idx = self._naik()
        if idx in self.gagal_pada:
            raise RuntimeError(self.gagal_pada[idx])
        self.aksi.append({"action": "back"})

    def bangun(self):
        self._naik()
        self.aksi.append({"action": "wake"})

    def quit(self):
        self.aksi.append({"action": "quit"})


def _resolusi_teks(params: dict, data: dict) -> str:
    """Resolusi params.text dari data uji (dukung {{kunci}} / $kunci)."""
    mentah = str((params or {}).get("text") or "")
    teks = mentah.strip()
    if teks.startswith("{{") and teks.endswith("}}"):
        kunci = teks[2:-2].strip()
        return str(data.get(kunci, ""))
    if teks.startswith("$"):
        return str(data.get(teks[1:], ""))
    return mentah


async def eksekusi_step(driver, step: dict, data: dict) -> Dict:
    """Eksekusi satu step via driver fake / Appium nyata."""
    aksi = (step.get("action") or "").strip()
    target = (step.get("role_label") or "").strip()
    params = step.get("params") or {}
    if aksi not in RUNNABLE_ACTIONS:
        raise ValueError(f"Aksi '{aksi}' tak didukung runner.")
    if isinstance(driver, FakeDriver):
        if aksi == "open_url":
            mentah = str(params.get("url") or params.get("text") or "").strip()
            if not mentah:
                raise ValueError("Step open_url wajib punya params.url.")
            url = _resolusi_teks({"text": mentah}, data or {})
            driver.get(url)
            return {"action": aksi, "target": target, "ok": True, "url": url}
        if aksi == "click":
            driver.klik(target)
        elif aksi == "fill":
            driver.isi(target, _resolusi_teks(params, data))
        elif aksi == "assert_visible":
            driver.assert_tampak(target)
        elif aksi == "scroll":
            driver.gulir(str(params.get("direction", "down")))
        elif aksi == "back":
            driver.kembali()
        elif aksi == "wake":
            driver.bangun()
        return {"action": aksi, "target": target, "ok": True}
    return await _eksekusi_via_appium(driver, aksi, target, params, data)


async def _eksekusi_via_appium(driver, aksi: str, target: str,
                               params: dict, data: dict) -> Dict:
    """Eksekusi via Appium WebDriver nyata (blocking -> thread)."""
    if aksi == "open_url":
        mentah = str(params.get("url") or params.get("text") or "").strip()
        if not mentah:
            raise ValueError("Step open_url wajib punya params.url.")
        url = _resolusi_teks({"text": mentah}, data or {})

        def _buka():
            out = driver.get(url)
            return out

        res = await asyncio.to_thread(_buka)
        if asyncio.iscoroutine(res):
            await res
        return {"action": aksi, "target": target, "ok": True, "url": url}

    def _kerja():
        if aksi == "back":
            driver.back()
            return {"action": aksi, "ok": True}
        if aksi == "wake":
            try:
                driver.execute_script("mobile: wakeUp", {})
            except Exception:
                pass
            return {"action": aksi, "ok": True}
        if aksi == "scroll":
            arah = str(params.get("direction", "down")).lower()
            driver.execute_script("mobile: scrollGesture", {
                "direction": arah, "percent": 0.8, "speed": 800})
            return {"action": aksi, "target": target, "ok": True}
        el = driver.find_element("accessibility id", target)
        if aksi == "click":
            el.click()
        elif aksi == "fill":
            el.clear()
            el.send_keys(_resolusi_teks(params, data))
        elif aksi == "assert_visible":
            if not el.is_displayed():
                raise AssertionError(f"Elemen '{target}' tak tampak.")
        return {"action": aksi, "target": target, "ok": True}
    return await asyncio.to_thread(_kerja)


def driver_factory_fake(device: dict, caps: dict):
    """Factory FakeDriver untuk mode simulate (tanpa Appium/kabel)."""
    return FakeDriver(device.get("adb_id", "FAKE"))


def driver_factory_default(device: dict, caps: dict):
    """Factory driver nyata (butuh Appium server + client 3.x/6.x)."""
    try:
        from appium import webdriver  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Appium-Python-Client belum terpasang. "
            f"pip install Appium-Python-Client. ({e})")
    url = server_url_untuk_device(device)
    # Client 6.x: Remote(command_executor, options=UiAutomator2Options).
    try:
        from appium.options.android import UiAutomator2Options  # type: ignore
        opts = UiAutomator2Options()
        try:
            opts.load_capabilities(dict(caps))
        except Exception:
            pass
        try:
            return webdriver.Remote(command_executor=url, options=opts)
        except TypeError:
            # Signature lama (client 2.x/3.x positional).
            return webdriver.Remote(url, opts)
    except Exception as e_opts:
        # Fallback terakhir: coba pola lama bila client lawas.
        try:
            from appium import webdriver as wd2  # type: ignore
            try:
                return wd2.Remote(url, dict(caps))  # type: ignore
            except TypeError:
                pass
        except Exception:
            pass
        raise RuntimeError(f"Gagal buat Appium session ke {url}: {e_opts}")

async def _buat_driver(device: dict, caps: dict, driver_factory=None):
    """Buat driver via factory (dukung sync/async)."""
    factory = driver_factory or driver_factory_default
    if factory is driver_factory_default:
        # Factory nyata blocking -> thread, panggil sekali saja.
        return await asyncio.to_thread(lambda: factory(device, caps))
    hasil = factory(device, caps)
    if asyncio.iscoroutine(hasil):
        return await hasil
    return hasil
async def jalankan_assignment(assignment_id: int, driver_factory=None,
                              test_data_id=None, klaim_otomatis=True,
                              stagger_index=0) -> Dict:
    """Jalankan satu assignment (satu device) sampai tuntas."""
    from backend.recalibration.service import cek_gate_untuk_skenario
    assign_repo = AssignmentRepository()
    run_repo = RunRepository()
    data_repo = TestDataRepository()
    detail = await assign_repo.get_detail(assignment_id)
    if not detail:
        raise ValueError(f"Assignment {assignment_id} tidak ditemukan.")
    sesi = await SessionRepository().get_by_id(detail["session_id"])
    if not sesi:
        raise ValueError(f"Sesi {detail['session_id']} tidak ditemukan.")
    if sesi["status"] != "running":
        raise ValueError(f"Sesi {sesi['id']} status '{sesi['status']}'.")
    skenario = await ScenarioRepository().get_by_id(detail["scenario_id"])
    if not skenario:
        raise ValueError(f"Skenario {detail['scenario_id']} tidak ditemukan.")
    device = await DeviceRepository().get_by_id(detail["device_id"])
    if not device:
        raise ValueError(f"Device {detail['device_id']} tidak ditemukan.")
    if device["status"] == "offline":
        raise ValueError(f"Device {device['adb_id']} offline.")
    client = await ClientRepository().get_by_id(skenario["client_id"])
    gate = await cek_gate_untuk_skenario(skenario["id"])
    if not gate.get("boleh_jalan"):
        run_id = await run_repo.mulai(assignment_id, test_data_id)
        await run_repo.selesaikan(run_id, "blocked", FAILURE_MAPPING)
        return {"assignment_id": assignment_id, "run_id": run_id,
                "status": "blocked", "failure_category": FAILURE_MAPPING,
                "alasan": f"Gate tertahan: {gate.get('alasan')}", "gate": gate}
    data_row = None
    data_isi: dict = {}
    if test_data_id is not None:
        data_row = await data_repo.get_by_id(test_data_id)
        if not data_row:
            raise ValueError(f"Data uji {test_data_id} tidak ditemukan.")
        if data_row["scenario_id"] != skenario["id"]:
            raise ValueError("Data uji beda skenario.")
        if data_row["status"] == "used":
            raise ValueError(f"Data uji {test_data_id} sudah used.")
        data_isi = data_row.get("data") or {}
    elif klaim_otomatis:
        diklaim = await data_repo.klaim_atomik(skenario["id"], device["id"])
        if diklaim:
            data_row = diklaim
            data_isi = diklaim.get("data") or {}
    run_id = await run_repo.mulai(
        assignment_id, data_row["id"] if data_row else None)
    if stagger_index > 0:
        jeda = _jitter_ms(client) * stagger_index / 1000.0
        await asyncio.sleep(min(jeda, 10.0))
    return await _jalan_steps(
        assignment_id, run_id, skenario, device, client,
        data_row, data_isi, driver_factory)
async def _jalan_steps(assignment_id, run_id, skenario, device,
                       client, data_row, data_isi, driver_factory) -> Dict:
    """Loop steps dengan semaphore klien + catat run granular."""
    run_repo = RunRepository()
    data_repo = TestDataRepository()
    sem = _semaphore_untuk_klien(client)
    steps = skenario.get("steps") or []
    caps = bangun_caps(device)
    driver = None
    hasil_steps: List[Dict] = []
    tunda = 0.5
    try:
        if client and client.get("min_delay_ms"):
            tunda = max(int(client["min_delay_ms"]), 100) / 1000.0
    except (TypeError, ValueError):
        tunda = 0.5
    try:
        async with sem:
            try:
                driver = await _buat_driver(device, caps, driver_factory)
            except Exception as e:
                kat = klasifikasi_error(e)
                await run_repo.selesaikan(run_id, "failed", kat)
                if data_row:
                    await data_repo.tandai_used(data_row["id"])
                return {"assignment_id": assignment_id, "run_id": run_id,
                        "status": "failed", "failure_category": kat,
                        "alasan": f"Gagal buka sesi Appium: {e}", "caps": caps}
            for idx, step in enumerate(steps):
                try:
                    hasil = await eksekusi_step(driver, step, data_isi)
                    hasil_steps.append({**hasil, "step_index": idx})
                except AssertionError as e:
                    await run_repo.selesaikan(run_id, "failed", FAILURE_VALIDATION)
                    if data_row:
                        await data_repo.tandai_used(data_row["id"])
                    return {"assignment_id": assignment_id, "run_id": run_id,
                            "status": "failed",
                            "failure_category": FAILURE_VALIDATION,
                            "alasan": f"Step {idx + 1} gagal validasi: {e}",
                            "steps_ok": hasil_steps}
                except Exception as e:
                    kat = klasifikasi_error(e)
                    await run_repo.selesaikan(run_id, "failed", kat)
                    if data_row:
                        await data_repo.tandai_used(data_row["id"])
                    return {"assignment_id": assignment_id, "run_id": run_id,
                            "status": "failed", "failure_category": kat,
                            "alasan": f"Step {idx + 1} gagal ({kat}): {e}",
                            "steps_ok": hasil_steps}
                await asyncio.sleep(min(tunda, 5.0))
            await run_repo.selesaikan(run_id, "passed")
            if data_row:
                await data_repo.tandai_used(data_row["id"])
            return {"assignment_id": assignment_id, "run_id": run_id,
                    "status": "passed", "steps_ok": hasil_steps,
                    "test_data_id": data_row["id"] if data_row else None}
    finally:
        if driver is not None:
            try:
                out = driver.quit() if hasattr(driver, "quit") else None
                if asyncio.iscoroutine(out):
                    await out
            except Exception:
                pass


async def jalankan_session(session_id: int, driver_factory=None,
                           test_data_ids=None) -> Dict:
    """Jalankan semua assignment satu sesi paralel (satu pair)."""
    sesi = await SessionRepository().get_by_id(session_id)
    if not sesi:
        raise ValueError(f"Sesi {session_id} tidak ditemukan.")
    if sesi["status"] != "running":
        raise ValueError(f"Sesi {session_id} status '{sesi['status']}'.")
    tugas = await SessionRepository().get_assignments(session_id)
    if not tugas:
        raise ValueError(f"Sesi {session_id} belum punya assignment.")
    if test_data_ids:
        terlihat = list(test_data_ids.values())
        if len(set(terlihat)) != len(terlihat):
            raise ValueError("Dua device satu pair tak boleh pakai data sama.")

    async def _satu(idx: int, tug: dict) -> Dict:
        data_id = (test_data_ids or {}).get(tug["id"])
        try:
            return await jalankan_assignment(
                tug["id"], driver_factory, data_id,
                klaim_otomatis=data_id is None, stagger_index=idx)
        except Exception as e:
            return {"assignment_id": tug["id"], "status": "failed",
                    "failure_category": klasifikasi_error(e),
                    "alasan": f"Gagal sebelum jalan: {e}"}

    hasil = await asyncio.gather(*[_satu(i, t) for i, t in enumerate(tugas)])
    ringkas = {"total": len(hasil), "passed": 0, "failed": 0, "blocked": 0}
    for h in hasil:
        st = h.get("status")
        if st in ringkas:
            ringkas[st] += 1
    dipakai = [h.get("test_data_id") for h in hasil if h.get("test_data_id") is not None]
    ganda = len(set(dipakai)) != len(dipakai) if dipakai else False
    alasan = f"{ringkas['passed']}/{ringkas['total']} passed."
    return {"session_id": session_id, "ringkasan": ringkas,
            "hasil": list(hasil), "data_ganda": ganda, "alasan": alasan}


async def jalankan_broadcast_fisik(client_id: int, action_type: str,
                                    target: str, device_ids=None,
                                    driver_factory=None,
                                    live_override=None) -> Dict:
    """Eksekusi fisik broadcast paralel ke peserta lolos safety check."""
    from backend.orchestrator.broadcast import safety_check_broadcast
    from backend.db.repositories.session_repo import BroadcastRepository
    cek = await safety_check_broadcast(
        client_id, action_type, target, device_ids, live_override)
    if not cek["boleh_jalan"]:
        raise ValueError(f"Broadcast ditolak: {cek['alasan']}")
    repo = BroadcastRepository()
    broadcast_id = await repo.catat_aksi(cek["action_type"], cek["target"])
    for ikut in cek["ikut"]:
        await repo.catat_peserta(broadcast_id, ikut["device_id"], True, "")
    for kec in cek["dikecualikan"]:
        await repo.catat_peserta(broadcast_id, kec["device_id"], False, kec["alasan"])
    aksi = cek["action_type"]
    tgt = cek["target"]

    async def _satu(d: dict) -> Dict:
        dev = await DeviceRepository().get_by_id(d["device_id"])
        basis = dev or d
        caps = bangun_caps(basis)
        driver = None
        try:
            driver = await _buat_driver(basis, caps, driver_factory)
            step = {"action": aksi, "role_label": tgt, "params": {}}
            if aksi == "fill" and "|" in tgt:
                role, teks = tgt.split("|", 1)
                step = {"action": "fill", "role_label": role.strip(),
                        "params": {"text": teks.strip()}}
            await eksekusi_step(driver, step, {})
            return {"device_id": d["device_id"],
                    "adb_id": d.get("adb_id"), "ok": True}
        except Exception as e:
            return {"device_id": d["device_id"],
                    "adb_id": d.get("adb_id"), "ok": False,
                    "failure_category": klasifikasi_error(e),
                    "alasan": str(e)}
        finally:
            if driver is not None:
                try:
                    out = driver.quit() if hasattr(driver, "quit") else None
                    if asyncio.iscoroutine(out):
                        await out
                except Exception:
                    pass

    hasil = await asyncio.gather(*[_satu(d) for d in cek["ikut"]])
    detail = await repo.get_by_id(broadcast_id)
    return {**(detail or {}), "boleh_jalan": True, "alasan": cek["alasan"],
            "ikut": cek["ikut"], "dikecualikan": cek["dikecualikan"],
            "eksekusi": list(hasil)}
