-- Migration 0007: add sync_warning column to turn_records

ALTER TABLE turn_records ADD COLUMN sync_warning TEXT;
