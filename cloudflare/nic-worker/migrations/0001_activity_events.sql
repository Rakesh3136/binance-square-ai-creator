CREATE TABLE IF NOT EXISTS activity_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  task_id TEXT,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  error_code TEXT
);

CREATE INDEX IF NOT EXISTS idx_activity_events_created_at ON activity_events(created_at);

CREATE TRIGGER IF NOT EXISTS activity_events_no_update
BEFORE UPDATE ON activity_events
BEGIN
  SELECT RAISE(ABORT, 'activity journal is append-only');
END;

CREATE TRIGGER IF NOT EXISTS activity_events_no_delete
BEFORE DELETE ON activity_events
BEGIN
  SELECT RAISE(ABORT, 'activity journal is append-only');
END;
