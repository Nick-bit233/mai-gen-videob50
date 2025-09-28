-- Database schema for mai-gen-videob50 project
-- Version: 1.0
-- Created: 2025-09-23

-- Users table - stores user information and global settings
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    rating_mai INTEGER,
    rating_chu FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT, -- JSON string for additional metadata
);

-- Save archives table -stores list of achievement records of a user
-- Replaces timestamp-based folder structure
CREATE TABLE IF NOT EXISTS save_archives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    archive_name TEXT NOT NULL,
    game_type TEXT NOT NULL DEFAULT 'maimai',
    sub_type TEXT NOT NULL DEFAULT 'best', -- best, custom, ap, etc.
    rating_mai INTEGER,
    rating_chu FLOAT,
    record_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    metadata TEXT, -- JSON string for additional metadata
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE(user_id, archive_name)
);

-- Records table - stores individual song records (B50 entries)
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_id INTEGER NOT NULL,
    -- TODO：单独建立一个表管理谱面信息，谱面信息与搜索缓存和本地视频信息挂钩
    song_id TEXT NOT NULL, -- [Update]: using new format align with Dxrating.net, song_id is unique text name, same as the title by default.
    title TEXT NOT NULL, -- Song title
    artist TEXT,  -- Song artist
    chart_type INTEGER NOT NULL, -- [maimai] 0, 1, 2 for std, dX, utage(宴) [chunithm] 0 for normal, 1 for WORLD'S END
    level_index INTEGER NOT NULL, -- 0-4 for Basic to Re:MASTER, 5 for utage / Basic to ULTIMA, 5 for WORLD'S END
    level_value REAL, -- Chart difficulty rating
    achievement REAL NOT NULL, -- 0.00 to 101.00 for maimai, 0.0 to 1010000.0 for chunithm
    
    fc_status TEXT, -- FC, FC+, AP, AP+, etc. / FC, AJ, AJC
    fs_status TEXT, -- FS, FS+, FDX, FDX+, etc. / Clear, Fullchain, AllChain
    dx_score INTEGER, -- only for maimai
    dx_rating REAL, -- only for maimai
    chuni_rating REAL, -- only for chunithm
    record_time TIMESTAMP,
    clip_name TEXT, -- Display name for video
    play_count INTEGER DEFAULT 0, -- Number of times played
    position INTEGER, -- Position in B50 list
    raw_data TEXT, -- JSON string for any additional data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (archive_id) REFERENCES save_archives (id) ON DELETE CASCADE

);

-- Video configs table - stores video-related configuration for each record
CREATE TABLE IF NOT EXISTS video_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    video_file_name TEXT, -- name to local downloaded video file
    video_file_url TEXT, -- direct URL of the video file(future use)
    -- image_path TEXT, -- Path to generated score image
    duration REAL DEFAULT 10.0, -- Video segment duration
    start_time REAL DEFAULT 0.0, -- Start time in video
    end_time REAL DEFAULT 10.0, -- End time in video
    user_comment TEXT, -- User comment for this segment
    video_url TEXT, -- Original video URL from streaming platform
    video_platform TEXT, -- youtube, bilibili, etc.
    video_id TEXT, -- Platform-specific video ID
    video_p_index INTEGER DEFAULT 0, -- video index only for bilibili
    download_status TEXT DEFAULT 'pending', -- pending, downloaded, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES records (id) ON DELETE CASCADE,
    UNIQUE(record_id)
);

-- Video search results 无需存储到数据库，直接在内存中处理即可
-- CREATE TABLE IF NOT EXISTS video_search_results (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     record_id INTEGER NOT NULL,
--     platform TEXT NOT NULL, -- youtube, bilibili
--     video_id TEXT NOT NULL, -- Platform-specific video ID
--     video_url TEXT NOT NULL, -- Original video URL from streaming platform
--     video_title TEXT, -- Original video title
--     video_description TEXT,  -- Original video description
--     duration REAL,
--     view_count INTEGER,
--     upload_date TIMESTAMP,
--     thumbnail_url TEXT,  -- URL of the video thumbnail
--     is_selected BOOLEAN DEFAULT 0,
--     search_query TEXT,
--     search_rank INTEGER, -- Rank in search results
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     FOREIGN KEY (record_id) REFERENCES records (id) ON DELETE CASCADE
-- );

-- Project configs table - stores intro/ending and other settings for video generation
CREATE TABLE IF NOT EXISTS extra_video_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_id INTEGER NOT NULL,
    config_type TEXT NOT NULL, -- intro, ending, global
    config_index INTEGER DEFAULT 0, -- for multiple intros/endings
    config_data TEXT NOT NULL, -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (archive_id) REFERENCES save_archives (id) ON DELETE CASCADE,
    UNIQUE(archive_id, config_type)
);

-- Assets table - tracks generated assets (images, videos, etc.)
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER,
    archive_id INTEGER,
    asset_type TEXT NOT NULL, -- image, video, audio, etc.
    file_path TEXT NOT NULL,
    file_size INTEGER,
    checksum TEXT, -- For integrity checking
    metadata TEXT, -- JSON string for additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES records (id) ON DELETE SET NULL,
    FOREIGN KEY (archive_id) REFERENCES save_archives (id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_records_archive_id ON records (archive_id);
CREATE INDEX IF NOT EXISTS idx_records_song_id ON records (song_id);
CREATE INDEX IF NOT EXISTS idx_records_song_chart ON records (song_id, chart_type, level_index);
CREATE INDEX IF NOT EXISTS idx_video_configs_record_id ON video_configs (record_id);
CREATE INDEX IF NOT EXISTS idx_video_search_record_id ON video_search_results (record_id);
CREATE INDEX IF NOT EXISTS idx_assets_record_id ON assets (record_id);
CREATE INDEX IF NOT EXISTS idx_assets_archive_id ON assets (archive_id);

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
