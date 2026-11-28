CREATE TABLE IF NOT EXISTS nic_linux_laptop (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('not_provisioned','provisioning','stopped','running','error')),
  provider_state TEXT NOT NULL CHECK(provider_state IN ('no_provider','configured','connected','disconnected')),
  provider_name TEXT,
  external_instance_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nic_linux_laptop_actions (
  id TEXT PRIMARY KEY,
  laptop_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('start','stop','restart')),
  requested_at TEXT NOT NULL,
  request_state TEXT NOT NULL CHECK(request_state IN ('blocked_no_provider','queued','accepted','succeeded','failed','cancelled')),
  result_code TEXT,
  FOREIGN KEY(laptop_id) REFERENCES nic_linux_laptop(id)
);
CREATE INDEX IF NOT EXISTS idx_nic_linux_laptop_actions_time
ON nic_linux_laptop_actions(laptop_id, requested_at DESC);
CREATE TRIGGER IF NOT EXISTS nic_linux_laptop_actions_no_update
BEFORE UPDATE ON nic_linux_laptop_actions
BEGIN SELECT RAISE(ABORT, 'laptop action requests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS nic_linux_laptop_actions_no_delete
BEFORE DELETE ON nic_linux_laptop_actions
BEGIN SELECT RAISE(ABORT, 'laptop action requests are append-only'); END;
