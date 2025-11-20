#!/usr/bin/env python3
"""
Demonstration script showing how to use the new SQLite database system
for mai-gen-videob50 project.

This script shows various usage patterns for the new database-based data storage.
"""

from utils.DatabaseManager import DatabaseManager
from utils.DatabaseDataHandler import DatabaseDataHandler
import json

def demo_basic_usage():
    """Demonstrate basic database usage"""
    print("="*60)
    print("BASIC DATABASE USAGE DEMO")
    print("="*60)
    
    # Initialize database handler
    handler = DatabaseDataHandler("demo_database.db")
    
    # Example 1: Create a user and save B50 data
    print("\n1. Creating user and saving B50 data...")
    
    sample_b50_data = {
        "version": "0.6",
        "type": "maimai",
        "sub_type": "best",
        "username": "demo_user",
        "rating": 15000,
        "length_of_content": 3,
        "records": [
            {
                "song_id": 100,
                "title": "Test Song 1",
                "artist": "Test Artist",
                "type": "DX",
                "level_index": 4,
                "level": 13.5,
                "achievements": 99.5,
                "fc": "FC+",
                "fs": "FDX",
                "dx_score": 1500,
                "dx_rating": 200,
                "clip_name": "Test_Song_1",
                "clip_id": "clip_1"
            },
            {
                "song_id": 101,
                "title": "Test Song 2", 
                "artist": "Test Artist 2",
                "type": "SD",
                "level_index": 3,
                "level": 12.0,
                "achievements": 98.2,
                "fc": "FC",
                "fs": "FS+",
                "dx_score": 1200,
                "dx_rating": 180,
                "clip_name": "Test_Song_2",
                "clip_id": "clip_2"
            },
            {
                "song_id": 102,
                "title": "Test Song 3",
                "artist": "Test Artist 3", 
                "type": "DX",
                "level_index": 4,
                "level": 14.0,
                "achievements": 97.8,
                "fc": "",
                "fs": "FS",
                "dx_score": 1400,
                "dx_rating": 195,
                "clip_name": "Test_Song_3",
                "clip_id": "clip_3"
            }
        ]
    }
    
    # Save the data
    archive_id = handler.save_b50_data("demo_user", sample_b50_data)
    print(f"   Saved B50 data to archive ID: {archive_id}")
    
    # Example 2: Load the data back
    print("\n2. Loading B50 data...")
    loaded_data = handler.load_b50_data("demo_user")
    print(f"   Loaded {len(loaded_data['records'])} records")
    print(f"   User rating: {loaded_data['rating']}")
    
    # Example 3: Get user's save list
    print("\n3. Getting user's save archives...")
    archives = handler.get_user_save_list("demo_user")
    for archive in archives:
        print(f"   Archive: {archive['archive_name']} - {archive['record_count']} records")
    
    # Example 4: Save video configuration
    print("\n4. Saving video configuration...")
    video_config = {
        "intro": [
            {
                "id": "intro_1",
                "duration": 5,
                "text": "Welcome to my B50 video!"
            }
        ],
        "ending": [
            {
                "id": "ending_1", 
                "duration": 3,
                "text": "Thanks for watching!"
            }
        ],
        "main": [
            {
                "id": "clip_1",
                "achievement_title": "Test Song 1-DX",
                "song_id": 100,
                "level_index": 4,
                "type": "DX",
                "main_image": "images/test_song_1.png",
                "video": "videos/test_song_1.mp4",
                "duration": 10,
                "start": 30,
                "end": 40,
                "text": "Amazing FC+ on this difficult chart!"
            }
        ]
    }
    
    handler.save_video_config("demo_user", video_config)
    print("   Video configuration saved")
    
    # Example 5: Load video configuration
    print("\n5. Loading video configuration...")
    loaded_config = handler.load_video_config("demo_user")
    print(f"   Loaded config with {len(loaded_config.get('main', []))} main entries")


def demo_song_tracking():
    """Demonstrate song progress tracking across time"""
    print("\n" + "="*60)
    print("SONG PROGRESS TRACKING DEMO")
    print("="*60)
    
    # Use the test database created by migration
    db = DatabaseManager("test_migration.db")
    
    # Example: Track progress for a specific song
    print("\n1. Tracking song progress for nickbit...")
    
    # Get user
    user = db.get_user("nickbit")
    if not user:
        print("   User 'nickbit' not found in test database")
        return
    
    # Find a song that appears multiple times
    song_history = db.get_song_history(user['id'], "833", "DX", 4)  # the EmpErroR
    
    if song_history:
        print(f"   Song: {song_history[0]['title']}")
        print(f"   Chart: {song_history[0]['chart_type']} Level {song_history[0]['level_index']}")
        print(f"   Progress across {len(song_history)} archives:")
        
        for record in song_history:
            print(f"     {record['archive_created_at']}: {record['achievement']:.4f}% (Rating: {record['archive_rating']})")
    
    # Example: Get user progress summary
    print(f"\n2. User progress summary for nickbit...")
    summary = db.get_user_progress_summary(user['id'])
    print(f"   Total archives: {summary['archive_count']}")
    print(f"   Total records: {summary['total_records']}")
    print(f"   First archive: {summary['first_archive']}")
    print(f"   Latest archive: {summary['latest_archive']}")
    print(f"   Best rating: {summary['best_rating']}")


