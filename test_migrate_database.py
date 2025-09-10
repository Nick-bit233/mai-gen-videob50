#!/usr/bin/env python3
"""
Test migration script for mai-gen-videob50 project.

This script scans existing JSON data in ./b50_datas and migrates it to SQLite database.
It provides detailed analysis and verification of the migration process.

Usage:
    python test_migrate_database.py [options]
"""

import os
import json
import glob
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import argparse
from utils.DatabaseManager import DatabaseManager
from utils.DataMigration import DataMigration

class TestDataScanner:
    """Scanner for existing JSON data structure"""
    
    def __init__(self, data_path: str = "b50_datas"):
        self.data_path = data_path
        self.scan_results = {}
    
    def scan_all_data(self) -> Dict:
        """Scan all existing JSON data and return analysis"""
        print(f"Scanning data directory: {self.data_path}")
        
        if not os.path.exists(self.data_path):
            print(f"Data directory '{self.data_path}' not found!")
            return {}
        
        users = []
        total_archives = 0
        total_records = 0
        
        # Scan user directories
        for user_dir in os.listdir(self.data_path):
            user_path = os.path.join(self.data_path, user_dir)
            if not os.path.isdir(user_path):
                continue
            
            print(f"\nScanning user: {user_dir}")
            user_data = self.scan_user_data(user_dir, user_path)
            if user_data:
                users.append(user_data)
                total_archives += user_data['archive_count']
                total_records += user_data['total_records']
        
        self.scan_results = {
            'total_users': len(users),
            'total_archives': total_archives,
            'total_records': total_records,
            'users': users
        }
        
        return self.scan_results
    
    def scan_user_data(self, username: str, user_path: str) -> Optional[Dict]:
        """Scan data for a specific user"""
        archives = []
        total_records = 0
        
        # Look for timestamp directories
        for item in os.listdir(user_path):
            item_path = os.path.join(user_path, item)
            if os.path.isdir(item_path) and self._is_timestamp_folder(item):
                archive_data = self.scan_archive(username, item, item_path)
                if archive_data:
                    archives.append(archive_data)
                    total_records += archive_data['record_count']
        
        if not archives:
            print(f"  No valid archives found for user {username}")
            return None
        
        # Sort archives by timestamp
        archives.sort(key=lambda x: x['timestamp'], reverse=True)
        
        user_data = {
            'username': username,
            'archive_count': len(archives),
            'total_records': total_records,
            'archives': archives,
            'latest_archive': archives[0]['timestamp'] if archives else None,
            'oldest_archive': archives[-1]['timestamp'] if archives else None
        }
        
        print(f"  Found {len(archives)} archives with {total_records} total records")
        return user_data
    
    def scan_archive(self, username: str, timestamp: str, archive_path: str) -> Optional[Dict]:
        """Scan a single archive directory"""
        # Check for required files
        b50_raw_path = os.path.join(archive_path, "b50_raw.json")
        b50_config_path = os.path.join(archive_path, "b50_config.json")
        video_config_path = os.path.join(archive_path, "video_config.json")
        
        if not os.path.exists(b50_raw_path):
            print(f"    Warning: {timestamp} missing b50_raw.json")
            return None
        
        try:
            # Load b50_raw.json
            with open(b50_raw_path, 'r', encoding='utf-8') as f:
                b50_data = json.load(f)
            
            # Analyze the data
            records = b50_data.get('records', [])
            
            # Check for additional config files
            has_b50_config = os.path.exists(b50_config_path)
            has_video_config = os.path.exists(video_config_path)
            
            # Scan for platform-specific config files
            platform_configs = []
            for config_file in glob.glob(os.path.join(archive_path, "b50_config_*.json")):
                platform = os.path.basename(config_file).replace('b50_config_', '').replace('.json', '')
                platform_configs.append(platform)
            
            # Check for assets
            images_path = os.path.join(archive_path, "images")
            videos_path = os.path.join(archive_path, "videos")
            
            image_count = 0
            video_count = 0
            
            if os.path.exists(images_path):
                image_count = len([f for f in os.listdir(images_path) 
                                 if f.endswith(('.png', '.jpg', '.jpeg'))])
            
            if os.path.exists(videos_path):
                video_count = len([f for f in os.listdir(videos_path) 
                                 if f.endswith(('.mp4', '.avi', '.mov'))])
            
            archive_data = {
                'timestamp': timestamp,
                'path': archive_path,
                'record_count': len(records),
                'game_type': b50_data.get('type', 'maimai'),
                'sub_type': b50_data.get('sub_type', 'best'),
                'rating': b50_data.get('rating'),
                'version': b50_data.get('version', 'unknown'),
                'has_b50_config': has_b50_config,
                'has_video_config': has_video_config,
                'platform_configs': platform_configs,
                'image_count': image_count,
                'video_count': video_count,
                'sample_records': records[:3] if records else []  # First 3 records for analysis
            }
            
            print(f"    {timestamp}: {len(records)} records, rating={b50_data.get('rating', 'N/A')}")
            
            return archive_data
            
        except Exception as e:
            print(f"    Error scanning {timestamp}: {e}")
            return None
    
    def _is_timestamp_folder(self, folder_name: str) -> bool:
        """Check if folder name matches timestamp pattern (YYYYMMDD_HHMMSS)"""
        pattern = r'^\d{8}_\d{6}$'
        return bool(re.match(pattern, folder_name))
    
    def print_analysis(self):
        """Print detailed analysis of scanned data"""
        if not self.scan_results:
            print("No scan results available. Run scan_all_data() first.")
            return
        
        results = self.scan_results
        
        print("\n" + "="*60)
        print("DATA ANALYSIS REPORT")
        print("="*60)
        
        print(f"Total Users: {results['total_users']}")
        print(f"Total Archives: {results['total_archives']}")
        print(f"Total Records: {results['total_records']}")
        
        if results['users']:
            print(f"\nAverage Archives per User: {results['total_archives'] / results['total_users']:.1f}")
            print(f"Average Records per Archive: {results['total_records'] / results['total_archives']:.1f}")
        
        print("\nUser Details:")
        print("-" * 40)
        
        for user in results['users']:
            print(f"\nUser: {user['username']}")
            print(f"  Archives: {user['archive_count']}")
            print(f"  Total Records: {user['total_records']}")
            print(f"  Date Range: {user['oldest_archive']} to {user['latest_archive']}")
            
            # Show latest archive details
            if user['archives']:
                latest = user['archives'][0]
                print(f"  Latest Archive:")
                print(f"    Timestamp: {latest['timestamp']}")
                print(f"    Records: {latest['record_count']}")
                print(f"    Rating: {latest['rating']}")
                print(f"    Game Type: {latest['game_type']}")
                print(f"    Assets: {latest['image_count']} images, {latest['video_count']} videos")
                
                if latest['platform_configs']:
                    print(f"    Platform Configs: {', '.join(latest['platform_configs'])}")
        
        # Analyze record structure
        print("\nRecord Structure Analysis:")
        print("-" * 40)
        
        sample_records = []
        for user in results['users']:
            for archive in user['archives']:
                sample_records.extend(archive['sample_records'])
        
        if sample_records:
            sample = sample_records[0]
            print("Sample record fields:")
            for key, value in sample.items():
                print(f"  {key}: {type(value).__name__} = {value}")


