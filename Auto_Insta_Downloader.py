import json
import os
import re
import shutil
import threading
import sqlite3
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

import requests
from camoufox.sync_api import Camoufox
from bs4 import BeautifulSoup
import time

def organize_files_by_type(user_dir):
    """
    Di chuyển file ảnh vào images/ và file video vào videos/ trong thư mục user.

    :param user_dir: đường dẫn thư mục user
    """
    images_dir = os.path.join(user_dir, "images")
    videos_dir = os.path.join(user_dir, "videos")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)

    # Các extension ảnh phổ biến
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    # Các extension video phổ biến
    video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"}

    # Duyệt tất cả file trong user_dir (không vào subfolder)
    for filename in os.listdir(user_dir):
        file_path = os.path.join(user_dir, filename)
        if os.path.isfile(file_path):
            _, ext = os.path.splitext(filename.lower())
            if ext in image_extensions:
                dest_path = os.path.join(images_dir, filename)
                shutil.move(file_path, dest_path)
            elif ext in video_extensions:
                dest_path = os.path.join(videos_dir, filename)
                shutil.move(file_path, dest_path)

def scrape_html(username, times=5):
    with Camoufox() as browser:
        page = browser.new_page()
        page.goto("https://gramsnap.com/en/")
        page.get_by_role("textbox", name="@username or link").fill(username)
        page.get_by_role("button", name="Search").click()
        time.sleep(1)
        page.wait_for_load_state("load")
        time.sleep(1)
        for _ in range(times):
            page.keyboard.press('End')
            page.wait_for_load_state("load")
            time.sleep(1)
            page.evaluate("window.scrollBy(0, -1000)")
            
            page.wait_for_load_state("load")
            time.sleep(1)
        time.sleep(5)

        return page.locator("ul.profile-media-list").inner_html()
    

# ==================== DATABASE FUNCTIONS ====================

