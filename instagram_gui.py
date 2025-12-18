import json
import os
import shutil
import threading
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk

import instaloader


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


def download_for_usernames(
    usernames,
    target_dir,
    download_stories=False,
    progress_callback=None,
    login_info=None,
    months=None,
    max_posts_override=None,
):
    """
    Tải nội dung cho danh sách usernames bằng instaloader.

    Logic mặc định:
    - Chỉ tải post trong N tháng gần đây (mặc định 12 nếu không truyền vào).
    - Giới hạn tối đa M post/user (mặc định 100 nếu không truyền vào).

    :param usernames: list[str]
    :param target_dir: thư mục gốc để lưu
    :param download_stories: có tải stories hay không
    :param progress_callback: hàm callback (index, total, username, status_msg)
    :param login_info: thông tin đăng nhập {'username': ..., 'password': ...} hoặc None
    :param months: số tháng gần đây để tải, None = dùng mặc định 12
    :param max_posts_override: số post tối đa mỗi user, None = dùng mặc định 100
    """
    # Logic mặc định: chỉ tải post trong 12 tháng gần đây, tối đa 100 post/user
    months_value = months if months is not None else 12
    max_posts = max_posts_override if max_posts_override is not None else 100
    from_date = (datetime.now() - timedelta(days=months_value * 30)).date()

    # Tạo đối tượng Instaloader (dùng chung cho tất cả username)
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
    )

    # Đăng nhập tùy chọn (qua GUI)
    if login_info and login_info.get("username"):
        L.login(login_info["username"], login_info.get("password", ""))

    total = len(usernames)

    for idx, username in enumerate(usernames, start=1):
        username = username.strip()
        if not username:
            continue

        if progress_callback:
            progress_callback(idx, total, username, f"Bắt đầu tải {username}...")

        user_dir = os.path.join(target_dir, username)
        os.makedirs(user_dir, exist_ok=True)
        L.dirname_pattern = user_dir

        try:
            profile = instaloader.Profile.from_username(L.context, username)
            count = 0

            # tải avatar & stories nếu muốn (không bị lọc theo ngày/số lượng)
            # L.download_profilepic(profile)
            if download_stories:
                for story in L.get_stories(userids=[profile.userid]):
                    for item in story.get_items():
                        L.download_storyitem(item, target=user_dir)

            # duyệt post và lọc theo logic mặc định
            for post in profile.get_posts():
                post_date = post.date_utc.date()

                # Chỉ lấy post trong 12 tháng gần đây
                if post_date < from_date:
                    break

                # Giới hạn tối đa 100 post
                if count >= max_posts:
                    break

                L.download_post(post, target=user_dir)
                count += 1

            # Sau khi tải xong, tổ chức file vào images/ và videos/
            if progress_callback:
                progress_callback(
                    idx, total, username, f"Đang tổ chức file cho {username}..."
                )
            organize_files_by_type(user_dir)

            if progress_callback:
                progress_callback(
                    idx, total, username, f"Hoàn thành {username} ({count} bài)"
                )
        except Exception as e:  # noqa: BLE001
            if progress_callback:
                progress_callback(
                    idx,
                    total,
                    username,
                    f"Lỗi với {username}: {e}",
                )
            # vẫn tiếp tục với username tiếp theo


class InstagramDownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Instagram Downloader")
        self.root.geometry("600x450")
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")

        # Biến trạng thái
        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Chọn folder và nhập usernames.")
        self.login_var = tk.BooleanVar(value=False)
        self.months_var = tk.StringVar()      # số tháng gần đây (trống = 12)
        self.max_posts_var = tk.StringVar()   # số post tối đa (trống = 100)

        self._build_ui()

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

        # Khung nhập usernames
        users_frame = ttk.Frame(self.root, padding=10)
        users_frame.pack(fill="both", expand=True)

        ttk.Label(users_frame, text="Usernames (mỗi dòng một username):").pack(
            anchor="w"
        )

        self.usernames_text = tk.Text(users_frame, height=10)
        self.usernames_text.pack(fill="both", expand=True, pady=(2, 5))

        # Khung cấu hình thời gian & số post
        filter_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        filter_frame.pack(fill="x")

        ttk.Label(
            filter_frame,
            text="Thời gian (tháng, trống = 12):",
        ).grid(row=0, column=0, sticky="w")
        months_entry = ttk.Entry(filter_frame, textvariable=self.months_var, width=6)
        months_entry.grid(row=0, column=1, padx=(5, 20), sticky="w")

        ttk.Label(
            filter_frame,
            text="Số post tối đa mỗi user (trống = 100):",
        ).grid(row=0, column=2, sticky="w")
        max_posts_entry = ttk.Entry(
            filter_frame, textvariable=self.max_posts_var, width=8
        )
        max_posts_entry.grid(row=0, column=3, padx=(5, 0), sticky="w")

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

        login_check = ttk.Checkbutton(
            button_frame,
            text="Đăng nhập Instagram",
            variable=self.login_var,
        )
        login_check.pack(side="left")

        self.start_button = ttk.Button(
            button_frame,
            text="Bắt đầu download",
            command=self.on_start,
        )
        self.start_button.pack(side="right")

        # Nút lưu config nhanh (tuỳ chọn)
        save_btn = ttk.Button(
            button_frame,
            text="Lưu cấu hình",
            command=self._save_config,
        )
        save_btn.pack(side="right", padx=(0, 8))

        # Load config nếu có
        self._load_config()

        # Lưu config khi đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def on_start(self):
        folder = self.folder_var.get().strip()
        usernames_raw = self.usernames_text.get("1.0", "end")
        usernames = [u.strip() for u in usernames_raw.splitlines() if u.strip()]

        # Validation cơ bản
        if not folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn folder lưu.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Lỗi", "Folder lưu không tồn tại.")
            return
        if not usernames:
            messagebox.showerror("Lỗi", "Vui lòng nhập ít nhất một username.")
            return

        # Nếu yêu cầu đăng nhập, hỏi thông tin qua dialog
        login_info = None
        if self.login_var.get():
            ig_user = simpledialog.askstring(
                "Đăng nhập Instagram",
                "Username:",
                parent=self.root,
            )
            if ig_user:
                ig_pass = simpledialog.askstring(
                    "Đăng nhập Instagram",
                    "Mật khẩu:",
                    parent=self.root,
                    show="*",
                )
                login_info = {"username": ig_user, "password": ig_pass or ""}
            else:
                # Nếu không nhập username, coi như không login
                login_info = None

        # Parse số tháng và số post tối đa từ GUI (có thể để trống)
        months = None
        max_posts_override = None
        months_str = self.months_var.get().strip()
        max_posts_str = self.max_posts_var.get().strip()

        try:
            if months_str:
                months_val = int(months_str)
                if months_val <= 0:
                    raise ValueError
                months = months_val
            if max_posts_str:
                max_posts_val = int(max_posts_str)
                if max_posts_val <= 0:
                    raise ValueError
                max_posts_override = max_posts_val
        except ValueError:
            messagebox.showerror(
                "Lỗi",
                "Số tháng và số post tối đa (nếu nhập) phải là số nguyên dương.",
            )
            return

        # Cài đặt progress bar
        self.progress["value"] = 0
        self.progress["maximum"] = len(usernames)
        self.status_var.set("Bắt đầu tải...")

        # Disable nút trong khi đang chạy
        self.start_button.config(state="disabled")

        # Lưu config ngay khi bắt đầu (để lần sau mở lại)
        self._save_config()

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=self._run_download_thread,
            args=(usernames, folder, login_info, months, max_posts_override),
            daemon=True,
        )
        thread.start()

    def _run_download_thread(self, usernames, folder, login_info, months, max_posts_override):
        def progress_callback(idx, total, username, msg):
            # Đảm bảo update UI trên main thread
            self.root.after(
                0,
                self._update_progress_ui,
                idx,
                total,
                username,
                msg,
            )

        try:
            download_for_usernames(
                usernames=usernames,
                target_dir=folder,
                download_stories=False,
                progress_callback=progress_callback,
                login_info=login_info,
                months=months,
                max_posts_override=max_posts_override,
            )
        finally:
            self.root.after(0, self._on_download_finished)

    def _update_progress_ui(self, idx, total, username, msg):
        self.progress["value"] = idx
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
            usernames = data.get("usernames", [])
             # months & max_posts (có thể không có trong file cũ)
            months = data.get("months")
            max_posts = data.get("max_posts")
            if folder:
                self.folder_var.set(folder)
            if usernames and isinstance(usernames, list):
                self.usernames_text.delete("1.0", "end")
                self.usernames_text.insert("1.0", "\n".join(usernames))
            if months is not None:
                self.months_var.set(str(months))
            if max_posts is not None:
                self.max_posts_var.set(str(max_posts))
            # login checkbox state (optional)
            if data.get("login_enabled") is True:
                self.login_var.set(True)
            else:
                self.login_var.set(False)
        except Exception as e:  # noqa: BLE001
            messagebox.showwarning(
                "Cảnh báo",
                f"Không thể đọc cấu hình: {e}",
            )

    def _save_config(self):
        try:
            usernames_raw = self.usernames_text.get("1.0", "end")
            usernames = [u.strip() for u in usernames_raw.splitlines() if u.strip()]
            months = self.months_var.get().strip()
            max_posts = self.max_posts_var.get().strip()
            data = {
                "folder": self.folder_var.get().strip(),
                "usernames": usernames,
                "login_enabled": bool(self.login_var.get()),
                "months": int(months) if months else None,
                "max_posts": int(max_posts) if max_posts else None,
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
    app = InstagramDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()