class TestMigration:
    """Test migration with verification"""
    
    def __init__(self, db_path: str = "test_mai_gen_videob50.db", data_path: str = "b50_datas"):
        self.db_path = db_path
        self.data_path = data_path
        self.db_manager = None
        self.migration = None
    
    def run_test_migration(self, clean_start: bool = True) -> Dict:
        """Run test migration with full verification"""
        print("\n" + "="*60)
        print("STARTING TEST MIGRATION")
        print("="*60)
        
        # Clean start - remove existing test database
        if clean_start and os.path.exists(self.db_path):
            os.remove(self.db_path)
            print(f"Removed existing test database: {self.db_path}")
        
        # Initialize database
        print(f"\nInitializing database: {self.db_path}")
        self.db_manager = DatabaseManager(self.db_path)
        
        # Create migration instance
        self.migration = DataMigration(self.db_manager, self.data_path)
        
        # Run migration
        print("\nStarting migration...")
        migration_log = self.migration.migrate_all_data()
        
        # Verify migration
        print("\nVerifying migration results...")
        verification = self.migration.verify_migration()
        
        # Additional verification
        detailed_verification = self.detailed_verification()
        
        results = {
            'migration_log': migration_log,
            'basic_verification': verification,
            'detailed_verification': detailed_verification
        }
        
        return results
    
    def detailed_verification(self) -> Dict:
        """Perform detailed verification of migrated data"""
        verification = {
            'users': [],
            'total_archives': 0,
            'total_records': 0,
            'errors': []
        }
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all users
                cursor.execute('SELECT * FROM users')
                users = [dict(row) for row in cursor.fetchall()]
                
                for user in users:
                    user_verification = self.verify_user_data(user)
                    verification['users'].append(user_verification)
                    verification['total_archives'] += user_verification['archive_count']
                    verification['total_records'] += user_verification['record_count']
                
        except Exception as e:
            verification['errors'].append(f"Verification error: {str(e)}")
        
        return verification
    
    def verify_user_data(self, user: Dict) -> Dict:
        """Verify data for a specific user"""
        user_id = user['id']
        username = user['username']
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get user's archives
            cursor.execute('SELECT * FROM save_archives WHERE user_id = ?', (user_id,))
            archives = [dict(row) for row in cursor.fetchall()]
            
            # Get total records for user
            cursor.execute('''
                SELECT COUNT(*) as record_count
                FROM records r
                JOIN save_archives sa ON r.archive_id = sa.id
                WHERE sa.user_id = ?
            ''', (user_id,))
            
            total_records = cursor.fetchone()[0]
            
            # Sample some records for verification
            cursor.execute('''
                SELECT r.*, sa.archive_name
                FROM records r
                JOIN save_archives sa ON r.archive_id = sa.id
                WHERE sa.user_id = ?
                LIMIT 5
            ''', (user_id,))
            
            sample_records = [dict(row) for row in cursor.fetchall()]
            
            return {
                'username': username,
                'user_id': user_id,
                'archive_count': len(archives),
                'record_count': total_records,
                'archives': archives,
                'sample_records': sample_records
            }
    
    def test_queries(self):
        """Test various database queries"""
        print("\n" + "="*60)
        print("TESTING DATABASE QUERIES")
        print("="*60)
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Test 1: Get users with most archives
            print("\nTest 1: Users with most archives")
            cursor.execute('''
                SELECT u.username, COUNT(sa.id) as archive_count
                FROM users u
                LEFT JOIN save_archives sa ON u.id = sa.user_id
                GROUP BY u.id
                ORDER BY archive_count DESC
                LIMIT 5
            ''')
            
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]} archives")
            
            # Test 2: Song history tracking
            print("\nTest 2: Song history tracking (sample)")
            cursor.execute('''
                SELECT r.song_id, r.title, COUNT(*) as appearance_count
                FROM records r
                GROUP BY r.song_id, r.title
                HAVING appearance_count > 1
                ORDER BY appearance_count DESC
                LIMIT 5
            ''')
            
            for row in cursor.fetchall():
                print(f"  {row[1]} (ID: {row[0]}): appears in {row[2]} archives")
            
            # Test 3: Progress tracking for a specific song
            cursor.execute('''
                SELECT u.username, r.song_id, r.title, r.achievement, sa.created_at
                FROM records r
                JOIN save_archives sa ON r.archive_id = sa.id
                JOIN users u ON sa.user_id = u.id
                WHERE r.song_id = (
                    SELECT song_id FROM records 
                    GROUP BY song_id 
                    HAVING COUNT(*) > 1 
                    LIMIT 1
                )
                ORDER BY u.username, sa.created_at
            ''')
            
            print("\nTest 3: Progress tracking for a popular song")
            current_user = None
            for row in cursor.fetchall():
                if current_user != row[0]:
                    current_user = row[0]
                    print(f"  User: {current_user}")
                    print(f"    Song: {row[2]} (ID: {row[1]})")
                
                print(f"    {row[4]}: {row[3]:.4f}%")
    
    def print_results(self, results: Dict):
        """Print migration test results"""
        print("\n" + "="*60)
        print("MIGRATION TEST RESULTS")
        print("="*60)
        
        basic = results['basic_verification']
        detailed = results['detailed_verification']
        
        print(f"Users migrated: {basic['users_migrated']}")
        print(f"Archives migrated: {basic['archives_migrated']}")
        print(f"Records migrated: {basic['records_migrated']}")
        
        if basic['errors']:
            print(f"\nBasic verification errors: {len(basic['errors'])}")
            for error in basic['errors']:
                print(f"  - {error}")
        
        if detailed['errors']:
            print(f"\nDetailed verification errors: {len(detailed['errors'])}")
            for error in detailed['errors']:
                print(f"  - {error}")
        
        print(f"\nDetailed verification:")
        print(f"  Total users verified: {len(detailed['users'])}")
        print(f"  Total archives verified: {detailed['total_archives']}")
        print(f"  Total records verified: {detailed['total_records']}")
        
        # Show sample user data
        if detailed['users']:
            print(f"\nSample user verification:")
            sample_user = detailed['users'][0]
            print(f"  User: {sample_user['username']}")
            print(f"  Archives: {sample_user['archive_count']}")
            print(f"  Records: {sample_user['record_count']}")
            
            if sample_user['sample_records']:
                print(f"  Sample record: {sample_user['sample_records'][0]['title']}")


