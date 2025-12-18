## Instagram Content Downloader GUI

Ứng dụng Python dùng `instaloader` và giao diện Tkinter để tải ảnh/video Instagram về máy tính.

### Tính năng

- Chọn **folder lưu** bằng GUI.
- Nhập **danh sách username** (mỗi dòng một tài khoản).
- Tuỳ chọn **đăng nhập Instagram** (checkbox + dialog nhập user/pass).
- Tự động:
  - Chỉ tải **post trong 12 tháng gần đây**.
  - Giới hạn **tối đa 100 post mỗi user**.
  - Sắp xếp file theo user:
    - `/<folder gốc>/<username>/images/` chứa ảnh.
    - `/<folder gốc>/<username>/videos/` chứa video.
- Lưu **cấu hình gần nhất** vào `config.json` (folder + usernames + trạng thái đăng nhập) và tự load lại khi mở app.

### Yêu cầu

- Python 3.10+ (khuyến nghị).
- Đã tạo và kích hoạt `venv` (virtual environment).

### Cài đặt

Trong thư mục project:

```bash
python -m venv venv
venv\Scripts\Activate.ps1   # PowerShell trên Windows
pip install instaloader
```

### Chạy ứng dụng GUI

```bash
python instagram_gui.py
```

### Cách sử dụng

1. **Folder lưu**: bấm `Browse...` chọn thư mục muốn lưu dữ liệu tải về.
2. **Usernames**: nhập mỗi dòng một username Instagram (không cần dấu `@`).
3. (Tuỳ chọn) Tick **“Đăng nhập Instagram”**:
   - Một cửa sổ nhỏ xuất hiện để nhập `Username` và `Mật khẩu`.
   - Nếu không tick, app tải được nội dung **public**.
4. Bấm **“Bắt đầu download”**:
   - Thanh tiến trình + trạng thái hiển thị quá trình tải.
   - Sau khi xong sẽ có thông báo “Hoàn thành”.
5. Cấu hình (folder + usernames + trạng thái đăng nhập) được lưu vào `config.json` và tự áp dụng ở lần mở sau.

### Ghi chú

- Việc đăng nhập và tải nhiều nội dung có thể khiến Instagram áp dụng **rate limit** hoặc yêu cầu xác minh bảo mật.
- Nên giới hạn số lượng user và số lần chạy liên tục để tránh bị tạm khoá tính năng.


