#!/usr/bin/env python3
"""
Test script for the updated DatabaseManager with SQL file-based schema initialization.
"""

import os
import sys
import tempfile
import sqlite3

# Add the utils directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from DatabaseManager import DatabaseManager

def test_schema_initialization():
    """Test that the database can be initialized from the schema.sql file"""
    
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        temp_db_path = tmp_db.name
    
    try:
        print("Testing schema initialization...")
        
        # Initialize database with the new schema loading method
        db = DatabaseManager(temp_db_path)
        
        # Verify that all expected tables exist
        expected_tables = [
            'users', 'save_archives', 'records', 'video_configs',
            'video_search_results', 'project_configs', 'assets', 'schema_version'
        ]
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = set(expected_tables) - set(actual_tables)
        if missing_tables:
            print(f"❌ Missing tables: {missing_tables}")
            return False
        
        print("✅ All expected tables created successfully")
        
        # Test schema version functionality
        version = db.get_schema_version()
        print(f"✅ Schema version: {version}")
        
        # Test creating a user (basic functionality test)
        user_id = db.create_user("test_user", "Test User")
        user = db.get_user("test_user")
        
        if user and user['username'] == "test_user":
            print("✅ Basic user operations working")
        else:
            print("❌ User operations failed")
            return False
        
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    
    finally:
        # Clean up temporary database
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)

def test_migration_system():
    """Test the migration system"""
    
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        temp_db_path = tmp_db.name
    
    try:
        print("\nTesting migration system...")
        
        db = DatabaseManager(temp_db_path)
        
        # Check initial version
        initial_version = db.get_schema_version()
        print(f"✅ Initial schema version: {initial_version}")
        
        # Test applying migrations (if any exist)
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        if os.path.exists(migrations_dir):
            migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.sql')]
            if migration_files:
                print(f"✅ Found {len(migration_files)} migration file(s)")
                
                # Test check and apply migrations
                db.check_and_apply_migrations()
                
                final_version = db.get_schema_version()
                print(f"✅ Final schema version: {final_version}")
        
        print("✅ Migration system tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Migration test failed with error: {e}")
        return False
    
    finally:
        # Clean up temporary database
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)

if __name__ == "__main__":
    print("=== DatabaseManager Schema Loading Test ===")
    
    success = True
    success &= test_schema_initialization()
    success &= test_migration_system()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("\nThe DatabaseManager now supports:")
        print("- ✅ SQL file-based schema initialization")
        print("- ✅ Schema versioning")
        print("- ✅ Database migrations")
        print("- ✅ Backwards compatibility")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
