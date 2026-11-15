@echo off
chcp 65001 > nul
title Tokudo AI OS — Automated Environment Setup
color 0A

echo ======================================================================
echo           🛠️ CÀI ĐẶT MÔI TRƯỜNG TỰ ĐỘNG CHO TOKUDO AI OS
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Kiểm tra Python
where python > nul 2>&1
if errorlevel 1 (
    echo ❌ Không tìm thấy Python trên máy tính của bạn!
    echo Vui lòng cài đặt Python 3.11 hoặc 3.12 từ https://www.python.org/
    echo Lưu ý: Hãy tích chọn "Add Python to PATH" khi cài đặt.
    pause
    exit /b 1
)

echo [1/4] Kiểm tra Python:
python --version

:: 2. Khởi tạo môi trường ảo .venv
echo.
echo [2/4] Đang khởi tạo môi trường ảo Python (.venv)...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ Không thể tạo môi trường ảo .venv!
        pause
        exit /b 1
    )
    echo ✅ Đã tạo môi trường ảo .venv thành công.
) else (
    echo ℹ️ Môi trường ảo .venv đã tồn tại sẵn.
)

:: 3. Cài đặt các thư viện cần thiết
echo.
echo [3/4] Đang cài đặt toàn bộ thư viện từ requirements.txt...
".venv\Scripts\python.exe" -m pip install --upgrade pip > nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Quá trình cài đặt thư viện gặp lỗi. Vui lòng kiểm tra kết nối mạng!
    pause
    exit /b 1
)
echo ✅ Đã cài đặt đầy đủ các thư viện cần thiết.

:: 4. Khởi tạo cấu hình ban đầu
echo.
echo [4/4] Kiểm tra cấu hình cấu trúc hệ thống...
if not exist ".env" (
    copy ".env.example" ".env" > nul
    echo ℹ️ Đã tạo file .env mẫu từ .env.example.
)

if not exist "data\screenshots" mkdir data\screenshots
if not exist "data\tts" mkdir data\tts
if not exist "data\uploads" mkdir data\uploads
if not exist "brain\memory" mkdir brain\memory
if not exist "brain\wiki" mkdir brain\wiki

echo.
echo ======================================================================
echo 🎉 HOÀN TẤT THIẾT LẬP TOKUDO AI OS THÀNH CÔNG!
echo ======================================================================
echo 👉 Bạn có thể chạy ngay bằng cách nhấp đúp chuột vào file: start.bat
echo 👉 Giao diện Web Dashboard sẽ tự động mở tại: http://localhost:8080
echo ======================================================================
echo.
pause
