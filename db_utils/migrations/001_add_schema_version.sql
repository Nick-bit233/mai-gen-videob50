-- Migration: Create schema_version table
-- Version: 1.1
-- Description: Add schema versioning support to track database structure changes

-- Create the schema_version table to track database migrations
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    description TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial version record
INSERT OR IGNORE INTO schema_version (version, description)
VALUES ('1.0', 'Initial database schema with all core tables');
