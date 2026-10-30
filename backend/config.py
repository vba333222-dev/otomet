"""
Konfigurasi minimalis untuk Phase 1 - DOM Scanner.
Log level dan output path untuk hasil analisa.
"""

import os
from pathlib import Path
from enum import Enum


class LogLevel(str, Enum):
    """Level logging dengan color-coding"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"

# Scanner settings
PLAYWRIGHT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))  # ms
WAIT_FOR_STABLE_DOM = int(os.getenv("WAIT_FOR_STABLE_DOM", "2000"))  # ms untuk SPA
USER_AGENT_MOBILE = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# Viewport mobile (sesuai Redmi 12C)
VIEWPORT_WIDTH = 720
VIEWPORT_HEIGHT = 1650

# Axe-core & dom-accessibility-api CDN
AXE_CORE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
DOM_ACCESSIBILITY_API_CDN = "https://cdn.jsdelivr.net/npm/dom-accessibility-api@0.6.3/dist/index.min.js"

# Scoring thresholds (baseline, nanti per-client di Phase 5)
MIN_CONFIDENCE_THRESHOLD = 0.6

# Database paths (Phase 2)
DB_DIR = PROJECT_ROOT / "backend" / "db" / "data"
DB_PATH = str(DB_DIR / "otomet.db")
BACKUP_DIR = PROJECT_ROOT / "backend" / "backup" / "backups"
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

# Ensure Phase 2 directories exist
DB_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

