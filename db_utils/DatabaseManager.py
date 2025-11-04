import sqlite3
import os
import json
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
        """
        Initializes the database with the schema, but only if the tables don't already exist.
        This makes the initialization idempotent.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check if a key table (e.g., 'users') already exists.
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone() is None:
                # Tables do not exist, so initialize the database.
                print("Database not found or empty. Initializing new database from schema...")
                schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
                
                if not os.path.exists(schema_path):
                    raise FileNotFoundError(f"Database schema file not found: {schema_path}")

                # Read and execute the schema file
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                # Use executescript to handle multiple statements and comments
                cursor.executescript(schema_sql)
                conn.commit()
                print("Database initialized successfully.")
    
    def get_schema_version(self) -> str:
        """Get the current database schema version"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
                result = cursor.fetchone()
                return result['version'] if result else "1.0"
            except sqlite3.OperationalError:
                # This happens if the schema_version table doesn't exist yet
                return "1.0"

    def update_schema_version(self, version: str, description: str = None):
        """Update the schema version after applying migrations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
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
                            print(f"Applying migration {migration_file} for version {file_version}...")
                            self.apply_migration(migration_file)
                            self.update_schema_version(file_version, f"Applied migration {migration_file}")
                            print(f"Successfully applied migration {migration_file}")
                        else:
                            print(f"Skipping migration {migration_file}, already applied.")
                            
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
                SET rating_mai = ?, rating_chu = ?
                WHERE id = ?
            ''', (rating_mai, rating_chu, user_id))
            conn.commit()
    
    def update_user_metadata(self, user_id: int, metadata: Dict):
        """Update user metadata"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET metadata = ?
                WHERE id = ?
            ''', (json.dumps(metadata), user_id))
            conn.commit()

    # Chart management methods
    def get_or_create_chart(self, chart_data: Dict) -> int:
        """Get a chart by its unique properties, or create it if it doesn't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Define the unique keys for a chart
            unique_keys = ['game_type', 'song_id', 'chart_type', 'level_index']
            
            # Check if the chart exists
            cursor.execute(f'''
                SELECT id FROM charts 
                WHERE game_type = ? AND song_id = ? AND chart_type = ? AND level_index = ?
            ''', tuple(chart_data.get(k) for k in unique_keys))
            
            row = cursor.fetchone()
            if row:
                return row['id']
            
            # If not, create it
            # Define all possible fields for a chart
            all_fields = unique_keys + ['difficulty', 'song_name', 'artist', 'max_dx_score', 'video_path']
            
            # Prepare for insertion
            columns = [field for field in all_fields if field in chart_data and chart_data[field] is not None]
            placeholders = ', '.join(['?'] * len(columns))
            values = [chart_data.get(col) for col in columns]
            
            cursor.execute(f'''
                INSERT INTO charts ({', '.join(columns)})
                VALUES ({placeholders})
            ''', values)
            
            conn.commit()
            return cursor.lastrowid

    def get_chart(self, chart_id: int) -> Optional[Dict]:
        """Retrieve chart metadata by chart_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM charts WHERE id = ?', (chart_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # Archive management methods
    def create_archive(self, user_id: int, archive_name: str, game_type: str, sub_type: str, 
                       rating_mai: Optional[int] = None, rating_chu: Optional[float] = None, game_version: str = 'latest') -> int:
        """Create a new save archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO archives (user_id, archive_name, game_type, sub_type, rating_mai, rating_chu, game_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, archive_name, game_type, sub_type, rating_mai, rating_chu, game_version))
            conn.commit()
            return cursor.lastrowid

    def get_user_archives(self, user_id: int, game_type: Optional[str] = None) -> List[Dict]:
        """Get all save archives for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if game_type:
                cursor.execute('''
                    SELECT * FROM archives 
                    WHERE user_id = ? AND game_type = ?
                    ORDER BY created_at DESC
                ''', (user_id, game_type))
            else:
                cursor.execute('''
                    SELECT * FROM archives 
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
            cursor.execute('SELECT * FROM archives WHERE id = ?', (archive_id,))
            row = cursor.fetchone()
            if row:
                archive = dict(row)
                archive['metadata'] = json.loads(archive['metadata'] or '{}')
                return archive
            return None
    
    def update_archive(self, archive_id: int, update_data: Dict):
        """Update an existing archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            updateable_fields = ['archive_name', 'game_type', 'sub_type', 
                                 'rating_mai', 'rating_chu', 'game_version', 
                                 'is_active', 'metadata']
            
            filtered_data = {k: v for k, v in update_data.items() if k in updateable_fields and v is not None}
            
            if not filtered_data:
                return # Nothing to update
            
            set_clauses = []
            values = []
            
            for field, value in filtered_data.items():
                set_clauses.append(f"{field} = ?")
                if field == 'metadata':
                    values.append(json.dumps(value or {}))
                else:
                    values.append(value)
            
            values.append(archive_id)
            
            update_query = f"""
                UPDATE archives 
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """
            
            cursor.execute(update_query, values)
            conn.commit()
    
    def get_active_archives(self, user_id: int) -> List[Dict]:
        """Get only active archives for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM archives 
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
    def add_record(self, archive_id: int, chart_id: int, record_data: Dict) -> int:
        """Add a new record to an archive"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Fields for the records table
            record_fields = [
                'order_in_archive', 'achievement', 'fc_status', 'fs_status', 
                'dx_score', 'dx_rating', 'chuni_rating', 'play_count', 'clip_title_name', 'raw_data'
            ]
            
            # Prepare for insertion
            columns = ['archive_id', 'chart_id']
            values = [archive_id, chart_id]
            
            for field in record_fields:
                if field in record_data and record_data[field] is not None:
                    columns.append(field)
                    value = record_data[field]
                    if field == 'raw_data':
                        values.append(json.dumps(value or {}))
                    else:
                        values.append(value)

            placeholders = ', '.join(['?'] * len(columns))
            
            cursor.execute(f'''
                INSERT INTO records ({', '.join(columns)})
                VALUES ({placeholders})
            ''', values)
            
            record_id = cursor.lastrowid
            
            # Update record count in archive
            cursor.execute('''
                UPDATE archives 
                SET record_count = (SELECT COUNT(*) FROM records WHERE archive_id = ?)
                WHERE id = ?
            ''', (archive_id, archive_id))
            
            conn.commit()
            return record_id

    def get_record(self, record_id: int) -> Optional[Dict]:
        """Get a single record by ID, joined with other tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    r.id AS record_id,
                    r.archive_id,
                    r.chart_id,
                    r.order_in_archive,
                    r.achievement,
                    r.fc_status,
                    r.fs_status,
                    r.dx_score,
                    r.dx_rating,
                    r.chuni_rating,
                    r.play_count,
                    r.clip_title_name,
                    r.raw_data,
                    c.game_type,
                    c.song_id,
                    c.chart_type,
                    c.difficulty,
                    c.level_index,
                    c.song_name,
                    c.artist,
                    c.max_dx_score,
                    c.video_path,
                    conf.background_image_path,
                    conf.achievement_image_path,
                    conf.video_slice_start,
                    conf.video_slice_end,
                    conf.comment_text,
                    conf.video_metadata
                FROM
                    records r
                JOIN
                    charts c ON r.chart_id = c.id
                LEFT JOIN
                    configurations conf ON r.archive_id = conf.archive_id AND r.chart_id = conf.chart_id
                WHERE
                    r.id = ?
            ''', (record_id,))
            
            row = cursor.fetchone()
            if row:
                record = dict(row)
                # Parse JSON fields
                if record.get('raw_data'):
                    record['raw_data'] = json.loads(record['raw_data'])
                if record.get('video_metadata'):
                    record['video_metadata'] = json.loads(record['video_metadata'])
                return record
            return None

    def update_record(self, record_id: int, update_data: Dict):
        """Update an existing record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            updateable_fields = [
                'order_in_archive', 'achievement', 'fc_status', 'fs_status', 
                'dx_score', 'dx_rating', 'chuni_rating', 'play_count', 'clip_title_name', 'raw_data'
            ]
            
            filtered_data = {k: v for k, v in update_data.items() if k in updateable_fields and v is not None}
            
            if not filtered_data:
                return # Nothing to update
            
            set_clauses = []
            values = []
            
            for field, value in filtered_data.items():
                set_clauses.append(f"{field} = ?")
                if field == 'raw_data':
                    values.append(json.dumps(value or {}))
                else:
                    values.append(value)
            
            values.append(record_id)
            
            update_query = f"""
                UPDATE records 
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """
            
            cursor.execute(update_query, values)
            conn.commit()

    def get_records_for_video_generation(self, archive_id: int, retrieve_raw_data: bool = False) -> List[Dict]:
        """
        Get all records for an archive, joined with chart and configuration data.
        This is the primary method for fetching data to generate a video.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    r.id AS record_id,
                    r.archive_id,
                    r.chart_id,
                    r.order_in_archive,
                    r.achievement,
                    r.fc_status,
                    r.fs_status,
                    r.dx_score,
                    r.dx_rating,
                    r.chuni_rating,
                    r.play_count,
                    r.clip_title_name,
                    r.raw_data,
                    c.game_type,
                    c.song_id,
                    c.chart_type,
                    c.difficulty,
                    c.level_index,
                    c.song_name,
                    c.artist,
                    c.max_dx_score,
                    c.video_path,
                    conf.background_image_path,
                    conf.achievement_image_path,
                    conf.video_slice_start,
                    conf.video_slice_end,
                    conf.comment_text,
                    conf.video_metadata
                FROM
                    records r
                JOIN
                    charts c ON r.chart_id = c.id
                LEFT JOIN
                    configurations conf ON r.archive_id = conf.archive_id AND r.chart_id = conf.chart_id
                WHERE
                    r.archive_id = ?
                ORDER BY
                    r.order_in_archive ASC;
            ''', (archive_id,))
            
            results = cursor.fetchall()
            # Convert rows to dicts and parse JSON fields
            parsed_results = []
            for row in results:
                row_dict = dict(row)
                if retrieve_raw_data and row_dict.get('raw_data'):
                    row_dict['raw_data'] = json.loads(row_dict['raw_data'])
                if row_dict.get('video_metadata'):
                    row_dict['video_metadata'] = json.loads(row_dict['video_metadata'])
                parsed_results.append(row_dict)
            return parsed_results

    def get_archive_records_simple(self, archive_id: int) -> List[Dict]:
        """Gets all records for an archive without joining other tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM records WHERE archive_id = ?', (archive_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_records(self, record_ids: List[int]):
        """Deletes multiple records by their IDs."""
        if not record_ids:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' for _ in record_ids)
            cursor.execute(f'DELETE FROM records WHERE id IN ({placeholders})', record_ids)
            conn.commit()

    # Configuration methods
    def set_configuration(self, archive_id: int, chart_id: int, config_data: Dict):
        """Set or update configuration for a chart in an archive."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if a config already exists
            cursor.execute('''
                SELECT id FROM configurations WHERE archive_id = ? AND chart_id = ?
            ''', (archive_id, chart_id))
            
            existing_id = cursor.fetchone()
            
            # Fields for the configurations table
            config_fields = [
                'background_image_path', 'achievement_image_path',
                'video_slice_start', 'video_slice_end', 
                'comment_text', 'video_metadata'
            ]
            
            # Filter out None values from config_data
            filtered_config = {k: v for k, v in config_data.items() if v is not None}

            if existing_id:
                # Update existing configuration
                update_clauses = []
                update_values = []
                for field in config_fields:
                    if field in filtered_config:
                        update_clauses.append(f"{field} = ?")
                        value = filtered_config[field]
                        if field == 'metadata':
                            update_values.append(json.dumps(value or {}))
                        else:
                            update_values.append(value)
                
                if not update_clauses:
                    return # Nothing to update
                
                update_values.extend([archive_id, chart_id])
                cursor.execute(f'''
                    UPDATE configurations SET {', '.join(update_clauses)}
                    WHERE archive_id = ? AND chart_id = ?
                ''', update_values)
            else:
                # Insert new configuration
                columns = ['archive_id', 'chart_id']
                values = [archive_id, chart_id]
                for field in config_fields:
                    if field in filtered_config:
                        columns.append(field)
                        value = filtered_config[field]
                        if field == 'metadata':
                            values.append(json.dumps(value or {}))
                        else:
                            values.append(value)
                
                if len(columns) > 2: # Only insert if there's data
                    placeholders = ', '.join(['?'] * len(columns))
                    cursor.execute(f'''
                        INSERT INTO configurations ({', '.join(columns)})
                        VALUES ({placeholders})
                    ''', values)

            conn.commit()
    
    def get_configuration(self, archive_id: int, chart_id: int) -> Optional[Dict]:
        """Get configuration for a chart in an archive."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM configurations WHERE archive_id = ? AND chart_id = ?', (archive_id, chart_id))
            row = cursor.fetchone()
            if row:
                config = dict(row)
                config['metadata'] = json.loads(config.get('metadata') or '{}')
                return config
            return None
    
    # Extra video configuration methods (no changes needed)
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
    def get_song_history(self, user_id: int, chart_id: int) -> List[Dict]:
        """Get all records for a specific chart across all archives for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, a.archive_name, a.created_at as archive_created_at, 
                       a.rating_mai as archive_rating_mai, a.rating_chu as archive_rating_chu
                FROM records r
                JOIN archives a ON r.archive_id = a.id
                WHERE a.user_id = ? AND r.chart_id = ?
                ORDER BY a.created_at DESC
            ''', (user_id, chart_id))
            
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
                FROM archives 
                WHERE user_id = ?
            ''', (user_id,))
            
            summary = dict(cursor.fetchone())
            
            # Get total record count
            cursor.execute('''
                SELECT COUNT(*) as total_records
                FROM records r
                JOIN archives a ON r.archive_id = a.id
                WHERE a.user_id = ?
            ''', (user_id,))
            
            summary.update(dict(cursor.fetchone()))
            
            return summary