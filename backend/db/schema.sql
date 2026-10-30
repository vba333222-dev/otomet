-- schema.sql - Database schema untuk Sistem Analisa Website & Automation Appium
-- SQLite dengan WAL mode untuk concurrency
-- Berdasarkan ERD-Web-Automation-Appium-System.md

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CLIENTS - Klien/website yang dianalisa & diuji
-- ============================================================================
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    base_url TEXT NOT NULL,
    min_delay_ms INTEGER DEFAULT 1000,
    max_concurrent_actions INTEGER DEFAULT 5,
    -- Threshold dinamis per klien (§4.3.1 design.md)
    threshold_similarity REAL DEFAULT 0.85,
    threshold_posisi REAL DEFAULT 0.90,
    threshold_tinggi_fallback REAL DEFAULT 0.80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clients_nama ON clients(nama);

-- ============================================================================
-- PAGES - Halaman yang dianalisa per klien
-- ============================================================================
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'analyzing', 'analyzed', 'failed')),
    last_analyzed_at TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pages_client_id ON pages(client_id);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);

-- ============================================================================
-- ELEMENTS - Elemen interaktif yang terdeteksi per halaman
-- ============================================================================
CREATE TABLE IF NOT EXISTS elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    role_label TEXT NOT NULL,
    -- Selectors disimpan sebagai JSON string (SQLite tidak punya tipe JSON native)
    selectors_json TEXT NOT NULL,
    text_snapshot TEXT,
    -- Bounding box disimpan sebagai JSON: {x, y, width, height}
    bbox_snapshot TEXT NOT NULL,
    confidence REAL NOT NULL,
    approved INTEGER DEFAULT 0 CHECK(approved IN (0, 1)),
    manifest_version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_elements_page_id ON elements(page_id);
CREATE INDEX IF NOT EXISTS idx_elements_role_label ON elements(role_label);
CREATE INDEX IF NOT EXISTS idx_elements_confidence ON elements(confidence);
CREATE INDEX IF NOT EXISTS idx_elements_approved ON elements(approved);

-- ============================================================================
-- SCENARIOS - Skenario pengujian yang disusun manual oleh operator
-- ============================================================================
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    nama_fungsi TEXT NOT NULL,
    -- Steps disimpan sebagai JSON array: [{action, role_label, params}, ...]
    steps_json TEXT NOT NULL,
    versi INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scenarios_client_id ON scenarios(client_id);

-- ============================================================================
-- TEST_DATA_POOL - Pool data uji untuk skenario
-- ============================================================================
CREATE TABLE IF NOT EXISTS test_data_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    -- Data disimpan sebagai JSON: {email, password, ...}
    data_json TEXT NOT NULL,
    status TEXT DEFAULT 'available' CHECK(status IN ('available', 'assigned', 'used')),
    assigned_to_device_id INTEGER,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to_device_id) REFERENCES devices(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_test_data_pool_scenario_id ON test_data_pool(scenario_id);
CREATE INDEX IF NOT EXISTS idx_test_data_pool_status ON test_data_pool(status);

-- ============================================================================
-- DEVICES - Device Android fisik (Xiaomi Redmi 12C)
-- ============================================================================
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adb_id TEXT NOT NULL UNIQUE,
    appium_port INTEGER NOT NULL UNIQUE,
    status TEXT DEFAULT 'offline' CHECK(status IN ('idle', 'busy', 'offline')),
    ram_gb INTEGER,
    last_health_check_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_adb_id ON devices(adb_id);

-- ============================================================================
-- SESSIONS - Sesi pair (2 device) untuk pengujian
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    pair_label TEXT NOT NULL,
    device_a_id INTEGER NOT NULL,
    device_b_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (device_a_id) REFERENCES devices(id) ON DELETE RESTRICT,
    FOREIGN KEY (device_b_id) REFERENCES devices(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_sessions_client_id ON sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

-- ============================================================================
-- SCENARIO_ASSIGNMENTS - Assignment skenario ke device dalam sesi
-- ============================================================================
CREATE TABLE IF NOT EXISTS scenario_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    scenario_id INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE RESTRICT,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_scenario_assignments_session_id ON scenario_assignments(session_id);
CREATE INDEX IF NOT EXISTS idx_scenario_assignments_device_id ON scenario_assignments(device_id);

-- ============================================================================
-- RUNS - Hasil eksekusi skenario
-- ============================================================================
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_assignment_id INTEGER NOT NULL,
    test_data_id INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running' CHECK(status IN ('running', 'passed', 'failed', 'blocked')),
    -- Kategori kegagalan granular
    failure_category TEXT CHECK(failure_category IN ('mapping_error', 'timeout', 'server_rejected', 'infra_error', 'validation_error', NULL)),
    log_path TEXT,
    screenshot_dir TEXT,
    video_path TEXT,
    FOREIGN KEY (scenario_assignment_id) REFERENCES scenario_assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (test_data_id) REFERENCES test_data_pool(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_scenario_assignment_id ON runs(scenario_assignment_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);

-- ============================================================================
-- RECALIBRATION_LOG - Log hasil recalibration
-- ============================================================================
CREATE TABLE IF NOT EXISTS recalibration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_batch_id TEXT NOT NULL,
    page_id INTEGER NOT NULL,
    -- Hasil per elemen disimpan sebagai JSON: [{element_id, status, old_selector, new_selector}, ...]
    hasil_per_elemen TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recalibration_log_run_batch_id ON recalibration_log(run_batch_id);
CREATE INDEX IF NOT EXISTS idx_recalibration_log_page_id ON recalibration_log(page_id);

-- ============================================================================
-- BROADCAST_ACTIONS - Aksi broadcast ke banyak device
-- ============================================================================
CREATE TABLE IF NOT EXISTS broadcast_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    target_role_or_coord TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_broadcast_actions_triggered_at ON broadcast_actions(triggered_at);

-- ============================================================================
-- BROADCAST_ACTION_DEVICES - Device yang ditarget oleh broadcast
-- ============================================================================
CREATE TABLE IF NOT EXISTS broadcast_action_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broadcast_action_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    included INTEGER DEFAULT 1 CHECK(included IN (0, 1)),
    exclude_reason TEXT,
    FOREIGN KEY (broadcast_action_id) REFERENCES broadcast_actions(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_broadcast_action_devices_broadcast_id ON broadcast_action_devices(broadcast_action_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_action_devices_device_id ON broadcast_action_devices(device_id);
