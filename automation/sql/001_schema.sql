-- IP12 automation database (basic v0.1)
-- Loaded automatically the first time the Postgres container starts.

-- One test session with the robot
CREATE TABLE IF NOT EXISTS runs (
  id          SERIAL PRIMARY KEY,
  run_code    TEXT UNIQUE NOT NULL,          -- e.g. "run-012"
  started_at  TIMESTAMPTZ DEFAULT now(),
  operator    TEXT,                          -- who ran the test
  setup       TEXT,                          -- camera / robot setup notes
  notes       TEXT
);

-- Every box YOLO detects (written by n8n workflow "YOLO Ingest")
CREATE TABLE IF NOT EXISTS detections (
  id             BIGSERIAL PRIMARY KEY,
  created_at     TIMESTAMPTZ DEFAULT now(),
  run_code       TEXT,
  frame_id       INTEGER,
  box_id         TEXT,
  class          TEXT NOT NULL,
  confidence     REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  x              REAL, y REAL, w REAL, h REAL, -- bounding box in pixels
  model_version  TEXT NOT NULL DEFAULT 'unknown'
);
CREATE INDEX IF NOT EXISTS idx_detections_run  ON detections (run_code);
CREATE INDEX IF NOT EXISTS idx_detections_time ON detections (created_at);

-- Human evaluation team results (later: from Google Form)
CREATE TABLE IF NOT EXISTS evaluations (
  id                SERIAL PRIMARY KEY,
  created_at        TIMESTAMPTZ DEFAULT now(),
  run_code          TEXT,
  box_id            TEXT,
  placed_correctly  BOOLEAN,
  accuracy          SMALLINT CHECK (accuracy BETWEEN 1 AND 5),
  evaluator         TEXT,
  comment           TEXT
);

-- Weekly WP "commits" (later: written by workflow "Weekly WP Commit")
CREATE TABLE IF NOT EXISTS wp_changelog (
  id        SERIAL PRIMARY KEY,
  week      TEXT,
  date      DATE,
  hash      TEXT,
  type      TEXT,
  task_id   TEXT,
  message   TEXT,
  owner     TEXT
);