def demo_search_and_assets():
    """Demonstrate video search and asset management"""
    print("\n" + "="*60)
    print("SEARCH AND ASSET MANAGEMENT DEMO")
    print("="*60)
    
    handler = DatabaseDataHandler("demo_database.db")
    
    # Example 1: Save search results
    print("\n1. Saving video search results...")
    
    search_results = [
        {
            "video_id": "abc123",
            "video_url": "https://youtube.com/watch?v=abc123",
            "title": "Test Song 1 - Expert gameplay",
            "description": "Perfect play of Test Song 1",
            "duration": 120,
            "view_count": 5000,
            "thumbnail_url": "https://img.youtube.com/vi/abc123/default.jpg",
            "search_query": "Test Song 1 maimai"
        },
        {
            "video_id": "def456", 
            "video_url": "https://youtube.com/watch?v=def456",
            "title": "Test Song 1 - Another gameplay",
            "description": "Good play of Test Song 1",
            "duration": 115,
            "view_count": 2000,
            "thumbnail_url": "https://img.youtube.com/vi/def456/default.jpg",
            "search_query": "Test Song 1 maimai"
        }
    ]
    
    handler.save_search_results("demo_user", "100", 4, "DX", "youtube", search_results)
    print("   Search results saved for Test Song 1")
    
    # Example 2: Get search results
    print("\n2. Getting search results...")
    results = handler.get_search_results("demo_user", "100", 4, "DX", "youtube")
    for result in results:
        print(f"   {result['title']} - {result['view_count']} views")
    
    # Example 3: Register assets
    print("\n3. Registering assets...")
    
    # Register a score image
    image_id = handler.register_asset("demo_user", "image", "images/test_song_1.png", "100", 4, "DX")
    print(f"   Registered image asset ID: {image_id}")
    
    # Register a video file
    video_id = handler.register_asset("demo_user", "video", "videos/test_song_1.mp4", "100", 4, "DX")
    print(f"   Registered video asset ID: {video_id}")
    
    # Example 4: Update download status
    print("\n4. Updating download status...")
    handler.update_download_status("demo_user", "100", 4, "DX", "downloaded", "videos/test_song_1.mp4")
    print("   Download status updated to 'downloaded'")


def demo_backward_compatibility():
    """Demonstrate backward compatibility functions"""
    print("\n" + "="*60)
    print("BACKWARD COMPATIBILITY DEMO")
    print("="*60)
    
    # Import the compatibility functions
    from utils.DatabaseDataHandler import load_user_data, save_user_data, load_video_config, save_video_config
    
    print("\n1. Using backward compatibility functions...")
    
    # These functions work exactly like the old JSON-based system
    # but use the database backend
    
    sample_data = {
        "version": "0.6",
        "type": "maimai", 
        "sub_type": "best",
        "username": "compat_user",
        "rating": 14500,
        "records": [
            {
                "song_id": 200,
                "title": "Compatibility Test",
                "type": "DX",
                "level_index": 3,
                "achievements": 96.5,
                "clip_id": "compat_clip_1"
            }
        ]
    }
    
    # Save using old-style function
    save_user_data("compat_user", sample_data)
    print("   Saved data using backward compatibility function")
    
    # Load using old-style function  
    loaded = load_user_data("compat_user")
    print(f"   Loaded data: {len(loaded['records'])} records, rating {loaded['rating']}")
    
    print("\n   This allows existing code to work without modification!")


def main():
    """Run all demonstrations"""
    print("Mai-gen-videob50 Database System Demonstration")
    print("This demo shows how to use the new SQLite-based data storage system.")
    
    try:
        demo_basic_usage()
        demo_song_tracking()
        demo_search_and_assets()
        demo_backward_compatibility()
        
        print("\n" + "="*60)
        print("DEMONSTRATION COMPLETE")
        print("="*60)
        print("The new database system provides:")
        print("- Efficient storage and querying of B50 data")
        print("- Song progress tracking across multiple archives")
        print("- Video search result management")
        print("- Asset tracking and management")
        print("- Backward compatibility with existing code")
        print("- Better data integrity and performance")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()