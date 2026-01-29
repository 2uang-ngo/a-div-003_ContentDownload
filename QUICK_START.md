# SQLite Database Integration - Quick Start Guide

## 3-Phase Workflow

### Phase 1: SCRAPE & INSERT DB
```
Action: Click "Bắt đầu scrape & insert DB"
Result: 
  - Metadata scraped from Instagram
  - URLs inserted into database with status='pending'
  - Duplicate URLs are automatically skipped
  - Fast operation (no file downloads)
```

### Phase 2: DOWNLOAD & UPDATE DB
```
Action: Click "Tải file từ DB"
Result:
  - All pending files are downloaded
  - Database updated with status='ready'
  - File paths stored in database
  - Files organized into /images and /videos
```

### Phase 3: TRACK & MANAGE
```
Result:
  - Full database of all downloads
  - Can query anytime using SQLite
  - Can retry failures
  - Can add more users without losing data
```

---

## Database Statistics

After each operation, popup shows:
```
Total:   100    (total URLs in database)
Pending: 30     (still need to download)
Ready:   70     (already downloaded)
```

---

## Database File Location

```
[Your Base Folder]/downloads.db
```

Example:
```
D:/Downloads/Instagram/downloads.db
```

---

## Key Features

✅ **Automatic Deduplication**
- Same URL won't be downloaded twice
- INSERT OR IGNORE prevents duplicates

✅ **Session Independence**
- Scrape today, download tomorrow
- Add more users anytime
- Progress saved in database

✅ **Full Traceability**
- Know which files are downloaded (status='ready')
- Know which files are pending (status='pending')
- File paths stored with each record

✅ **Fast & Efficient**
- Separate scrape and download phases
- Can cancel anytime
- Retry only what's needed

---

## Log File

Located: `[Your Base Folder]/log.txt`

Contains:
- Timestamp of each operation
- How many URLs inserted vs skipped
- How many downloads succeeded vs failed
- Final database statistics

---

## Files Changed

1. **Auto_Insta_Downloader.py** - Main application
   - Added DownloadDatabase class (150+ lines)
   - Added 2 new buttons and 2 new worker methods
   - Total: ~200 new lines of code

2. **test_db.py** - New test file
   - Validates all database operations

3. **DATABASE_IMPLEMENTATION.md** - Full documentation

---

## Quick Commands

### Check database from command line:
```bash
cd "[Your Base Folder]"
sqlite3 downloads.db
```

### Count by status:
```sql
SELECT status, COUNT(*) FROM downloads GROUP BY status;
```

### Count by user:
```sql
SELECT username, COUNT(*) FROM downloads GROUP BY username;
```

### See pending files:
```sql
SELECT id, username, url FROM downloads WHERE status='pending' LIMIT 10;
```

### See downloaded files:
```sql
SELECT id, username, file_path FROM downloads WHERE status='ready';
```

---

## What Happens When...

### Same username scraped twice?
- URLs that were already in database: SKIPPED (duplicate)
- URLs that are new: INSERTED as pending

### Download fails?
- File marked as pending still
- Can retry clicking "Tải file từ DB" again
- It will only try pending files

### Want to change folder?
- Database is specific to that folder
- New folder = new database
- Old folder keeps its database

### Want to restart everything?
- Delete the `downloads.db` file
- Next scrape will create a fresh database

---

## Status Meanings

| Status | Meaning | Next Action |
|--------|---------|------------|
| pending | URL scraped, not downloaded yet | Click "Tải file từ DB" |
| ready | File successfully downloaded | Done! Check /images or /videos |

---

## Database Columns

| Column | Meaning | Example |
|--------|---------|---------|
| id | Record ID | 1, 2, 3... |
| username | Instagram username | insta_user1 |
| url | Direct download link | https://example.com/photo.jpg |
| timestamp | Post timestamp | 2025-01-28, 10:30:15 |
| file_path | Where file is saved | insta_user1/2025-01-28_10-30-15.jpg |
| status | Download status | pending or ready |
| created_at | When scraped | 2025-01-28 15:30:45 |
| updated_at | Last update | 2025-01-28 16:42:30 |

---

## Common Scenarios

### Scenario 1: Scrape Multiple Users in One Session
1. Enter 5 usernames in text area
2. Click "Bắt đầu scrape & insert DB"
3. Wait for all 5 to complete
4. Database now has all URLs from all 5 users
5. Click "Tải file từ DB" to download all at once

### Scenario 2: Add More Users Later
1. Add new usernames to text area
2. Click "Bắt đầu scrape & insert DB"
3. New URLs inserted, old ones skipped
4. Click "Tải file từ DB" - downloads only new ones
5. Old files remain at status='ready'

### Scenario 3: Download Only Some Users
1. After scraping, note which usernames' files to download
2. Click "Tải file từ DB" downloads ALL pending
3. (To download selectively, you'd need manual SQLite queries)

### Scenario 4: Recover from Accidental Deletion
1. If you deleted files but DB still has status='ready'
2. Update DB: `UPDATE downloads SET status='pending' WHERE username='user1'`
3. Click "Tải file từ DB" to re-download

---

## Performance Tips

✅ **Do This:**
- Scrape all users in one session (batch scrape)
- Then download all files in one session (batch download)
- Check logs after each operation

❌ **Don't Do This:**
- Scrape, download, scrape, download (inefficient)
- Delete database without knowing the consequences
- Run multiple instances of the app on same database

---

## Need Help?

1. **Check log.txt** - Most errors are logged there
2. **Check database stats** - Click buttons to see current state
3. **Read DATABASE_IMPLEMENTATION.md** - Full technical details
4. **Run test_db.py** - Verify database is working: `python test_db.py`

---

## What's New vs Old Version?

| Feature | Old | New |
|---------|-----|-----|
| Speed | Downloads while scraping (slow) | Scrape only, super fast! |
| Duplicates | Downloaded again | Skipped automatically |
| Tracking | No record of what was downloaded | Full database record |
| Sessions | One-shot only | Can continue across sessions |
| Retry | Manual process | Query database, retry pending |
| Queries | Not possible | Full SQL access to database |

---

## Database Structure (Visual)

```
downloads.db
├─ downloads table (1 table, many rows)
│  ├─ Row 1: insta_user1, url1, pending, ...
│  ├─ Row 2: insta_user1, url2, ready, insta_user1/photo.jpg
│  ├─ Row 3: insta_user2, url3, pending, ...
│  └─ Row 4: insta_user2, url4, ready, insta_user2/video.mp4
```

**One row per URL per user**
