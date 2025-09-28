import os
import json
import glob
from datetime import datetime
from typing import Dict, List, Optional
from db_utils.DatabaseManager import DatabaseManager
import shutil

class DataMigration:
    """
    Migration utility to convert existing JSON-based data storage to SQLite database.
    Handles migration of user data, save archives, records, and configurations.
    """
    
    def __init__(self, db_manager: DatabaseManager, b50_data_path: str = "b50_datas"):
        self.db = db_manager
        self.b50_data_path = b50_data_path
        self.migration_log = []
    
    def log(self, message: str):
        """Log migration progress"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.migration_log.append(log_entry)
        print(log_entry)
    
    def migrate_all_data(self):
        """Migrate all existing JSON data to SQLite database"""
        self.log("Starting data migration from JSON to SQLite...")
        
        if not os.path.exists(self.b50_data_path):
            self.log(f"No existing data directory found at {self.b50_data_path}")
            return
        
        # Get all user directories
        user_dirs = [d for d in os.listdir(self.b50_data_path) 
                    if os.path.isdir(os.path.join(self.b50_data_path, d))]
        
        self.log(f"Found {len(user_dirs)} user directories to migrate")
        
        for user_dir in user_dirs:
            try:
                self.migrate_user_data(user_dir)
            except Exception as e:
                self.log(f"Error migrating user {user_dir}: {str(e)}")
        
        self.log("Migration completed!")
        return self.migration_log
    
    def migrate_user_data(self, username: str):
        """Migrate data for a specific user"""
        user_path = os.path.join(self.b50_data_path, username)
        self.log(f"Migrating user: {username}")
        
        # Create or get user in database
        user = self.db.get_user(username)
        if not user:
            user_id = self.db.create_user(username)
            self.log(f"Created new user: {username} (ID: {user_id})")
        else:
            user_id = user['id']
            self.log(f"Found existing user: {username} (ID: {user_id})")
        
        # Get all save archive directories (timestamp-based folders)
        archive_dirs = [d for d in os.listdir(user_path) 
                       if os.path.isdir(os.path.join(user_path, d)) and 
                       self._is_timestamp_folder(d)]
        
        self.log(f"Found {len(archive_dirs)} save archives for user {username}")
        
        for archive_dir in archive_dirs:
            try:
                self.migrate_save_archive(user_id, username, archive_dir)
            except Exception as e:
                self.log(f"Error migrating archive {archive_dir}: {str(e)}")
    
    def migrate_save_archive(self, user_id: int, username: str, archive_dir: str):
        """Migrate a single save archive"""
        archive_path = os.path.join(self.b50_data_path, username, archive_dir)
        self.log(f"Migrating archive: {archive_dir}")
        
        # Load b50_raw.json
        b50_raw_path = os.path.join(archive_path, "b50_raw.json")
        if not os.path.exists(b50_raw_path):
            self.log(f"No b50_raw.json found in {archive_dir}, skipping")
            return
        
        with open(b50_raw_path, 'r', encoding='utf-8') as f:
            b50_data = json.load(f)
        
        # Extract archive metadata
        archive_name = archive_dir  # Use timestamp as archive name
        game_type = b50_data.get('type', 'maimai')
        sub_type = b50_data.get('sub_type', 'best')
        rating = b50_data.get('rating')
        version = b50_data.get('version', '0.5')
        
        # Create save archive
        archive_id = self.db.create_save_archive(
            user_id=user_id,
            archive_name=archive_name,
            game_type=game_type,
            sub_type=sub_type,
            rating=rating,
            metadata={
                'version': version,
                'username': b50_data.get('username'),
                'length_of_content': b50_data.get('length_of_content'),
                'original_path': archive_path
            }
        )
        
        self.log(f"Created archive: {archive_name} (ID: {archive_id})")
        
        # Migrate records
        records = b50_data.get('records', [])
        self.log(f"Migrating {len(records)} records")
        
        for i, record in enumerate(records):
            try:
                record_id = self.migrate_record(archive_id, record, i + 1)
                
                # Migrate video configuration if exists
                self.migrate_video_config(record_id, archive_path, record)
                
            except Exception as e:
                self.log(f"Error migrating record {i}: {str(e)}")
        
        # Migrate video_config.json (intro/ending configurations)
        self.migrate_project_configs(archive_id, archive_path)
        
        # Migrate assets (images and videos)
        self.migrate_assets(archive_id, archive_path)
    
    def migrate_record(self, archive_id: int, record_data: Dict, position: int) -> int:
        """Migrate a single record"""
        # Map old field names to new schema
        record = {
            'song_id': str(record_data.get('song_id', '')),
            'title': record_data.get('title', ''),
            'artist': record_data.get('artist', ''),
            'chart_type': record_data.get('type', ''),
            'level_index': record_data.get('level_index', 0),
            'level_value': record_data.get('level', 0.0),
            'achievement': record_data.get('achievements', 0.0),
            'fc_status': record_data.get('fc', ''),
            'fs_status': record_data.get('fs', ''),
            'dx_score': record_data.get('dx_score', 0),
            'dx_rating': record_data.get('dx_rating', 0.0),
            'play_time': record_data.get('play_time'),
            'clip_name': record_data.get('clip_name', ''),
            'clip_id': record_data.get('clip_id', f"clip_{position}"),
            'position': position,
            'raw_data': record_data  # Store original data for reference
        }
        
        return self.db.add_record(archive_id, record)
    
    def migrate_video_config(self, record_id: int, archive_path: str, record_data: Dict):
        """Migrate video configuration for a record"""
        # Load video_config.json if exists
        video_config_path = os.path.join(archive_path, "video_config.json")
        if not os.path.exists(video_config_path):
            return
        
        with open(video_config_path, 'r', encoding='utf-8') as f:
            video_config = json.load(f)
        
        # Find matching configuration in video_config.json
        clip_id = record_data.get('clip_id')
        main_configs = video_config.get('main', [])
        
        matching_config = None
        for config in main_configs:
            if config.get('id') == clip_id:
                matching_config = config
                break
        
        if not matching_config:
            return
        
        # Extract video configuration
        video_path = matching_config.get('video', '')
        image_path = matching_config.get('main_image', '')
        duration = matching_config.get('duration', 10.0)
        start_time = matching_config.get('start', 0.0)
        end_time = matching_config.get('end', duration)
        comment = matching_config.get('text', '')
        
        # Convert relative paths to absolute paths
        if video_path and not os.path.isabs(video_path):
            video_path = os.path.join(archive_path, video_path)
        if image_path and not os.path.isabs(image_path):
            image_path = os.path.join(archive_path, image_path)
        
        config_data = {
            'video_path': video_path,
            'image_path': image_path,
            'duration': duration,
            'start_time': start_time,
            'end_time': end_time,
            'comment': comment,
            'download_status': 'downloaded' if os.path.exists(video_path) else 'pending'
        }
        
        self.db.set_video_config(record_id, config_data)
    
    def migrate_project_configs(self, archive_id: int, archive_path: str):
        """Migrate project-level configurations (intro, ending)"""
        video_config_path = os.path.join(archive_path, "video_config.json")
        if not os.path.exists(video_config_path):
            return
        
        with open(video_config_path, 'r', encoding='utf-8') as f:
            video_config = json.load(f)
        
        # Migrate intro configuration
        if 'intro' in video_config:
            self.db.set_project_config(archive_id, 'intro', video_config['intro'])
        
        # Migrate ending configuration
        if 'ending' in video_config:
            self.db.set_project_config(archive_id, 'ending', video_config['ending'])
        
        # Migrate any global settings
        global_config = {}
        for key, value in video_config.items():
            if key not in ['intro', 'ending', 'main']:
                global_config[key] = value
        
        if global_config:
            self.db.set_project_config(archive_id, 'global', global_config)
    
    def migrate_assets(self, archive_id: int, archive_path: str):
        """Migrate asset files (images, videos)"""
        # Migrate images
        images_path = os.path.join(archive_path, "images")
        if os.path.exists(images_path):
            for image_file in os.listdir(images_path):
                if image_file.endswith(('.png', '.jpg', '.jpeg')):
                    image_path = os.path.join(images_path, image_file)
                    self.db.add_asset(
                        asset_type='image',
                        file_path=image_path,
                        archive_id=archive_id,
                        metadata={'original_name': image_file}
                    )
        
        # Migrate videos
        videos_path = os.path.join(archive_path, "videos")
        if os.path.exists(videos_path):
            for video_file in os.listdir(videos_path):
                if video_file.endswith(('.mp4', '.avi', '.mov')):
                    video_path = os.path.join(videos_path, video_file)
                    self.db.add_asset(
                        asset_type='video',
                        file_path=video_path,
                        archive_id=archive_id,
                        metadata={'original_name': video_file}
                    )
    
    def migrate_search_configs(self, archive_path: str):
        """Migrate video search configurations"""
        # Look for b50_config_*.json files
        config_files = glob.glob(os.path.join(archive_path, "b50_config_*.json"))
        
        search_data = {}
        for config_file in config_files:
            platform = os.path.basename(config_file).replace('b50_config_', '').replace('.json', '')
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            search_data[platform] = config_data
        
        return search_data
    
    def _is_timestamp_folder(self, folder_name: str) -> bool:
        """Check if folder name matches timestamp pattern (YYYYMMDD_HHMMSS)"""
        import re
        pattern = r'^\d{8}_\d{6}$'
        return bool(re.match(pattern, folder_name))
    
    def create_backup(self):
        """Create backup of existing JSON data before migration"""
        backup_path = f"{self.b50_data_path}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if os.path.exists(self.b50_data_path):
            shutil.copytree(self.b50_data_path, backup_path)
            self.log(f"Created backup at: {backup_path}")
            return backup_path
        
        return None
    
    def verify_migration(self) -> Dict:
        """Verify migration results"""
        verification = {
            'users_migrated': 0,
            'archives_migrated': 0,
            'records_migrated': 0,
            'errors': []
        }
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count migrated data
                cursor.execute('SELECT COUNT(*) FROM users')
                verification['users_migrated'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM save_archives')
                verification['archives_migrated'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM records')
                verification['records_migrated'] = cursor.fetchone()[0]
                
        except Exception as e:
            verification['errors'].append(f"Verification error: {str(e)}")
        
        return verification


def run_migration():
    """Convenience function to run the complete migration process"""
    print("Starting migration from JSON to SQLite database...")
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Create migration instance
    migration = DataMigration(db_manager)
    
    # Create backup
    backup_path = migration.create_backup()
    if backup_path:
        print(f"Backup created at: {backup_path}")
    
    # Run migration
    migration_log = migration.migrate_all_data()
    
    # Verify results
    verification = migration.verify_migration()
    
    print("\n" + "="*50)
    print("MIGRATION SUMMARY")
    print("="*50)
    print(f"Users migrated: {verification['users_migrated']}")
    print(f"Archives migrated: {verification['archives_migrated']}")
    print(f"Records migrated: {verification['records_migrated']}")
    
    if verification['errors']:
        print("\nErrors encountered:")
        for error in verification['errors']:
            print(f"  - {error}")
    
    print(f"\nFull migration log has {len(migration_log)} entries")
    print("Migration completed!")
    
    return verification


if __name__ == "__main__":
    run_migration()