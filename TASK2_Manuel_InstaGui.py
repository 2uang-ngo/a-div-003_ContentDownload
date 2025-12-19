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


class TASK2ManualInstaGuiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TASK2 Manual Instagram Downloader")
        self.root.geometry("700x600")
        self.config_path = os.path.join(os.path.dirname(__file__), "TASK2_config.json")

        # Biến trạng thái
        self.folder_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Chọn folder và nhập links.")

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
        username_frame.pack(fill="x")

        ttk.Label(username_frame, text="Username (tùy chọn, để tổ chức thư mục):").pack(
            anchor="w"
        )

        username_entry = ttk.Entry(username_frame, textvariable=self.username_var)
        username_entry.pack(fill="x", pady=(2, 5))

        # Khung nhập links
        links_frame = ttk.Frame(self.root, padding=10)
        links_frame.pack(fill="both", expand=True)

        ttk.Label(links_frame, text="Paste các link download vào đây (mỗi dòng một link):").pack(
            anchor="w"
        )

        self.links_text = tk.Text(links_frame, height=15)
        self.links_text.pack(fill="both", expand=True, pady=(2, 5))

        # Scrollbar cho text widget
        scrollbar = ttk.Scrollbar(links_frame, orient="vertical", command=self.links_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.links_text.config(yscrollcommand=scrollbar.set)

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
            text="Bắt đầu download",
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
        Parse tất cả URLs từ text.

        :param text: nội dung text từ widget
        :return: list các URL hợp lệ
        """
        # Hỗ trợ cả HTML input: lấy từ href/src, absolute http(s) và protocol-relative (//...)
        import html as _html

        if not text:
            return []

        candidates = []

        # Lấy các giá trị trong href="..." hoặc src='...'
        attr_pattern = re.compile(r'(?:href|src)=[\"\'](.*?)[\"\']', re.IGNORECASE)
        candidates.extend(attr_pattern.findall(text))

        # Lấy các absolute http(s) URLs trong text
        abs_pattern = re.compile(r'https?://[^\s\"\'<>]+', re.IGNORECASE)
        candidates.extend(abs_pattern.findall(text))

        # Lấy protocol-relative URLs như //example.com/...
        proto_pattern = re.compile(r'//[^\s\"\'<>]+')
        candidates.extend(proto_pattern.findall(text))

        # Normalize, unescape HTML entities, strip trailing punctuation, dedupe preserving order
        seen = set()
        unique_urls = []
        for u in candidates:
            if not u:
                continue
            url = _html.unescape(u).strip()
            if url.startswith('//'):
                url = 'https:' + url
            # strip surrounding quotes or trailing punctuation
            url = url.strip('"\'')
            url = url.rstrip('.,;:!?)"\'')
            # only keep http(s) URLs
            if url.lower().startswith('http://') or url.lower().startswith('https://'):
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)

        return unique_urls

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

    def _download_link(self, url, save_dir, index, progress_callback=None):
        """
        Download một link cụ thể.

        :param url: URL cần download
        :param save_dir: thư mục lưu file
        :param index: số thứ tự (để đặt tên file)
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
            filename = self._get_filename_from_url(url, index)

            # Nếu không có extension, thử đoán từ Content-Type
            if "." not in filename or filename.endswith(".bin"):
                content_type = response.headers.get("Content-Type", "")
                if "image/jpeg" in content_type or "image/jpg" in content_type:
                    filename = filename.replace(".bin", ".jpg") if filename.endswith(".bin") else f"file_{index}.jpg"
                elif "image/png" in content_type:
                    filename = filename.replace(".bin", ".png") if filename.endswith(".bin") else f"file_{index}.png"
                elif "video/mp4" in content_type:
                    filename = filename.replace(".bin", ".mp4") if filename.endswith(".bin") else f"file_{index}.mp4"
                elif "image/gif" in content_type:
                    filename = filename.replace(".bin", ".gif") if filename.endswith(".bin") else f"file_{index}.gif"

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
        username = self.username_var.get().strip()
        links_text = self.links_text.get("1.0", "end")

        # Validation
        if not folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn folder lưu.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Lỗi", "Folder lưu không tồn tại.")
            return

        # Parse links
        links = self._parse_links_from_text(links_text)
        if not links:
            messagebox.showerror("Lỗi", "Không tìm thấy link hợp lệ trong ô text.")
            return

        # Xác định thư mục lưu
        if username:
            save_dir = os.path.join(folder, username)
        else:
            save_dir = folder
        os.makedirs(save_dir, exist_ok=True)

        # Cài đặt progress bar
        self.progress["value"] = 0
        self.progress["maximum"] = len(links)
        self.status_var.set(f"Tìm thấy {len(links)} link(s). Bắt đầu tải...")

        # Disable nút trong khi đang chạy
        self.start_button.config(state="disabled")

        # Lưu config
        self._save_config()

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_download_thread,
            args=(links, save_dir),
            daemon=True,
        )
        thread.start()

    def _run_download_thread(self, links, save_dir):
        def progress_callback(idx, total, url, msg):
            # Đảm bảo update UI trên main thread
            self.root.after(
                0,
                self._update_progress_ui,
                idx,
                len(links),
                url,
                msg,
            )

        success_count = 0
        fail_count = 0

        try:
            for idx, link in enumerate(links, start=1):
                if self._download_link(link, save_dir, idx, progress_callback):
                    success_count += 1
                else:
                    fail_count += 1

            # Sau khi download xong, tổ chức file vào images/ và videos/
            progress_callback(len(links), len(links), "", "Đang tổ chức file...")
            organize_files_by_type(save_dir)

            # Hiển thị kết quả
            result_msg = f"Hoàn thành! Thành công: {success_count}, Thất bại: {fail_count}"
            progress_callback(len(links), len(links), "", result_msg)

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
            username = data.get("username", "")
            links_text = data.get("links_text", "")

            if folder:
                self.folder_var.set(folder)
            if username:
                self.username_var.set(username)
            if links_text:
                self.links_text.delete("1.0", "end")
                self.links_text.insert("1.0", links_text)
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning(
                "Cảnh báo",
                f"Không thể đọc cấu hình: {e}",
            )

    def _save_config(self):
        try:
            links_text = self.links_text.get("1.0", "end")
            data = {
                "folder": self.folder_var.get().strip(),
                "username": self.username_var.get().strip(),
                "links_text": links_text,
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

