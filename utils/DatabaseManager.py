import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager
import uuid

class DatabaseManager:
    """
    SQLite database manager for mai-gen-videob50 project.
    Replaces the JSON-based data storage system with a relational database.
    """
    
    def __init__(self, db_path: str = "mai_gen_videob50.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database with all required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table - stores user information and global settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    rating INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    global_settings TEXT -- JSON string for user-specific settings
                )
            ''')
            
            # Save archives table - replaces timestamp-based folder structure
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS save_archives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    archive_name TEXT NOT NULL,
                    game_type TEXT NOT NULL DEFAULT 'maimai',
                    sub_type TEXT NOT NULL DEFAULT 'best', -- best, custom, ap, etc.
                    version TEXT NOT NULL DEFAULT '0.6',
                    rating INTEGER,
                    record_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT, -- JSON string for additional metadata
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, archive_name)
                )
            ''')
            
            # Records table - stores individual song records (B50 entries)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    song_id TEXT NOT NULL, -- Can be numeric ID or encoded hash
                    title TEXT NOT NULL,
                    artist TEXT,
                    chart_type TEXT NOT NULL, -- SD, DX, 宴, 协
                    level_index INTEGER NOT NULL, -- 0-4 for Basic to Re:MASTER
                    level_value REAL, -- Chart difficulty rating
                    achievement REAL NOT NULL,
                    fc_status TEXT, -- FC, FC+, AP, AP+, etc.
                    fs_status TEXT, -- FS, FS+, FDX, FDX+, etc.
                    dx_score INTEGER,
                    dx_rating REAL,
                    play_time TIMESTAMP,
                    clip_name TEXT, -- Display name for video
                    clip_id TEXT, -- Unique identifier for this record
                    position INTEGER, -- Position in B50 list
                    raw_data TEXT, -- JSON string for any additional data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (archive_id) REFERENCES save_archives (id) ON DELETE CASCADE
                )
            ''')
            
            # Video configs table - stores video-related configuration for each record
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL,
                    video_path TEXT, -- Path to downloaded video file
                    image_path TEXT, -- Path to generated score image
                    duration REAL DEFAULT 10.0, -- Video segment duration
                    start_time REAL DEFAULT 0.0, -- Start time in video
                    end_time REAL DEFAULT 10.0, -- End time in video
                    comment TEXT, -- User comment for this segment
                    video_url TEXT, -- Original video URL
                    video_platform TEXT, -- youtube, bilibili, etc.
                    video_id TEXT, -- Platform-specific video ID
                    download_status TEXT DEFAULT 'pending', -- pending, downloaded, failed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (record_id) REFERENCES records (id) ON DELETE CASCADE,
                    UNIQUE(record_id)
                )
            ''')
            
            # Video search results table - stores search results for videos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL,
                    platform TEXT NOT NULL, -- youtube, bilibili
                    video_id TEXT NOT NULL,
                    video_url TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    duration REAL,
                    view_count INTEGER,
                    upload_date TIMESTAMP,
                    thumbnail_url TEXT,
                    is_selected BOOLEAN DEFAULT 0,
                    search_query TEXT,
                    search_rank INTEGER, -- Rank in search results
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (record_id) REFERENCES records (id) ON DELETE CASCADE
                )
            ''')
            
            # Project configs table - stores intro/ending and global video settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS project_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    archive_id INTEGER NOT NULL,
                    config_type TEXT NOT NULL, -- intro, ending, global
                    config_data TEXT NOT NULL, -- JSON string
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (archive_id) REFERENCES save_archives (id) ON DELETE CASCADE,
                    UNIQUE(archive_id, config_type)
                )
            ''')
            
            # Assets table - tracks generated assets (images, videos, etc.)
            cursor.execute('''
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
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_records_archive_id ON records (archive_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_records_song_id ON records (song_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_records_song_chart ON records (song_id, chart_type, level_index)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_configs_record_id ON video_configs (record_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_search_record_id ON video_search_results (record_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_record_id ON assets (record_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_archive_id ON assets (archive_id)')
            
            conn.commit()
    
    # User management methods
    def create_user(self, username: str, display_name: str = None, global_settings: Dict = None) -> int:
        """Create a new user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            settings_json = json.dumps(global_settings or {})
            cursor.execute('''
                INSERT INTO users (username, display_name, global_settings)
                VALUES (?, ?, ?)
            ''', (username, display_name or username, settings_json))
            conn.commit()
            return cursor.lastrowid
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            if row:
                user = dict(row)
                user['global_settings'] = json.loads(user['global_settings'] or '{}')
                return user
            return None
    
    def update_user_settings(self, user_id: int, settings: Dict):
        """Update user's global settings"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET global_settings = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (json.dumps(settings), user_id))
            conn.commit()
    
    # Save archive management methods
    def create_save_archive(self, user_id: int, archive_name: str, game_type: str = 'maimai', 
                           sub_type: str = 'best', rating: int = None, metadata: Dict = None) -> int:
        """Create a new save archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata or {})
            cursor.execute('''
                INSERT INTO save_archives (user_id, archive_name, game_type, sub_type, rating, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, archive_name, game_type, sub_type, rating, metadata_json))
            conn.commit()
            return cursor.lastrowid
    
    def get_user_archives(self, user_id: int) -> List[Dict]:
        """Get all save archives for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM save_archives 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (user_id,))
            archives = []
            for row in cursor.fetchall():
                archive = dict(row)
                archive['metadata'] = json.loads(archive['metadata'] or '{}')
                archives.append(archive)
            return archives
    
    def get_archive(self, archive_id: int) -> Optional[Dict]:
        """Get save archive by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM save_archives WHERE id = ?', (archive_id,))
            row = cursor.fetchone()
            if row:
                archive = dict(row)
                archive['metadata'] = json.loads(archive['metadata'] or '{}')
                return archive
            return None
    
    # Record management methods
    def add_record(self, archive_id: int, record_data: Dict) -> int:
        """Add a new record to an archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Generate clip_id if not provided
            if 'clip_id' not in record_data:
                record_data['clip_id'] = f"clip_{uuid.uuid4().hex[:8]}"
            
            cursor.execute('''
                INSERT INTO records (
                    archive_id, song_id, title, artist, chart_type, level_index, level_value,
                    achievement, fc_status, fs_status, dx_score, dx_rating, play_time,
                    clip_name, clip_id, position, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                archive_id,
                record_data.get('song_id'),
                record_data.get('title'),
                record_data.get('artist'),
                record_data.get('chart_type'),
                record_data.get('level_index'),
                record_data.get('level_value'),
                record_data.get('achievement'),
                record_data.get('fc_status'),
                record_data.get('fs_status'),
                record_data.get('dx_score'),
                record_data.get('dx_rating'),
                record_data.get('play_time'),
                record_data.get('clip_name'),
                record_data.get('clip_id'),
                record_data.get('position'),
                json.dumps(record_data.get('raw_data', {}))
            ))
            
            record_id = cursor.lastrowid
            
            # Update record count in archive
            cursor.execute('''
                UPDATE save_archives 
                SET record_count = (SELECT COUNT(*) FROM records WHERE archive_id = ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (archive_id, archive_id))
            
            conn.commit()
            return record_id
    
    def get_archive_records(self, archive_id: int) -> List[Dict]:
        """Get all records for an archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, vc.video_path, vc.image_path, vc.duration, vc.start_time, 
                       vc.end_time, vc.comment, vc.download_status
                FROM records r
                LEFT JOIN video_configs vc ON r.id = vc.record_id
                WHERE r.archive_id = ?
                ORDER BY r.position ASC, r.created_at ASC
            ''', (archive_id,))
            
            records = []
            for row in cursor.fetchall():
                record = dict(row)
                record['raw_data'] = json.loads(record['raw_data'] or '{}')
                records.append(record)
            return records
    
    # Video configuration methods
    def set_video_config(self, record_id: int, config_data: Dict):
        """Set or update video configuration for a record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO video_configs (
                    record_id, video_path, image_path, duration, start_time, end_time,
                    comment, video_url, video_platform, video_id, download_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record_id,
                config_data.get('video_path'),
                config_data.get('image_path'),
                config_data.get('duration', 10.0),
                config_data.get('start_time', 0.0),
                config_data.get('end_time', 10.0),
                config_data.get('comment'),
                config_data.get('video_url'),
                config_data.get('video_platform'),
                config_data.get('video_id'),
                config_data.get('download_status', 'pending')
            ))
            conn.commit()
    
    def get_video_config(self, record_id: int) -> Optional[Dict]:
        """Get video configuration for a record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM video_configs WHERE record_id = ?', (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # Video search results methods
    def add_search_results(self, record_id: int, platform: str, results: List[Dict]):
        """Add video search results for a record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Clear existing results for this record and platform
            cursor.execute('''
                DELETE FROM video_search_results 
                WHERE record_id = ? AND platform = ?
            ''', (record_id, platform))
            
            # Add new results
            for i, result in enumerate(results):
                cursor.execute('''
                    INSERT INTO video_search_results (
                        record_id, platform, video_id, video_url, title, description,
                        duration, view_count, upload_date, thumbnail_url, search_query, search_rank
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record_id, platform, result.get('video_id'), result.get('video_url'),
                    result.get('title'), result.get('description'), result.get('duration'),
                    result.get('view_count'), result.get('upload_date'), result.get('thumbnail_url'),
                    result.get('search_query'), i + 1
                ))
            
            conn.commit()
    
    def get_search_results(self, record_id: int, platform: str = None) -> List[Dict]:
        """Get video search results for a record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute('''
                    SELECT * FROM video_search_results 
                    WHERE record_id = ? AND platform = ?
                    ORDER BY search_rank ASC
                ''', (record_id, platform))
            else:
                cursor.execute('''
                    SELECT * FROM video_search_results 
                    WHERE record_id = ?
                    ORDER BY platform ASC, search_rank ASC
                ''', (record_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Project configuration methods
    def set_project_config(self, archive_id: int, config_type: str, config_data: Dict):
        """Set project configuration (intro, ending, global settings)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO project_configs (archive_id, config_type, config_data)
                VALUES (?, ?, ?)
            ''', (archive_id, config_type, json.dumps(config_data)))
            conn.commit()
    
    def get_project_config(self, archive_id: int, config_type: str) -> Optional[Dict]:
        """Get project configuration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT config_data FROM project_configs 
                WHERE archive_id = ? AND config_type = ?
            ''', (archive_id, config_type))
            row = cursor.fetchone()
            if row:
                return json.loads(row['config_data'])
            return None
    
    # Asset management methods
    def add_asset(self, asset_type: str, file_path: str, record_id: int = None, 
                  archive_id: int = None, metadata: Dict = None) -> int:
        """Add an asset record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
            
            cursor.execute('''
                INSERT INTO assets (record_id, archive_id, asset_type, file_path, file_size, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (record_id, archive_id, asset_type, file_path, file_size, json.dumps(metadata or {})))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_assets(self, record_id: int = None, archive_id: int = None, 
                   asset_type: str = None) -> List[Dict]:
        """Get assets by various filters"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM assets WHERE 1=1'
            params = []
            
            if record_id:
                query += ' AND record_id = ?'
                params.append(record_id)
            if archive_id:
                query += ' AND archive_id = ?'
                params.append(archive_id)
            if asset_type:
                query += ' AND asset_type = ?'
                params.append(asset_type)
            
            query += ' ORDER BY created_at DESC'
            
            cursor.execute(query, params)
            assets = []
            for row in cursor.fetchall():
                asset = dict(row)
                asset['metadata'] = json.loads(asset['metadata'] or '{}')
                assets.append(asset)
            return assets
    
    # Query methods for tracking records across time
    def get_song_history(self, user_id: int, song_id: str, chart_type: str, level_index: int) -> List[Dict]:
        """Get all records for a specific song across all archives for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, sa.archive_name, sa.created_at as archive_created_at, sa.rating as archive_rating
                FROM records r
                JOIN save_archives sa ON r.archive_id = sa.id
                WHERE sa.user_id = ? AND r.song_id = ? AND r.chart_type = ? AND r.level_index = ?
                ORDER BY sa.created_at DESC
            ''', (user_id, str(song_id), chart_type, level_index))
            
            records = []
            for row in cursor.fetchall():
                record = dict(row)
                record['raw_data'] = json.loads(record['raw_data'] or '{}')
                records.append(record)
            return records
    
    def get_user_progress_summary(self, user_id: int) -> Dict:
        """Get summary of user's progress across all archives"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get archive count and date range
            cursor.execute('''
                SELECT COUNT(*) as archive_count, 
                       MIN(created_at) as first_archive,
                       MAX(created_at) as latest_archive,
                       MAX(rating) as best_rating
                FROM save_archives 
                WHERE user_id = ?
            ''', (user_id,))
            
            summary = dict(cursor.fetchone())
            
            # Get total record count
            cursor.execute('''
                SELECT COUNT(*) as total_records
                FROM records r
                JOIN save_archives sa ON r.archive_id = sa.id
                WHERE sa.user_id = ?
            ''', (user_id,))
            
            summary.update(dict(cursor.fetchone()))
            
            return summary