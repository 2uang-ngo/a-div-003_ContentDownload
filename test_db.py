#!/usr/bin/env python3
"""
Test script để verify SQLite database functionality
"""

import os
import tempfile
from Auto_Insta_Downloader import DownloadDatabase

def test_database():
    """Test database operations."""
    # Tạo temp folder
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        print(f"Testing database at: {db_path}")
        print("-" * 50)
        
        # Khởi tạo DB
        db = DownloadDatabase(db_path)
        print("✓ Database initialized")
        
        # Test INSERT OR IGNORE
        print("\n--- Testing INSERT OR IGNORE ---")
        # Create file_path values similar to what the scraper would generate
        file1 = "testuser/2025-01-28_10-00-00.bin"
        file2 = "testuser/2025-01-28_10-05-00.bin"

        result1 = db.insert_or_ignore("testuser", "https://example.com/photo1.jpg", "2025-01-28, 10:00:00", file1)
        print(f"Insert 1: {result1}")
        
        result2 = db.insert_or_ignore("testuser", "https://example.com/photo2.jpg", "2025-01-28, 10:05:00", file2)
        print(f"Insert 2: {result2}")
        
        # Try insert duplicate (same file_path but different URL)
        result_dup = db.insert_or_ignore("testuser", "https://example.com/photo1_alt.jpg", "2025-01-28, 10:00:00", file1)
        print(f"Insert duplicate (should be ignored due to same file_path): {result_dup}")
        
        # Test GET STATS
        print("\n--- Testing GET STATS ---")
        stats = db.get_stats()
        print(f"Stats: {stats}")
        print(f"  Total: {stats['total']}")
        print(f"  Pending: {stats['pending']}")
        print(f"  Ready: {stats['ready']}")
        
        # Test GET PENDING
        print("\n--- Testing GET PENDING DOWNLOADS ---")
        pending = db.get_pending_downloads()
        print(f"Found {len(pending)} pending downloads:")
        for row in pending:
            print(f"  ID={row[0]}, Username={row[1]}, URL={row[2][:40]}..., Timestamp={row[3]}")
        
        # Test UPDATE STATUS
        print("\n--- Testing UPDATE STATUS ---")
        if pending:
            first_id = pending[0][0]
            result = db.update_download_status(first_id, 'ready', 'testuser/photo1.jpg')
            print(f"Update ID {first_id} to ready: {result}")
        
        # Check stats again
        print("\n--- Stats after update ---")
        stats = db.get_stats()
        print(f"Stats: {stats}")
        
        # Test GET DOWNLOAD BY ID
        print("\n--- Testing GET DOWNLOAD BY ID ---")
        if pending:
            download = db.get_download_by_id(first_id)
            if download:
                print(f"Download details:")
                print(f"  ID: {download[0]}")
                print(f"  Username: {download[1]}")
                print(f"  URL: {download[2][:40]}...")
                print(f"  Status: {download[5]}")
                print(f"  File Path: {download[4]}")
        
        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")

if __name__ == "__main__":
    test_database()
