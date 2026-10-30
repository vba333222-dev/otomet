"""Paket orchestrator — device pool + pairing sesi + broadcast + runner (Phase 7).

Prinsip fail-safe: device ragu/offline/busy = di-exclude, bukan dipaksa ikut.
Recalibration gate wajib lolos sebelum assignment (S4.3).
Anti race-condition antar device satu pair ditangani runner paralel:
klaim data atomik + stagger start (jitter) + semaphore max_concurrent_actions.
"""
from backend.orchestrator.device_pool import (
    daftar_perangkat_adb,
    register_device,
    heartbeat_device,
    health_check_device,
    health_check_semua,
    ambil_device_idle_fifo,
)
from backend.orchestrator.session_manager import (
    buat_sesi_pair,
    tugaskan_skenario,
    akhiri_sesi,
)
from backend.orchestrator.broadcast import (
    safety_check_broadcast,
    jalankan_broadcast,
)
from backend.orchestrator.runner import (
    bangun_caps,
    server_url_untuk_device,
    klasifikasi_error,
    FakeDriver,
    driver_factory_fake,
    driver_factory_default,
    eksekusi_step,
    jalankan_assignment,
    jalankan_session,
    jalankan_broadcast_fisik,
)
from backend.orchestrator.chrome_real import (
    driver_factory_chrome_real,
    eksekusi_step_real,
    pasang_open_url,
)

__all__ = [
    "daftar_perangkat_adb",
    "register_device",
    "heartbeat_device",
    "health_check_device",
    "health_check_semua",
    "ambil_device_idle_fifo",
    "buat_sesi_pair",
    "tugaskan_skenario",
    "akhiri_sesi",
    "safety_check_broadcast",
    "jalankan_broadcast",
    "bangun_caps",
    "server_url_untuk_device",
    "klasifikasi_error",
    "FakeDriver",
    "driver_factory_fake",
    "driver_factory_default",
    "eksekusi_step",
    "jalankan_assignment",
    "jalankan_session",
    "jalankan_broadcast_fisik",
    "driver_factory_chrome_real",
    "eksekusi_step_real",
    "pasang_open_url",
]
