# SQLite Database Integration - Implementation Summary

## Overview
Implemented a complete SQLite database system for tracking Instagram content downloads with a 3-phase workflow:
1. **Scrape Phase**: Extract metadata and INSERT OR IGNORE into database (status=pending)
2. **Worker Phase**: Process pending downloads and update database (status=ready + file_path)
3. **Track Phase**: Full visibility into all downloads with SQLite database

---

## Architecture

### Database Schema

```sql
CREATE TABLE downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    timestamp TEXT,
    file_path TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending' or 'ready'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Key Features:**
- **UNIQUE constraint on file_path**: Prevents duplicate downloads based on the generated `file_path` (deduplication now uses file_path created at scrape time).
- **INSERT OR IGNORE**: Automatically skips duplicate URLs
- **Status tracking**: pending → ready
- **Timestamps**: Track creation and updates
- **File paths**: Store relative paths after successful download

---

## Workflow

### Phase 1: Scraping (Metadata Only)

**Button:** "Bắt đầu scrape & insert DB"

**Flow:**
1. Scrape HTML from gramsnap.com for each username
2. Extract metadata: URL, timestamp, from media items
3. INSERT OR IGNORE into database with status='pending'
4. Log results (inserts vs skips for duplicates)

**Benefits:**
- Fast scraping without waiting for downloads
- Deduplication built-in
- Can run multiple times without losing data
- Continues session-by-session

---

### Phase 2: Worker Downloads

**Button:** "Tải file từ DB"

**Flow:**
1. Query all downloads with status='pending'
2. Download each file from URL
3. Save with timestamp-based filename
4. UPDATE database: status='ready' + file_path
5. Organize files into /images and /videos subdirectories

**Benefits:**
- Independent from scraping
- Can retry failed downloads
- Transparent progress tracking
- Automatic organization

---

## Class Implementation: `DownloadDatabase`

Located in `Auto_Insta_Downloader.py`

### Methods

#### `__init__(db_path)`
Initializes database connection and creates schema if needed.

#### `init_database()`
Creates the downloads table with proper schema and constraints.

#### `insert_or_ignore(username, url, timestamp)`
- **Purpose**: Insert metadata into database
- **Returns**: True if inserted, False if duplicate
- **Status**: Automatically set to 'pending'

#### `get_pending_downloads(limit=None)`
- **Purpose**: Fetch all pending downloads
- **Returns**: List of tuples (id, username, url, timestamp)

#### `update_download_status(download_id, status, file_path=None)`
- **Purpose**: Update download record after successful download
- **Parameters**:
  - `download_id`: Primary key
  - `status`: 'ready' or 'pending'
  - `file_path`: Relative path like 'username/filename.jpg'
- **Updates**: status, file_path, updated_at timestamp

#### `get_download_by_id(download_id)`
- **Purpose**: Fetch single download record
- **Returns**: Row object with all columns

#### `get_stats()`
- **Purpose**: Get database statistics
- **Returns**: Dict with keys: total, pending, ready
- **Example**: `{'total': 100, 'pending': 30, 'ready': 70}`

---

## GUI Changes

### New UI Elements

1. **Worker Button**: "Tải file từ DB"
   - Disabled until scraping creates database
   - Enabled after scrape completes
   - Runs in background thread

2. **Updated Scrape Button**: "Bắt đầu scrape & insert DB"
   - Only performs scraping + database insertion
   - Does NOT download files
   - Much faster than before

3. **Updated Status Messages**
   - Shows database statistics after operations
   - Displays pending/ready counts

### Callback Methods

- `_on_scrape_finished()`: Shows database stats after scrape
- `_on_worker_finished()`: Shows final statistics after downloads

---

## Database Location

**Path**: `[base_folder]/downloads.db`

The database file is created in the base folder (same level as usernames' folders). This allows:
- Single database for all users
- Easy backup and portability
- Single query for all statistics

**Example structure:**
```
/D/Downloads/Instagram/
├── downloads.db           ← Database file
├── username1/
│   ├── images/
│   └── videos/
└── username2/
    ├── images/
    └── videos/
