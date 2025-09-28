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
    Implements basic database interactions for all the tables.
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
        """Initialize database with all required tables from schema.sql file"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Database schema file not found: {schema_path}")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Read and execute the schema file
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Execute the schema (split by semicolon to handle multiple statements)
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement:  # Skip empty statements
                    cursor.execute(statement)
            
            conn.commit()
    
    def get_schema_version(self) -> str:
        """Get the current database schema version"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Check if schema_version table exists
                cursor.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='schema_version'
                ''')
                if not cursor.fetchone():
                    return "1.0"  # Default version for existing databases
                
                cursor.execute('SELECT version FROM schema_version ORDER BY id DESC LIMIT 1')
                result = cursor.fetchone()
                return result['version'] if result else "1.0"
            except sqlite3.Error:
                return "1.0"
    
    def update_schema_version(self, version: str, description: str = None):
        """Update the schema version after applying migrations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create schema_version table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT INTO schema_version (version, description)
                VALUES (?, ?)
            ''', (version, description))
            
            conn.commit()
    
    def apply_migration(self, migration_file: str):
        """Apply a database migration from a SQL file"""
        migration_path = os.path.join(os.path.dirname(__file__), 'migrations', migration_file)
        
        if not os.path.exists(migration_path):
            raise FileNotFoundError(f"Migration file not found: {migration_path}")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Read and execute the migration file
            with open(migration_path, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            
            # Execute the migration (split by semicolon to handle multiple statements)
            for statement in migration_sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):  # Skip empty statements and comments
                    cursor.execute(statement)
            
            conn.commit()
    
    def check_and_apply_migrations(self, target_version: str = None):
        """
        Check for and apply pending migrations
        
        Args:
            target_version: Apply migrations up to this version (optional)
        """
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        
        if not os.path.exists(migrations_dir):
            return  # No migrations directory
        
        current_version = self.get_schema_version()
        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.sql')])
        
        for migration_file in migration_files:
            # Extract version from migration file if it follows naming convention
            # This is a simple implementation - you might want more sophisticated versioning
            migration_path = os.path.join(migrations_dir, migration_file)
            
            try:
                with open(migration_path, 'r', encoding='utf-8') as f:
                    header = f.readline()
                    if 'Version:' in header:
                        file_version = header.split('Version:')[1].strip().replace('--', '').strip()
                        
                        # Simple version comparison (you might want to use proper semantic versioning)
                        if self._version_greater_than(file_version, current_version):
                            if target_version is None or not self._version_greater_than(file_version, target_version):
                                print(f"Applying migration: {migration_file}")
                                self.apply_migration(migration_file)
                                
                                # Extract description
                                f.seek(0)
                                content = f.read()
                                description = "Migration applied"
                                for line in content.split('\n'):
                                    if 'Description:' in line:
                                        description = line.split('Description:')[1].strip().replace('--', '').strip()
                                        break
                                
                                self.update_schema_version(file_version, description)
                                current_version = file_version
            except Exception as e:
                print(f"Error applying migration {migration_file}: {e}")
                raise
    
    def _version_greater_than(self, version1: str, version2: str) -> bool:
        """Simple version comparison - you might want to use proper semantic versioning"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad with zeros to make them the same length
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))
            
            return v1_parts > v2_parts
        except ValueError:
            # Fallback to string comparison if not numeric
            return version1 > version2
    
    # User management methods
    def create_user(self, username: str, display_name: str = None, rating_mai: int = None, 
                   rating_chu: float = None, metadata: Dict = None) -> int:
        """Create a new user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata or {})
            cursor.execute('''
                INSERT INTO users (username, display_name, rating_mai, rating_chu, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, display_name or username, rating_mai, rating_chu, metadata_json))
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
                user['metadata'] = json.loads(user['metadata'] or '{}')
                return user
            return None

    def update_user_ratings(self, user_id: int, rating_mai: int = None, rating_chu: float = None):
        """Update user's global ratings"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET rating_mai = ?, rating_chu = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (rating_mai, rating_chu, user_id))
            conn.commit()
    
    def update_user_metadata(self, user_id: int, metadata: Dict):
        """Update user metadata"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (json.dumps(metadata), user_id))
            conn.commit()
    
    # Save archive management methods
    def create_save_archive(self, user_id: int, archive_name: str, game_type: str = 'maimai', 
                           sub_type: str = 'best', rating_mai: int = None, rating_chu: float = None, 
                           metadata: Dict = None) -> int:
        """Create a new save archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata or {})
            cursor.execute('''
                INSERT INTO save_archives (user_id, archive_name, game_type, sub_type, rating_mai, rating_chu, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, archive_name, game_type, sub_type, rating_mai, rating_chu, metadata_json))
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
    
    def update_archive_status(self, archive_id: int, is_active: bool):
        """Update archive active status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE save_archives
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (is_active, archive_id))
            conn.commit()
    
    def get_active_archives(self, user_id: int) -> List[Dict]:
        """Get only active archives for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM save_archives 
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
            ''', (user_id,))
            archives = []
            for row in cursor.fetchall():
                archive = dict(row)
                archive['metadata'] = json.loads(archive['metadata'] or '{}')
                archives.append(archive)
            return archives
    
    # Record management methods
    def add_record(self, archive_id: int, record_data: Dict) -> int:
        """Add a new record to an archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO records (
                    archive_id, song_id, title, artist, chart_type, level_index, level_value,
                    achievement, fc_status, fs_status, dx_score, dx_rating, chuni_rating, record_time,
                    clip_name, play_count, position, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                record_data.get('chuni_rating'),
                record_data.get('record_time'),
                record_data.get('clip_name'),
                record_data.get('play_count'),
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
    
    def update_record(self, record_id: int, update_data: Dict):
        """Update an existing record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # First, get the existing record to check song_id
            cursor.execute('SELECT song_id FROM records WHERE id = ?', (record_id,))
            existing_record = cursor.fetchone()
            
            if not existing_record:
                raise ValueError(f"Record with ID {record_id} not found")

            # Build dynamic UPDATE query based on provided fields
            updateable_fields = [
                'song_id',
                'title', 'artist', 'chart_type', 'level_index', 'level_value', 
                'achievement', 'fc_status', 'fs_status', 'dx_score', 'dx_rating', 
                'chuni_rating', 'record_time', 'clip_name', 'play_count', 'position'
            ]
            
            # Filter update_data to only include valid fields
            filtered_data = {k: v for k, v in update_data.items() if k in updateable_fields}
            
            if not filtered_data:
                raise ValueError("No valid fields to update")
            
            # Build the SET clause
            set_clauses = []
            values = []
            
            for field, value in filtered_data.items():
                set_clauses.append(f"{field} = ?")
                values.append(value)
            
            # Update raw_data if provided
            if 'raw_data' in update_data:
                set_clauses.append("raw_data = ?")
                values.append(json.dumps(update_data['raw_data']))
            
            # Always update the updated_at timestamp
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            
            # Add record_id for WHERE clause
            values.append(record_id)
            
            # Execute the update
            update_query = f"""
                UPDATE records 
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """
            
            cursor.execute(update_query, values)
            
            if cursor.rowcount == 0:
                print(f"Warning: No record was updated for ID {record_id}")
            
            conn.commit()

    def get_archive_records(self, archive_id: int) -> List[Dict]:
        """Get all records for an archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, vc.video_file_name, vc.video_file_url, vc.duration, vc.start_time, 
                       vc.end_time, vc.user_comment, vc.video_url, vc.video_platform, vc.video_id,
                       vc.video_p_index, vc.download_status
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
                    record_id, video_file_name, video_file_url, duration, start_time, end_time,
                    user_comment, video_url, video_platform, video_id, video_p_index, download_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record_id,
                config_data.get('video_file_name'),
                config_data.get('video_file_url'),
                config_data.get('duration', 10.0),
                config_data.get('start_time', 0.0),
                config_data.get('end_time', 10.0),
                config_data.get('user_comment'),
                config_data.get('video_url'),
                config_data.get('video_platform'),
                config_data.get('video_id'),
                config_data.get('video_p_index', 0),
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
    
    # Extra video configuration methods (intro/ending settings)
    def set_extra_video_config(self, archive_id: int, config_type: str, config_data: Dict, config_index: int = 0):
        """Set extra video configuration (intro, ending, global settings)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO extra_video_configs (archive_id, config_type, config_index, config_data)
                VALUES (?, ?, ?, ?)
            ''', (archive_id, config_type, config_index, json.dumps(config_data)))
            conn.commit()
    
    def get_extra_video_config(self, archive_id: int, config_type: str, config_index: int = 0) -> Optional[Dict]:
        """Get extra video configuration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT config_data FROM extra_video_configs 
                WHERE archive_id = ? AND config_type = ? AND config_index = ?
            ''', (archive_id, config_type, config_index))
            row = cursor.fetchone()
            if row:
                return json.loads(row['config_data'])
            return None
    
    def get_all_extra_video_configs(self, archive_id: int, config_type: str = None) -> List[Dict]:
        """Get all extra video configurations for an archive, optionally filtered by type"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if config_type:
                cursor.execute('''
                    SELECT * FROM extra_video_configs 
                    WHERE archive_id = ? AND config_type = ?
                    ORDER BY config_index ASC
                ''', (archive_id, config_type))
            else:
                cursor.execute('''
                    SELECT * FROM extra_video_configs 
                    WHERE archive_id = ?
                    ORDER BY config_type ASC, config_index ASC
                ''', (archive_id,))
            
            configs = []
            for row in cursor.fetchall():
                config = dict(row)
                config['config_data'] = json.loads(config['config_data'])
                configs.append(config)
            return configs
    
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
                SELECT r.*, sa.archive_name, sa.created_at as archive_created_at, 
                       sa.rating_mai as archive_rating_mai, sa.rating_chu as archive_rating_chu
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
                       MAX(rating_mai) as best_rating_mai,
                       MAX(rating_chu) as best_rating_chu
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
    
    def update_record_time(self, record_id: int, record_time: datetime):
        """Update record timestamp"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE records
                SET record_time = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (record_time, record_id))
            conn.commit()
    
    def get_records_by_game_type(self, archive_id: int, game_type: str = None) -> List[Dict]:
        """Get records filtered by game type (maimai/chunithm)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if game_type:
                cursor.execute('''
                    SELECT r.*, sa.game_type
                    FROM records r
                    JOIN save_archives sa ON r.archive_id = sa.id
                    WHERE r.archive_id = ? AND sa.game_type = ?
                    ORDER BY r.position ASC, r.created_at ASC
                ''', (archive_id, game_type))
            else:
                cursor.execute('''
                    SELECT r.*, sa.game_type
                    FROM records r
                    JOIN save_archives sa ON r.archive_id = sa.id
                    WHERE r.archive_id = ?
                    ORDER BY r.position ASC, r.created_at ASC
                ''', (archive_id,))
            
            records = []
            for row in cursor.fetchall():
                record = dict(row)
                record['raw_data'] = json.loads(record['raw_data'] or '{}')
                records.append(record)
            return records

    def get_record(self, record_id: int) -> Optional[Dict]:
        """Get a single record by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, vc.video_file_name, vc.video_file_url, vc.duration, vc.start_time, 
                       vc.end_time, vc.user_comment, vc.video_url, vc.video_platform, vc.video_id,
                       vc.video_p_index, vc.download_status
                FROM records r
                LEFT JOIN video_configs vc ON r.id = vc.record_id
                WHERE r.id = ?
            ''', (record_id,))
            
            row = cursor.fetchone()
            if row:
                record = dict(row)
                record['raw_data'] = json.loads(record['raw_data'] or '{}')
                return record
            return None