def main():
    parser = argparse.ArgumentParser(description='Test migration for mai-gen-videob50')
    parser.add_argument('--data-path', default='b50_datas', 
                       help='Path to JSON data directory')
    parser.add_argument('--db-path', default='test_mai_gen_videob50.db',
                       help='Path for test database')
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan existing data, don\'t migrate')
    parser.add_argument('--migrate-only', action='store_true',
                       help='Only run migration, don\'t scan')
    parser.add_argument('--keep-db', action='store_true',
                       help='Keep existing test database')
    
    args = parser.parse_args()
    
    print("Mai-gen-videob50 Test Migration Tool")
    print("=" * 40)
    
    # Step 1: Scan existing data
    if not args.migrate_only:
        print("\n1. Scanning existing JSON data...")
        scanner = TestDataScanner(args.data_path)
        scan_results = scanner.scan_all_data()
        
        if scan_results:
            scanner.print_analysis()
        else:
            print("No data found to scan.")
            if not args.scan_only:
                print("Proceeding with empty database initialization...")
    
    if args.scan_only:
        return
    
    # Step 2: Test migration
    print("\n2. Running test migration...")
    test_migration = TestMigration(args.db_path, args.data_path)
    results = test_migration.run_test_migration(clean_start=not args.keep_db)
    
    # Step 3: Print results
    test_migration.print_results(results)
    
    # Step 4: Test queries
    test_migration.test_queries()
    
    print(f"\nTest database created at: {args.db_path}")
    print("Migration test completed successfully!")


if __name__ == "__main__":
    main()