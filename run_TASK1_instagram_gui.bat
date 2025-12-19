@echo off
REM Đi tới thư mục dự án
cd /d "C:\Users\ming805c\Projekt\Quang\a-div-003_ContentDownload"

REM Kích hoạt virtualenv (sửa 'venv' nếu venv của bạn tên khác)
call "venv\Scripts\activate.bat"

REM EM Chạy chương trình Instagram GUI
python TASK1_instagram_gui.py

REM Giữ cửa sổ mở sau khi chạy xong
echo.
pause