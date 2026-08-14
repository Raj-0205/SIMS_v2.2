-- database/schema/schema.sql

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
