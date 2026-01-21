import json
import os
import re
import shutil
import threading
from urllib.parse import urlparse, parse_qs
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
                if not os.path.exists(dest_path):  # Tránh overwrite nếu đã tồn tại
                    shutil.move(file_path, dest_path)
            elif ext in video_extensions:
                dest_path = os.path.join(videos_dir, filename)
                if not os.path.exists(dest_path):
                    shutil.move(file_path, dest_path)

def scrape_html(username, times=5):
    with Camoufox() as browser:
        page = browser.new_page()
        page.goto("https://gramsnap.com/en/")
        page.get_by_role("textbox", name="@username or link").fill(username)
        page.get_by_role("button", name="Search").click()
        for _ in range(times):
            page.keyboard.press('End')
            page.evaluate("window.scrollBy(0, -1000)")
            time.sleep(2)

        return page.locator("ul.profile-media-list").inner_html()
class TASK2ManualInstaGuiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TASK2 Manual Instagram Downloader")
        self.root.geometry("700x600")
        self.config_path = os.path.join(os.path.dirname(__file__), "TASK2_config.json")

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
            text="Bắt đầu scrape & download",
            command=self.on_start,
        )
        self.start_button.pack(side="right")

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

    def _download_link(self, url, save_dir, filename_base=None, index=None, progress_callback=None):
        """
        Download một link cụ thể.

        :param url: URL cần download
        :param save_dir: thư mục lưu file
        :param filename_base: tên file cơ bản (không có extension)
        :param index: số thứ tự (dùng khi không có filename_base)
        :param progress_callback: hàm callback (index, total, url, status_msg)
        :return: True nếu thành công, False nếu thất bại
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

            return True

        except Exception as e:  # noqa: BLE001
            if progress_callback:
                progress_callback(index, None, url, f"Lỗi: {e}")
            return False

    def on_start(self):
        folder = self.folder_var.get().strip()
        usernames_text = self.username_text.get("1.0", "end")
        times_str = self.times_var.get().strip()

        # Validation
        if not folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn folder lưu.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Lỗi", "Folder lưu không tồn tại.")
            return

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
            target=self._run_scrape_and_download_multi_thread,
            args=(folder, usernames, times),
            daemon=True,
        )
        thread.start()

    def _run_scrape_and_download_multi_thread(self, folder, usernames, times=5):
        def progress_callback(idx, total, url, msg):
            # Đảm bảo update UI trên main thread
            self.root.after(
                0,
                self._update_progress_ui,
                idx,
                total,
                url,
                msg,
            )

        try:
            total_usernames = len(usernames)
            for user_idx, username in enumerate(usernames, start=1):
                try:
                    # Xác định thư mục lưu cho username này
                    save_dir = os.path.join(folder, username)
                    os.makedirs(save_dir, exist_ok=True)

                    # Cập nhật status
                    progress_callback(user_idx - 1, total_usernames, "", f"Scraping {username} ({user_idx}/{total_usernames})...")

                    # Scrape HTML từ web
                    html_content = scrape_html(username, times=times)

                    # Parse links từ HTML (trả về list các dict với url và filename)
                    links_data = self._parse_links_from_text(html_content)
                    if not links_data:
                        progress_callback(user_idx, total_usernames, "", f"⚠ {username}: Không tìm thấy link")
                        continue

                    progress_callback(user_idx - 1, total_usernames, "", f"Tìm thấy {len(links_data)} link cho {username}. Bắt đầu tải...")

                    success_count = 0
                    fail_count = 0

                    # Download từng file
                    for idx, link_data in enumerate(links_data, start=1):
                        url = link_data['url']
                        filename = link_data['filename']
                        if self._download_link(url, save_dir, filename_base=filename, index=idx, progress_callback=lambda i, t, u, m: progress_callback(i or idx, None, u, m)):
                            success_count += 1
                        else:
                            fail_count += 1

                    # Tổ chức file
                    organize_files_by_type(save_dir)

                    # Status cho username này
                    result_msg = f"✓ {username}: {success_count} thành công, {fail_count} thất bại"
                    progress_callback(user_idx, total_usernames, "", result_msg)

                except Exception as e:
                    progress_callback(user_idx, total_usernames, "", f"✗ {username}: Lỗi - {str(e)[:50]}")
                    organize_files_by_type(save_dir)
                    continue

        finally:
            self.root.after(0, self._on_download_finished)
        
        

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

