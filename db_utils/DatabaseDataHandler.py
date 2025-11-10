from typing import Dict, List, Optional, Tuple, Any, Union
from unittest import case
from db_utils.DatabaseManager import DatabaseManager
from utils.DataUtils import get_jacket_image_from_url, query_songs_metadata, format_record_tag
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
    
    def get_user_save_list(self, username: str, game_type: Optional[str] = None) -> List[Dict]:
        """Get list of all save archives for a given user and optional game_type filter."""
        user_id = self.set_current_user(username)
        archives = self.db.get_user_archives(user_id, game_type)
        return archives

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
    def load_or_create_chart_by_data(self, chart_data: Dict) -> int:
        """Get or create a chart entry in the database from metadata."""

        chart_id = self.db.get_or_create_chart(chart_data)
        return chart_id
    
    def load_chart_by_id(self, chart_id: int) -> Optional[Dict]:
        """Retrieve chart metadata by chart_id"""
        return self.db.get_chart(chart_id)
    
    def update_chart_video_metadata(self, chart_id: int, video_info_match: Dict) -> Optional[Dict]:
        """Update video metadata (matched video WEB info) for a chart."""
        if video_info_match: 
             # video_metadata == chart_data['video_info_match']
            self.db.update_chart(
                chart_id=chart_id,
                chart_data={
                    'video_metadata': video_info_match
                }
            )
            return self.load_chart_by_id(chart_id)
        return None
    
    def update_chart_video_path(self, chart_id: int, video_path: str) -> Optional[Dict]:
        """Update video path (static, local) for a chart."""
        if video_path: 
            self.db.update_chart(
                chart_id=chart_id,
                chart_data={
                    'video_path': video_path
                }
            )
            return self.load_chart_by_id(chart_id)
        return None

    # --------------------------------------
    # Record and archive update handler from json data
    # --------------------------------------
    def update_archive_metadata(self, username: str, archive_name: str, metadata: Dict) -> Optional[Dict]:
        """Update metadata fields of an existing archive."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError(f"Archive '{archive_name}' not found for user '{username}'")
        
        allowed_fields = ['archive_name', 'game_type', 'sub_type', 'rating_mai', 'rating_chu', 'game_version']
        update_data = {k: v for k, v in metadata.items() if k in allowed_fields}
        
        if update_data:
            self.db.update_archive(archive_id, update_data)
            return self.load_archive_metadata(username, archive_name)
        return None

    def update_archive_records(self, username: str, new_records_data: List[Dict], archive_name: str) -> int:
        """
        Smartly updates records in an archive based on new data.
        Input new_records_data format:
            [
                {
                    "chart_data": { ... },  # Chart metadata for get_or_create_chart
                    "order_in_archive": 0,
                    "achievement": 100.6225,
                    ... # Same fields as in record table except ids
                }
            ]   
        Progressively:
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
                chart_data = record_data.get('chart_data')
                if not chart_data:
                    raise ValueError("Each record must include 'chart_data' field.")
                chart_id = self.db.get_or_create_chart(chart_data)
                processed_chart_ids.add(chart_id)

                # print(f"Updating record for chart_id {chart_id} with data: {record_data}")
                # 2. Check if this chart already has a record in the archive
                if chart_id in existing_records_map:
                    # It exists, so update it
                    existing_record = existing_records_map[chart_id]
                    self.db.update_record(existing_record['id'], record_data)
                else:
                    # It's a new record for this archive, so add it
                    self.db.add_record(archive_id, chart_id, record_data)
            
            # 3. Determine which records to delete
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

    # --------------------------------------
    # Archive, Record, and Config loaders and joint query handlers
    # --------------------------------------

    def load_archive_metadata(self, username: str, archive_name: str) -> Optional[Dict]:
        """Load metadata for a given archive."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return None
        
        archive = self.db.get_archive(archive_id)
        return archive

    def load_archive_records(self, username: str, archive_name: str) -> List[Dict]:
        """Load all records for a given archive."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return []
        
        records = self.db.get_archive_records_simple(archive_id)
        return records
    
    def load_charts_of_archive_records(self, username: str, archive_name: str) -> List[Dict]:
        """Load all charts for a given archive."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return []
        
        charts = self.db.get_charts_of_archive(archive_id)
        return charts

    def load_archive_for_image_generation(self, archive_id: int) -> List[Dict]:
        """Load archive data formatted for image generation scripts."""
        # load game type
        archive = self.db.get_archive(archive_id)
        game_type = archive['game_type']

        # load records with complete fields
        records = self.db.get_records_for_video_generation(archive_id)

        # format data as "style_config" needed by game type
        ret_records = []
        if game_type == 'maimai':
            # 需要从music metadata中获取max dx score以及封面图片
            for record in records:
                title = record['song_name']
                artist = record['artist']
                # 获取歌曲元数据
                metadata = query_songs_metadata(game_type, title, artist)
                image_code = metadata.get('imageName', None)
                # 下载封面图片
                jacket_image = get_jacket_image_from_url(image_code)
                reformat_data = {
                    'chart_id': record['chart_id'],
                    'song_id': record['song_id'],
                    'title': title,
                    'artist': artist,
                    'type': record['chart_type'],
                    'level_index': record['level_index'],
                    'ds': float(record['difficulty']),
                    'achievements': f"{record['achievement']:.4f}", # Format as string with 4 decimal places
                    'fc': record['fc_status'],
                    'fs': record['fs_status'],
                    'dxScore': record['dx_score'],
                    'max_dx_score': record['max_dx_score'],
                    'jacket': jacket_image,
                    'ra': record['dx_rating'],
                    'playCount': record['play_count'],
                    'clip_name': record['clip_title_name'] or f"Clip_{record['order_in_archive'] + 1}"
                }
                ret_records.append(reformat_data)
        elif game_type == 'chunithm':
            for record in records:
                title = record['song_name']
                artist = record['artist']
                # 获取歌曲元数据
                metadata = query_songs_metadata(game_type, title, artist)
                # TODO: 需要从music metadata中获取多版本定数
                # ds_next = get_chunithm_ds_next(metadata)
                reformat_data = {
                    'chart_id': record['chart_id'],
                    'song_id': record['song_id'],
                    'title': record['song_name'],
                    'artist': record['artist'],
                    'type': record['chart_type'],
                    'level_index': record['level_index'],
                    'ds_cur': float(record['difficulty']),
                    'ds_next': None,
                    'score': int(record['achievement']), # Format as integer score
                    'combo_type': record['fc_status'],
                    'chain_type': record['fs_status'],
                    'ra': record['chuni_rating'],
                    'playCount': record['play_count'],
                    'clip_name': record['clip_title_name'] or f"Clip_{record['order_in_archive'] + 1}"
                }
                ret_records.append(reformat_data)

        return game_type, ret_records

    def load_archive_as_old_b50_config(self, username: str, archive_name: str = None) -> Optional[Dict]:
        """Load B50 data (old format) from database.
           Use only for backward (v0.5~v0.6) compatibility. Supported game_type = maimai only."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return None
        
        archive = self.db.get_archive(archive_id)
        if not archive: 
            return None
        
        game_type = archive['game_type']
        if game_type != 'maimai':
            raise NotImplementedError("Only 'maimai' game type is supported for old b50 format.")

        records = self.db.get_records_for_video_generation(archive_id)
        # Reconstruct b50_data format
        b50_data = {
            'version': self.db.get_schema_version(),
            'type': game_type,
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
    
    def load_archive_complete_config(self, username: str, archive_name: str) -> Optional[Dict]:
        """Load complete archive info including metadata, all records with full video config."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            return None
        
        archive = self.db.get_archive(archive_id)
        if not archive:
            return None
        
        records = self.db.get_records_for_video_generation(archive_id)
        
        complete_info = {
            'archive': archive,
            'records': records
        }
        return complete_info

    # --------------------------------------
    # Configuration table and
    # Video_extra_configs table handler using video_config format
    # --------------------------------------
    def update_image_config_for_record(self, archive_id: int, chart_id: int, image_path_data: Dict) -> bool:
        # Update image configuration for a specific record
        bg_image_path = image_path_data.get('background_image_path', None)
        achievement_image_path = image_path_data.get('achievement_image_path', None)
        self.db.set_configuration(
            archive_id,
            chart_id,
            {
                'background_image_path': bg_image_path,
                'achievement_image_path': achievement_image_path
            }
        )

    def save_video_config(self, username: str, video_config: Dict, archive_name: str = None):
        """Save video configuration(main) to the database."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found to save configuration.")
        
        # Save main (chart/record-specific) configurations
        for entry in video_config:
            chart_id = entry.get('chart_id', None)
            
            if chart_id:
                config_data = {
                    'background_image_path': entry.get('bg_image'),
                    'achievement_image_path': entry.get('achievement_image'),
                    'video_slice_start': entry.get('start'),
                    'video_slice_end': entry.get('end'),
                    'comment_text': entry.get('text')
                }
                self.db.set_configuration(archive_id, chart_id, config_data)
            else:
                raise ValueError("Invalid video configuration entry: missing chart_id")
    
    def load_video_config(self, username: str, archive_name: str = None) -> Dict:
        """Load video configuration(main) from the database."""
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found to load configuration.")

        # Load main configurations
        full_records = self.db.get_records_for_video_generation(archive_id)
        ret_video_config = []
        for record in full_records:
            video_metadata = record.get('video_metadata', None)
            # print(f"type: {type(video_metadata)}, content: {video_metadata}")
            # Parse default value if no metadata found in the database
            duration = video_metadata.get('duration', 0) if video_metadata else 0
            video_url = video_metadata.get('url', None) if video_metadata else None
            video_id = video_metadata.get('id', None) if video_metadata else None

            entry = {
                'game_type': record.get('game_type'),
                'chart_id': record.get('chart_id', None),
                'bg_image': record.get('background_image_path'),
                'achievement_image': record.get('achievement_image_path'),
                'start': record.get('video_slice_start'),
                'end': record.get('video_slice_end'),
                'text': record.get('comment_text'),
                'video': record.get('video_path'),  # From charts table: c.video_path
                'duration': duration,
                'video_url': video_url,
                'video_id': video_id,
                'clip_title_name': record.get('clip_title_name'),
                'record_tag': format_record_tag(
                    record.get('game_type'), record.get('clip_title_name'), 
                    record.get('song_id'), record.get('chart_type', -1), record.get('level_index', -1)
                )
            }
            ret_video_config.append(entry)
        return ret_video_config
    
    def load_extra_video_config(self, username: str, config_type: str, archive_name: str = None):
        """
        Load extra video configuration from the database.
        
        Args:
            username: The username to load configuration for
            archive_name: The archive name (optional, uses current if not provided)
            
        Returns:
            List of configuration data dictionaries, ordered by config_index
        """
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found to load configuration.")

        # Load extra video configurations
        extra_configs = self.db.get_all_extra_video_configs(archive_id, config_type)
        return extra_configs

    def save_extra_video_config(self, username: str, config_type: str, config_data_list: List, archive_name: str = None):
        """
        Save extra video configuration to the database.
        
        Args:
            username: The username to save configuration for
            config_type: The type of configuration (e.g., 'intro', 'ending', 'extra')
            config_data_list: List of configuration data dictionaries
            archive_name: The archive name (optional, uses current if not provided)
        """
        archive_id = self.load_save_archive(username, archive_name)
        if not archive_id:
            raise ValueError("No active archive found to save configuration.")
        
        # Delete existing configurations of this type
        # with self.db.get_connection() as conn:
        #     cursor = conn.cursor()
        #     cursor.execute('''
        #         DELETE FROM extra_video_configs 
        #         WHERE archive_id = ? AND config_type = ?
        #     ''', (archive_id, config_type))
        #     conn.commit()
        
        # Save new configurations with proper indexing
        for index, config_data in enumerate(config_data_list):
            self.db.set_extra_video_config(archive_id, config_type, config_data, index)

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
        b50_data = self.load_archive_as_old_b50_config(username, archive_name)
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
    return handler.load_archive_as_old_b50_config(username, archive_name)


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