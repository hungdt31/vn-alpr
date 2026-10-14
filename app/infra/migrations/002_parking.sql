-- Parking lot: tickets, typed slots, camera snapshots and visits.
CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'in_use', 'locked')),
    returned_at TEXT
);
CREATE TABLE IF NOT EXISTS slots (
    id           TEXT PRIMARY KEY,
    vehicle_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS captures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    path       TEXT NOT NULL,
    plates     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         INTEGER NOT NULL REFERENCES cards (id),
    slot_id         TEXT NOT NULL REFERENCES slots (id),
    vehicle_type    TEXT NOT NULL,
    vehicle_style   TEXT NOT NULL DEFAULT '{}',
    plate           TEXT NOT NULL,
    display         TEXT NOT NULL,
    plate_ocr       TEXT NOT NULL DEFAULT '',
    ocr_conf        REAL NOT NULL DEFAULT 0,
    edited          INTEGER NOT NULL DEFAULT 0,
    entry_capture   INTEGER REFERENCES captures (id),
    entry_box       TEXT,
    entry_time      TEXT NOT NULL,
    exit_capture    INTEGER REFERENCES captures (id),
    exit_plate_ocr  TEXT,
    exit_match      TEXT,
    exit_time       TEXT,
    fee             INTEGER,
    lost_card       INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT,
    status          TEXT NOT NULL DEFAULT 'parked' CHECK (status IN ('parked', 'exited'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_plate ON sessions (plate, status);
