-- Migration: 001_core_entities
-- Description: Baseline schema establishing required core tables for subsequent migrations.
-- Contract verified against existing modules/student repository and DTO.

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    mobile_number TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
