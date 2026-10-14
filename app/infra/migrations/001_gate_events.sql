-- Gate log: every entry/exit seen by a gate camera.
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plate       TEXT NOT NULL,
    display     TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    gate        TEXT NOT NULL DEFAULT 'main',
    confidence  REAL NOT NULL,
    image_path  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_plate ON events (plate, created_at);
