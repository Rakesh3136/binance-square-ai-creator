CREATE TABLE IF NOT EXISTS nic_conversations (
 id TEXT PRIMARY KEY,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nic_conversations_updated_at ON nic_conversations(updated_at);
CREATE TABLE IF NOT EXISTS nic_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 conversation_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),
 content TEXT NOT NULL,
 FOREIGN KEY(conversation_id) REFERENCES nic_conversations(id)
);
CREATE INDEX IF NOT EXISTS idx_nic_messages_conversation_id_id ON nic_messages(conversation_id,id DESC);