class DownloadDatabase:
    """Quản lý SQLite database cho tracking downloads."""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Tạo database và bảng nếu chưa tồn tại."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tạo bảng downloads
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    timestamp TEXT,
                    file_path TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            # Tạo index UNIQUE trên file_path để dùng file_path làm khóa trùng lặp
            try:
                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_downloads_file_path ON downloads(file_path)')
                conn.commit()
            except sqlite3.Error:
                # Nếu không thể tạo index (ví dụ do dữ liệu trùng lặp cũ), bỏ qua nhưng log
                print("Cảnh báo: Không thể tạo unique index trên file_path - có thể có các giá trị trùng lặp cũ.")
            conn.close()
        except sqlite3.Error as e:
            print(f"Lỗi tạo database: {e}")
    
    def insert_or_ignore(self, username, url, timestamp, file_path):
        """INSERT OR IGNORE một bản ghi vào DB với status=pending.

        Sử dụng `file_path` (relative path) làm khóa để kiểm tra trùng lặp.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO downloads 
                (username, url, timestamp, file_path, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (username, url, timestamp, file_path))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Lỗi insert: {e}")
            return False
    
    def get_pending_downloads(self, limit=None):
        """Lấy tất cả downloads với status=pending."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if limit:
                cursor.execute('''
                    SELECT id, username, url, timestamp, file_path FROM downloads 
                    WHERE status = 'pending'
                    LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT id, username, url, timestamp, file_path FROM downloads 
                    WHERE status = 'pending'
                ''')
            
            results = cursor.fetchall()
            conn.close()
            return results
        except sqlite3.Error as e:
            print(f"Lỗi query: {e}")
            return []
    
    def update_download_status(self, download_id, status, file_path=None):
        """Update status và file_path của một download."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if file_path:
                cursor.execute('''
                    UPDATE downloads 
                    SET status = ?, file_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, file_path, download_id))
            else:
                cursor.execute('''
                    UPDATE downloads 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, download_id))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Lỗi update: {e}")
            return False
    
    def get_download_by_id(self, download_id):
        """Lấy thông tin một download theo ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM downloads WHERE id = ?', (download_id,))
            result = cursor.fetchone()
            conn.close()
            return result
        except sqlite3.Error as e:
            print(f"Lỗi query: {e}")
            return None
    
    def get_stats(self):
        """Lấy số liệu thống kê: total, pending, ready."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM downloads')
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM downloads WHERE status = 'pending'")
            pending = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM downloads WHERE status = 'ready'")
            ready = cursor.fetchone()[0]
            
            conn.close()
            return {'total': total, 'pending': pending, 'ready': ready}
        except sqlite3.Error as e:
            print(f"Lỗi query stats: {e}")
            return {'total': 0, 'pending': 0, 'ready': 0}

class TASK2ManualInstaGuiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TASK2 Manual Instagram Downloader")
        self.root.geometry("700x600")
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.db = None
        self.db_path = None

        # Biến trạng thái
        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Chọn folder và nhập usernames.")

        self._build_ui()
        self._load_config()

        # Lưu config khi đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # Khung chọn folder
        folder_frame = ttk.Frame(self.root, padding=10)
        folder_frame.pack(fill="x")

        ttk.Label(folder_frame, text="Folder lưu:").pack(anchor="w")

        entry_frame = ttk.Frame(folder_frame)
        entry_frame.pack(fill="x", pady=(2, 5))

        folder_entry = ttk.Entry(entry_frame, textvariable=self.folder_var)
        folder_entry.pack(side="left", fill="x", expand=True)

        browse_btn = ttk.Button(
            entry_frame,
            text="Browse...",
            command=self.browse_folder,
        )
        browse_btn.pack(side="left", padx=(5, 0))

        # Khung nhập username
        username_frame = ttk.Frame(self.root, padding=10)
        username_frame.pack(fill="both", expand=True)

        ttk.Label(username_frame, text="Usernames (mỗi dòng một username):").pack(anchor="w")

        self.username_text = tk.Text(username_frame, height=8)
        self.username_text.pack(fill="both", expand=True, pady=(2, 5))

        # Scrollbar cho username text widget
        username_scrollbar = ttk.Scrollbar(username_frame, orient="vertical", command=self.username_text.yview)
        username_scrollbar.pack(side="right", fill="y")
        self.username_text.config(yscrollcommand=username_scrollbar.set)

        # Khung nhập số lượt scroll
        times_frame = ttk.Frame(self.root, padding=10)
        times_frame.pack(fill="x")

        ttk.Label(times_frame, text="Số lượt scroll (mặc định: 5):").pack(anchor="w")

        self.times_var = tk.StringVar(value="5")
        times_entry = ttk.Entry(times_frame, textvariable=self.times_var, width=10)
        times_entry.pack(anchor="w", pady=(2, 5))

        # Thanh tiến trình + trạng thái
        progress_frame = ttk.Frame(self.root, padding=10)
        progress_frame.pack(fill="x")

        self.progress = ttk.Progressbar(
            progress_frame,
            mode="determinate",
        )
        self.progress.pack(fill="x")

        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.pack(anchor="w", pady=(5, 0))

        # Nút bắt đầu
        button_frame = ttk.Frame(self.root, padding=10)
        button_frame.pack(fill="x")

        self.start_button = ttk.Button(
            button_frame,
            text="Bắt đầu scrape & insert DB",
            command=self.on_start,
        )
        self.start_button.pack(side="right")

        # Nút tải file từ DB (worker)
        self.worker_button = ttk.Button(
            button_frame,
            text="Tải file từ DB",
            command=self.on_start_worker,
            state="disabled",
        )
        self.worker_button.pack(side="right", padx=(0, 8))

        # Nút lưu config
        save_btn = ttk.Button(
            button_frame,
            text="Lưu cấu hình",
            command=self._save_config,
        )
        save_btn.pack(side="right", padx=(0, 8))

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _parse_links_from_text(self, text):
        """
        Parse tất cả URLs + metadata từ text, chỉ từ bên trong <div class="media-content__info">.
        Lấy URL và timestamp từ title attribute để tạo tên file.

        :param text: nội dung text từ widget (HTML)
        :return: list các dict {'url': '...', 'filename': '...'}, xử lý trùng lặp tên file
        """
        if not text:
            return []

        soup = BeautifulSoup(text, 'html.parser')
        results = []

        # Tìm tất cả div có class "media-content__info"
        divs = soup.find_all('div', class_='media-content__info')

        for div in divs:
            # Lấy URL từ div
            url = self._extract_url_from_content(div)
            if not url:
                continue

            # Lấy timestamp từ <p class="media-content__meta-time" title="...">
            timestamp = self._extract_timestamp_from_content(div)
            
            # Chuyển timestamp thành tên file hợp lệ
            filename = self._timestamp_to_filename(timestamp)

            results.append({
                'url': url,
                'filename': filename,
                'timestamp': timestamp
            })

        # Xử lý trùng lặp tên file: đánh số thứ tự ở cuối
        filename_count = {}
        for item in results:
            filename = item['filename']
            if filename in filename_count:
                filename_count[filename] += 1
                base, ext = os.path.splitext(filename)
                item['filename'] = f"{base}_{filename_count[filename]}{ext}"
            else:
                filename_count[filename] = 1

        return results

    def _extract_url_from_content(self, div_element):
        """Trích xuất URL từ BeautifulSoup div element."""
        import html as _html

        # Tìm tất cả thẻ a, img, video, source...
        for tag in div_element.find_all(['a', 'img', 'video', 'source']):
            url = tag.get('href') or tag.get('src') or tag.get('data-src')
            if url:
                url = _html.unescape(str(url)).strip()
                if url.startswith('//'):
                    url = 'https:' + url
                url = url.strip('"\'')
                url = url.rstrip('.,;:!?)"\'')
                if url.lower().startswith('http://') or url.lower().startswith('https://'):
                    return url

        return None

    def _extract_timestamp_from_content(self, div_element):
        """Trích xuất timestamp từ title attribute của <p class="media-content__meta-time">."""
        p_tag = div_element.find('p', class_='media-content__meta-time')
        if p_tag:
            return p_tag.get('title')
        return None

    def _timestamp_to_filename(self, timestamp):
        """
        Chuyển timestamp thành tên file hợp lệ.
        Ví dụ: "7/6/2025, 8:46:19 AM" -> "2025-07-06_08-46-19"
        """
        if not timestamp:
            return "file.bin"

        try:
            # Thử parse timestamp (ví dụ: "7/6/2025, 8:46:19 AM")
            from datetime import datetime
            # Thử các format khác nhau
            for fmt in ["%m/%d/%Y, %I:%M:%S %p", "%d/%m/%Y, %H:%M:%S", "%Y-%m-%d, %H:%M:%S"]:
                try:
                    dt = datetime.strptime(timestamp.strip(), fmt)
                    return dt.strftime("%Y-%m-%d_%H-%M-%S.bin")
                except ValueError:
                    continue
            
            # Nếu không parse được, dùng timestamp trực tiếp, loại bỏ ký tự không hợp lệ
            filename = re.sub(r'[<>:"/\\|?*]', '_', timestamp)
            return filename + ".bin"
        except Exception:
            return "file.bin"

    def _get_filename_from_url(self, url, index):
        """
        Lấy filename từ URL hoặc dùng auto_number.

        :param url: URL cần download
        :param index: số thứ tự (để dùng auto_number nếu không tìm được filename)
        :return: filename
        """
        try:
            # Thử lấy từ query parameter 'filename'
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if "filename" in params and params["filename"]:
                filename = params["filename"][0]
                if filename:
                    return filename
        except Exception:  # noqa: BLE001
            pass

        # Thử extract từ path
        try:
            parsed = urlparse(url)
            path = parsed.path
            if path:
                filename = os.path.basename(path)
                if filename and "." in filename:
                    return filename
        except Exception:  # noqa: BLE001
            pass

        # Nếu không tìm được, dùng auto_number
        # Thử đoán extension từ Content-Type hoặc dùng .bin
        return f"file_{index}.bin"

    def _write_log(self, log_path, message):
        """
        Ghi log vào file.

        :param log_path: đường dẫn file log
        :param message: nội dung message cần ghi
        """
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"Lỗi ghi log: {e}")

    def _download_link(self, url, save_dir, filename_base=None, index=None, progress_callback=None):
        """
        Download một link cụ thể.

        :param url: URL cần download
        :param save_dir: thư mục lưu file
        :param filename_base: tên file cơ bản (không có extension)
        :param index: số thứ tự (dùng khi không có filename_base)
        :param progress_callback: hàm callback (index, total, url, status_msg)
        :return: saved absolute file path as string nếu thành công, None nếu thất bại
        """
        try:
            # Headers giả lập browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            if progress_callback:
                progress_callback(index, None, url, f"Đang tải {url}...")

            # Request GET
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            # Lấy filename
            if filename_base:
                filename = filename_base
            else:
                filename = self._get_filename_from_url(url, index)

            # Nếu không có extension, thử đoán từ Content-Type
            if "." not in filename or filename.endswith(".bin"):
                content_type = response.headers.get("Content-Type", "")
                base, ext = os.path.splitext(filename)
                if "image/jpeg" in content_type or "image/jpg" in content_type:
                    filename = f"{base}.jpg"
                elif "image/png" in content_type:
                    filename = f"{base}.png"
                elif "video/mp4" in content_type:
                    filename = f"{base}.mp4"
                elif "image/gif" in content_type:
                    filename = f"{base}.gif"

            # Đảm bảo filename không có ký tự không hợp lệ
            filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

            file_path = os.path.join(save_dir, filename)

            # Tránh overwrite nếu file đã tồn tại
            if os.path.exists(file_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(file_path):
                    new_filename = f"{base}_{counter}{ext}"
                    file_path = os.path.join(save_dir, new_filename)
                    counter += 1

            # Download và lưu file
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            if progress_callback:
                progress_callback(index, None, url, f"Đã tải: {os.path.basename(file_path)}")

            # Trả về đường dẫn file đã lưu (absolute path) để caller có thể cập nhật DB chính xác
            return file_path

        except Exception as e:  # noqa: BLE001
            if progress_callback:
                progress_callback(index, None, url, f"Lỗi: {e}")
            return None

    def on_start(self):
        folder = self.folder_var.get().strip()
        usernames_text = self.username_text.get("1.0", "end")
        times_str = self.times_var.get().strip()

        # Validation
        if not folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn folder lưu.")
            return
        if not os.path.isdir(folder):
            messagebox.showinfo("Info", "Folder lưu không tồn tại. Tự động tạo Folder")
            os.makedirs(folder, exist_ok=True)

        # Parse usernames từ text
        usernames = [u.strip() for u in usernames_text.split('\n') if u.strip()]
        if not usernames:
            messagebox.showerror("Lỗi", "Vui lòng nhập ít nhất một username.")
            return

        # Validate times
        try:
            times = int(times_str) if times_str else 5
            if times < 1:
                times = 5
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượt scroll phải là số nguyên dương.")
            return

        # Cài đặt progress bar
        self.progress["value"] = 0
        self.progress["maximum"] = len(usernames)
        self.status_var.set(f"Chuẩn bị scrape {len(usernames)} username(s)...")

        # Disable nút trong khi đang chạy
        self.start_button.config(state="disabled")

        # Lưu config
        self._save_config()

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_scrape_only_multi_thread,
            args=(folder, usernames, times),
            daemon=True,
        )
        thread.start()

    def on_start_worker(self):
        """Bắt đầu worker download từ các pending items trong DB."""
        if not self.db_path or not os.path.isfile(self.db_path):
            messagebox.showerror("Lỗi", "Không tìm thấy database. Vui lòng scrape trước.")
            return
        
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Lỗi", "Folder lưu không hợp lệ.")
            return
        
        # Cập nhật progress bar
        self.progress["value"] = 0
        self.status_var.set("Chuẩn bị tải file từ database...")
        
        # Disable nút trong khi đang chạy
        self.worker_button.config(state="disabled")
        self.start_button.config(state="disabled")
        
        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_download_worker_thread,
            args=(folder,),
            daemon=True,
        )
        thread.start()

    def _run_scrape_only_multi_thread(self, folder, usernames, times=5):
        """Chỉ scrape và insert vào DB, không download file."""
        # Khởi tạo database
        self.db_path = os.path.join(folder, "downloads.db")
        self.db = DownloadDatabase(self.db_path)
        
        def scrape_progress_callback(idx, total, msg):
            self.root.after(
                0,
                self._update_progress_ui,
                idx,
                total,
                "",
                msg,
            )

        # Tạo file log
        log_path = os.path.join(folder, "log.txt")
        self._write_log(log_path, "="*50)
        self._write_log(log_path, f"Bắt đầu scrape lúc: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._write_log(log_path, "="*50)

        try:
            total_usernames = len(usernames)
            for user_idx, username in enumerate(usernames, start=1):
                try:
                    # Xác định thư mục lưu cho username này
                    save_dir = os.path.join(folder, username)
                    os.makedirs(save_dir, exist_ok=True)

                    # Cập nhật status - scraping
                    scrape_progress_callback(
                        user_idx - 1, 
                        total_usernames, 
                        f"Scraping {username} ({user_idx}/{total_usernames})..."
                    )

                    # Scrape HTML từ web
                    html_content = scrape_html(username, times=times)

                    # Parse links từ HTML
                    links_data = self._parse_links_from_text(html_content)
                    if not links_data:
                        msg = f"⚠ {username}: Không tìm thấy link"
                        self._write_log(log_path, f"❌ {username}: Không tìm thấy link (0 file)")
                        scrape_progress_callback(user_idx, total_usernames, msg)
                        continue

                    # INSERT vào database (sử dụng file_path làm khóa trùng lặp)
                    insert_count = 0
                    skip_count = 0
                    for link_data in links_data:
                        url = link_data['url']
                        timestamp = link_data['timestamp']

                        # Sinh tên file từ timestamp và tạo file_path tương đối theo username
                        filename = self._timestamp_to_filename(timestamp)
                        file_path = os.path.join(username, filename)

                        if self.db.insert_or_ignore(username, url, timestamp, file_path):
                            insert_count += 1
                        else:
                            skip_count += 1

                    result_msg = f"✓ {username}: {insert_count} insert, {skip_count} skip (trùng lặp)"
                    scrape_progress_callback(user_idx, total_usernames, result_msg)
                    self._write_log(log_path, f"✓ {username}: {insert_count} insert, {skip_count} skip")

                except Exception as e:
                    error_msg = f"✗ {username}: Lỗi - {str(e)[:50]}"
                    scrape_progress_callback(user_idx, total_usernames, error_msg)
                    self._write_log(log_path, f"✗ {username}: Lỗi - {str(e)}")
                    continue

        finally:
            # Ghi thống kê vào log
            stats = self.db.get_stats()
            self._write_log(log_path, f"Thống kê DB: Total={stats['total']}, Pending={stats['pending']}, Ready={stats['ready']}")
            self._write_log(log_path, "="*50)
            self._write_log(log_path, f"Kết thúc lúc: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._write_log(log_path, "="*50)
            self.root.after(0, self._on_scrape_finished)

    def _run_download_worker_thread(self, folder):
        """Worker thread để download tất cả pending items từ database."""
        if not self.db:
            self.db = DownloadDatabase(self.db_path)
        
        log_path = os.path.join(folder, "log.txt")
        self._write_log(log_path, "="*50)
        self._write_log(log_path, f"Bắt đầu worker download lúc: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._write_log(log_path, "="*50)

        try:
            pending = self.db.get_pending_downloads()
            if not pending:
                self.root.after(0, lambda: messagebox.showinfo("Info", "Không có file pending để tải."))
                return
            
            total = len(pending)
            self.progress["maximum"] = total
            
            success_count = 0
            fail_count = 0
            
            for idx, row in enumerate(pending, start=1):
                try:
                    # Support sqlite3.Row or tuple
                    download_id = row['id'] if hasattr(row, 'keys') else row[0]
                    username = row['username'] if hasattr(row, 'keys') else row[1]
                    url = row['url'] if hasattr(row, 'keys') else row[2]
                    timestamp = row['timestamp'] if hasattr(row, 'keys') else row[3]
                    orig_file_path = row['file_path'] if hasattr(row, 'keys') else (row[4] if len(row) > 4 else None)
                    
                    # Tạo thư mục nếu cần
                    save_dir = os.path.join(folder, username)
                    os.makedirs(save_dir, exist_ok=True)
                    
                    # Use the filename previously generated during scrape as filename_base
                    if orig_file_path:
                        filename_base = os.path.basename(orig_file_path)
                    else:
                        filename_base = self._timestamp_to_filename(timestamp)
                    
                    # Update progress
                    self.root.after(
                        0,
                        self._update_progress_ui,
                        idx,
                        total,
                        url[:50] + "...",
                        f"Tải ({idx}/{total}): {username}"
                    )
                    
                    # Download file (returns absolute saved path or None)
                    saved_abspath = self._download_link(url, save_dir, filename_base=filename_base, index=idx)
                    if saved_abspath:
                        # Xác định thư mục đích theo loại file (images/videos)
                        _, ext = os.path.splitext(saved_abspath)
                        ext = ext.lower()
                        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
                        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"}

                        if ext in image_extensions:
                            dest_dir = os.path.join(folder, username, "images")
                        elif ext in video_extensions:
                            dest_dir = os.path.join(folder, username, "videos")
                        else:
                            dest_dir = os.path.join(folder, username)

                        os.makedirs(dest_dir, exist_ok=True)
                        dest_path = os.path.join(dest_dir, os.path.basename(saved_abspath))

                        # Move file to destination if needed
                        try:
                            if os.path.abspath(saved_abspath) != os.path.abspath(dest_path):
                                shutil.move(saved_abspath, dest_path)
                        except Exception as e:
                            # Nếu không thể move, log và tiếp tục với đường dẫn gốc
                            self._write_log(log_path, f"⚠ ID={download_id}, {username}: Không thể di chuyển file: {e}")
                            dest_path = saved_abspath

                        # Lưu relative path so với base folder trong DB
                        rel_path = os.path.relpath(dest_path, folder)
                        self.db.update_download_status(download_id, 'ready', rel_path)
                        success_count += 1
                        self._write_log(log_path, f"✓ ID={download_id}, {username}: {rel_path}")
                    else:
                        fail_count += 1
                        self._write_log(log_path, f"✗ ID={download_id}, {username}: Lỗi tải")
                    
                except Exception as e:
                    fail_count += 1
                    self._write_log(log_path, f"✗ Exception: {str(e)}")
                    continue
            
            # Tổ chức file
            for username in set(row[1] for row in pending):
                user_dir = os.path.join(folder, username)
                if os.path.exists(user_dir):
                    organize_files_by_type(user_dir)
            
            stats = self.db.get_stats()
            self._write_log(log_path, f"Kết quả: {success_count} thành công, {fail_count} thất bại")
            self._write_log(log_path, f"Thống kê DB: Total={stats['total']}, Pending={stats['pending']}, Ready={stats['ready']}")
            
        finally:
            self._write_log(log_path, "="*50)
            self._write_log(log_path, f"Kết thúc lúc: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._write_log(log_path, "="*50)
            self.root.after(0, self._on_worker_finished)

    def _update_progress_ui(self, idx, total, url, msg):
        self.progress["value"] = idx
        if url:
            # Hiển thị URL ngắn gọn
            url_display = url[:50] + "..." if len(url) > 50 else url
            self.status_var.set(f"{msg} ({idx}/{total}) - {url_display}")
        else:
            self.status_var.set(f"{msg} ({idx}/{total})")

    def _on_download_finished(self):
        self.start_button.config(state="normal")
        messagebox.showinfo("Hoàn thành", "Quá trình tải đã kết thúc.")

    def _on_scrape_finished(self):
        """Callback khi scrape xong."""
        self.start_button.config(state="normal")
        self.worker_button.config(state="normal")
        stats = self.db.get_stats() if self.db else {}
        msg = f"Scrape hoàn thành!\n\nDB Stats:\nTotal: {stats.get('total', 0)}\nPending: {stats.get('pending', 0)}\nReady: {stats.get('ready', 0)}\n\nBấm nút 'Tải file từ DB' để tải file."
        messagebox.showinfo("Hoàn thành", msg)

    def _on_worker_finished(self):
        """Callback khi worker download xong."""
        self.worker_button.config(state="normal")
        self.start_button.config(state="normal")
        stats = self.db.get_stats() if self.db else {}
        msg = f"Download hoàn thành!\n\nDB Stats:\nTotal: {stats.get('total', 0)}\nPending: {stats.get('pending', 0)}\nReady: {stats.get('ready', 0)}"
        messagebox.showinfo("Hoàn thành", msg)

    # -------------------------------------------------
    # Config helpers
    # -------------------------------------------------
    def _load_config(self):
        if not os.path.isfile(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            folder = data.get("folder")
            usernames_text = data.get("usernames", "")
            times = data.get("times", "5")

            if folder:
                self.folder_var.set(folder)
            if usernames_text:
                self.username_text.delete("1.0", "end")
                self.username_text.insert("1.0", usernames_text)
            if times:
                self.times_var.set(times)
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning(
                "Cảnh báo",
                f"Không thể đọc cấu hình: {e}",
            )

    def _save_config(self):
        try:
            usernames_text = self.username_text.get("1.0", "end")
            data = {
                "folder": self.folder_var.get().strip(),
                "usernames": usernames_text,
                "times": self.times_var.get().strip(),
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning(
                "Cảnh báo",
                f"Không thể lưu cấu hình: {e}",
            )

    def on_close(self):
        self._save_config()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = TASK2ManualInstaGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()


