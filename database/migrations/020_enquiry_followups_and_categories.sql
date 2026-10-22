-- Migration: 020_enquiry_followups_and_categories.sql
-- Description: Adds lead categories, timing preferences, loss reasons and multi-turn follow-ups timeline.

ALTER TABLE enquiries ADD COLUMN category TEXT DEFAULT 'WARM';
ALTER TABLE enquiries ADD COLUMN preferred_timing TEXT DEFAULT 'ANY';
ALTER TABLE enquiries ADD COLUMN loss_reason TEXT;

CREATE TABLE IF NOT EXISTS enquiry_follow_ups (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    enquiry_id              INTEGER NOT NULL REFERENCES enquiries(id) ON DELETE CASCADE,
    follow_up_date          DATE NOT NULL,
    call_type               TEXT NOT NULL DEFAULT 'PHONE',  -- PHONE, WALK_IN, WHATSAPP, VISIT
    discussion_notes        TEXT NOT NULL,
    category_after_call     TEXT NOT NULL DEFAULT 'WARM',   -- HOT, WARM, COLD, LOST, CONVERTED
    next_follow_up_date     DATE,
    counselor_name          TEXT,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_enquiries_category ON enquiries(category);
CREATE INDEX IF NOT EXISTS idx_followups_enquiry_id ON enquiry_follow_ups(enquiry_id);
CREATE INDEX IF NOT EXISTS idx_followups_next_date ON enquiry_follow_ups(next_follow_up_date);