```

---

## Logging

### Log File: `log.txt`

Both scrape and worker phases append to `log.txt` with timestamps:

**Scrape Log Example:**
```
==================================================
Bắt đầu scrape lúc: 2025-01-28 15:30:45
==================================================
✓ insta_user1: 25 insert, 0 skip
✓ insta_user2: 18 insert, 3 skip
Thống kê DB: Total=43, Pending=43, Ready=0
==================================================
Kết thúc lúc: 2025-01-28 15:35:12
==================================================
```

**Worker Log Example:**
```
==================================================
Bắt đầu worker download lúc: 2025-01-28 15:40:00
==================================================
✓ ID=1, insta_user1: insta_user1/2025-01-28_10-30-15.jpg
✓ ID=2, insta_user1: insta_user1/2025-01-28_10-32-45.mp4
✗ ID=3, insta_user2: Lỗi tải
Kết quả: 2 thành công, 1 thất bại
Thống kê DB: Total=43, Pending=40, Ready=3
==================================================
Kết thúc lúc: 2025-01-28 15:42:30
==================================================
```

---

## Key Design Decisions

### 1. **INSERT OR IGNORE Strategy**
- **Why**: Prevents duplicate downloads automatically
- **Benefit**: Can scrape multiple times, only new URLs are added
- **Alternative considered**: REPLACE INTO (would waste space on duplicates)

### 2. **Separate Scrape and Download Phases**
- **Why**: Decouple metadata collection from file transfer
- **Benefits**:
  - Faster initial scraping
  - Can retry downloads independently
  - More control and visibility
  - Can cancel at any point

### 3. **Relative File Paths in Database**
- **Format**: `username/filename.ext`
- **Why**: Portable if folder is moved
- **Example**: `insta_user1/2025-01-28_10-30-15.jpg`

### 4. **Status Column**
- **Values**: 'pending' or 'ready'
- **Purpose**: Track which files have been downloaded
- **Query**: `SELECT * FROM downloads WHERE status='pending'`

### 5. **UNIQUE Constraint on file_path**

The database uses a unique index on `file_path` so that items are deduplicated based on the filename that will be saved locally. This ensures duplicates are detected even when the remote URL changes for the same content.
- **Why**: Enforce no duplicate URLs at database level
- **Benefit**: Impossible to have same URL twice
- **Trade-off**: Slightly slower inserts (negligible)

---

## Testing

### Test File: `test_db.py`

Run tests with:
```bash
python test_db.py
```

**Test Coverage:**
1. Database initialization
2. INSERT OR IGNORE (normal + duplicate)
3. GET STATS
4. GET PENDING DOWNLOADS
5. UPDATE STATUS
6. GET DOWNLOAD BY ID

**Test Results:** ✓ All tests passed

---

## Usage Workflow

### Session 1: Scraping
1. Open application
2. Select folder: `D:/Downloads/Instagram`
3. Enter usernames: `insta_user1`, `insta_user2`
4. Click "Bắt đầu scrape & insert DB"
5. Wait for completion → See DB stats in popup
6. Database now has 43 pending downloads

### Session 2: Download (same day or later)
1. Open application (same folder)
2. Click "Tải file từ DB"
3. Wait for downloads to complete
4. Files are organized into /images and /videos
5. Database updated with status='ready' and file paths

### Session 3: Add More Users (next day)
1. Add new usernames to text area
2. Click "Bắt đầu scrape & insert DB"
3. New URLs inserted, existing URLs skipped
4. "Tải file từ DB" downloads only the new ones
5. Previous downloads remain at status='ready'

---

## Advanced Queries (Manual SQLite Access)

If you want to query the database directly:

```bash
sqlite3 downloads.db
```

**Useful queries:**

```sql
-- Count by status
SELECT status, COUNT(*) FROM downloads GROUP BY status;

-- Count by username
SELECT username, COUNT(*) FROM downloads GROUP BY username;

-- Get all pending for a specific user
SELECT id, url, timestamp FROM downloads 
WHERE status='pending' AND username='insta_user1';

-- Get all ready files
SELECT username, file_path FROM downloads WHERE status='ready';

-- Recently added
SELECT * FROM downloads 
ORDER BY created_at DESC LIMIT 10;

-- Files added today
SELECT * FROM downloads 
WHERE DATE(created_at) = DATE('now');
```

---

## Files Modified

1. **Auto_Insta_Downloader.py**
   - Added `import sqlite3`
   - Added `DownloadDatabase` class
   - Modified `TASK2ManualInstaGuiApp.__init__()` to add `self.db` and `self.db_path`
   - Modified UI to add "Tải file từ DB" button
   - Added `_run_scrape_only_multi_thread()` - scrape + insert DB
   - Added `_run_download_worker_thread()` - download + update DB
   - Added `on_start_worker()` - trigger worker downloads
   - Added `_on_scrape_finished()` - scrape callback
   - Added `_on_worker_finished()` - worker callback

2. **test_db.py** (new)
   - Database functionality tests

---

## Future Enhancements (Optional)

1. **Batch Retry**
   - Add UI button: "Retry Failed Downloads"
   - Query: `WHERE status='pending' AND updated_at < datetime('now', '-1 hour')`

2. **Advanced Filtering**
   - Filter by date range in UI
   - Filter by username
   - Search by URL

3. **Database Export**
   - Export to CSV: username, url, status, file_path
   - Excel/Google Sheets integration

4. **Delete Management**
   - Mark files as deleted in database
   - Track local vs database state
   - Clean up orphaned entries

5. **Multi-Instance Support**
   - Multiple apps using same database
   - Database locking and concurrency

6. **GUI Database Viewer**
   - Show database contents in UI
   - Edit status manually
   - View statistics in real-time

---

## Troubleshooting

### Database locked
- Ensure only one instance of application is running
- Close any external SQLite tools accessing the database

### Duplicate detected error
- This is normal! It means the URL already exists
- Check logs to see how many were skipped

### File not downloading
- Check log file for specific error
- Verify URL is still valid
- Check internet connection

### Database file missing
- Must scrape first before using worker
- Database is created in base folder on first scrape

### Permission denied on database
- Ensure folder has write permissions
- Check file is not locked by another process
