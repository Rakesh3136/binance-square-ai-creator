CREATE TABLE IF NOT EXISTS nic_virtual_devices (
  id TEXT PRIMARY KEY,
  device_type TEXT NOT NULL UNIQUE CHECK(device_type IN ('android','windows')),
  display_name TEXT NOT NULL,
  lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('not_provisioned','provisioning','stopped','running','error')),
  provider_state TEXT NOT NULL CHECK(provider_state IN ('no_provider','configured','connected','disconnected')),
  provider_name TEXT,
  external_instance_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nic_device_action_requests (
  id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('start','stop','restart')),
  requested_at TEXT NOT NULL,
  request_state TEXT NOT NULL CHECK(request_state IN ('blocked_no_provider','queued','accepted','succeeded','failed','cancelled')),
  result_code TEXT,
  FOREIGN KEY(device_id) REFERENCES nic_virtual_devices(id)
);

CREATE INDEX IF NOT EXISTS idx_nic_device_actions_device_time
ON nic_device_action_requests(device_id, requested_at DESC);

CREATE TRIGGER IF NOT EXISTS nic_device_actions_no_update
BEFORE UPDATE ON nic_device_action_requests
BEGIN
  SELECT RAISE(ABORT, 'device action requests are append-only');
END;

CREATE TRIGGER IF NOT EXISTS nic_device_actions_no_delete
BEFORE DELETE ON nic_device_action_requests
BEGIN
  SELECT RAISE(ABORT, 'device action requests are append-only');
END;
