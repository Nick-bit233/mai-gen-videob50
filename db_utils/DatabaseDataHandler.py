from typing import Dict, List, Optional, Tuple, Any, Union
from db_utils.DatabaseManager import DatabaseManager
from utils.DataUtils import encode_song_id, decode_song_id
import os
import json
from datetime import datetime

class DatabaseDataHandler:
    """
    New data handler that replaces JSON-based storage with SQLite database.
    Provides backward-compatible interface for existing code while using the new database backend.
    """
    
    def __init__(self, db_path: str = "mai_gen_videob50.db"):
        self.db = DatabaseManager(db_path)
        self.current_user_id = None
        self.current_archive_id = None
    
    # User management
    def set_current_user(self, username: str) -> int:
        """Set current user, create if doesn't exist"""
        user = self.db.get_user(username)
        if not user:
            self.current_user_id = self.db.create_user(username)
        else:
            self.current_user_id = user['id']
        return self.current_user_id
    
    # Save archive management (replaces timestamp-based folders)
    def create_new_archive(self, username: str, game_type: str = 'maimai', 
                       sub_type: str = 'best', rating_mai: int = None, rating_chu: float = None) -> Tuple[int, str]:
        """Create a new save archive"""
        user_id = self.set_current_user(username)
        
        # Generate archive name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{username}_{game_type}_{sub_type}_{timestamp}"
        
        archive_id = self.db.create_save_archive(
            user_id=user_id,
            archive_name=archive_name,
            game_type=game_type,
            sub_type=sub_type,
            rating_mai=rating_mai,
            rating_chu=rating_chu,
        )
        
        self.current_archive_id = archive_id
        return archive_id, archive_name
    
    # get existing save archive, return archive_id or None
    def load_save_archive(self, username: str, archive_name: str = None) -> Optional[int]:
        """Load an existing save archive (most recent if archive_name not specified)"""
        user_id = self.set_current_user(username)
        archives = self.db.get_user_archives(user_id)
        
        if not archives:
            return None
        
        if archive_name:
            # Find specific archive
            for archive in archives:
                if archive['archive_name'] == archive_name:
                    self.current_archive_id = archive['id']
                    return archive['id']
            return None
        else:
            # Load most recent archive
            self.current_archive_id = archives[0]['id']
            return archives[0]['id']
    
    def get_user_save_list(self, username: str) -> List[Dict]:
        """Get list of all save archives for a user"""
        user_id = self.set_current_user(username)
        return self.db.get_user_archives(user_id)
    
    def delete_save_archive(self, username: str, archive_name: str) -> bool:
        """Delete a save archive"""
        user_id = self.set_current_user(username)
        archives = self.db.get_user_archives(user_id)
        
        for archive in archives:
            if archive['archive_name'] == archive_name:
                # Note: Database foreign key constraints will handle cascading deletes
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM save_archives WHERE id = ?', (archive['id'],))
                    conn.commit()
                return True
        return False
    
    # Record management (replaces b50_raw.json)
    def update_archive_b50_data(self, username: str, b50_data: Dict, archive_name: str = None, type: str = 'maimai') -> int:
        """update B50 data to database"""
        # Only allowed to use existing archive
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError(f"Archive {archive_name} not found")
        
        new_records = b50_data.get('records', [])  
        existing_records = self.db.get_archive_records(archive_id)
        for each in existing_records:
            pos = each.get('position')
            match = next((r for r in new_records if r.get('position') == pos), None)
            if match:
                self.db.update_record(each['id'], match)

        return archive_id
    
    def copy_archive(self, username: str, source_archive_name: str) -> Optional[int]:
        """Create a new archive by copying an existing one"""
        archive_id = self.load_save_archive(username, source_archive_name)

        # Get the source archive metadata
        source_archive = self.db.get_archive(archive_id)
        if not source_archive:
            raise ValueError(f"Archive {source_archive_name} not found")

        # Create new archive with same metadata
        new_archive_id, new_archive_name = self.create_new_archive(
            username=username,
            game_type=source_archive['game_type'],
            sub_type=source_archive['sub_type'],
            rating_mai=source_archive.get('rating_mai'),
            rating_chu=source_archive.get('rating_chu')
        )
        
        # Copy records
        records = self.db.get_archive_records(source_archive['id'])
        for record in records:
            record_copy = record.copy()
            record_copy.pop('id', None)  # Remove id to avoid conflicts
            record_copy.pop('archive_id', None)  # Will be set to new archive_id
            self.db.add_record(new_archive_id, record_copy)

        # TODO: Copy video configs as well if needed
        return new_archive_id, new_archive_name

    def load_archive_b50_data(self, username: str, archive_name: str = None) -> Optional[Dict]:
        """Load B50 data from database (replaces reading b50_raw.json)"""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return None
        
        archive = self.db.get_archive(archive_id)
        records = self.db.get_archive_records(archive_id)

        db_version = self.db.get_schema_version()
        
        # Reconstruct b50_data format for backward compatibility
        b50_data = {
            'version': archive['metadata'].get('version', db_version),
            'type': archive['game_type'],
            'sub_type': archive['sub_type'],
            'username': username,
            'rating_mai': archive['rating_mai'],
            'rating_chu': archive['rating_chu'],
            'length_of_content': len(records),
            'records': []
        }
        
        to_sort_records = []
        for record in records:
            # Convert database record back to original format
            record_data = {
                'song_id': record['song_id'],
                'title': record['title'],
                'artist': record['artist'],
                'type': record['chart_type'],
                'level_index': record['level_index'],
                'level': record['level_value'],
                'achievements': record['achievement'],
                'fc': record['fc_status'],
                'fs': record['fs_status'],
                'dx_score': record['dx_score'],
                'dx_rating': record['dx_rating'],
                'play_time': record['play_count'],
                'clip_name': record['clip_name'],
            }
            
            # Add any additional data from raw_data field
            # if record['raw_data']:
            #     try:
            #         raw_data = json.loads(record['raw_data'])
            #         record_data.update(raw_data)
            #     except:
            #         pass

            pos = record.get('position')
            to_sort_records.append((pos, record_data))

        # Sort records by position
        reversed = b50_data['sub_type'] in ['best', 'ap']
        to_sort_records.sort(key=lambda x: x[0], reverse=reversed)
        b50_data['records'] = [x[1] for x in to_sort_records]

        return b50_data
    
    # Video configuration management (replaces video_config.json)
    def save_video_config(self, username: str, video_config: Dict, archive_name: str = None):
        """Save video configuration to database (replaces video_config.json)"""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found")
        
        # Save intro configuration
        if 'intro' in video_config:
            self.db.set_project_config(archive_id, 'intro', video_config['intro'])
        
        # Save ending configuration
        if 'ending' in video_config:
            self.db.set_project_config(archive_id, 'ending', video_config['ending'])
        
        # Save main (record-specific) configurations
        if 'main' in video_config:
            records = self.db.get_archive_records(archive_id)
            record_map = {r['clip_id']: r['id'] for r in records}
            
            for main_config in video_config['main']:
                clip_id = main_config.get('id')
                if clip_id in record_map:
                    record_id = record_map[clip_id]
                    
                    config_data = {
                        'video_path': main_config.get('video'),
                        'image_path': main_config.get('main_image'),
                        'duration': main_config.get('duration', 10.0),
                        'start_time': main_config.get('start', 0.0),
                        'end_time': main_config.get('end', 10.0),
                        'comment': main_config.get('text', ''),
                        'video_url': main_config.get('video_url'),
                        'video_platform': main_config.get('video_platform'),
                        'video_id': main_config.get('video_id'),
                        'download_status': main_config.get('download_status', 'pending')
                    }
                    
                    self.db.set_video_config(record_id, config_data)
    
    def load_video_config(self, username: str, archive_name: str = None) -> Dict:
        """Load video configuration from database (replaces reading video_config.json)"""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return {}
        
        # Load project configurations
        intro_config = self.db.get_project_config(archive_id, 'intro') or []
        ending_config = self.db.get_project_config(archive_id, 'ending') or []
        
        # Load record-specific configurations
        records = self.db.get_archive_records(archive_id)
        main_configs = []
        
        for record in records:
            video_config = self.db.get_video_config(record['id'])
            if video_config:
                main_config = {
                    'id': record['clip_id'],
                    'achievement_title': f"{record['title']}-{record['chart_type']}",
                    'song_id': record['song_id'],
                    'level_index': record['level_index'],
                    'type': record['chart_type'],
                    'main_image': video_config['image_path'],
                    'video': video_config['video_path'],
                    'duration': video_config['duration'],
                    'start': video_config['start_time'],
                    'end': video_config['end_time'],
                    'text': video_config['comment'] or ''
                }
                main_configs.append(main_config)
        
        return {
            'intro': intro_config,
            'ending': ending_config,
            'main': main_configs
        }
    
    def update_download_status(self, username: str, song_id: str, level_index: int, 
                              chart_type: str, status: str, video_path: str = None,
                              archive_name: str = None):
        """Update download status for a record"""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return
        
        # Find the record
        records = self.db.get_archive_records(archive_id)
        target_record = None
        
        for record in records:
            if (record['song_id'] == str(song_id) and 
                record['level_index'] == level_index and 
                record['chart_type'] == chart_type):
                target_record = record
                break
        
        if target_record:
            existing_config = self.db.get_video_config(target_record['id']) or {}
            existing_config['download_status'] = status
            if video_path:
                existing_config['video_path'] = video_path
            
            self.db.set_video_config(target_record['id'], existing_config)
    
    # Asset management
    def register_asset(self, username: str, asset_type: str, file_path: str, 
                      song_id: str = None, level_index: int = None, 
                      chart_type: str = None, archive_name: str = None) -> int:
        """Register an asset (image, video, etc.) in the database"""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found")
        
        record_id = None
        if song_id is not None and level_index is not None and chart_type is not None:
            # Find specific record
            records = self.db.get_archive_records(archive_id)
            for record in records:
                if (record['song_id'] == str(song_id) and 
                    record['level_index'] == level_index and 
                    record['chart_type'] == chart_type):
                    record_id = record['id']
                    break
        
        return self.db.add_asset(
            asset_type=asset_type,
            file_path=file_path,
            record_id=record_id,
            archive_id=archive_id
        )
    
    def get_assets(self, username: str, asset_type: str = None, 
                   song_id: str = None, level_index: int = None, 
                   chart_type: str = None, archive_name: str = None) -> List[Dict]:
        """Get assets from the database"""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return []
        
        record_id = None
        if song_id is not None and level_index is not None and chart_type is not None:
            # Find specific record
            records = self.db.get_archive_records(archive_id)
            for record in records:
                if (record['song_id'] == str(song_id) and 
                    record['level_index'] == level_index and 
                    record['chart_type'] == chart_type):
                    record_id = record['id']
                    break
        
        return self.db.get_assets(
            record_id=record_id,
            archive_id=archive_id,
            asset_type=asset_type
        )
    
    # Utility methods for backward compatibility
    def get_archive_path(self, username: str, archive_name: str = None) -> str:
        """Get virtual archive path for backward compatibility"""
        # This method provides a path-like interface for code that expects file paths
        # In reality, data is stored in the database
        if not archive_name:
            archives = self.get_user_save_list(username)
            if archives:
                archive_name = archives[0]['archive_name']
        
        return f"database://{username}/{archive_name}"
    
    def archive_exists(self, username: str, archive_name: str) -> bool:
        """Check if archive exists"""
        archives = self.get_user_save_list(username)
        return any(a['archive_name'] == archive_name for a in archives)
    
    # Migration helpers
    def import_from_json(self, json_data_path: str):
        """Import data from existing JSON structure"""
        from db_utils.DataMigration import DataMigration
        migration = DataMigration(self.db, json_data_path)
        return migration.migrate_all_data()
    
    def export_to_json(self, username: str, archive_name: str, output_path: str):
        """Export archive data to JSON format for backup"""
        b50_data = self.load_archive_b50_data(username, archive_name)
        video_config = self.load_video_config(username, archive_name)
        
        export_data = {
            'b50_data': b50_data,
            'video_config': video_config,
            'export_timestamp': datetime.now().isoformat()
        }
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)


# Convenience functions for easy migration from existing code
def get_database_handler() -> DatabaseDataHandler:
    """Get a singleton instance of the database handler"""
    if not hasattr(get_database_handler, '_instance'):
        get_database_handler._instance = DatabaseDataHandler()
    return get_database_handler._instance


# Backward compatibility aliases
def load_user_data(username: str, archive_name: str = None) -> Optional[Dict]:
    """Load user B50 data (backward compatibility)"""
    handler = get_database_handler()
    return handler.load_archive_b50_data(username, archive_name)


def update_user_data(username: str, b50_data: Dict, archive_name: str = None) -> int:
    """Save user B50 data (backward compatibility)"""
    handler = get_database_handler()
    return handler.update_archive_b50_data(username, b50_data, archive_name)


def load_video_config(username: str, archive_name: str = None) -> Dict:
    """Load video configuration (backward compatibility)"""
    handler = get_database_handler()
    return handler.load_video_config(username, archive_name)


def save_video_config(username: str, video_config: Dict, archive_name: str = None):
    """Save video configuration (backward compatibility)"""
    handler = get_database_handler()
    return handler.save_video_config(username, video_config, archive_name)