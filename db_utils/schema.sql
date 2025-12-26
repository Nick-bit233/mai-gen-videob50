-- Database schema for mai-gen-videob50 project
-- Version: 1.0
-- Created: 2025-09-29

-- Users table: Stores user information
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    rating_mai INTEGER, -- User's overall maimai rating
    rating_chu REAL,   -- User's overall Chunithm rating
    metadata TEXT,     -- JSON for extra user data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Charts table: Stores unique music chart information
CREATE TABLE IF NOT EXISTS charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_type TEXT NOT NULL, -- 'maimai' or 'chunithm'
    song_id TEXT NOT NULL,
    chart_type INTEGER NOT NULL, -- [maimai] 0, 1, 2 for std, dx, utage(宴) [chunithm] 0 for normal, 1 for WORLD'S END
    level_index INTEGER NOT NULL, -- [maimai] 0-4 for Basic to Re:MASTER, 5 for utage / [chunithm] 0-4 for Basic to ULTIMA, 5 for WORLD'S END
    difficulty TEXT, -- detail level number in text, e.g., '14.9', '15.0'
    max_dx_score INTEGER, -- only for maimai DX
    song_name TEXT,
    artist TEXT,
    video_path TEXT, -- Path to the reference video file, stored in charts instead of configurations.
    video_metadata TEXT,    -- JSON for other config data like video source URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_type, song_id, chart_type, level_index)
);

-- Archives table: Represents a user's saved list of scores (e.g., a B50)
CREATE TABLE IF NOT EXISTS archives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    archive_name TEXT NOT NULL,
    game_type TEXT DEFAULT 'maimai',
    game_version TEXT DEFAULT 'latest', -- game version for update difficulty numbers, latest means auto-sync with web data. e.g., 'maimai CiRCLE'
    sub_type TEXT DEFAULT 'best', -- e.g., 'best', 'custom'
    rating_mai INTEGER,
    rating_chu REAL,
    record_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    metadata TEXT, -- JSON for extra archive data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Records table: Stores a specific score record within an archive
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_id INTEGER NOT NULL,
    chart_id INTEGER NOT NULL,
    order_in_archive INTEGER NOT NULL, -- The position of this record in the archive list, start from 0
    achievement REAL, -- Score(chuni)/achievement percentage(maimai)
    fc_status TEXT,   -- 'fc', 'aj', 'none'.. (chuni) / 'fc', 'ap', 'none'..(maimai)
    fs_status TEXT,   -- 'fc', 'fcr', 'none'.. (chuni) / 'fs', 'fsd', 'none' .. (maimai)
    dx_score INTEGER, -- only for maimai DX
    dx_rating INTEGER, -- only for maimai DX
    chuni_rating REAL, -- only for Chunithm
    play_count INTEGER DEFAULT 0, -- Number of times played, 0 means unknown
    clip_title_name TEXT, -- Custom title for the background text in video
    raw_data TEXT,    -- JSON for any other raw data from source
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (archive_id) REFERENCES archives(id) ON DELETE CASCADE,
    FOREIGN KEY (chart_id) REFERENCES charts(id) ON DELETE RESTRICT, -- Prevent deleting a chart if it's in use
    UNIQUE(archive_id, chart_id) -- A chart can only appear once per archive
);

-- Configurations table: Stores user-defined settings for a record in a specific archive for video generation
CREATE TABLE IF NOT EXISTS configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_id INTEGER NOT NULL,
    chart_id INTEGER NOT NULL,
    background_image_path TEXT, -- Path to the background image
    achievement_image_path TEXT, -- Path to the achievement image
    video_slice_start REAL, -- Custom start time for the video clip
    video_slice_end REAL,   -- Custom end time for the video clip
    comment_text TEXT,      -- User comment to display on the video
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (archive_id) REFERENCES archives(id) ON DELETE CASCADE,
    FOREIGN KEY (chart_id) REFERENCES charts(id) ON DELETE CASCADE,
    UNIQUE(archive_id, chart_id) -- Unique config for a chart within an archive
);

-- Extra video configs table: For intro, ending, and other settings per archive
CREATE TABLE IF NOT EXISTS extra_video_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_id INTEGER NOT NULL,
    config_type TEXT NOT NULL, -- e.g., 'intro', 'ending', 'extra'
    config_index INTEGER DEFAULT 0, -- For ordering multiple intros/endings
    config_data TEXT, -- JSON for config content, like comment text and duration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (archive_id) REFERENCES archives(id) ON DELETE CASCADE
    UNIQUE (archive_id, config_type, config_index) -- Unique ex_config for a type of config within an archive
);

-- Assets table: Tracks generated or used assets like images and videos
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER, -- Optional link to a specific record
    archive_id INTEGER, -- Optional link to a specific archive
    asset_type TEXT NOT NULL, -- e.g., 'background_image', 'font'
    file_path TEXT NOT NULL,
    file_size INTEGER,
    metadata TEXT, -- JSON for extra asset data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE SET NULL,
    FOREIGN KEY (archive_id) REFERENCES archives(id) ON DELETE SET NULL
);

-- Triggers to automatically update the 'updated_at' timestamp
CREATE TRIGGER IF NOT EXISTS update_users_updated_at
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_archives_updated_at
AFTER UPDATE ON archives
FOR EACH ROW
BEGIN
    UPDATE archives SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_records_updated_at
AFTER UPDATE ON records
FOR EACH ROW
BEGIN
    UPDATE records SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_configurations_updated_at
AFTER UPDATE ON configurations
FOR EACH ROW
BEGIN
    UPDATE configurations SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS update_charts_updated_at
AFTER UPDATE ON charts
FOR EACH ROW
BEGIN
    UPDATE charts SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Schema version table - tracks database structure changes
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    description TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial version record
INSERT OR IGNORE INTO schema_version (version, description)
VALUES ('1.0', 'Initial database schema with all core tables');

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_records_archive_chart ON records (archive_id, chart_id);
CREATE INDEX IF NOT EXISTS idx_archives_user ON archives (user_id);
CREATE INDEX IF NOT EXISTS idx_configs_archive_chart ON configurations (archive_id, chart_id);
CREATE INDEX IF NOT EXISTS idx_charts_song ON charts (song_id);
CREATE INDEX IF NOT EXISTS idx_assets_record ON assets (record_id);
CREATE INDEX IF NOT EXISTS idx_assets_archive ON assets (archive_id);