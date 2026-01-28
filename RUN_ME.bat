@echo off
chcp 65001 >nul 2>&1
REM File bat de chay TASK2 workflow

@REM REM Buoc 1: Mo file TASK2_README.md
@REM echo Dang mo file TASK2_README.pdf...
@REM start "" "TASK2_README.pdf"

@REM REM Doi mot chut de file mo
@REM timeout /t 2 /nobreak >nul

@REM REM Buoc 2: Hien cua so hoi "Doc xong chua?"
@REM powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Vui long doc file TASK2_README.pdf. Sau khi doc xong, nhan OK de tiep tuc.', 'Thong bao', 'OK', 'Information')"

@REM REM Kiem tra neu nguoi dung nhan Cancel hoac dong cua so thi thoat
@REM if errorlevel 1 (
@REM     echo Nguoi dung da huy.
@REM     exit /b
@REM )


REM Buoc 5: Chay script Auto_Insta_Downloader.py
echo Dang chay script Auto_Insta_Downloader.py...
call "venv\Scripts\activate.bat"
python Auto_Insta_Downloader.py

REM Kiem tra loi khi chay Python
if errorlevel 1 (
    echo Co loi xay ra khi chay Auto_Insta_Downloader.py
    pause
    exit /b 1
)

echo Hoan thanh!
pause

