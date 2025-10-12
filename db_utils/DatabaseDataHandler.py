from typing import Dict, List, Optional, Tuple, Any, Union
from unittest import case
from db_utils.DatabaseManager import DatabaseManager
from utils.DataUtils import chart_type_str2value, level_label_to_index
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
    
    # --------------------------------------
    # User table handler
    # --------------------------------------
    def set_current_user(self, username: str) -> int:
        """Set current user, create if doesn't exist"""
        user = self.db.get_user(username)
        if not user:
            self.current_user_id = self.db.create_user(username)
        else:
            self.current_user_id = user['id']
        return self.current_user_id
    

    # --------------------------------------
    # Save archive table handler
    # --------------------------------------
    def create_new_archive(self, username: str, game_type: str = 'maimai', 
                       sub_type: str = 'best', rating_mai: int = None, rating_chu: float = None, 
                       game_version: str = 'latest', initial_records: List[Dict] = None) -> Tuple[int, str]:
        """Create a new save archive and optionally populate it with initial records."""
        user_id = self.set_current_user(username)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{username}_{game_type}_{sub_type}_{timestamp}"
        
        archive_id = self.db.create_archive(
            user_id=user_id,
            archive_name=archive_name,
            game_type=game_type,
            sub_type=sub_type,
            rating_mai=rating_mai,
            rating_chu=rating_chu,
            game_version=game_version
        )
        
        self.current_archive_id = archive_id

        if initial_records:
            self.update_archive_records(username, initial_records, archive_name)

        return archive_id, archive_name
    
    def load_save_archive(self, username: str, archive_name: str = None) -> Optional[int]:
        """Load an existing save archive (most recent if archive_name not specified)"""
        user_id = self.set_current_user(username)
        archives = self.db.get_user_archives(user_id)
        
        if not archives:
            return None
        
        target_archive = None
        if archive_name:
            for archive in archives:
                if archive['archive_name'] == archive_name:
                    target_archive = archive
                    break
        else:
            # Load most recent archive
            target_archive = archives[0]

        if target_archive:
            self.current_archive_id = target_archive['id']
            return target_archive['id']
            
        return None
    
    def get_user_save_list(self, username: str) -> List[Dict]:
        """Get list of all save archives for a user"""
        user_id = self.set_current_user(username)
        return self.db.get_user_archives(user_id)
    
    def delete_save_archive(self, username: str, archive_name: str) -> bool:
        """Delete a save archive"""
        user_id = self.set_current_user(username)
        archive_id = self.load_save_archive(username, archive_name)
        
        if archive_id:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM archives WHERE id = ?', (archive_id,))
                conn.commit()
            return True
        return False

    # --------------------------------------
    # Chart table handler
    # --------------------------------------
    def get_or_create_chart(self, chart_data: Dict) -> int:
        """Get or create a chart entry in the database from metadata."""

        chart_id = self.db.get_or_create_chart(chart_data)
        return chart_id

    # --------------------------------------
    # Record and archive update handler from json data
    # --------------------------------------
    def update_archive_records(self, username: str, new_records_data: List[Dict], archive_name: str) -> int:
        """
        Smartly updates records in an archive based on new data.
        - Updates existing records.
        - Adds new records.
        - Deletes old records not present in the new data.
        - Preserves configurations for existing charts.
        """
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError(f"Archive '{archive_name}' not found for user '{username}'")

        # Get existing records from DB, mapped by chart_id for quick lookup
        existing_records_list = self.db.get_archive_records_simple(archive_id)
        existing_records_map = {rec['chart_id']: rec for rec in existing_records_list}
        
        processed_chart_ids = set()

        with self.db.get_connection() as conn: # Use a single transaction
            for i, record_data in enumerate(new_records_data):
                # 1. Get or create the chart for the incoming record
                chart_data = self._extract_chart_data(record_data)  # TODO: check chart_data format
                chart_id = self.db.get_or_create_chart(chart_data)
                processed_chart_ids.add(chart_id)

                # 2. Prepare record data
                # TODO: 检查Order是否需要调整
                record_update_data = self._prepare_record_data(record_data, order=i)

                # 3. Check if this chart already has a record in the archive
                if chart_id in existing_records_map:
                    # It exists, so update it
                    existing_record = existing_records_map[chart_id]
                    self.db.update_record(existing_record['id'], record_update_data)
                else:
                    # It's a new record for this archive, so add it
                    self.db.add_record(archive_id, chart_id, record_update_data)
            
            # 4. Determine which records to delete
            chart_ids_to_delete = set(existing_records_map.keys()) - processed_chart_ids
            record_ids_to_delete = [
                rec['id'] for chart_id, rec in existing_records_map.items() 
                if chart_id in chart_ids_to_delete
            ]
            
            if record_ids_to_delete:
                self.db.delete_records(record_ids_to_delete)

        # Update the record count in the archive table
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE archives SET record_count = ? WHERE id = ?",
                (len(new_records_data), archive_id)
            )
            conn.commit()

        return archive_id

    def copy_archive(self, username: str, source_archive_name: str) -> Optional[Tuple[int, str]]:
        """Create a new archive by copying an existing one, including records and configurations."""
        source_archive_id = self.load_save_archive(username, source_archive_name)
        if not source_archive_id:
            raise ValueError(f"Source archive '{source_archive_name}' not found.")

        source_archive = self.db.get_archive(source_archive_id)
        if not source_archive:
            raise ValueError("Could not retrieve source archive details.")

        # Create a new archive with same metadata
        new_archive_id, new_archive_name = self.create_new_archive(
            username=username,
            game_type=source_archive['game_type'],
            sub_type=source_archive['sub_type'],
            rating_mai=source_archive.get('rating_mai'),
            rating_chu=source_archive.get('rating_chu'),
            game_version=source_archive.get('game_version', 'latest')
        )
        
        # Get all records and their associated data from the source archive
        source_records = self.db.get_records_for_video_generation(source_archive_id)
        
        with self.db.get_connection() as conn:
            for record in source_records:
                # Prepare record data for insertion
                record_copy_data = {
                    'order_in_archive': record['order_in_archive'],
                    'achievement': record['achievement'],
                    'fc_status': record['fc_status'],
                    'fs_status': record['fs_status'],
                    'dx_score': record['dx_score'],
                    'dx_rating': record['dx_rating'],
                    'chuni_rating': record['chuni_rating'],
                    'play_count': record['play_count'],
                    'clip_title_name': record['clip_title_name'],
                    'raw_data': record['raw_data']
                }
                # Add the record to the new archive
                self.db.add_record(new_archive_id, record['chart_id'], record_copy_data)
                
                # Prepare configuration data for insertion
                config_copy_data = {
                    'background_image_path': record.get('background_image_path'),
                    'achievement_image_path': record.get('achievement_image_path'),
                    'video_slice_start': record.get('video_slice_start'),
                    'video_slice_end': record.get('video_slice_end'),
                    'comment_text': record.get('comment_text'),
                    'video_metadata': record.get('video_metadata')
                }
                # If there was any config data, copy it
                if any(v is not None for v in config_copy_data.values()):
                    self.db.set_configuration(new_archive_id, record['chart_id'], config_copy_data)

        return new_archive_id, new_archive_name

    def load_archive_b50_data(self, username: str, archive_name: str = None) -> Optional[Dict]:
        """Load B50 data from database, formatted for backward compatibility."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return None
        
        archive = self.db.get_archive(archive_id)
        if not archive: 
            return None

        records = self.db.get_records_for_video_generation(archive_id)
        
        # Reconstruct b50_data format
        b50_data = {
            'version': self.db.get_schema_version(),
            'type': archive['game_type'],
            'sub_type': archive['sub_type'],
            'username': username,
            'rating_mai': archive['rating_mai'],
            'rating_chu': archive['rating_chu'],
            'length_of_content': len(records),
            'records': []
        }
        
        for record in records:
            raw_data = record.get('raw_data', {})
            record_data = {
                'song_id': record['song_id'],
                'title': record['song_name'],
                'artist': record['artist'],
                'type': record['chart_type'], # 'type' is old key for chart_type
                'level_index': record['level_index'],
                'level': record['difficulty'], # 'difficulty' is the new 'level'
                'achievements': record['achievement'],
                'fc': record['fc_status'],
                'fs': record['fs_status'],
                'dx_score': record['dx_score'],
                'dx_rating': record['dx_rating'],
                'play_count': record['play_count'],
                'clip_name': record['clip_title_name'] or f"{record['song_id']}_{record['chart_type']}",
            }
            b50_data['records'].append(record_data)

        return b50_data
    
    # --------------------------------------
    # Configuration table and
    # Video_extra_configs table handler using video_config format
    # --------------------------------------
    def save_video_config(self, username: str, video_config: Dict, archive_name: str = None):
        """Save video configuration to the database."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found to save configuration.")
        
        # Save intro/ending/extra configurations
        for config_type in ['intro', 'ending', 'extra']:
            if config_type in video_config:
                # Assuming single config item for now, extend if multiple are needed
                self.db.set_extra_video_config(archive_id, config_type, video_config[config_type])
        
        # Save main (record-specific) configurations
        if 'main' in video_config:
            records = self.db.get_records_for_video_generation(archive_id)
            record_map = {
                (str(r['song_id']), r['level_index']): r['chart_id'] 
                for r in records
            }

            for main_config in video_config['main']:
                lookup_key = (
                    str(main_config.get('song_id')), 
                    main_config.get('level_index')
                )
                chart_id = record_map.get(lookup_key)
                
                if chart_id:
                    config_data = {
                        'background_image_path': main_config.get('main_image'),
                        'achievement_image_path': main_config.get('achievement_image'),
                        'video_slice_start': main_config.get('start'),
                        'video_slice_end': main_config.get('end'),
                        'comment_text': main_config.get('text'),
                        'video_metadata': json.dumps({
                            'video_url': main_config.get('video_url'),
                            'video_platform': main_config.get('video_platform'),
                            'video_id': main_config.get('video_id'),
                            'video_p_index': main_config.get('video_p_index', 0)
                        })
                    }
                    self.db.set_configuration(archive_id, chart_id, config_data)
    
    def load_video_config(self, username: str, archive_name: str = None) -> Dict:
        """Load video configuration from the database."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return {'intro': [], 'ending': [], 'extra': [], 'main': []}
        
        # Load intro/ending/extra configurations
        extra_configs = self.db.get_all_extra_video_configs(archive_id)
        video_config = {'intro': [], 'ending': [], 'extra': [], 'main': []}
        for cfg in extra_configs:
            if cfg['config_type'] in video_config:
                video_config[cfg['config_type']].append(cfg['config_data'])

        # Load main configurations
        records_with_configs = self.db.get_records_for_video_generation(archive_id)
        
        for record in records_with_configs:
            video_meta = json.loads(record.get('video_metadata') or '{}')
            main_config = {
                'id': f"{record['song_id']}_{record['level_index']}",
                'achievement_title': record['clip_title_name'] or f"{record['song_name']}-{record['chart_type']}",
                'song_id': record['song_id'],
                'level_index': record['level_index'],
                'type': record['chart_type'],
                'main_image': record.get('background_image_path'),
                'achievement_image': record.get('achievement_image_path'),
                'video': record.get('video_path'), # From charts table
                'duration': (record.get('video_slice_end', 10.0) or 10.0) - (record.get('video_slice_start', 0.0) or 0.0),
                'start': record.get('video_slice_start'),
                'end': record.get('video_slice_end'),
                'text': record.get('comment_text'),
                'video_url': video_meta.get('video_url'),
                'video_platform': video_meta.get('video_platform'),
                'video_id': video_meta.get('video_id'),
            }
            video_config['main'].append(main_config)
        
        return video_config
    
    # --------------------------------------
    # Internal Helper methods
    # TODO: Refactor if needed
    # --------------------------------------

    def _extract_chart_data(self, record_data: Dict) -> Dict:
        """Fish-style chart data to standard chart table format."""
        return {
            'game_type': record_data.get('game_type', 'maimai'),
            'song_id': str(record_data.get('title')),
            'chart_type': chart_type_str2value(record_data.get('type'), fish_record_style=True), 
            'level_index': record_data.get('level_index'),
            'difficulty': record_data.get('ds'), 
            'song_name': record_data.get('title'),
            'artist': record_data.get('artist', None), # TODO：部分歌曲信息需要从元数据查询
            'max_dx_score': record_data.get('max_dx_score', None),
            'video_path': record_data.get('video_path', None)
        }

    def _prepare_record_data(self, record_data: Dict, order: int) -> Dict:
        """Prepares record-specific fields for database insertion/update."""
        return {
            'order_in_archive': order,
            'achievement': record_data.get('achievements'), # 'achievements' in old format
            'fc_status': record_data.get('fc'),
            'fs_status': record_data.get('fs'),
            'dx_score': record_data.get('dxScore', None),
            'dx_rating': record_data.get('ra', 0),
            'chuni_rating': record_data.get('chuni_rating', 0),
            'play_count': record_data.get('play_count', 0),
            'clip_title_name': record_data.get('clip_title_name'),
            'raw_data': record_data # Store the original record for full fidelity
        }
    
    # ----------------------------------
    # Migration helpers
    # TODO: Not finished, refactor to migration old data under v0.6
    # ----------------------------------
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
def get_database_handler() -> "DatabaseDataHandler":
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
    records = b50_data.get('records', [])
    
    archive_id = handler.load_save_archive(username, archive_name)
    if not archive_id:
        archive_id, archive_name = handler.create_new_archive(
            username=username,
            game_type=b50_data.get('type', 'maimai'),
            sub_type=b50_data.get('sub_type', 'best'),
            rating_mai=b50_data.get('rating_mai'),
            rating_chu=b50_data.get('rating_chu'),
            game_version=b50_data.get('game_version', 'latest')
        )

    return handler.update_archive_records(username, records, archive_name)


def load_video_config(username: str, archive_name: str = None) -> Dict:
    """Load video configuration (backward compatibility)"""
    handler = get_database_handler()
    return handler.load_video_config(username, archive_name)


def save_video_config(username: str, video_config: Dict, archive_name: str = None):
    """Save video configuration (backward compatibility)"""
    handler = get_database_handler()
    return handler.save_video_config(username, video_config, archive_name)